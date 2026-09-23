# -*- coding: utf-8 -*-
"""
Page : Tableau de Bord Realisation
Filtres independants : Annee, Mois, Atelier
3 blocs de graphiques horizontaux :
  - TAUX DE REALISATION TVX
  - INSPECTION
  - PREPARATION VS PLANIFICATION
"""

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

MOIS_FR = {
    1: "janv", 2: "fevr", 3: "mars", 4: "avr",
    5: "mai",  6: "juin", 7: "juil", 8: "aout",
    9: "sept", 10: "oct", 11: "nov", 12: "dec",
}

C_ORANGE = "#F5A623"
C_BLEU   = "#00AEEF"
C_TITRE  = "#1E3A5F"

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
    return s.fillna("").str.strip().str.split().str[0].isin(["CREE", "CREE"])


def _est_lanc(s):
    return s.fillna("").str.strip().str.split().str[0] == "LANC"


def _taux(num, den):
    if den == 0:
        return 100.0
    return min(round((num / den) * 100, 1), 100.0)


def _calc_kpis_mois(df, mois_list, annee):
    rows = []
    col_type  = "Type d'ordre"
    col_sys   = "Statut systeme"
    col_user  = "Statut utilisateur"
    col_date  = "Date de debut planifiee"

    # Detecter les vrais noms de colonnes (gestion encodage)
    for c in df.columns:
        if "type" in c.lower() and "ordre" in c.lower():
            col_type = c
        if "statut" in c.lower() and "syst" in c.lower():
            col_sys = c
        if "statut" in c.lower() and "util" in c.lower():
            col_user = c
        if "date" in c.lower() and "but" in c.lower() and "plan" in c.lower():
            col_date = c

    for m in sorted(mois_list):
        label = MOIS_FR.get(m, str(m))
        mask_periode = (
            (df[col_date].dt.year  == annee) &
            (df[col_date].dt.month == m)
        )
        dm = df[mask_periode].copy()

        if dm.empty:
            rows.append({
                "mois": m, "label": label,
                "taux_travaux_planifies": 0.0, "taux_pm_syst": 0.0,
                "taux_zcor_inspection": 0.0, "taux_calendrier_prv": 0.0,
                "taux_planification": 0.0, "taux_preparation": 0.0,
            })
            continue

        clot       = _est_clot(dm[col_sys])
        cree       = _est_cree(dm[col_sys])
        lanc       = _est_lanc(dm[col_sys])
        sopl       = dm[col_user].fillna("").str.contains("SOPL", na=False)
        type_ordre = dm[col_type].fillna("")

        # 1. Travaux Planifies (SOPL)
        n_tp  = int((sopl & clot).sum())
        d_tp  = int(sopl.sum())
        taux_tp = _taux(n_tp, d_tp)

        # 2. PM Systematique (ZEST)
        mask_zest = type_ordre == "ZEST"
        n_pm  = int((mask_zest & clot).sum())
        d_pm  = int(mask_zest.sum())
        taux_pm = _taux(n_pm, d_pm)

        # 3. OT ZCOR Inspection
        mask_zcor = type_ordre == "ZCOR"
        n_zcor = int((mask_zcor & clot).sum())
        d_zcor = int(mask_zcor.sum())
        taux_zcor = _taux(n_zcor, d_zcor)

        # 4. Calendrier PRV (ZPRV)
        mask_prv = type_ordre == "ZPRV"
        n_prv  = int((mask_prv & clot).sum())
        d_prv  = int(mask_prv.sum())
        taux_prv = _taux(n_prv, d_prv)

        # 5. Taux Planification
        sopl_clot     = int((sopl & clot).sum())
        sopl_lanc_ncl = int((sopl & lanc & ~clot).sum())
        taux_plan = _taux(sopl_clot - sopl_lanc_ncl, sopl_clot)

        # 6. Taux Preparation
        sopl_cree = int((sopl & cree).sum())
        taux_prep = _taux(sopl_clot - sopl_cree, sopl_clot)

        rows.append({
            "mois": m, "label": label,
            "taux_travaux_planifies": taux_tp, "taux_pm_syst": taux_pm,
            "taux_zcor_inspection": taux_zcor, "taux_calendrier_prv": taux_prv,
            "taux_planification": taux_plan, "taux_preparation": taux_prep,
        })

    return pd.DataFrame(rows)


def _make_chart(kpi_df, col1, col2, label1, label2, titre):
    df_plot = kpi_df.sort_values("mois", ascending=True).reset_index(drop=True)
    labels_y = df_plot["label"].tolist()
    n_mois = len(labels_y)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=labels_y, x=df_plot[col1], name=label1,
        orientation="h", marker_color=C_ORANGE,
        text=[f"{v:.0f}%" for v in df_plot[col1]],
        textposition="inside",
        textfont=dict(color="white", size=11, family="Arial Black"),
        hovertemplate=f"<b>%{{y}}</b><br>{label1}: %{{x:.1f}}%<extra></extra>",
        width=0.35, offset=-0.37,
    ))
    fig.add_trace(go.Bar(
        y=labels_y, x=df_plot[col2], name=label2,
        orientation="h", marker_color=C_BLEU,
        text=[f"{v:.0f}%" for v in df_plot[col2]],
        textposition="inside",
        textfont=dict(color="white", size=11, family="Arial Black"),
        hovertemplate=f"<b>%{{y}}</b><br>{label2}: %{{x:.1f}}%<extra></extra>",
        width=0.35, offset=0.02,
    ))

    hauteur = max(280, n_mois * 72)
    fig.update_layout(
        title=dict(
            text=f"<b>{titre}</b>",
            font=dict(size=13, color="white"),
            x=0, pad=dict(l=8, t=6),
        ),
        paper_bgcolor=C_TITRE,
        plot_bgcolor="#FFFFFF",
        barmode="overlay",
        height=hauteur,
        margin=dict(l=10, r=20, t=60, b=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0,
            font=dict(size=9, color="white"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            range=[0, 110], showgrid=True,
            gridcolor="#e8e8e8", ticksuffix="%",
            tickfont=dict(size=10), showticklabels=False,
        ),
        yaxis=dict(tickfont=dict(size=11, color="#333"), automargin=True),
    )
    return fig


def render_taux_realisation_tab(df_full):
    """Point d'entree appele depuis app.py. df_full = DataFrame OT complet."""

    st.markdown(
        "<h3 style='color:#1E3A5F;margin-bottom:4px'>Tableau de Bord - Taux de Realisation</h3>",
        unsafe_allow_html=True,
    )

    col_date = None
    for c in df_full.columns:
        if "date" in c.lower() and "but" in c.lower() and "plan" in c.lower():
            col_date = c
            break
    if col_date is None:
        st.error("Colonne 'Date de debut planifiee' introuvable dans les donnees.")
        return

    if df_full[col_date].dropna().empty:
        st.info("Aucune date disponible dans les donnees.")
        return

    annees_dispo = sorted(
        df_full[col_date].dropna().dt.year.unique().astype(int).tolist(),
        reverse=True,
    )

    fc1, fc2, fc3 = st.columns([1, 2, 2])
    with fc1:
        annee_sel = st.selectbox("Annee", options=annees_dispo, index=0, key="tr_annee")
    with fc2:
        mask_an = df_full[col_date].dt.year == annee_sel
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

    # Metriques resumees
    st.markdown("---")
    mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
    metrics = [
        (mc1, "Travaux Planifies", kpi_df["taux_travaux_planifies"].mean(), C_ORANGE),
        (mc2, "PM Systematique",   kpi_df["taux_pm_syst"].mean(),           C_BLEU),
        (mc3, "ZCOR Inspection",   kpi_df["taux_zcor_inspection"].mean(),   C_ORANGE),
        (mc4, "Calendrier ZPRV",   kpi_df["taux_calendrier_prv"].mean(),    C_BLEU),
        (mc5, "Planification",     kpi_df["taux_planification"].mean(),     C_ORANGE),
        (mc6, "Preparation",       kpi_df["taux_preparation"].mean(),       C_BLEU),
    ]
    for col_m, lbl, val, color in metrics:
        with col_m:
            st.markdown(
                f'<div style="background:{color};padding:10px 6px;border-radius:8px;text-align:center">'
                f'<div style="color:white;font-size:10px;font-weight:700;line-height:1.2">{lbl}</div>'
                f'<div style="color:white;font-size:22px;font-weight:900;line-height:1.3">{val:.0f}%</div>'
                f'<div style="color:rgba(255,255,255,.7);font-size:10px">moy. periode</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # 3 graphiques
    g1, g2, g3 = st.columns(3)
    with g1:
        st.plotly_chart(
            _make_chart(kpi_df,
                "taux_travaux_planifies", "taux_pm_syst",
                "TAUX DE REALISATION DES TRAVAUX PLANIFIES",
                "TAUX DE REALISATION PM SYSTEMATIQUE",
                "TAUX DE REALISATION TVX"),
            use_container_width=True, config={"displayModeBar": False},
        )
    with g2:
        st.plotly_chart(
            _make_chart(kpi_df,
                "taux_zcor_inspection", "taux_calendrier_prv",
                "TAUX DE REALISATION DES OT CURATIF ISSU INSPECTION",
                "TAUX DE REALISATION CALENDRIER D INSPECTION GLOBAL",
                "INSPECTION"),
            use_container_width=True, config={"displayModeBar": False},
        )
    with g3:
        st.plotly_chart(
            _make_chart(kpi_df,
                "taux_planification", "taux_preparation",
                "TAUX PLANIFICATION",
                "TAUX PREPARATION",
                "PREPARATION VS PLANIFICATION"),
            use_container_width=True, config={"displayModeBar": False},
        )

    # Tableau detail
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
