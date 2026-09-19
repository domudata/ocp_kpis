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
import re
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

LIBELLE_APPROBATION = {"APRV": "Approuvé", "APRQ": "En attente", "REJT": "Rejeté"}

DICT_STATUTS_AVIS = {
    "AOUV": "OUVERT", "AENC": "EN COURS", "ACLO": "CLÔTURÉ", "OAFF": "AFFICHÉ",
    "AIMP": "IMPRIMÉ", "TSUP": "STATUT TECHNIQUE SUPPLÉMENTAIRE",
    "TAMO": "TRAITEMENT COMPLÉMENTAIRE", "MARC": "MARQUÉ POUR SUPPRESSION",
}

NATURES_FUITES_PATTERNS = [
    ("PRODUIT CHIMIQUE", r"\bproduits?\s+chimiques?\b|\bchimiques?\b"),
    ("AMMONIAQUE", r"\b(ammoniaque|ammoniac|nh3)\b"),
    ("HYDROCARBURE", r"\bhydrocarbures?\b"),
    ("CONDENSAT", r"\bcondensats?\b"),
    ("ACIDE", r"\bacides?\b|\bh2so4\b|\bh3po4\b|\bhcl\b"),
    ("VAPEUR", r"\bvapeurs?\b"),
    ("HUILE", r"\bhuiles?\b"),
    ("GRAISSE", r"\bgraisses?\b"),
    ("SOUDE", r"\bsoudes?\b|\bnaoh\b"),
    ("FUEL", r"\b(fuel|fioul|mazout)\b"),
    ("BOUE", r"\bboues?\b"),
    ("GAZ", r"\bgaz\b"),
    ("AIR", r"\bair\b"),
    ("EAU", r"\beau[x]?\b"),
    ("LIQUIDE", r"\bliquides?\b"),
]

NAVY = "#1E3A5F"; BLUE = "#2563EB"; GREEN = "#10B981"; TEAL = "#0D9488"
SKY = "#0EA5E9"; EMERAUDE = "#059669"; CYAN = "#06B6D4"; INDIGO = "#4F46E5"
GREY = "#64748B"; DARK = "#1E293B"

PALETTE_STATUT = {"TCLO": GREEN, "CLOT": EMERAUDE, "CRÉÉ": SKY, "CREE": SKY,
                   "LANC": INDIGO, "PART": TEAL}
PALETTE_APPROBATION = {"Approuvé": GREEN, "En attente": SKY, "Rejeté": INDIGO}
PALETTE_OMS = {"Thermographie": BLUE, "Vibration": TEAL}
PALETTE_LIEN = {"Avec avis": BLUE, "Sans avis": GREY}

PALETTE_NATURES = {
    "EAU": "#0EA5E9", "GAZ": "#6366F1", "HUILE": "#D97706", "VAPEUR": "#64748B",
    "ACIDE": "#EF4444", "AIR": "#06B6D4", "FUEL": "#78350F", "HYDROCARBURE": "#B45309",
    "GRAISSE": "#A16207", "SOUDE": "#8B5CF6", "AMMONIAQUE": "#14B8A6",
    "CONDENSAT": "#38BDF8", "BOUE": "#713F12", "PRODUIT CHIMIQUE": "#F43F5E",
    "LIQUIDE": "#3B82F6", "FUITE NON DÉFINIE": "#94A3B8",
}

PALETTE_STATUT_UNIFIE = {"Clôturé": "#10B981", "En cours": "#0EA5E9", "Rejeté": "#EF4444"}


def _classifier_statut(statut_sys, statut_util=None):
    s_u = str(statut_util).strip().upper().split()[0] if statut_util and str(statut_util).lower() not in ["nan", "none"] else ""
    s_s = str(statut_sys).strip().upper().split()[0] if statut_sys and str(statut_sys).lower() not in ["nan", "none"] else ""
    if s_u == "REJT":
        return "Rejeté"
    if s_s in ["AOUV", "AENC"]:
        return "En cours"
    if s_s == "ACLO":
        return "Clôturé"
    return "Rejeté"

def _statut_court(serie):
    return serie.fillna("").astype(str).str.strip().str.split().str[0].replace("", "Inconnu")


def _regrouper_atelier(poste):
    if poste is None:
        return "AUTRE"
    p = str(poste).strip()
    if not p or p.lower() in ["nan", "none"]:
        return "AUTRE"
    p_upper = p.upper()
    if "GCMC" in p_upper or "GCFD" in p_upper:
        return "AUTRE"
    for code in ("TSP", "REX", "MCP", "DCP", "PP1", "PP2", "PS3", "PS4"):
        if code in p_upper:
            return code
    if re.search(r'(?:^|[\s\-_]|[EMRI])CU(?:$|[\s\-_0-9])', p_upper) or re.search(r'\bCU\b', p_upper):
        return "PC"
    if re.search(r'(?:^|[\s\-_]|[EMRI])UT(?:$|[\s\-_0-9])', p_upper) or re.search(r'\bUT\b', p_upper):
        return "CENTRAL"
    return p


def _analyser_nature(txt):
    if not txt:
        return "FUITE NON DÉFINIE"
    t = str(txt).lower()
    for nat, pat in NATURES_FUITES_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return nat
    return "FUITE NON DÉFINIE"


def _extraire_premier_statut(statut_sys):
    if statut_sys is None:
        return "NON RENSEIGNÉ"
    txt = str(statut_sys).strip()
    if not txt or txt.lower() in ["nan", "none"]:
        return "NON RENSEIGNÉ"
    return txt.split()[0].upper()


def _libelle_statut_complet(code):
    if not code or code == "NON RENSEIGNÉ":
        return "NON RENSEIGNÉ"
    libelle = DICT_STATUTS_AVIS.get(code, code)
    if libelle != code:
        return f"{libelle} ({code})"
    return code


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
    nb_cols = len(pivot.columns)
    ncol = max(1, min(nb_cols, 4))
    pad = 24 if nb_cols <= 4 else (24 + 14 * ((nb_cols - 1) // 4))
    ax.set_title(titre, fontsize=11.5, fontweight="bold", color=NAVY, loc="left", pad=pad)
    ax.set_xlabel(xlabel, fontsize=9)
    if nb_cols > 1 or (nb_cols == 1 and str(pivot.columns[0]) not in [titre, "Avis", "Fuites"]):
        ax.legend(fontsize=8.5, frameon=False, ncol=ncol,
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


def _bar_statuts_avec_pct(pivot, titre, palette=None, xlabel="Nombre d'avis", max_postes=25):
    if pivot is None or pivot.empty:
        return None
    totaux = pivot.sum(axis=1).sort_values()
    n_total = len(totaux)
    if n_total > max_postes:
        totaux = totaux.tail(max_postes)
        titre = f"{titre} (top {max_postes} sur {n_total})"
    pivot = pivot.loc[totaux.index]
    ordre_cols = [c for c in ["Clôturé", "En cours", "Rejeté"] if c in pivot.columns]
    autres = [c for c in pivot.columns if c not in ordre_cols]
    pivot = pivot[ordre_cols + autres]
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
    for i, idx in enumerate(pivot.index):
        tot = gauche[i]
        if tot > 0:
            enc = float(pivot.loc[idx, "En cours"]) if "En cours" in pivot.columns else 0.0
            pct_enc = (enc / tot * 100) if tot > 0 else 0
            ax.text(tot + maxi * 0.012, i, f"{int(tot)} ({pct_enc:.0f}% en cours)", va="center",
                    fontsize=8.5, fontweight="bold", color=DARK)
    nb_cols = len(pivot.columns)
    ncol = max(1, min(nb_cols, 4))
    pad = 24 if nb_cols <= 4 else (24 + 14 * ((nb_cols - 1) // 4))
    ax.set_title(titre, fontsize=11.5, fontweight="bold", color=NAVY, loc="left", pad=pad)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.legend(fontsize=8.5, frameon=False, ncol=ncol, loc="lower left", bbox_to_anchor=(0, 1.005))
    ax.grid(axis="x", color="#F1F5F9", linewidth=1)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.set_xlim(0, maxi * 1.25 if maxi > 0 else 1)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def _bar_fuites_par_type(pivot, titre="Ventilation des avis fuites par type (Clôturé / En cours / %)", palette=None, max_types=18):
    if pivot is None or pivot.empty:
        return None
    totaux = pivot.sum(axis=1).sort_values()
    n_total = len(totaux)
    if n_total > max_types:
        totaux = totaux.tail(max_types)
        titre = f"{titre} (top {max_types} sur {n_total})"
    pivot = pivot.loc[totaux.index]
    ordre_cols = [c for c in ["Clôturé", "En cours", "Rejeté"] if c in pivot.columns]
    autres = [c for c in pivot.columns if c not in ordre_cols]
    pivot = pivot[ordre_cols + autres]
    hauteur = max(2.8, 0.42 * len(pivot) + 1.1)
    fig, ax = plt.subplots(figsize=(9.5, hauteur), dpi=170)
    gauche = np.zeros(len(pivot))
    for col in pivot.columns:
        vals = pivot[col].values.astype(float)
        ax.barh(pivot.index.astype(str), vals, left=gauche, height=0.62,
                color=(palette or {}).get(col, GREY), label=str(col),
                edgecolor="white", linewidth=0.8)
        gauche += vals
    maxi = max(gauche) if len(gauche) else 1
    for i, idx in enumerate(pivot.index):
        tot = gauche[i]
        if tot > 0:
            clot = float(pivot.loc[idx, "Clôturé"]) if "Clôturé" in pivot.columns else 0.0
            enc = float(pivot.loc[idx, "En cours"]) if "En cours" in pivot.columns else 0.0
            pct_c = (clot / tot * 100) if tot > 0 else 0
            pct_e = (enc / tot * 100) if tot > 0 else 0
            ax.text(tot + maxi * 0.012, i, f"{int(tot)} ({pct_c:.0f}% clôt. | {pct_e:.0f}% enc.)", va="center",
                    fontsize=8.5, fontweight="bold", color=DARK)
    nb_cols = len(pivot.columns)
    ncol = max(1, min(nb_cols, 4))
    pad = 24 if nb_cols <= 4 else (24 + 14 * ((nb_cols - 1) // 4))
    ax.set_title(titre, fontsize=11.5, fontweight="bold", color=NAVY, loc="left", pad=pad)
    ax.set_xlabel("Nombre d'avis fuites", fontsize=9)
    ax.legend(fontsize=8.5, frameon=False, ncol=ncol, loc="lower left", bbox_to_anchor=(0, 1.005))
    ax.grid(axis="x", color="#F1F5F9", linewidth=1)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.set_xlim(0, maxi * 1.30 if maxi > 0 else 1)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


@st.cache_data(show_spinner="Analyse HSE en cours...", max_entries=8)
def _calculer_sections_hse(_dfp, _avf, vp_tuple, date_str, sel_annee, sel_mois, sel_sem, sel_atelier="Tous"):
    ot = _ajouter_periode(_dfp.copy(), "Créé le")
    avis = _ajouter_periode(_avf.copy(), "Créé le") if _avf is not None and not _avf.empty else pd.DataFrame()
    vp = [p for p in vp_tuple if not re.search("GCMC|GCFD", str(p), re.IGNORECASE)]

    col_p_ot = next((c for c in ot.columns if "poste" in str(c).lower() and "trav" in str(c).lower()), "Poste travail princ.")
    col_p_av = next((c for c in avis.columns if "poste" in str(c).lower() and "trav" in str(c).lower()), "Poste travail princ.") if not avis.empty else "Poste travail princ."

    if not ot.empty and col_p_ot in ot.columns:
        ot = ot[~ot[col_p_ot].astype(str).str.contains("GCMC|GCFD", case=False, na=False)].copy()
    if not avis.empty and col_p_av in avis.columns:
        avis = avis[~avis[col_p_av].astype(str).str.contains("GCMC|GCFD", case=False, na=False)].copy()

    ot_gen = _filtrer_periode(ot, sel_annee, sel_mois, sel_sem)
    avis_gen = avis[avis[col_p_av].isin(vp)].copy() if (not avis.empty and col_p_av in avis.columns) else pd.DataFrame()
    avis_gen = _filtrer_periode(avis_gen, sel_annee, sel_mois, sel_sem)

    ot_gen["_Statut"] = _statut_court(ot_gen["Statut système"]) if "Statut système" in ot_gen.columns else "Inconnu"
    ot_gen["_tw"] = ot_gen["_tw_num"] if "_tw_num" in ot_gen.columns else pd.to_numeric(ot_gen.get("Type de travail"), errors="coerce")
    desig = ot_gen["Désignation"].fillna("").astype(str) if "Désignation" in ot_gen.columns else pd.Series("", index=ot_gen.index)
    if not avis_gen.empty:
        avis_gen["_Approbation"] = _approbation(avis_gen)

    ot_securite = ot_gen[ot_gen["_tw"] == TYPE_TRAVAIL_SECURITE]
    masque_therm = desig.str.contains("thermograph", case=False, na=False)
    masque_vib = desig.str.contains("vibration|vibratoire", case=False, na=False)
    ot_oms_therm = ot_gen[masque_therm]
    ot_oms_vib = ot_gen[masque_vib & ~masque_therm]
    ot_structure = ot_gen[desig.str.contains("structure", case=False, na=False)]

    avis_zi = avis_gen[avis_gen["Type d'avis"] == "ZI"] if not avis_gen.empty and "Type d'avis" in avis_gen.columns else pd.DataFrame()
    avis_zh = avis_gen[avis_gen["Type d'avis"] == "ZH"] if not avis_gen.empty and "Type d'avis" in avis_gen.columns else pd.DataFrame()

    avis_fuites_source = avis.copy()
    avis_fuites_source = _filtrer_periode(avis_fuites_source, sel_annee, sel_mois, sel_sem)

    if not avis_fuites_source.empty and col_p_av in avis_fuites_source.columns:
        avis_fuites_source["_Atelier"] = avis_fuites_source[col_p_av].apply(_regrouper_atelier)
        if sel_atelier != "Tous":
            avis_fuites_source = avis_fuites_source[avis_fuites_source["_Atelier"] == sel_atelier].copy()

    col_d_av = next((c for c in avis_fuites_source.columns if str(c).lower() in ["description", "désignation", "designation"] or "descript" in str(c).lower() or "designat" in str(c).lower()), None) if not avis_fuites_source.empty else None

    if not avis_fuites_source.empty:
        if col_d_av and col_d_av in avis_fuites_source.columns:
            desig_av = avis_fuites_source[col_d_av].fillna("").astype(str)
            masque_fuite = desig_av.str.contains(r"\bfuites?\b", case=False, na=False, regex=True)
            avis_fuites_source["_EstFuite"] = masque_fuite
            avis_fuites_source["_NatureFuite"] = "FUITE NON DÉFINIE"
            if masque_fuite.any():
                avis_fuites_source.loc[masque_fuite, "_NatureFuite"] = desig_av[masque_fuite].apply(_analyser_nature)
        else:
            avis_fuites_source["_EstFuite"] = False
            avis_fuites_source["_NatureFuite"] = "FUITE NON DÉFINIE"

        avis_fuites_source["_StatutCat"] = avis_fuites_source.apply(
            lambda r: _classifier_statut(r.get("Statut système"), r.get("Statut utilisateur")),
            axis=1
        )
    else:
        avis_fuites_source["_EstFuite"] = pd.Series(dtype=bool)
        avis_fuites_source["_NatureFuite"] = pd.Series(dtype=str)
        avis_fuites_source["_StatutCat"] = pd.Series(dtype=str)

    df_fuites = avis_fuites_source[avis_fuites_source["_EstFuite"] == True].copy() if not avis_fuites_source.empty else pd.DataFrame()

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

    if not df_fuites.empty:
        counts_fuites_st = df_fuites["_StatutCat"].value_counts().to_dict()
        p1 = _pie(counts_fuites_st, "Répartition des avis types fuites par statut", PALETTE_STATUT_UNIFIE)
        if p1:
            buffers["pie_fuites_statut"] = p1

        if "_Atelier" in df_fuites.columns:
            piv_fuites = df_fuites.groupby("_Atelier").size().to_frame(name="Avis Fuites")
            b2 = _bar(piv_fuites, "Nombre d'avis fuites par Atelier", {"Avis Fuites": "#D97706"}, xlabel="Nombre d'avis fuites", max_postes=25)
            if b2:
                buffers["bar_fuites_atelier"] = b2

        if "_NatureFuite" in df_fuites.columns:
            piv_fuites_type = pd.crosstab(df_fuites["_NatureFuite"], df_fuites["_StatutCat"])
            b3 = _bar_fuites_par_type(piv_fuites_type, "Ventilation des avis fuites par type (Clôturé / En cours / %)", PALETTE_STATUT_UNIFIE)
            if b3:
                buffers["bar_fuites_type"] = b3

        if "_Atelier" in df_fuites.columns:
            piv_statuts_at = pd.crosstab(df_fuites["_Atelier"], df_fuites["_StatutCat"])
            b4 = _bar_statuts_avec_pct(piv_statuts_at, "Statuts des avis fuites par Atelier (avec % en cours)", PALETTE_STATUT_UNIFIE, xlabel="Nombre d'avis fuites", max_postes=25)
            if b4:
                buffers["bar_statuts_fuites_atelier"] = b4

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
            "ot_structure": ot_structure,
            "df_fuites": df_fuites,
            "buffers": buffers,
            "annees": sorted({int(a) for a in pd.concat(
                [s for s in (ot.get("_Année"), avis.get("_Année")) if s is not None]
            ).dropna().unique()}) if len(ot) or len(avis) else [],
            }


@st.cache_data(show_spinner=False, ttl=120)
def _charger_documents_joints(vp_tuple, chemin="documents_joints.xlsx"):
    if not os.path.exists(chemin):
        return None, f"Fichier `{chemin}` introuvable à la racine du dépôt."
    try:
        df = pd.read_excel(chemin)
    except Exception as e:
        return None, f"Lecture impossible : {e}"

    col_poste = next((c for c in df.columns
                      if "poste" in str(c).lower()), None)
    if col_poste is None:
        return None, (f"Colonne des postes introuvable. Colonnes présentes : "
                      f"{list(df.columns)}")

    col_nb = next((c for c in df.columns
                   if "doc" in str(c).lower() and c != col_poste), None)
    if col_nb is None:
        col_nb = "Nombre documents joints"
        df[col_nb] = pd.NA

    df[col_poste] = df[col_poste].astype(str).str.strip()
    postes_connus = {str(p).strip() for p in vp_tuple}
    df_filtre = df[df[col_poste].isin(postes_connus)]

    msg = (f"{len(df_filtre)} poste(s) affiché(s) sur {len(df)} présents dans le fichier "
           f"({len(postes_connus)} postes dans le périmètre courant).")
    if df_filtre.empty and len(df) > 0:
        msg += (f" ⚠️ Aucune correspondance : vérifiez que les noms de postes du fichier "
                f"correspondent à ceux de SAP. Exemple dans le fichier : "
                f"{df[col_poste].head(3).tolist()}")

    resultat = (df_filtre[[col_poste, col_nb]]
                .rename(columns={col_poste: "Poste de travail",
                                  col_nb: "Nombre documents joints"})
                .sort_values("Poste de travail").reset_index(drop=True))
    return resultat, msg


def _export_excel_bytes(df, nom_feuille="Données"):
    """AJOUTÉ (demande explicite) : exporte un DataFrame en bytes .xlsx
    pour le bouton de téléchargement Excel de chaque section."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        (df if not df.empty else pd.DataFrame({"Info": ["Aucune donnée pour la sélection actuelle."]})).to_excel(
            writer, sheet_name=str(nom_feuille)[:31], index=False
        )
    buf.seek(0)
    return buf.getvalue()


def _bouton_excel_section(df, cle, libelle_fichier, date_str):
    """AJOUTÉ (demande explicite) : bouton de téléchargement Excel des
    données brutes d'une section — l'image du graphique déjà affichée
    sert d'aperçu, ce bouton donne accès aux données complètes."""
    st.download_button(
        f"⬇️ Télécharger les données (Excel) — {len(df)} ligne(s)",
        data=_export_excel_bytes(df, libelle_fichier),
        file_name=f"{cle}_{str(date_str).replace('/', '-')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key=f"dl_excel_{cle}",
    )


def _section_active(nom, sections_actives):
    """AJOUTÉ (demande explicite) : vérifie si une section doit être
    affichée selon la sélection du filtre dynamique."""
    return nom in sections_actives


def _section_avis(df, titre, icone, couleur_principale, buffers, cle, date_str=""):
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

    _bouton_excel_section(df, cle, titre, date_str)


def _section_ot(df, titre, icone, couleur_principale, buffers, cle, date_str=""):
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

    _bouton_excel_section(df, cle, titre, date_str)


def _tableau_avis_fuites_par_atelier_et_type(df_fuites):
    if df_fuites is None or df_fuites.empty:
        return pd.DataFrame(columns=["Atelier", "Total Avis Fuites"])

    col_at = "_Atelier" if "_Atelier" in df_fuites.columns else "Atelier"
    col_nat = "_NatureFuite" if "_NatureFuite" in df_fuites.columns else "Nature"
    if col_at not in df_fuites.columns or col_nat not in df_fuites.columns:
        return pd.DataFrame(columns=["Atelier", "Total Avis Fuites"])

    ct = pd.crosstab(df_fuites[col_at], df_fuites[col_nat])
    if ct.empty:
        return pd.DataFrame(columns=["Atelier", "Total Avis Fuites"])

    col_totals = ct.sum(axis=0).sort_values(ascending=False)
    ct = ct[col_totals.index]
    ct["Total Avis Fuites"] = ct.sum(axis=1)
    ct = ct.sort_values(by="Total Avis Fuites", ascending=False)

    df_res = ct.reset_index().rename(columns={col_at: "Atelier"})

    tot_row = {"Atelier": "TOTAL GÉNÉRAL"}
    for col in df_res.columns:
        if col != "Atelier":
            tot_row[col] = int(df_res[col].sum())

    df_res = pd.concat([df_res, pd.DataFrame([tot_row])], ignore_index=True)
    return df_res


def _html_tableau_avis_fuites(df_tab):
    if df_tab.empty:
        return '<div style="padding:10px;color:#64748B;">Aucun avis fuite à afficher.</div>'
    cols = list(df_tab.columns)
    h = '<div style="overflow-x:auto;margin-top:8px;"><table class="tw omt" style="width:100%;border-collapse:collapse;font-size:12px;"><thead><tr style="background:#1e3a5f;color:#ffffff;">'
    for c in cols:
        align = "left" if c == "Atelier" else "center"
        h += f'<th style="text-align:{align};padding:9px 12px;font-size:11px;font-weight:700;white-space:nowrap;">{c}</th>'
    h += '</tr></thead><tbody>'
    for idx, r in df_tab.iterrows():
        is_total = (r["Atelier"] == "TOTAL GÉNÉRAL")
        row_style = "font-weight:800;background:#e2e8f0;border-top:2px solid #94a3b8;" if is_total else ("background:#f8fafc;" if idx % 2 == 1 else "")
        h += f'<tr style="{row_style}">'
        for c in cols:
            val = r[c]
            align = "left" if c == "Atelier" else "center"
            cell_style = f"text-align:{align};padding:7px 12px;border-bottom:1px solid #e2e8f0;"
            if is_total:
                cell_style += "color:#1e3a5f;font-weight:800;" if c == "Atelier" else ("color:#0f172a;font-weight:900;background:#cbd5e1;" if c == "Total Avis Fuites" else "font-weight:800;")
            else:
                if c == "Atelier":
                    cell_style += "font-weight:700;color:#1e3a5f;"
                elif c == "Total Avis Fuites":
                    cell_style += "font-weight:800;color:#0f172a;background:#f1f5f9;"
                elif isinstance(val, (int, float, np.integer)) and val > 0:
                    cell_style += "font-weight:600;color:#0369a1;"
                else:
                    cell_style += "color:#94a3b8;"
            h += f'<td style="{cell_style}">{val}</td>'
        h += '</tr>'
    h += '</tbody></table></div>'
    return h


def _section_analyse_avis_fuites(df_fuites, buffers, date_str=""):
    st.markdown("### 💧 Analyse des avis types fuites")
    if df_fuites is None or df_fuites.empty:
        st.info("Aucun avis fuite disponible sur la période et l'atelier sélectionnés.")
        return

    total_fuites = len(df_fuites)
    fuites_clot = int((df_fuites["_StatutCat"] == "Clôturé").sum())
    pct_clot = (fuites_clot / total_fuites * 100) if total_fuites > 0 else 0

    fuites_encours = int((df_fuites["_StatutCat"] == "En cours").sum())
    pct_encours = (fuites_encours / total_fuites * 100) if total_fuites > 0 else 0

    fuites_rejetes = int((df_fuites["_StatutCat"] == "Rejeté").sum())
    pct_rejetes = (fuites_rejetes / total_fuites * 100) if total_fuites > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    _carte(c1, "Total Avis Fuites", f"{total_fuites:,}".replace(",", " "), NAVY, "avis fuites enregistrés")
    _carte(c2, "Avis Fuites Clôturés", f"{fuites_clot:,}".replace(",", " "), GREEN, f"<b style='font-size:13px;color:#059669;'>{pct_clot:.1f}%</b> du total")
    _carte(c3, "Avis Fuites En cours", f"{fuites_encours:,}".replace(",", " "), SKY, f"<b style='font-size:13px;color:#0284C7;'>{pct_encours:.1f}%</b> du total")
    _carte(c4, "Avis Fuites Rejetés", f"{fuites_rejetes:,}".replace(",", " "), "#EF4444", f"<b style='font-size:13px;color:#DC2626;'>{pct_rejetes:.1f}%</b> du total")

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    g1, g2 = st.columns([2, 3])
    if buffers.get("pie_fuites_statut"):
        g1.image(buffers["pie_fuites_statut"], use_container_width=True)
    if buffers.get("bar_fuites_atelier"):
        g2.image(buffers["bar_fuites_atelier"], use_container_width=True)

    st.markdown("---")
    st.markdown("#### 🔍 Analyse & Répartition par Type d'Avis Fuites")

    g3, g4 = st.columns([3, 3])
    if buffers.get("bar_fuites_type"):
        g3.image(buffers["bar_fuites_type"], use_container_width=True)
    if buffers.get("bar_statuts_fuites_atelier"):
        g4.image(buffers["bar_statuts_fuites_atelier"], use_container_width=True)

    st.markdown("##### 📊 Nombre des avis fuites par atelier et par type")
    tab_croise = _tableau_avis_fuites_par_atelier_et_type(df_fuites)
    if not tab_croise.empty:
        st.markdown(_html_tableau_avis_fuites(tab_croise), unsafe_allow_html=True)
    else:
        st.info("Aucun avis fuite à afficher.")

    _bouton_excel_section(df_fuites, "fuites", "Analyse fuites", date_str)


def _libelle_periode(sel_annee, sel_mois_lbl, sel_sem, sel_atelier="Tous"):
    parties = []
    if sel_atelier != "Tous":
        parties.append(f"atelier {sel_atelier}")
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
    for i, item in enumerate(sections_stats):
        titre, cle, stats, chart_keys, commentaire = item
        story.append(_entete(f"Section {i+1}/{n_sec} — {titre} · {nb_postes} poste(s) · "
                              f"Extraction du {date_str}"))
        story.append(Spacer(1, 8))
        if stats:
            story.append(_cartes(stats))
            story.append(Spacer(1, 10))
        # AJOUTÉ : commentaire/conclusion auto-généré, sous les cartes
        if commentaire:
            story.append(Paragraph(commentaire, ParagraphStyle(
                name=f"comm{i}", fontSize=9, textColor=colors.HexColor("#334155"),
                leading=12, spaceAfter=8, fontName="Helvetica-Oblique")))
        # AJOUTÉ : chart_keys explicite (au lieu de bar_{cle} + 4 pies fixes)
        # permet d'inclure TOUS les graphiques réellement présents pour la
        # section, y compris "Analyse des avis fuites" qui a une structure
        # de graphiques différente (4 clés propres, pas de bar_{cle}).
        bars_a_afficher = [k for k in chart_keys if buffers.get(k) and k.startswith("bar_")]
        if not bars_a_afficher and buffers.get(f"bar_{cle}"):
            bars_a_afficher = [f"bar_{cle}"]
        for bk in bars_a_afficher:
            bar = buffers.get(bk)
            if bar:
                t = Table([[_img(bar, 14 * cm, hauteur_max_cm=7)]], colWidths=[LARGEUR])
                t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
                story.append(t)
                story.append(Spacer(1, 8))
        pie_keys = [k for k in chart_keys if buffers.get(k) and not k.startswith("bar_")]
        pies = [buffers[k] for k in pie_keys]
        if pies:
            # Sur 2 lignes de 2 si plus de 2 camemberts, pour rester lisible
            for debut in range(0, len(pies), 2):
                lot = pies[debut:debut + 2]
                imgs = [_img(p, 9.5 * cm, hauteur_max_cm=6.0) for p in lot]
                t = Table([imgs], colWidths=[LARGEUR / len(imgs)] * len(imgs))
                t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
                story.append(t)
                story.append(Spacer(1, 6))
        if i < n_sec - 1:
            story.append(PageBreak())

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=1.2 * cm,
                             bottomMargin=1.2 * cm, leftMargin=1.6 * cm, rightMargin=1.6 * cm)
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def render_suivi_hse_tab(dfp, avf, vp, date_str=""):
    st.markdown("## 🦺 Suivi HSE")
    st.caption("Avis d'inspection et HSE, ordres de travail sécurité, OMS et contrôle structure.")

    if dfp is None or dfp.empty:
        st.warning("⚠️ Aucune donnée disponible. Chargez d'abord ot.xlsx / avis.xlsx.")
        return

    col_p_ot = next((c for c in dfp.columns if "poste" in str(c).lower() and "trav" in str(c).lower()), "Poste travail princ.")
    col_p_av = next((c for c in avf.columns if "poste" in str(c).lower() and "trav" in str(c).lower()), "Poste travail princ.") if avf is not None and not avf.empty else None

    if col_p_ot in dfp.columns:
        dfp = dfp[~dfp[col_p_ot].astype(str).str.contains("GCMC|GCFD", case=False, na=False)].copy()
    if col_p_av and col_p_av in avf.columns:
        avf = avf[~avf[col_p_av].astype(str).str.contains("GCMC|GCFD", case=False, na=False)].copy()
    vp = [p for p in vp if not re.search("GCMC|GCFD", str(p), re.IGNORECASE)]

    ot = _ajouter_periode(dfp.copy(), "Créé le")
    avis = _ajouter_periode(avf.copy(), "Créé le") if avf is not None and not avf.empty else pd.DataFrame()

    st.markdown("#### 🎛️ Filtres")
    st.caption("Ces filtres s'appliquent EN PLUS des filtres division / poste / période du panneau latéral.")
    sources = [s for s in (ot.get("_Année"), avis.get("_Année")) if s is not None]
    annees = sorted({int(a) for a in pd.concat(sources).dropna().unique()}) if sources else []
    sources_s = [s for s in (ot.get("_Semaine"), avis.get("_Semaine")) if s is not None]
    semaines = sorted({s for s in pd.concat(sources_s).dropna().unique()}) if sources_s else []

    postes_ot = dfp[col_p_ot].dropna().unique() if col_p_ot in dfp.columns else []
    postes_av = avf[col_p_av].dropna().unique() if (col_p_av and col_p_av in avf.columns) else []
    tous_ateliers = sorted({
        _regrouper_atelier(p) for p in set(postes_ot) | set(postes_av)
        if str(p).strip() and str(p).lower() != "nan" and not re.search("GCMC|GCFD", str(p), re.IGNORECASE)
    })

    f1, f2, f3, f4 = st.columns(4)
    sel_annee = f1.selectbox("Année", ["Toutes"] + [str(a) for a in annees], key="hse_annee")
    sel_mois_lbl = f2.selectbox("Mois", ["Tous"] + MOIS_FR, key="hse_mois")
    sel_mois = "Tous" if sel_mois_lbl == "Tous" else str(MOIS_FR.index(sel_mois_lbl) + 1)
    sel_sem = f3.selectbox("Semaine", ["Toutes"] + list(semaines), key="hse_sem")
    sel_atelier = f4.selectbox("Atelier", ["Tous"] + tous_ateliers, key="hse_atelier")

    # ── Filtre dynamique des sections a afficher (demande explicite) ──
    # Par defaut, seules 2 sections sont affichees (au lieu des 7) pour
    # alleger la page — l'utilisateur choisit celles qu'il veut voir.
    TOUTES_SECTIONS = [
        "Avis Inspection", "Analyse des avis fuites", "Avis HSE",
        "OT Sécurité", "OMS Thermographie", "OMS Vibration", "Contrôle structure",
    ]
    sections_actives = st.multiselect(
        "🧭 Sections à afficher",
        TOUTES_SECTIONS,
        default=["Avis Inspection", "Avis HSE"],
        key="hse_sections_actives",
    )

    res = _calculer_sections_hse(dfp, avf, tuple(vp), date_str, sel_annee, sel_mois, sel_sem, sel_atelier)
    buffers = res["buffers"]

    if "Avis Inspection" in sections_actives:
        st.markdown("---")
        _section_avis(res["avis_zi"], "Avis Inspection", "🔍", BLUE, buffers, "zi", date_str)
    if "Analyse des avis fuites" in sections_actives:
        st.markdown("---")
        _section_analyse_avis_fuites(res["df_fuites"], buffers, date_str)
    if "Avis HSE" in sections_actives:
        st.markdown("---")
        _section_avis(res["avis_zh"], "Avis HSE", "🦺", TEAL, buffers, "zh", date_str)
    if "OT Sécurité" in sections_actives:
        st.markdown("---")
        _section_ot(res["ot_securite"], "OT Sécurité", "🛡️", EMERAUDE, buffers, "secu", date_str)
    if "OMS Thermographie" in sections_actives:
        st.markdown("---")
        _section_ot(res["ot_oms_therm"], "OMS Thermographie", "🌡️", BLUE, buffers, "therm", date_str)
    if "OMS Vibration" in sections_actives:
        st.markdown("---")
        _section_ot(res["ot_oms_vib"], "OMS Vibration", "📳", TEAL, buffers, "vib", date_str)
    if "Contrôle structure" in sections_actives:
        st.markdown("---")
        _section_ot(res["ot_structure"], "Contrôle structure", "🏗️", CYAN, buffers, "struct", date_str)

    st.markdown("---")
    st.markdown("### 📎 Documents joints par poste de travail")
    tab_docs, msg_docs = _charger_documents_joints(tuple(vp))
    if tab_docs is None:
        st.warning(
            f"⚠️ {msg_docs}\n\nLe fichier doit contenir une colonne de postes "
            f"(« Poste travail princ. ») et une colonne de comptage "
            f"(« Nombre documents joints »), et être committé sur GitHub."
        )
    elif tab_docs.empty:
        st.warning(f"⚠️ {msg_docs}")
    else:
        renseignes = int(tab_docs["Nombre documents joints"].notna().sum())
        st.caption(
            f"Source : `documents_joints.xlsx` — {msg_docs} "
            f"{renseignes} poste(s) avec un nombre renseigné. "
            f"Complétez la colonne dans le fichier Excel puis committez-le : "
            f"le tableau se mettra à jour automatiquement."
        )
        st.dataframe(tab_docs, use_container_width=True, hide_index=True, height=320)

    st.markdown("---")
    st.markdown("#### 📄 Rapport de synthèse")
    libelle = _libelle_periode(sel_annee, sel_mois_lbl, sel_sem, sel_atelier)
    st.caption(f"Titre du rapport : « Suivi HSE{libelle} »" if libelle
               else "Aucun filtre de période actif — titre : « Suivi HSE ».")

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

    def _stats_fuites(df, couleur):
        if df is None or df.empty:
            return []
        n = len(df)
        cl = int((df["_StatutCat"] == "Clôturé").sum())
        en = int((df["_StatutCat"] == "En cours").sum())
        rj = int((df["_StatutCat"] == "Rejeté").sum())
        return [("Total Avis Fuites", n, couleur, "avis"),
                ("Clôturés", cl, GREEN, f"{cl/n*100:.0f}%"),
                ("En cours", en, SKY, f"{en/n*100:.0f}%"),
                ("Rejetés", rj, "#EF4444", f"{rj/n*100:.0f}%")]

    def _commentaire_avis(titre, stats):
        """AJOUTÉ (demande explicite) : commentaire/conclusion auto-généré
        à partir des statistiques calculées — pas de texte fixe, le
        contenu s'adapte aux vrais chiffres de la section."""
        if not stats:
            return ""
        d = {lbl: val for lbl, val, *_ in stats}
        total = d.get("Total") or d.get("Total OT") or d.get("Total Avis Fuites") or 0
        if total == 0:
            return f"Aucune donnée disponible pour « {titre} » sur le périmètre et la période sélectionnés."
        if "Approuvés" in d:
            pct_appr = d["Approuvés"] / total * 100
            pct_rej = d.get("Rejetés", 0) / total * 100
            appreciation = "un taux d'approbation satisfaisant" if pct_appr >= 80 else "un taux d'approbation à surveiller"
            return (f"Sur {total} avis « {titre} », {appreciation} est observé ({pct_appr:.0f}% approuvés). "
                    f"{pct_rej:.0f}% des avis ont été rejetés, à analyser si ce taux progresse.")
        if "Clôturés" in d:
            pct_clot = d["Clôturés"] / total * 100
            appreciation = "un bon niveau de clôture" if pct_clot >= 70 else "un retard de clôture à surveiller"
            return (f"Sur {total} ordres « {titre} », {appreciation} est constaté ({pct_clot:.0f}% clôturés, "
                    f"{100 - pct_clot:.0f}% encore en cours).")
        return f"{total} élément(s) enregistré(s) pour « {titre} »."

    TOUTES_SECTIONS_RAPPORT = [
        "Avis Inspection", "Analyse des avis fuites", "Avis HSE",
        "OT Sécurité", "OMS Thermographie", "OMS Vibration", "Contrôle structure",
    ]
    sections_rapport_choisies = st.multiselect(
        "📑 Sections à inclure dans le rapport PDF",
        TOUTES_SECTIONS_RAPPORT,
        default=TOUTES_SECTIONS_RAPPORT,
        key="hse_sections_rapport",
    )

    if st.button("🖨️ Générer le rapport PDF", type="primary", use_container_width=True):
        try:
            # AJOUTÉ : chaque section liste EXPLICITEMENT TOUS ses
            # graphiques (chart_keys) — "Analyse des avis fuites" a sa
            # propre structure de 4 graphiques (auparavant absente du
            # PDF), et chaque section porte un commentaire auto-généré.
            candidats = []
            if "Avis Inspection" in sections_rapport_choisies:
                st_ = _stats_avis(res["avis_zi"], BLUE)
                candidats.append(("Avis Inspection", "zi", st_,
                                   ["bar_zi", "pie_appr_zi", "pie_ot_zi"],
                                   _commentaire_avis("Avis Inspection", st_)))
            if "Analyse des avis fuites" in sections_rapport_choisies:
                st_ = _stats_fuites(res["df_fuites"], NAVY)
                candidats.append(("Analyse des avis fuites", "fuites", st_,
                                   ["pie_fuites_statut", "bar_fuites_atelier",
                                    "bar_fuites_type", "bar_statuts_fuites_atelier"],
                                   _commentaire_avis("Analyse des avis fuites", st_)))
            if "Avis HSE" in sections_rapport_choisies:
                st_ = _stats_avis(res["avis_zh"], TEAL)
                candidats.append(("Avis HSE", "zh", st_,
                                   ["bar_zh", "pie_appr_zh", "pie_ot_zh"],
                                   _commentaire_avis("Avis HSE", st_)))
            if "OT Sécurité" in sections_rapport_choisies:
                st_ = _stats_ot(res["ot_securite"], EMERAUDE)
                candidats.append(("OT Sécurité (type 320)", "secu", st_,
                                   ["bar_secu", "pie_statut_secu", "pie_cat_secu"],
                                   _commentaire_avis("OT Sécurité", st_)))
            if "OMS Thermographie" in sections_rapport_choisies:
                st_ = _stats_ot(res["ot_oms_therm"], BLUE)
                candidats.append(("OMS Thermographie", "therm", st_,
                                   ["bar_therm", "pie_statut_therm", "pie_cat_therm"],
                                   _commentaire_avis("OMS Thermographie", st_)))
            if "OMS Vibration" in sections_rapport_choisies:
                st_ = _stats_ot(res["ot_oms_vib"], TEAL)
                candidats.append(("OMS Vibration", "vib", st_,
                                   ["bar_vib", "pie_statut_vib", "pie_cat_vib"],
                                   _commentaire_avis("OMS Vibration", st_)))
            if "Contrôle structure" in sections_rapport_choisies:
                st_ = _stats_ot(res["ot_structure"], CYAN)
                candidats.append(("Contrôle structure", "struct", st_,
                                   ["bar_struct", "pie_statut_struct", "pie_cat_struct"],
                                   _commentaire_avis("Contrôle structure", st_)))

            sections = [c for c in candidats if c[2] or any(buffers.get(k) for k in c[3])]
            if not sections:
                st.warning("⚠️ Aucune section sélectionnée ne contient de données à inclure dans le rapport.")
            else:
                pdf = _generer_rapport_pdf(buffers, sections, libelle, date_str, len(vp))
                st.download_button("⬇️ Télécharger le rapport HSE (PDF)", data=pdf,
                                    file_name=f"rapport_HSE_{str(date_str).replace('/', '-')}.pdf",
                                    mime="application/pdf", use_container_width=True)
                st.success(f"✅ Rapport généré avec {len(sections)} section(s) — cliquez sur le bouton de téléchargement ci-dessus.")
        except Exception as e:
            st.error(f"❌ Erreur lors de la génération : {e}")
