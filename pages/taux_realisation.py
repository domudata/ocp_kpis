# -*- coding: utf-8 -*-
"""
Page : Tableau de Bord Realisation
Filtres independants : Annee, Mois, Atelier
3 blocs de graphiques horizontaux
"""

import io
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

MOIS_FR = {
    1: "janv", 2: "fevr", 3: "mars", 4: "avr",
    5: "mai",  6: "juin", 7: "juil", 8: "aout",
    9: "sept", 10: "oct", 11: "nov", 12: "dec",
}

C_ORANGE = "#F5A623"
C_BLEU   = "#00AEEF"

# Fond des graphiques : blanc avec bandeau titre colore
BG_CHART  = "#FFFFFF"
BG_PAPER  = "#F4F6FA"
C_TITRE_TVX   = "#1E3A5F"   # bleu marine - bloc TVX
C_TITRE_INS   = "#1E3A5F"   # meme couleur
C_TITRE_PREP  = "#1E3A5F"   # meme couleur

ATELIERS = [
    "All",
    "Sulfurique (PS)",
    "Phosphorique (PP)",
    "Centrale (CU)",
    "Engrais (TSP/REX)",
    "Feed (MCP/DCP)",
]


def _filtre_atelier(df, atelier):
    if atelier == "All" or not atelier:
        return df
    col = "Poste travail princ."
    if col not in df.columns:
        return df
    p = df[col].astype(str).str.upper()
    if atelier == "Sulfurique (PS)":
        mask = p.str.contains("PS", na=False)
    elif atelier == "Phosphorique (PP)":
        mask = p.str.contains("PP", na=False)
    elif atelier == "Centrale (CU)":
        mask = p.str.contains("CU", na=False)
    elif atelier == "Engrais (TSP/REX)":
        mask = p.str.contains("TSP|REX", na=False)
    elif atelier == "Feed (MCP/DCP)":
        mask = p.str.contains("MCP|DCP", na=False)
    else:
        mask = pd.Series(True, index=df.index)
    return df[mask].copy()


def _est_clot(s):
    return s.fillna("").str.contains(r"CLOT|TCLO", regex=True, na=False)


def _est_cree(s):
    first = s.fillna("").str.strip().str.split().str[0]
    return first.isin(["CREE", "CREE"])


def _est_lanc(s):
    return s.fillna("").str.strip().str.split().str[0] == "LANC"


def _taux(num, den):
    if den == 0:
        return 100.0
    return min(round((num / den) * 100, 1), 100.0)


def _calc_kpis_mois(df, mois_list, annee):
    rows = []
    col_type = col_sys = col_user = col_date = None
    for c in df.columns:
        cl = c.lower()
        if "type" in cl and "ordre" in cl:   col_type = c
        if "statut" in cl and "syst" in cl:  col_sys  = c
        if "statut" in cl and "util" in cl:  col_user = c
        if "date"   in cl and "but"  in cl and "plan" in cl: col_date = c

    if not all([col_type, col_sys, col_user, col_date]):
        return pd.DataFrame()

    for m in sorted(mois_list):
        label = MOIS_FR.get(m, str(m))
        mask_periode = (df[col_date].dt.year == annee) & (df[col_date].dt.month == m)
        dm = df[mask_periode].copy()

        if dm.empty:
            rows.append({"mois": m, "label": label,
                "taux_travaux_planifies": 0.0, "taux_pm_syst": 0.0,
                "taux_zcor_inspection": 0.0,  "taux_calendrier_prv": 0.0,
                "taux_planification": 0.0,    "taux_preparation": 0.0})
            continue

        clot       = _est_clot(dm[col_sys])
        cree       = _est_cree(dm[col_sys])
        lanc       = _est_lanc(dm[col_sys])
        sopl       = dm[col_user].fillna("").str.contains("SOPL", na=False)
        type_ordre = dm[col_type].fillna("")

        # 1. Travaux Planifies (SOPL)
        taux_tp  = _taux(int((sopl & clot).sum()), int(sopl.sum()))
        # 2. PM Systematique (ZEST)
        mz = type_ordre == "ZEST"
        taux_pm  = _taux(int((mz & clot).sum()), int(mz.sum()))
        # 3. OT ZCOR
        mc = type_ordre == "ZCOR"
        taux_zcor = _taux(int((mc & clot).sum()), int(mc.sum()))
        # 4. Calendrier ZPRV
        mp = type_ordre == "ZPRV"
        taux_prv = _taux(int((mp & clot).sum()), int(mp.sum()))
        # 5. Planification
        sopl_clot     = int((sopl & clot).sum())
        sopl_lanc_ncl = int((sopl & lanc & ~clot).sum())
        taux_plan = _taux(sopl_clot - sopl_lanc_ncl, sopl_clot)
        # 6. Preparation
        sopl_cree = int((sopl & cree).sum())
        taux_prep = _taux(sopl_clot - sopl_cree, sopl_clot)

        rows.append({"mois": m, "label": label,
            "taux_travaux_planifies": taux_tp, "taux_pm_syst": taux_pm,
            "taux_zcor_inspection": taux_zcor,  "taux_calendrier_prv": taux_prv,
            "taux_planification": taux_plan,    "taux_preparation": taux_prep})

    return pd.DataFrame(rows)


def _make_chart(kpi_df, col1, col2, label1, label2, titre, couleur_titre=C_TITRE_TVX):
    """
    Graphique a barres horizontales avec :
    - fond blanc
    - bandeau de titre colore (annote en haut)
    - valeurs % affiches EN DEHORS des barres (a droite), en couleur foncee
    - labels de mois sur l axe Y clairement visibes
    """
    df_plot = kpi_df.sort_values("mois", ascending=True).reset_index(drop=True)
    labels_y = df_plot["label"].tolist()
    n_mois   = len(labels_y)
    hauteur  = max(300, n_mois * 80)

    fig = go.Figure()

    # Barre 1 - orange (premier KPI)
    fig.add_trace(go.Bar(
        y=labels_y,
        x=df_plot[col1],
        name=label1,
        orientation="h",
        marker_color=C_ORANGE,
        marker_line=dict(width=0),
        text=[f"<b>{v:.0f}%</b>" for v in df_plot[col1]],
        textposition="outside",
        textfont=dict(color=C_ORANGE, size=12, family="Arial"),
        hovertemplate=f"<b>%{{y}}</b><br>{label1}: %{{x:.1f}}%<extra></extra>",
        width=0.35,
        offset=-0.37,
    ))

    # Barre 2 - bleu clair (deuxieme KPI)
    fig.add_trace(go.Bar(
        y=labels_y,
        x=df_plot[col2],
        name=label2,
        orientation="h",
        marker_color=C_BLEU,
        marker_line=dict(width=0),
        text=[f"<b>{v:.0f}%</b>" for v in df_plot[col2]],
        textposition="outside",
        textfont=dict(color=C_BLEU, size=12, family="Arial"),
        hovertemplate=f"<b>%{{y}}</b><br>{label2}: %{{x:.1f}}%<extra></extra>",
        width=0.35,
        offset=0.02,
    ))

    fig.update_layout(
        # Titre rendu comme annotation (bandeau colore en haut)
        annotations=[dict(
            text=f"<b>{titre}</b>",
            x=0, y=1.06, xref="paper", yref="paper",
            xanchor="left", yanchor="bottom",
            showarrow=False,
            font=dict(size=13, color="white", family="Arial Black"),
            bgcolor=couleur_titre,
            borderpad=6,
        )],
        paper_bgcolor=BG_PAPER,
        plot_bgcolor=BG_CHART,
        barmode="overlay",
        height=hauteur,
        margin=dict(l=10, r=60, t=55, b=10),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.04,
            xanchor="left",
            x=0,
            font=dict(size=9, color="#333"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            range=[0, 130],
            showgrid=True,
            gridcolor="#e8e8e8",
            gridwidth=1,
            ticksuffix="%",
            tickfont=dict(size=9, color="#aaa"),
            showticklabels=False,
            zeroline=False,
        ),
        yaxis=dict(
            tickfont=dict(size=12, color="#1E3A5F", family="Arial Bold"),
            automargin=True,
            tickmode="array",
            tickvals=labels_y,
            ticktext=[f"<b>{l}</b>" for l in labels_y],
        ),
    )
    return fig


# ── Export PowerPoint ────────────────────────────────────────────────────────
def _build_pptx(figs, titres, annee, atelier, mois_labels):
    """
    Genere un fichier PowerPoint avec une slide par graphique
    + une slide de titre.
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]  # layout vide

    # ── Slide de titre ────────────────────────────────────────────────────────
    slide0 = prs.slides.add_slide(blank_layout)
    # Fond bleu marine
    bg = slide0.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(0x1E, 0x3A, 0x5F)

    tf = slide0.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(1.5))
    p = tf.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = "Tableau de Bord - Taux de Realisation"
    run.font.size = Pt(36)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    tf2 = slide0.shapes.add_textbox(Inches(1), Inches(4.2), Inches(11), Inches(0.6))
    p2 = tf2.text_frame.paragraphs[0]
    p2.alignment = PP_ALIGN.CENTER
    run2 = p2.add_run()
    mois_str = ", ".join(mois_labels) if mois_labels else "Tous les mois"
    run2.text = f"Annee {annee}  |  Atelier : {atelier}  |  Mois : {mois_str}"
    run2.font.size = Pt(16)
    run2.font.color.rgb = RGBColor(0xF5, 0xA6, 0x23)

    # ── Slide par graphique ───────────────────────────────────────────────────
    for fig, titre in zip(figs, titres):
        slide = prs.slides.add_slide(blank_layout)
        bg2 = slide.background
        fill2 = bg2.fill
        fill2.solid()
        fill2.fore_color.rgb = RGBColor(0xF4, 0xF6, 0xFA)

        # Exporter la figure en image PNG en memoire
        img_bytes = pio.to_image(fig, format="png", width=1200, height=fig.layout.height or 600, scale=2)
        img_stream = io.BytesIO(img_bytes)

        # Calculer la position pour centrer l image
        img_w = Inches(12)
        img_h = Inches(6.2)
        left  = (prs.slide_width  - img_w) // 2
        top   = Inches(0.8)
        slide.shapes.add_picture(img_stream, left, top, img_w, img_h)

        # Titre de la slide
        tb = slide.shapes.add_textbox(Inches(0.3), Inches(0.1), Inches(12), Inches(0.6))
        p3 = tb.text_frame.paragraphs[0]
        p3.alignment = PP_ALIGN.LEFT
        r3 = p3.add_run()
        r3.text = titre
        r3.font.size = Pt(18)
        r3.font.bold = True
        r3.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


# ── Rendu principal ──────────────────────────────────────────────────────────
def render_taux_realisation_tab(df_full):
    """Point d entree appele depuis app.py."""

    st.markdown(
        "<h3 style='color:#1E3A5F;margin-bottom:4px'>Tableau de Bord - Taux de Realisation</h3>",
        unsafe_allow_html=True,
    )

    # Detecter colonne date
    col_date = None
    for c in df_full.columns:
        cl = c.lower()
        if "date" in cl and "but" in cl and "plan" in cl:
            col_date = c
            break
    if col_date is None:
        st.error("Colonne date de debut planifiee introuvable.")
        return
    if df_full[col_date].dropna().empty:
        st.info("Aucune date disponible dans les donnees.")
        return

    annees_dispo = sorted(
        df_full[col_date].dropna().dt.year.unique().astype(int).tolist(), reverse=True
    )

    # ── Filtres ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([1, 2, 2])
    with fc1:
        annee_sel = st.selectbox("Annee", options=annees_dispo, index=0, key="tr_annee")
    with fc2:
        mask_an   = df_full[col_date].dt.year == annee_sel
        mois_dispo = sorted(
            df_full[mask_an][col_date].dropna().dt.month.unique().astype(int).tolist()
        )
        mois_sel = st.multiselect(
            "Mois",
            options=mois_dispo,
            default=mois_dispo,
            format_func=lambda m: MOIS_FR.get(m, str(m)),
            key="tr_mois",
        )
    with fc3:
        atelier_sel = st.selectbox("Atelier", options=ATELIERS, index=0, key="tr_atelier")

    if not mois_sel:
        st.warning("Veuillez selectionner au moins un mois.")
        return

    df_work = _filtre_atelier(df_full.copy(), atelier_sel)
    if df_work.empty:
        st.info("Aucune donnee pour l atelier selectionne.")
        return

    with st.spinner("Calcul des indicateurs..."):
        kpi_df = _calc_kpis_mois(df_work, mois_sel, annee_sel)

    if kpi_df.empty:
        st.info("Aucune donnee disponible pour la periode selectionnee.")
        return

    # ── Metriques resumees ────────────────────────────────────────────────────
    st.markdown("---")
    mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
    metriques = [
        (mc1, "Travaux Planifies", kpi_df["taux_travaux_planifies"].mean(), C_ORANGE),
        (mc2, "PM Systematique",   kpi_df["taux_pm_syst"].mean(),           C_BLEU),
        (mc3, "ZCOR Inspection",   kpi_df["taux_zcor_inspection"].mean(),   C_ORANGE),
        (mc4, "Calendrier ZPRV",   kpi_df["taux_calendrier_prv"].mean(),    C_BLEU),
        (mc5, "Planification",     kpi_df["taux_planification"].mean(),     C_ORANGE),
        (mc6, "Preparation",       kpi_df["taux_preparation"].mean(),       C_BLEU),
    ]
    for col_m, lbl, val, color in metriques:
        with col_m:
            st.markdown(
                f'<div style="background:{color};padding:10px 6px;border-radius:8px;text-align:center">'
                f'<div style="color:white;font-size:10px;font-weight:700;line-height:1.2">{lbl}</div>'
                f'<div style="color:white;font-size:22px;font-weight:900;line-height:1.3">{val:.0f}%</div>'
                f'<div style="color:rgba(255,255,255,.7);font-size:10px">moy. periode</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Construire les figures ─────────────────────────────────────────────────
    TITRES = [
        "TAUX DE REALISATION TVX",
        "INSPECTION",
        "PREPARATION VS PLANIFICATION",
    ]
    fig_tvx = _make_chart(
        kpi_df,
        "taux_travaux_planifies", "taux_pm_syst",
        "TAUX DE REALISATION DES TRAVAUX PLANIFIES",
        "TAUX DE REALISATION PM SYSTEMATIQUE",
        TITRES[0],
    )
    fig_ins = _make_chart(
        kpi_df,
        "taux_zcor_inspection", "taux_calendrier_prv",
        "TAUX DE REALISATION DES OT CURATIF ISSU INSPECTION",
        "TAUX DE REALISATION CALENDRIER D INSPECTION GLOBAL",
        TITRES[1],
    )
    fig_prep = _make_chart(
        kpi_df,
        "taux_planification", "taux_preparation",
        "TAUX PLANIFICATION",
        "TAUX PREPARATION",
        TITRES[2],
    )

    # ── Affichage des graphiques ───────────────────────────────────────────────
    g1, g2, g3 = st.columns(3)
    with g1:
        st.plotly_chart(fig_tvx,  use_container_width=True, config={"displayModeBar": False})
    with g2:
        st.plotly_chart(fig_ins,  use_container_width=True, config={"displayModeBar": False})
    with g3:
        st.plotly_chart(fig_prep, use_container_width=True, config={"displayModeBar": False})

    # ── Bouton export PowerPoint ───────────────────────────────────────────────
    st.markdown("---")
    export_col, _ = st.columns([1, 3])
    with export_col:
        with st.spinner("Preparation du PowerPoint..."):
            try:
                mois_labels = [MOIS_FR.get(m, str(m)) for m in sorted(mois_sel)]
                pptx_bytes = _build_pptx(
                    figs=[fig_tvx, fig_ins, fig_prep],
                    titres=TITRES,
                    annee=annee_sel,
                    atelier=atelier_sel,
                    mois_labels=mois_labels,
                )
                st.download_button(
                    label="Telecharger PowerPoint (.pptx)",
                    data=pptx_bytes,
                    file_name=f"Taux_Realisation_{annee_sel}_{atelier_sel.replace(' ', '_').replace('/', '-')}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Export PowerPoint impossible : {e}")

    # ── Tableau detail ─────────────────────────────────────────────────────────
    with st.expander("Voir le detail par mois", expanded=False):
        detail = kpi_df[["label", "taux_travaux_planifies", "taux_pm_syst",
                          "taux_zcor_inspection", "taux_calendrier_prv",
                          "taux_planification", "taux_preparation"]].copy()
        detail.columns = [
            "Mois", "Travaux Planifies (%)", "PM Systematique (%)",
            "ZCOR Inspection (%)", "Calendrier ZPRV (%)",
            "Planification (%)", "Preparation (%)",
        ]
        st.dataframe(
            detail.style.format({c: "{:.1f}" for c in detail.columns if "%" in c}),
            use_container_width=True, hide_index=True,
        )
        st.download_button(
            "Telecharger CSV",
            data=detail.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"taux_realisation_{annee_sel}.csv",
            mime="text/csv",
        )
