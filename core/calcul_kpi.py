# -*- coding: utf-8 -*-
"""
Module de calcul des KPIs (Indicateurs Clés de Performance).

Calcule l'ensemble des indicateurs pour chaque poste de travail :
- Taux de réalisation correctif
- Âge des OT (préparation, planification, exécution)
- Performance (Graissage, Inspection, Systématiques)
- Taux d'approbation des avis
- Backlog caractérisé (préparation, planification)
- OT confirmés, OT coûts égaux
"""

import numpy as np
import pandas as pd

from core.constants import QK, PK, CIBLE, LOWER_BETTER

# ─── Constantes ──────────────────────────────────────────────────────────────

TW_PREV = [350, 290, 300, 310, 360]
CRPR_KW = ['ATPD', 'ATMR', 'ATRS', 'ATMO', 'ATER']
ATPL_KW = ['ATEI', 'ATAL', 'ATAS', 'AGAR', 'ATHS']

STATUT_CLOT    = ["CLOT", "TCLO"]
TRANCHES_AGE   = ["<1 mois", "1 mois < <3 mois", ">3 mois"]
COL_AGE_DEFAUT = "Inconnu"


# ─── Fonctions utilitaires ───────────────────────────────────────────────────

def ckpi(n, d, sz=100):
    """Calcul d'un taux : (n / d) * 100, avec valeur par défaut sz si d == 0."""
    return np.where(d == 0, sz, (n / d) * 100)


def ckpi_inv(n, d, sz=100):
    """100 - (n/d*100) : pour tranches 1-3m et >3m."""
    return np.where(d == 0, sz, 100.0 - (n / d) * 100)


def cpiv(df, filt, col, posts):
    """Pivot table standard : index=Poste, columns=col, count Ordre."""
    return pd.pivot_table(
        df[filt],
        index="Poste travail princ.",
        columns=col,
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(posts, fill_value=0)


def _ensure_columns(pv, cols, fill=0):
    """Garantit la présence de colonnes dans un pivot, les ajoute si absentes."""
    for col in cols:
        if col not in pv.columns:
            pv[col] = fill
    return pv


def _age_kpis(df, col_age, tranche_1m, tranche_1m3m, tranche_3m):
    """Calcule les KPIs d'âge pour une catégorie donnée."""
    total_ots = df.sum(axis=1)
    
    # Use ckpi_inv for '>3 mois' as it's '100 - (caractérisé / total)'
    kpis_3m = ckpi_inv(df[tranche_3m], total_ots)
    # For '<1 mois' and '1 mois < <3 mois', it's a direct percentage
    kpis_1m = ckpi(df[tranche_1m], total_ots)
    kpis_1m3m = ckpi(df[tranche_1m3m], total_ots)

    return {
        col_age + " <1 mois": kpis_1m,
        col_age + " >3 mois": kpis_3m,
        col_age + " 1mois< <3mois": kpis_1m3m,
    }


def build_statut_pivot(df, filt, posts, col_name="Statut OT"):
    """
    PLACEHOLDER: Construit une table pivot pour les statuts.
    Similaire à cpiv, mais potentiellement avec des spécificités pour les statuts.
    À adapter selon l'usage réel dans backlog_widgets.py.
    """
    return pd.pivot_table(
        df[filt],
        index="Poste travail princ.",
        columns=col_name,
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(posts, fill_value=0)

def get_text_col(df, col_name, row_idx=0, default=""):
    """
    PLACEHOLDER: Récupère une valeur textuelle d'une colonne.
    À adapter selon l'usage réel dans backlog_widgets.py.
    """
    if col_name in df.columns and row_idx < len(df):
        return str(df.iloc[row_idx][col_name])
    return default


def gscore(val, cible, lower_is_better=False):
    """Calcule un score de performance entre 0 et 100."""
    if cible == 0:  # Eviter la division par zéro
        return 0

    if lower_is_better:
        if val >= cible: # Si la valeur est pire ou égale à la cible
            return 0 # Score = 0 (très mauvais)
        else:
            # Inversement proportionnel: plus c'est bas, mieux c'est.
            # Max 100 si val est 0, 0 si val est cible
            return max(0, 100 * (1 - val / cible)) # Assure un score non negatif
    else:
        if val <= cible: # Si la valeur est pire ou égale à la cible
            return max(0, 100 * (val / cible)) # Score = 0 si val est 0, 100 si val est cible
        else:
            return 100 # Score maximum si la valeur depasse la cible


def is_lb(kpi_name):
    """Indique si un KPI doit être interprété comme 'plus bas = mieux'."""
    return kpi_name in LOWER_BETTER


def calc_kpis(dfp: pd.DataFrame, avf: pd.DataFrame, apm: list, ano_map: dict) -> dict:
    """Calcule l'ensemble des KPIs pour tous les postes de travail."""
    res = {}

    # ── Taux de réalisation correctif ──────────────────────────────────
    n_cor = cpiv(dfp, dfp["is_correctif"], "Statut système", apm)
    n_cor = _ensure_columns(n_cor, STATUT_CLOT + ["LANC"])
    res["taux_realisation_correctif"] = ckpi(n_cor["CLOT"] + n_cor["TCLO"], n_cor["CLOT"] + n_cor["TCLO"] + n_cor["LANC"])

    # ── KPIs d'âge ─────────────────────────────────────────────────────
    pv_prep = cpiv(dfp, ~dfp["is_correctif"], "ap", apm)
    pv_plan = cpiv(dfp, (~dfp["is_correctif"]) & (dfp["Statut OT"] == "LANC"), "alp", apm)
    pv_exec = cpiv(dfp, (~dfp["is_correctif"]) & (dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 1), "aex", apm)

    pv_prep = _ensure_columns(pv_prep, TRANCHES_AGE + [COL_AGE_DEFAUT])
    pv_plan = _ensure_columns(pv_plan, TRANCHES_AGE + [COL_AGE_DEFAUT])
    pv_exec = _ensure_columns(pv_exec, TRANCHES_AGE + [COL_AGE_DEFAUT])

    kpis_prep = _age_kpis(pv_prep, "OT préparation", "<1 mois", "1 mois < <3 mois", ">3 mois")
    kpis_plan = _age_kpis(pv_plan, "OT planification", "<1 mois", "1 mois < <3 mois", ">3 mois")
    kpis_exec = _age_kpis(pv_exec, "OT exécution", "<1 mois", "1 mois < <3 mois", ">3 mois")


    # ── Performance Graissage/Inspection/Systématiques ─────────────────
    g_df = pd.pivot_table(
        dfp[
            (dfp["_tw_num"] == TW_PREV[0]) &
            (~dfp["Statut OT"].isin(["CLOT","TCLO"])) &
            (dfp["Contient SOPL"] == 1)
        ],
        index="Poste travail princ.",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(apm, fill_value=0)
    g_df.columns = ["Performance Graissage"]

    ins_df = pd.pivot_table(
        dfp[
            (dfp["_tw_num"].isin(TW_PREV[1:4])) &
            (~dfp["Statut OT"].isin(["CLOT","TCLO"])) &
            (dfp["Contient SOPL"] == 1)
        ],
        index="Poste travail princ.",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(apm, fill_value=0)
    ins_df.columns = ["Performance Inspection"]

    sys_df = pd.pivot_table(
        dfp[
            (dfp["_tw_num"] == TW_PREV[4]) &
            (~dfp["Statut OT"].isin(["CLOT","TCLO"])) &
            (dfp["Contient SOPL"] == 1)
        ],
        index="Poste travail princ.",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(apm, fill_value=0)
    sys_df.columns = ["Performance Systématiques"]


    # ── Taux d'approbation des Avis ────────────────────────────────────
    tca = pd.pivot_table(
        avf,
        index="Poste travail princ.",
        columns="Statut utilisateur",
        values="Avis",
        aggfunc="count",
        fill_value=0,
    ).reindex(apm, fill_value=0)
    tca = _ensure_columns(tca, ["APRQ", "NOAV"])
    tca["Taux d'approbation des Avis"] = ckpi(tca["APRQ"], tca["APRQ"] + tca["NOAV"])


    # ── OT LANC ESTIME : charge estimee > 0 ────────────────────────────
    la = pd.pivot_table(
        dfp[(dfp["Statut OT"] == "LANC") & (dfp["OT LANC ESTIME"] == "OUI")],
        index="Poste travail princ.",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(apm, fill_value=0)
    la.columns = ["OT LANC ESTIME"]


    # ── Backlog préparation caractérisé ────────────────────────────────
    pc = pd.pivot_table(
        dfp[
            (dfp["Statut OT"] == "CRÉÉ") &
            (~dfp["is_correctif"]) &
            (dfp["Backlog preparation"] == "CARACTERISE")
        ],
        index="Poste travail princ.",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(apm, fill_value=0)
    pc.columns = ["Backlog préparation caractérisé"]

    # --- Start of new code for Characterization Rate ---
    # Retrieve anomaly counts for "Backlog préparation caractérisé (Anomalie)" from ano_map
    # Use .get() with a default Series of zeros to handle cases where the anomaly might not exist in ano_map
    anomaly_bpc_counts = ano_map.get("Backlog préparation caractérisé (Anomalie)", pd.Series(0, index=apm))
    anomaly_bpc_counts = anomaly_bpc_counts.reindex(apm, fill_value=0) # Ensure full alignment

    # Calculate the total backlog for this category (characterized + non-characterized)
    total_backlog_prep = pc["Backlog préparation caractérisé"] + anomaly_bpc_counts

    # Calculate the Characterization Rate
    # Handle division by zero: if total_backlog_prep is 0, rate is 0%
    characterization_rate = np.where(
        total_backlog_prep == 0,
        0.0,
        (pc["Backlog préparation caractérisé"] / total_backlog_prep) * 100
    )
    # --- End of new code for Characterization Rate ---


    # ── Backlog planification caractérisé ──────────────────────────────
    plc = pd.pivot_table(
        dfp[
            (~dfp["is_correctif"]) &
            (dfp["Statut OT"] == "LANC") &
            (dfp["Contient SOPL"] == 0) &
            (dfp["Backlog planification"] == "CARACTERISE")
        ],
        index="Poste travail princ.",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(apm, fill_value=0)
    plc.columns = ["Backlog planification caractérisé"]


    # ── OT CONFIME : OT cloturés mais non confirmés ────────────────────
    pv_conf = pd.pivot_table(
        dfp[dfp["OT CONFIME"] == "OUI"],
        index="Poste travail princ.",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(apm, fill_value=0)
    pv_conf.columns = ["OT CONFIME"]


    # ── OT_COR_EGAL : anomalies de coûts ───────────────────────────────
    res["ot_cor_egal"] = {
        "OT_COR_EGAL": pd.pivot_table(
            dfp[dfp["OT_COR_EGAL"] == "OUI"],
            index="Poste travail princ.",
            values="Ordre",
            aggfunc="count",
            fill_value=0,
        ).reindex(apm, fill_value=0)
    }
    res["ot_cor_egal"]["OT_COR_EGAL"].columns = ["OT_COR_EGAL"]


    # ── OT Fiabilité et Total Avis de Panne ────────────────────────────
    # Calcul de OT Fiabilité (nombre d'OT correctifs qui sont CLOTURES et CONFIRMES)
    fiab_s = pd.pivot_table(
        dfp[
            (dfp["is_correctif"]) &
            (dfp["Statut OT"].isin(STATUT_CLOT)) &
            (dfp["Statut système"].str.contains("CONF", na=False))
        ],
        index="Poste travail princ.",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(apm, fill_value=0)
    fiab_s.columns = ["OT Fiabilité"]

    # Calcul de Total Avis de Panne (nombre d'avis de type panne)
    avpan_s = pd.pivot_table(
        avf[avf["Type d'avis"] == "Z1"],
        index="Poste travail princ.",
        values="Avis",
        aggfunc="count",
        fill_value=0,
    ).reindex(apm, fill_value=0)
    avpan_s.columns = ["Total Avis de Panne"]


    # ── Consolidation finale des KPIs ──────────────────────────────────
    kpis_df = pd.DataFrame({
        "Taux de réalisation correctif":     res["taux_realisation_correctif"],
        # Âge Préparation
        "OT préparation <1 mois":          kpis_prep["OT préparation <1 mois"],
        "OT préparation >3 mois":          kpis_prep["OT préparation >3 mois"],
        "OT préparation 1mois< <3mois":    kpis_prep["OT préparation 1mois< <3mois"],
        # Âge Planification
        "OT planification <1 mois":          kpis_plan["OT planification <1 mois"],
        "OT planification >3 mois":          kpis_plan["OT planification >3 mois"],
        "OT planification 1mois< <3mois":    kpis_plan["OT planification 1mois< <3mois"],
        # Âge Exécution
        "OT exécution <1 mois":              kpis_exec["OT exécution <1 mois"],
        "OT exécution >3 mois":              kpis_exec["OT exécution >3 mois"],
        "OT exécution 1mois< <3mois":        kpis_exec["OT exécution 1mois< <3mois"],
        # Performance
        "Performance Graissage":             g_df["Performance Graissage"],
        "Performance Inspection":            ins_df["Performance Inspection"],
        "Performance Systématiques":         sys_df["Performance Systématiques"],
        # Avis
        "Taux d'approbation des Avis":       tca["Taux d'approbation des Avis"],
        # Backlog / Estimation
        "OT LANC ESTIME":                    la["OT LANC ESTIME"],
        "Backlog préparation caractérisé":   pc["Backlog préparation caractérisé"],
        "Backlog planification caractérisé": plc["Backlog planification caractérisé"],
        # Add the new 'Taux de caractérisation' KPI here
        "Taux de caractérisation préparation": characterization_rate,
        # Qualité
        "OT CONFIME":                        pv_conf["OT CONFIME"],
        "OT_COR_EGAL":                       res["ot_cor_egal"]["OT_COR_EGAL"],
        "OT Fiabilité":                      fiab_s,
        "Total Avis de Panne":               avpan_s,
    })

    # Stocker les pivots bruts pour les graphiques backlog
    res['pv_prep'] = pv_prep
    res['pv_plan'] = pv_plan
    res['pv_exec'] = pv_exec

    return res


# ─── NOTE POUR constants.py ──────────────────────────────────────────────────
# Avec la nouvelle logique 100-val, mettre à jour dans constants.py :
#
# CIBLE = {
#     ...
#     "OT préparation <1 mois":         80,
#     "OT préparation 1mois< <3mois":   85,
#     "OT préparation >3 mois":         95,
#     "OT planification <1 mois":       80,
#     "OT planification 1mois< <3mois": 85,
#     "OT planification >3 mois":       95,
#     "OT exécution <1 mois":           80,
#     "OT exécution 1mois< <3mois":     85,
#     "OT exécution >3 mois":           95,
#     ...
# }
#
# LOWER_BETTER doit être VIDE pour ces KPIs car
# la logique 100-val les rend tous "plus haut = mieux"
# ─────────────────────────────────────────────────────────────────────────────
