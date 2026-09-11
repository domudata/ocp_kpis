# -*- coding: utf-8 -*-
"""
Onglet "Suivi HSE" — structuré en 5 sections thématiques :
  1. Avis Inspection (type ZI)
  2. Avis HSE (type ZH)
  3. OT Sécurité (type de travail 320)
  4. OMS (thermographie & vibration)
  5. Contrôle structure

Chaque section présente des cartes de synthèse, un graphique de
répartition par poste de travail (barres) et des camemberts — sans
tableau, l'information étant portée par les visuels.

À placer dans : pages/suivi_hse.py
"""
import io
import os
import numpy as np
import pandas as pd
import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TYPE_TRAVAIL_SECURITE = 320
STATUTS_CLOTURE = ["TCLO", "CLOT"]

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

# Statut d'approbation SAP (champ "Statut utilisateur")
LIBELLE_APPROBATION = {"APRV": "Approuvé", "APRQ": "En attente", "REJT": "Rejeté"}

# ── Palette harmonisée verts / bleus ──
NAVY = "#1E3A5F"
BLUE = "#2563EB"
GREEN = "#10B981"
TEAL = "#0D9488"
SKY = "#0EA5E9"
EMERAUDE = "#059669"
CYAN = "#06B6D4"
INDIGO = "#4F46E5"
GREY = "#64748B"
DARK = "#1E293B"

PALETTE_STATUT = {"TCLO": GREEN, "CLOT": EMERAUDE, "CRÉÉ": SKY, "CREE": SKY,
                   "LANC": INDIGO, "PART": TEAL}
PALETTE_APPROBATION = {"Approuvé": GREEN, "En attente": SKY, "Rejeté": INDIGO}
PALETTE_OMS = {"Thermographie": BLUE, "Vibration": TEAL}
PALETTE_LIEN = {"Avec avis": BLUE, "Sans avis": GREY}


# ═══════════════════════════════════════════════════════════════════
# Utilitaires
# ═══════════════════════════════════════════════════════════════════

def _statut_court(serie):
    return serie.fillna("").astype(str).str.strip().str.split().str[0].replace("", "Inconnu")


def _approbation(df):
    if "Statut utilisateur" not in df.columns:
        return pd.Series("Non renseigné", index=df.index)
    return (df["Statut utilisateur"].fillna("").astype(str).str.strip().str.split().str[0]
            .map(LIBELLE_APPROBATION).fillna("Non renseigné"))


def _ajouter_periode(df, col_date):
    df = df.copy()
    d = pd.to_datetime(df.get(col_date), errors="coerce")
    df["_Année"] = d.dt.year
    df["_Mois"] = d.dt.month
    df["_Semaine"] = "S" + d.dt.isocalendar().week.astype("Int64").astype(str).str.zfill(2)
    return df


def _filtrer_periode(df, annee, mois, semaine):
    if df.empty:
        return df
    if annee != "Toutes":
        df = df[df["_Année"] == int(annee)]
    if mois != "Tous":
        df = df[df["_Mois"] == int(mois)]
    if semaine != "Toutes":
        df = df[df["_Semaine"] == semaine]
    return df


def _carte(col, label, valeur, couleur, sous=""):
    col.markdown(
        f"""<div style="background:{couleur}12;border:1px solid {couleur}40;border-radius:12px;
        padding:14px 10px;text-align:center;height:100%;">
            <div style="font-size:10.5px;color:#64748B;font-weight:700;text-transform:uppercase;
            letter-spacing:0.5px;margin-bottom:5px;">{label}</div>
            <div style="font-size:26px;font-weight:800;color:{couleur};line-height:1.1;">{valeur}</div>
            <div style="font-size:10.5px;color:#64748B;margin-top:3px;">{sous}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _pie(donnees, titre, palette=None, seuil=7):
    """Camembert avec éclatement automatique des petits secteurs."""
    donnees = {k: float(v) for k, v in donnees.items() if v and float(v) > 0}
    if not donnees:
        return None
    labels, valeurs = list(donnees.keys()), list(donnees.values())
    total = sum(valeurs)
    parts = [v / total * 100 for v in valeurs]
    defaut = [BLUE, SKY, GREEN, TEAL, INDIGO, EMERAUDE, CYAN, GREY] * 5
    couleurs = [(palette or {}).get(l) or defaut[i] for i, l in enumerate(labels)]
    explode = [0.14 if p < seuil else 0.02 for p in parts]

    fig, ax = plt.subplots(figsize=(4.4, 3.3), dpi=170)
    wedges, _, _ = ax.pie(
        valeurs, colors=couleurs, explode=explode, startangle=90,
        autopct=lambda p: f"{p:.0f}%" if p >= seuil else "",
        textprops={"fontsize": 10, "color": "white", "fontweight": "bold"},
        wedgeprops={"edgecolor": "white", "linewidth": 2}, pctdistance=0.72,
    )
    ax.legend(wedges, [f"{l} — {int(v)} ({v/total*100:.1f}%)" for l, v in zip(labels, valeurs)],
              loc="center left", bbox_to_anchor=(0.96, 0.5), fontsize=8.5, frameon=False)
    ax.set_title(titre, fontsize=11, fontweight="bold", color=NAVY, pad=10)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def _bar(pivot, titre, palette=None, xlabel="Nombre", max_postes=12):
    """Barres empilées horizontales par poste de travail, triées par total.
    Limité aux `max_postes` postes les plus représentés : au-delà, les
    barres deviennent trop fines pour rester lisibles, et les postes
    marginaux n'apportent pas d'information exploitable."""
    if pivot is None or pivot.empty:
        return None
    totaux = pivot.sum(axis=1).sort_values()
    n_total = len(totaux)
    if n_total > max_postes:
        totaux = totaux.tail(max_postes)
        titre = f"{titre} (top {max_postes} sur {n_total})"
    pivot = pivot.loc[totaux.index]
    hauteur = max(2.8, 0.42 * len(pivot) + 1.1)
    fig, ax = plt.subplots(figsize=(9, hauteur), dpi=170)
    gauche = np.zeros(len(pivot))
    for col in pivot.columns:
        vals = pivot[col].values.astype(float)
        ax.barh(pivot.index.astype(str), vals, left=gauche, height=0.62,
                color=(palette or {}).get(col, GREY), label=str(col),
                edgecolor="white", linewidth=0.8)
        gauche += vals
    maxi = max(gauche) if len(gauche) else 1
    for i, tot in enumerate(gauche):
        if tot > 0:
            ax.text(tot + maxi * 0.012, i, f"{int(tot)}", va="center",
                    fontsize=9, fontweight="bold", color=DARK)
    ax.set_title(titre, fontsize=11.5, fontweight="bold", color=NAVY, loc="left", pad=24)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.legend(fontsize=8.5, frameon=False, ncol=max(1, len(pivot.columns)),
              loc="lower left", bbox_to_anchor=(0, 1.005))
    ax.grid(axis="x", color="#F1F5F9", linewidth=1)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.set_xlim(0, maxi * 1.13 if maxi > 0 else 1)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# ═══════════════════════════════════════════════════════════════════
# Sections
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="Analyse HSE en cours...", max_entries=8)
def _calculer_sections_hse(_dfp, _avf, vp_tuple, date_str, sel_annee, sel_mois, sel_sem):
    """
    Calcule les découpages thématiques et TOUS les graphiques de la page.

    MISE EN CACHE : la clé est constituée de la date d'extraction
    (date.txt) et des filtres actifs — les DataFrames sont passés avec
    un préfixe underscore (_dfp, _avf) pour que Streamlit NE les hache
    PAS (opération très coûteuse sur 146 000 lignes). Conséquence : tant
    que date.txt et les filtres ne changent pas, les 15 graphiques ne
    sont calculés qu'une seule fois, au lieu d'être régénérés à chaque
    interaction avec la page.
    """
    ot = _ajouter_periode(_dfp.copy(), "Créé le")
    avis = _ajouter_periode(_avf.copy(), "Créé le") if _avf is not None and not _avf.empty else pd.DataFrame()
    vp = list(vp_tuple)
    if not avis.empty and "Poste travail princ." in avis.columns:
        avis = avis[avis["Poste travail princ."].isin(vp)]

    ot = _filtrer_periode(ot, sel_annee, sel_mois, sel_sem)
    avis = _filtrer_periode(avis, sel_annee, sel_mois, sel_sem)

    ot["_Statut"] = _statut_court(ot["Statut système"]) if "Statut système" in ot.columns else "Inconnu"
    ot["_tw"] = ot["_tw_num"] if "_tw_num" in ot.columns else pd.to_numeric(ot.get("Type de travail"), errors="coerce")
    desig = ot["Désignation"].fillna("").astype(str) if "Désignation" in ot.columns else pd.Series("", index=ot.index)
    if not avis.empty:
        avis["_Approbation"] = _approbation(avis)

    ot_securite = ot[ot["_tw"] == TYPE_TRAVAIL_SECURITE]
    masque_therm = desig.str.contains("thermograph", case=False, na=False)
    masque_vib = desig.str.contains("vibration|vibratoire", case=False, na=False)
    # OMS scindé en deux familles distinctes, chacune ayant sa propre
    # section : les volumes et les problématiques diffèrent nettement.
    ot_oms_therm = ot[masque_therm]
    ot_oms_vib = ot[masque_vib & ~masque_therm]
    ot_structure = ot[desig.str.contains("structure", case=False, na=False)]

    avis_zi = avis[avis["Type d'avis"] == "ZI"] if not avis.empty and "Type d'avis" in avis.columns else pd.DataFrame()
    avis_zh = avis[avis["Type d'avis"] == "ZH"] if not avis.empty and "Type d'avis" in avis.columns else pd.DataFrame()

    # Pré-calcul de tous les graphiques (l'opération la plus coûteuse)
    buffers = {}
    for df, cle, couleur, titre in [(avis_zi, "zi", BLUE, "Avis Inspection"),
                                      (avis_zh, "zh", TEAL, "Avis HSE")]:
        if df.empty:
            continue
        total = len(df)
        en_ot = int(df["Ordre"].notna().sum()) if "Ordre" in df.columns else 0
        if "Poste travail princ." in df.columns:
            piv = df.groupby("Poste travail princ.").size().to_frame(name=titre)
            b = _bar(piv, f"Affectation des {titre.lower()} par poste de travail",
                     {titre: couleur}, "Nombre d'avis")
            if b:
                buffers[f"bar_{cle}"] = b
        p1 = _pie(df["_Approbation"].value_counts().to_dict(), "Statut d'approbation", PALETTE_APPROBATION)
        if p1:
            buffers[f"pie_appr_{cle}"] = p1
        p2 = _pie({"Transformé en OT": en_ot, "Sans OT": total - en_ot},
                   "Transformation en ordre de travail", {"Transformé en OT": BLUE, "Sans OT": GREY})
        if p2:
            buffers[f"pie_ot_{cle}"] = p2

    for df, cle, titre in [
            (ot_securite, "secu", "OT Sécurité"),
            (ot_oms_therm, "therm", "OMS Thermographie"),
            (ot_oms_vib, "vib", "OMS Vibration"),
            (ot_structure, "struct", "Contrôle structure")]:
        if df.empty:
            continue
        total = len(df)
        avec_avis = int(df["Avis"].notna().sum()) if "Avis" in df.columns else 0
        if "Poste travail princ." in df.columns:
            piv = pd.crosstab(df["Poste travail princ."], df["_Statut"])
            b = _bar(piv, f"{titre} par poste de travail et par statut", PALETTE_STATUT, "Nombre d'OT")
            if b:
                buffers[f"bar_{cle}"] = b
        p1 = _pie(df["_Statut"].value_counts().to_dict(), "Répartition par statut", PALETTE_STATUT)
        if p1:
            buffers[f"pie_statut_{cle}"] = p1
        p2 = _pie({"Avec avis": avec_avis, "Sans avis": total - avec_avis},
                   "Rattachement à un avis", PALETTE_LIEN)
        if p2:
            buffers[f"pie_cat_{cle}"] = p2

    return {"avis_zi": avis_zi, "avis_zh": avis_zh, "ot_securite": ot_securite,
            "ot_oms_therm": ot_oms_therm, "ot_oms_vib": ot_oms_vib,
            "ot_structure": ot_structure, "buffers": buffers,
            "annees": sorted({int(a) for a in pd.concat(
                [s for s in (ot.get("_Année"), avis.get("_Année")) if s is not None]
            ).dropna().unique()}) if len(ot) or len(avis) else [],
            }


@st.cache_data(show_spinner=False, ttl=120)
def _charger_documents_joints(vp_tuple, chemin="documents_joints.xlsx"):
    """
    Charge le fichier de référence des documents joints par poste de
    travail. Ce fichier est la SOURCE DE VÉRITÉ de cette information :
    l'application ne fait que l'afficher, elle ne la calcule pas (la
    donnée n'existe pas dans les extractions SAP disponibles).
    Pour la mettre à jour : compléter la colonne dans le fichier Excel,
    puis le committer sur GitHub.
    """
    if not os.path.exists(chemin):
        return None
    df = pd.read_excel(chemin)
    col_poste = "Poste travail princ."
    col_nb = "Nombre documents joints"
    if col_poste not in df.columns:
        return None
    if col_nb not in df.columns:
        df[col_nb] = None
    df = df[df[col_poste].isin(list(vp_tuple))]
    return df[[col_poste, col_nb]].rename(
        columns={col_poste: "Poste de travail", col_nb: "Nombre documents joints"}
    ).sort_values("Poste de travail").reset_index(drop=True)


def _section_avis(df, titre, icone, couleur_principale, buffers, cle):
    """Affiche une section d'avis. Les graphiques sont déjà calculés et
    mis en cache par _calculer_sections_hse — cette fonction ne fait que
    les afficher."""
    st.markdown(f"### {icone} {titre}")
    if df.empty:
        st.info(f"Aucun {titre.lower()} sur le périmètre et la période sélectionnés.")
        return

    total = len(df)
    approuves = int((df["_Approbation"] == "Approuvé").sum())
    rejetes = int((df["_Approbation"] == "Rejeté").sum())
    en_ot = int(df["Ordre"].notna().sum()) if "Ordre" in df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    _carte(c1, "Total", str(total), couleur_principale, "avis enregistrés")
    _carte(c2, "Approuvés", str(approuves), GREEN, f"{approuves/total*100:.0f}% du total")
    _carte(c3, "Transformés en OT", str(en_ot), BLUE, f"{en_ot/total*100:.0f}% du total")
    _carte(c4, "Rejetés", str(rejetes), INDIGO, f"{rejetes/total*100:.0f}% du total")

    g1, g2 = st.columns([3, 2])
    if buffers.get(f"bar_{cle}"):
        g1.image(buffers[f"bar_{cle}"], use_container_width=True)
    with g2:
        for k in (f"pie_appr_{cle}", f"pie_ot_{cle}"):
            if buffers.get(k):
                st.image(buffers[k], use_container_width=True)


def _section_ot(df, titre, icone, couleur_principale, buffers, cle):
    """Affiche une section d'ordres de travail (graphiques déjà en cache)."""
    st.markdown(f"### {icone} {titre}")
    if df.empty:
        st.info(f"Aucun ordre de travail « {titre} » sur le périmètre et la période sélectionnés.")
        return

    total = len(df)
    clotures = int(df["_Statut"].isin(STATUTS_CLOTURE).sum())
    avec_avis = int(df["Avis"].notna().sum()) if "Avis" in df.columns else 0
    en_cours = total - clotures

    c1, c2, c3, c4 = st.columns(4)
    _carte(c1, "Total OT", str(total), couleur_principale, "sur le périmètre")
    _carte(c2, "Clôturés", str(clotures), GREEN, f"{clotures/total*100:.0f}% (TCLO/CLOT)")
    _carte(c3, "En cours", str(en_cours), SKY, f"{en_cours/total*100:.0f}% du total")
    _carte(c4, "Rattachés à un avis", str(avec_avis), BLUE, f"{avec_avis/total*100:.0f}% du total")

    g1, g2 = st.columns([3, 2])
    if buffers.get(f"bar_{cle}"):
        g1.image(buffers[f"bar_{cle}"], use_container_width=True)
    with g2:
        for k in (f"pie_statut_{cle}", f"pie_cat_{cle}"):
            if buffers.get(k):
                st.image(buffers[k], use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
# Rapport PDF
# ═══════════════════════════════════════════════════════════════════

def _libelle_periode(sel_annee, sel_mois_lbl, sel_sem):
    parties = []
    if sel_sem != "Toutes":
        parties.append(f"semaine {sel_sem}")
    if sel_mois_lbl != "Tous":
        parties.append(sel_mois_lbl)
    if sel_annee != "Toutes":
        parties.append(str(sel_annee))
    return " — " + " ".join(parties) if parties else ""


def _generer_rapport_pdf(buffers, sections_stats, libelle, date_str, nb_postes):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, Image, PageBreak)
    from PIL import Image as PILImage

    C_NAVY = colors.HexColor(NAVY)
    C_GREY = colors.HexColor(GREY)
    LARGEUR = 25.7 * cm

    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="T1x", fontSize=18, textColor=C_NAVY, fontName="Helvetica-Bold", leading=23))
    s.add(ParagraphStyle(name="Subx", fontSize=9.5, textColor=C_GREY, leading=13))

    def _entete(sous_titre):
        bloc = [Paragraph(f"Suivi HSE{libelle}", s["T1x"]), Spacer(1, 3),
                Paragraph(sous_titre, s["Subx"])]
        if os.path.exists("logo.png"):
            e = Table([[Image("logo.png", width=2 * cm, height=2 * cm), bloc]],
                       colWidths=[2.5 * cm, LARGEUR - 2.5 * cm])
        else:
            e = Table([[bloc]], colWidths=[LARGEUR])
        e.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("LINEBELOW", (0, 0), (-1, -1), 1.2, C_NAVY),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        return e

    def _cartes(stats):
        cells = []
        for label, valeur, couleur, sous in stats:
            cells.append([
                Paragraph(label.upper(), ParagraphStyle(name=f"l{label}", fontSize=7, alignment=1,
                          textColor=C_GREY, fontName="Helvetica-Bold", leading=9)),
                Paragraph(str(valeur), ParagraphStyle(name=f"v{label}", fontSize=16, alignment=1,
                          textColor=colors.HexColor(couleur), fontName="Helvetica-Bold", leading=19)),
                Paragraph(sous, ParagraphStyle(name=f"s{label}", fontSize=6.5, alignment=1,
                          textColor=C_GREY, leading=8)),
            ])
        t = Table([cells], colWidths=[LARGEUR / len(cells)] * len(cells))
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#E2E8F0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        return t

    def _img(buf, largeur_cm, hauteur_max_cm=11.5):
        """Insère une image en respectant son ratio, MAIS en la bornant en
        hauteur : un graphique à barres comportant beaucoup de postes peut
        sinon dépasser la hauteur utile de la page (erreur ReportLab)."""
        buf.seek(0)
        w, h = PILImage.open(buf).size
        buf.seek(0)
        largeur = largeur_cm
        hauteur = largeur * h / w
        if hauteur > hauteur_max_cm * cm:
            hauteur = hauteur_max_cm * cm
            largeur = hauteur * w / h
        return Image(buf, width=largeur, height=hauteur)

    story = []
    n_sec = len(sections_stats)
    for i, (titre, cle, stats) in enumerate(sections_stats):
        story.append(_entete(f"Section {i+1}/{n_sec} — {titre} · {nb_postes} poste(s) · "
                              f"Extraction du {date_str}"))
        story.append(Spacer(1, 8))
        if stats:
            story.append(_cartes(stats))
            story.append(Spacer(1, 10))
        bar = buffers.get(f"bar_{cle}")
        if bar:
            t = Table([[_img(bar, 14 * cm, hauteur_max_cm=7)]], colWidths=[LARGEUR])
            t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(t)
            story.append(Spacer(1, 8))
        pies = [buffers[k] for k in
                (f"pie_appr_{cle}", f"pie_ot_{cle}", f"pie_statut_{cle}", f"pie_cat_{cle}")
                if buffers.get(k)]
        if pies:
            imgs = [_img(p, 6.8 * cm, hauteur_max_cm=4.6) for p in pies]
            t = Table([imgs], colWidths=[LARGEUR / len(imgs)] * len(imgs))
            t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(t)
        if i < n_sec - 1:
            story.append(PageBreak())

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=1.2 * cm,
                             bottomMargin=1.2 * cm, leftMargin=1.6 * cm, rightMargin=1.6 * cm)
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════
# Page principale
# ═══════════════════════════════════════════════════════════════════

def render_suivi_hse_tab(dfp, avf, vp, date_str=""):
    """
    dfp : DataFrame des OT déjà filtré par la sidebar.
    avf : DataFrame des avis déjà chargé (fichier principal avis.xlsx).
    vp  : liste des postes de travail visibles selon la sidebar.
    """
    st.markdown("## 🦺 Suivi HSE")
    st.caption("Avis d'inspection et HSE, ordres de travail sécurité, OMS et contrôle structure.")

    if dfp is None or dfp.empty:
        st.warning("⚠️ Aucune donnée disponible. Chargez d'abord ot.xlsx / avis.xlsx.")
        return

    ot = _ajouter_periode(dfp.copy(), "Créé le")
    avis = _ajouter_periode(avf.copy(), "Créé le") if avf is not None and not avf.empty else pd.DataFrame()
    if not avis.empty and "Poste travail princ." in avis.columns:
        avis = avis[avis["Poste travail princ."].isin(vp)]

    # ── Filtres période ──
    st.markdown("#### 🎛️ Filtres")
    st.caption("Ces filtres s'appliquent EN PLUS des filtres division / poste / période du panneau latéral.")
    sources = [s for s in (ot.get("_Année"), avis.get("_Année")) if s is not None]
    annees = sorted({int(a) for a in pd.concat(sources).dropna().unique()}) if sources else []
    sources_s = [s for s in (ot.get("_Semaine"), avis.get("_Semaine")) if s is not None]
    semaines = sorted({s for s in pd.concat(sources_s).dropna().unique()}) if sources_s else []
    f1, f2, f3 = st.columns(3)
    sel_annee = f1.selectbox("Année", ["Toutes"] + [str(a) for a in annees], key="hse_annee")
    sel_mois_lbl = f2.selectbox("Mois", ["Tous"] + MOIS_FR, key="hse_mois")
    sel_mois = "Tous" if sel_mois_lbl == "Tous" else str(MOIS_FR.index(sel_mois_lbl) + 1)
    sel_sem = f3.selectbox("Semaine", ["Toutes"] + list(semaines), key="hse_sem")

    # ── Calcul (mis en cache : ne se relance que si date.txt ou les
    #    filtres changent — voir _calculer_sections_hse) ──
    res = _calculer_sections_hse(dfp, avf, tuple(vp), date_str, sel_annee, sel_mois, sel_sem)
    buffers = res["buffers"]

    st.markdown("---")
    _section_avis(res["avis_zi"], "Avis Inspection", "🔍", BLUE, buffers, "zi")
    st.markdown("---")
    _section_avis(res["avis_zh"], "Avis HSE", "🦺", TEAL, buffers, "zh")
    st.markdown("---")
    _section_ot(res["ot_securite"], "OT Sécurité", "🛡️", EMERAUDE, buffers, "secu")
    st.markdown("---")
    _section_ot(res["ot_oms_therm"], "OMS Thermographie", "🌡️", BLUE, buffers, "therm")
    st.markdown("---")
    _section_ot(res["ot_oms_vib"], "OMS Vibration", "📳", TEAL, buffers, "vib")
    st.markdown("---")
    _section_ot(res["ot_structure"], "Contrôle structure", "🏗️", CYAN, buffers, "struct")

    # ── Documents joints par poste de travail ──
    st.markdown("---")
    st.markdown("### 📎 Documents joints par poste de travail")
    tab_docs = _charger_documents_joints(tuple(vp))
    if tab_docs is None:
        st.warning(
            "⚠️ Fichier `documents_joints.xlsx` introuvable à la racine du dépôt. "
            "Committez-le sur GitHub : il doit contenir les colonnes "
            "« Poste travail princ. » et « Nombre documents joints »."
        )
    else:
        renseignes = int(tab_docs["Nombre documents joints"].notna().sum())
        st.caption(
            f"Source : `documents_joints.xlsx` — {renseignes} poste(s) renseigné(s) "
            f"sur {len(tab_docs)}. Complétez la colonne dans le fichier Excel, puis "
            f"committez-le : le tableau ci-dessous se mettra à jour automatiquement."
        )
        st.dataframe(tab_docs, use_container_width=True, hide_index=True, height=320)

    # ── Rapport PDF ──
    st.markdown("---")
    st.markdown("#### 📄 Rapport de synthèse")
    libelle = _libelle_periode(sel_annee, sel_mois_lbl, sel_sem)
    st.caption(f"Titre du rapport : « Suivi HSE{libelle} »" if libelle
               else "Aucun filtre de période actif — titre : « Suivi HSE ».")

    if st.button("🖨️ Générer le rapport PDF", type="primary", use_container_width=True):
        try:
            def _stats_avis(df, couleur):
                if df.empty:
                    return []
                n = len(df)
                ap = int((df["_Approbation"] == "Approuvé").sum())
                rj = int((df["_Approbation"] == "Rejeté").sum())
                eo = int(df["Ordre"].notna().sum()) if "Ordre" in df.columns else 0
                return [("Total", n, couleur, "avis"),
                        ("Approuvés", ap, GREEN, f"{ap/n*100:.0f}%"),
                        ("Transformés en OT", eo, BLUE, f"{eo/n*100:.0f}%"),
                        ("Rejetés", rj, INDIGO, f"{rj/n*100:.0f}%")]

            def _stats_ot(df, couleur):
                if df.empty:
                    return []
                n = len(df)
                cl = int(df["_Statut"].isin(STATUTS_CLOTURE).sum())
                av = int(df["Avis"].notna().sum()) if "Avis" in df.columns else 0
                return [("Total OT", n, couleur, "ordres"),
                        ("Clôturés", cl, GREEN, f"{cl/n*100:.0f}%"),
                        ("En cours", n - cl, SKY, f"{(n-cl)/n*100:.0f}%"),
                        ("Avec avis", av, BLUE, f"{av/n*100:.0f}%")]

            sections = [
                ("Avis Inspection", "zi", _stats_avis(res["avis_zi"], BLUE)),
                ("Avis HSE", "zh", _stats_avis(res["avis_zh"], TEAL)),
                ("OT Sécurité (type 320)", "secu", _stats_ot(res["ot_securite"], EMERAUDE)),
                ("OMS Thermographie", "therm", _stats_ot(res["ot_oms_therm"], BLUE)),
                ("OMS Vibration", "vib", _stats_ot(res["ot_oms_vib"], TEAL)),
                ("Contrôle structure", "struct", _stats_ot(res["ot_structure"], CYAN)),
            ]
            sections = [s for s in sections if s[2]]
            pdf = _generer_rapport_pdf(buffers, sections, libelle, date_str, len(vp))
            st.download_button("⬇️ Télécharger le rapport HSE (PDF)", data=pdf,
                                file_name=f"rapport_HSE_{str(date_str).replace('/', '-')}.pdf",
                                mime="application/pdf", use_container_width=True)
            st.success("✅ Rapport généré — cliquez sur le bouton de téléchargement ci-dessus.")
        except Exception as e:
            st.error(f"❌ Erreur lors de la génération : {e}")
