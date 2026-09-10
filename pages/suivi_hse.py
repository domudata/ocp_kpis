# -*- coding: utf-8 -*-
"""
Onglet "Suivi HSE" — suivi croisé :
  · des ordres de travail HSE (Type de travail = 320) issus de ot.xlsx ;
  · des avis d'incident (ZI) et d'hygiène/sécurité (ZH) issus de avis_total.xlsx.

À placer dans : pages/suivi_hse.py
Fichier requis à la racine du dépôt : avis_total.xlsx
"""
import io
import os
import numpy as np
import pandas as pd
import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TYPE_TRAVAIL_HSE = 320
TYPES_AVIS_HSE = ["ZI", "ZH"]
STATUTS_CLOTURE = ["TCLO", "CLOT"]

NAVY = "#1E3A5F"
BLUE = "#2563EB"
GREEN = "#10B981"
ORANGE = "#F59E0B"
RED = "#EF4444"
TEAL = "#0D9488"
PURPLE = "#7C3AED"
GREY = "#64748B"
DARK = "#1E293B"

PALETTE_STATUT = {
    "TCLO": GREEN, "CLOT": TEAL, "CRÉÉ": ORANGE, "CREE": ORANGE,
    "LANC": BLUE, "PART": PURPLE,
}
PALETTE_AVIS = {"ZI": RED, "ZH": ORANGE}


@st.cache_data(show_spinner="Chargement des avis HSE...")
def _charger_avis_total(chemin):
    """Charge avis_total.xlsx (même structure que avis.xlsx, avec
    davantage d'avis historiques)."""
    df = pd.read_excel(chemin)
    for c in ["Créé le", "Date de la clôture"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def _statut_court(serie):
    """Extrait le premier mot du statut système SAP (TCLO, CLOT, CRÉÉ, LANC...)."""
    return serie.fillna("").astype(str).str.strip().str.split().str[0].replace("", "Inconnu")


def _ajouter_periode(df, col_date):
    """Ajoute les colonnes Année / Mois / Semaine (S01..S53) à partir d'une date."""
    df = df.copy()
    d = pd.to_datetime(df[col_date], errors="coerce")
    df["_Année"] = d.dt.year
    df["_Mois"] = d.dt.month
    df["_Semaine"] = "S" + d.dt.isocalendar().week.astype("Int64").astype(str).str.zfill(2)
    return df


def _appliquer_filtres_periode(df, annee, mois, semaine):
    if annee != "Toutes":
        df = df[df["_Année"] == int(annee)]
    if mois != "Tous":
        df = df[df["_Mois"] == int(mois)]
    if semaine != "Toutes":
        df = df[df["_Semaine"] == semaine]
    return df


def _pie(donnees, titre, palette=None, seuil_explode=8):
    """Camembert avec éclatement (explode) automatique des petits secteurs,
    pour qu'ils restent visibles et lisibles."""
    labels = list(donnees.keys())
    valeurs = [float(v) for v in donnees.values()]
    total = sum(valeurs)
    if total <= 0:
        return None
    parts = [v / total * 100 for v in valeurs]
    defaut = [BLUE, ORANGE, GREEN, RED, PURPLE, TEAL, GREY] * 5
    couleurs = [(palette or {}).get(l) or defaut[i] for i, l in enumerate(labels)]
    explode = [0.16 if p < seuil_explode else 0.02 for p in parts]

    fig, ax = plt.subplots(figsize=(4.6, 3.6), dpi=160)
    wedges, _, _ = ax.pie(
        valeurs, colors=couleurs, explode=explode, startangle=90,
        autopct=lambda p: f"{p:.0f}%" if p >= seuil_explode else "",
        textprops={"fontsize": 9, "color": "white", "fontweight": "bold"},
        wedgeprops={"edgecolor": "white", "linewidth": 2},
        pctdistance=0.72,
    )
    legende = [f"{l} — {int(v)} ({v/total*100:.1f}%)" for l, v in zip(labels, valeurs)]
    ax.legend(wedges, legende, loc="center left", bbox_to_anchor=(0.98, 0.5),
              fontsize=8, frameon=False)
    ax.set_title(titre, fontsize=10.5, fontweight="bold", color=NAVY, pad=12)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def _bar_empilee(df_pivot, titre, palette=None, ylabel="Nombre d'OT"):
    """Barres empilées horizontales par poste de travail."""
    if df_pivot.empty:
        return None
    fig, ax = plt.subplots(figsize=(8.4, max(3.2, 0.42 * len(df_pivot))), dpi=160)
    gauche = np.zeros(len(df_pivot))
    for col in df_pivot.columns:
        vals = df_pivot[col].values.astype(float)
        ax.barh(df_pivot.index.astype(str), vals, left=gauche, height=0.62,
                color=(palette or {}).get(col, GREY), label=str(col), edgecolor="white", linewidth=0.8)
        gauche += vals
    maxi = max(gauche) if len(gauche) else 1
    for i, tot in enumerate(gauche):
        if tot > 0:
            ax.text(tot + maxi * 0.012, i, f"{int(tot)}", va="center",
                    fontsize=8, fontweight="bold", color=DARK)
    ax.set_title(titre, fontsize=11, fontweight="bold", color=NAVY, loc="left", pad=26)
    ax.set_xlabel(ylabel, fontsize=9)
    ax.legend(fontsize=8, frameon=False, ncol=max(1, len(df_pivot.columns)),
              loc="lower left", bbox_to_anchor=(0, 1.005))
    ax.grid(axis="x", color="#F1F5F9", linewidth=1)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8.5)
    ax.set_xlim(0, maxi * 1.14 if maxi > 0 else 1)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def _carte(col, label, valeur, couleur, sous_texte=""):
    col.markdown(
        f"""<div style="background:{couleur}12;border:1px solid {couleur}40;border-radius:12px;
        padding:16px 12px;text-align:center;height:100%;">
            <div style="font-size:11px;color:#64748B;font-weight:700;text-transform:uppercase;
            letter-spacing:0.6px;margin-bottom:6px;">{label}</div>
            <div style="font-size:27px;font-weight:800;color:{couleur};line-height:1.1;">{valeur}</div>
            <div style="font-size:11px;color:#64748B;margin-top:4px;">{sous_texte}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _generer_rapport_pdf(tab_ot, tab_avis, tab_sans, buffers, contexte):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

    C_NAVY = colors.HexColor(NAVY)
    C_GREY = colors.HexColor(GREY)
    C_LGREY = colors.HexColor("#F1F5F9")

    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="T1x", fontSize=18, textColor=C_NAVY, fontName="Helvetica-Bold", leading=23, spaceAfter=8))
    s.add(ParagraphStyle(name="Subx", fontSize=9.5, textColor=C_GREY, leading=13, spaceAfter=14))
    s.add(ParagraphStyle(name="H2y", fontSize=12, textColor=C_NAVY, fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6))
    s.add(ParagraphStyle(name="Cy", fontSize=8.5, leading=11))

    story = [Paragraph("Rapport de suivi HSE", s["T1x"]), Paragraph(contexte, s["Subx"])]

    def _table(df, titre):
        story.append(Paragraph(titre, s["H2y"]))
        if df is None or df.empty:
            story.append(Paragraph("Aucune donnée sur ce périmètre.", s["Cy"]))
            return
        n = len(df.columns)
        rows = [list(df.columns)] + df.astype(str).values.tolist()
        t = Table(rows, colWidths=[16.5 / n * cm] * n, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_LGREY]),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    _table(tab_ot, "1. Ordres de travail HSE (type de travail 320) par poste")

    imgs = [Image(buffers[k], width=7.6 * cm, height=6 * cm)
            for k in ("pie_statut", "pie_avis_ot") if buffers.get(k)]
    if imgs:
        story.append(Spacer(1, 8))
        t = Table([imgs], colWidths=[8.2 * cm] * len(imgs))
        t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(t)

    _table(tab_avis, "2. Avis HSE (ZI / ZH) par poste de travail")

    if buffers.get("pie_type_avis"):
        story.append(Spacer(1, 8))
        t = Table([[Image(buffers["pie_type_avis"], width=7.6 * cm, height=6 * cm)]], colWidths=[8.2 * cm])
        t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(t)

    _table(tab_sans, "3. Postes de travail sans OT 320 et sans avis ZI/ZH")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=1.7 * cm, rightMargin=1.7 * cm)
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def render_suivi_hse_tab(dfp, vp, date_str="", chemin_avis_total="avis_total.xlsx"):
    """
    dfp : DataFrame des OT déjà filtré par la sidebar (division, poste, période).
    vp  : liste des postes de travail visibles selon la sidebar.
    """
    st.markdown("### 🦺 Suivi HSE")
    st.caption(
        "Suivi croisé des ordres de travail HSE (type de travail 320) et des avis "
        "d'incident (ZI) / hygiène-sécurité (ZH)."
    )

    if not os.path.exists(chemin_avis_total):
        st.warning(f"⚠️ Fichier `{chemin_avis_total}` introuvable à la racine du dépôt. Committez-le sur GitHub.")
        return
    avis = _charger_avis_total(chemin_avis_total)

    ot = dfp.copy()
    ot["_tw"] = ot["_tw_num"] if "_tw_num" in ot.columns else pd.to_numeric(ot.get("Type de travail"), errors="coerce")
    ot = ot[ot["_tw"] == TYPE_TRAVAIL_HSE]

    if "Type d'avis" in avis.columns:
        avis = avis[avis["Type d'avis"].isin(TYPES_AVIS_HSE)]
    else:
        avis = avis.iloc[0:0]
    if "Poste travail princ." in avis.columns:
        avis = avis[avis["Poste travail princ."].isin(vp)]

    ot = _ajouter_periode(ot, "Créé le") if "Créé le" in ot.columns else ot.assign(_Année=np.nan, _Mois=np.nan, _Semaine=pd.NA)
    avis = _ajouter_periode(avis, "Créé le") if "Créé le" in avis.columns else avis.assign(_Année=np.nan, _Mois=np.nan, _Semaine=pd.NA)

    st.markdown("#### 🎛️ Filtres complémentaires")
    st.caption("Ces filtres s'appliquent EN PLUS des filtres division / poste / période du panneau latéral.")
    annees = sorted({int(a) for a in pd.concat([ot["_Année"], avis["_Année"]]).dropna().unique()})
    semaines = sorted({s for s in pd.concat([ot["_Semaine"], avis["_Semaine"]]).dropna().unique()})
    f1, f2, f3 = st.columns(3)
    sel_annee = f1.selectbox("Année", ["Toutes"] + [str(a) for a in annees], key="hse_annee")
    sel_mois = f2.selectbox("Mois", ["Tous"] + [str(m) for m in range(1, 13)], key="hse_mois")
    sel_sem = f3.selectbox("Semaine", ["Toutes"] + list(semaines), key="hse_semaine")

    ot = _appliquer_filtres_periode(ot, sel_annee, sel_mois, sel_sem)
    avis = _appliquer_filtres_periode(avis, sel_annee, sel_mois, sel_sem)

    if ot.empty and avis.empty:
        st.info("Aucune donnée HSE sur ce périmètre et cette période.")
        return

    ot["Statut"] = _statut_court(ot["Statut système"]) if "Statut système" in ot.columns else "Inconnu"
    ot["Clôturé"] = ot["Statut"].isin(STATUTS_CLOTURE)
    ot["A un avis"] = ot["Avis"].notna() if "Avis" in ot.columns else False
    if not avis.empty and "Statut système" in avis.columns:
        avis["Statut"] = _statut_court(avis["Statut système"])

    n_ot = len(ot)
    n_clot = int(ot["Clôturé"].sum()) if n_ot else 0
    n_avec_avis = int(ot["A un avis"].sum()) if n_ot else 0
    n_zi = int((avis["Type d'avis"] == "ZI").sum()) if not avis.empty else 0
    n_zh = int((avis["Type d'avis"] == "ZH").sum()) if not avis.empty else 0

    st.markdown("---")
    c1, c2, c3, c4, c5 = st.columns(5)
    _carte(c1, "OT HSE (tw 320)", str(n_ot), NAVY, "sur le périmètre filtré")
    _carte(c2, "OT clôturés", str(n_clot), GREEN, f"{n_clot/n_ot*100:.0f}% (TCLO + CLOT)" if n_ot else "—")
    _carte(c3, "OT avec avis", str(n_avec_avis), BLUE, f"{n_avec_avis/n_ot*100:.0f}% des OT" if n_ot else "—")
    _carte(c4, "Avis ZI", str(n_zi), RED, "incidents")
    _carte(c5, "Avis ZH", str(n_zh), ORANGE, "hygiène / sécurité")

    st.markdown("---")
    st.markdown("#### 📋 Ordres de travail HSE (type 320) par poste de travail")
    tab_ot = pd.DataFrame()
    if ot.empty:
        st.info("Aucun OT de type 320 sur ce périmètre.")
    else:
        pivot = pd.crosstab(ot["Poste travail princ."], ot["Statut"])
        pivot["Total"] = pivot.sum(axis=1)
        pivot["Clôturés"] = sum((pivot[s] for s in STATUTS_CLOTURE if s in pivot.columns),
                                 pd.Series(0, index=pivot.index))
        pivot["% clôture"] = (pivot["Clôturés"] / pivot["Total"] * 100).round(0).astype(int).astype(str) + "%"
        avec_avis = ot[ot["A un avis"]].groupby("Poste travail princ.").size()
        pivot["OT avec avis"] = avec_avis.reindex(pivot.index, fill_value=0)
        pivot["% avec avis"] = (pivot["OT avec avis"] / pivot["Total"] * 100).round(0).astype(int).astype(str) + "%"
        # Documents joints : non disponible dans l'extraction SAP actuelle,
        # colonne laissée vide en attendant la source de données correspondante.
        pivot["Documents joints"] = ""
        tab_ot = pivot.reset_index().rename(columns={"Poste travail princ.": "Poste de travail"})
        st.dataframe(tab_ot, use_container_width=True, hide_index=True)

        cols_statut = [c for c in pivot.columns if c in PALETTE_STATUT]
        if cols_statut:
            buf_bar = _bar_empilee(pivot[cols_statut], "Répartition des OT HSE par poste et par statut", PALETTE_STATUT)
            if buf_bar:
                st.image(buf_bar, use_container_width=True)

    st.markdown("#### 📊 Répartitions")
    g1, g2, g3 = st.columns(3)
    buffers = {}
    if not ot.empty:
        b = _pie(ot["Statut"].value_counts().to_dict(), "Statut des OT HSE", PALETTE_STATUT)
        buffers["pie_statut"] = b
        if b:
            g1.image(b, use_container_width=True)
        b2 = _pie({"Avec avis": n_avec_avis, "Sans avis": n_ot - n_avec_avis},
                   "OT HSE rattachés à un avis", {"Avec avis": BLUE, "Sans avis": GREY})
        buffers["pie_avis_ot"] = b2
        if b2:
            g2.image(b2, use_container_width=True)
    if not avis.empty:
        b3 = _pie(avis["Type d'avis"].value_counts().to_dict(), "Répartition des avis HSE", PALETTE_AVIS)
        buffers["pie_type_avis"] = b3
        if b3:
            g3.image(b3, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 🚨 Avis HSE (ZI / ZH) par poste de travail")
    tab_avis = pd.DataFrame()
    if avis.empty:
        st.info("Aucun avis ZI/ZH sur ce périmètre.")
    else:
        piv_av = pd.crosstab(avis["Poste travail princ."], avis["Type d'avis"])
        for t in TYPES_AVIS_HSE:
            if t not in piv_av.columns:
                piv_av[t] = 0
        piv_av = piv_av[TYPES_AVIS_HSE]
        piv_av["Total"] = piv_av.sum(axis=1)
        tab_avis = piv_av.reset_index().rename(columns={"Poste travail princ.": "Poste de travail"})
        st.dataframe(tab_avis.sort_values("Total", ascending=False), use_container_width=True, hide_index=True)
        buf_av = _bar_empilee(piv_av[TYPES_AVIS_HSE], "Répartition des avis HSE par poste et par type",
                               PALETTE_AVIS, "Nombre d'avis")
        if buf_av:
            st.image(buf_av, use_container_width=True)

    st.markdown("---")
    st.markdown("#### ⚪ Postes de travail sans activité HSE")
    st.caption("Postes n'ayant NI ordre de travail de type 320, NI avis ZI/ZH sur le périmètre et la période sélectionnés.")
    postes_ot = set(ot["Poste travail princ."].dropna().unique()) if not ot.empty else set()
    postes_avis = set(avis["Poste travail princ."].dropna().unique()) if not avis.empty else set()
    sans = sorted(set(vp) - postes_ot - postes_avis)
    tab_sans = pd.DataFrame({"Poste de travail": sans,
                              "OT type 320": ["Aucun"] * len(sans),
                              "Avis ZI/ZH": ["Aucun"] * len(sans)})
    if sans:
        st.dataframe(tab_sans, use_container_width=True, hide_index=True)
        st.caption(f"{len(sans)} poste(s) sur {len(vp)} sans aucune activité HSE enregistrée.")
    else:
        st.success("✅ Tous les postes du périmètre présentent au moins une activité HSE.")

    st.markdown("---")
    st.markdown("#### 📄 Rapport de synthèse")
    contexte = (f"Périmètre : {len(vp)} poste(s) · Année : {sel_annee} · Mois : {sel_mois} · "
                f"Semaine : {sel_sem} · Extraction du {date_str}")
    if st.button("🖨️ Générer le rapport PDF", type="primary", use_container_width=True):
        try:
            pdf_bytes = _generer_rapport_pdf(tab_ot, tab_avis, tab_sans, buffers, contexte)
            st.download_button(
                "⬇️ Télécharger le rapport HSE (PDF)", data=pdf_bytes,
                file_name=f"rapport_HSE_{str(date_str).replace('/', '-')}.pdf",
                mime="application/pdf", use_container_width=True,
            )
            st.success("✅ Rapport généré — cliquez sur le bouton de téléchargement ci-dessus.")
        except Exception as e:
            st.error(f"❌ Erreur lors de la génération : {e}")
