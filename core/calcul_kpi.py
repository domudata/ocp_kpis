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
    for c in cols:
        if c not in pv.columns:
            pv[c] = fill
    return pv


def get_text_col(df):
    """Détecte automatiquement la colonne contenant le texte/désignation."""
    candidates = [
        "Désignation", "Designation", "Désignation OT",
        "Texte ordre", "Texte", "Description",
        "Libellé", "Libelle",
    ]
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        if df[c].dtype == 'object' and any(
            kw in str(c).lower() for kw in ['sign', 'text', 'desc', 'libell']
        ):
            return c
    return None


def build_statut_pivot(df_sub, posts):
    """Pivot table des statuts OT (CRÉÉ, LANC, CLOT, TCLO) par poste."""
    statuts = ["CRÉÉ", "LANC", "CLOT", "TCLO"]
    if df_sub.empty:
        return pd.DataFrame(
            index=posts, columns=statuts + ["Total"]
        ).fillna(0).astype(int)
    piv = pd.pivot_table(
        df_sub,
        index="Poste travail princ.",
        columns="Statut OT",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    )
    for s in statuts:
        if s not in piv.columns:
            piv[s] = 0
    piv["Total"] = piv[statuts].sum(axis=1)
    return piv.reindex(posts, fill_value=0).fillna(0).astype(int)


def gscore(k, a, t):
    """
    Score binaire par KPI :
    - KPI normal (plus haut = mieux)      : 1 si a >= t, sinon 0
    - KPI LOWER_BETTER (plus bas = mieux) : 1 si a <= t, sinon 0
    """
    if pd.isna(a) or pd.isna(t):
        return 0
    if k in LOWER_BETTER:
        return 1 if a <= t else 0
    return 1 if a >= t else 0


def is_lb(k):
    """Indique si le KPI k est de type 'plus bas = mieux'."""
    return k in LOWER_BETTER


# ─── Âge des OT ──────────────────────────────────────────────────────────────

def _age_kpis(df, filt, col_age, posts, prefix):
    """
    Calcule les taux bruts d'OT dans chaque tranche d'âge.

    - <1m  : N_inf1m / Total * 100   (maximiser, cible >= 80%)
    - 1-3m : N_1-3m  / Total * 100   (minimiser, cible <= 15%)
    - >3m  : N_sup3m / Total * 100   (minimiser, cible <= 5%)
    """
    pv = cpiv(df, filt, col_age, posts)
    pv = _ensure_columns(pv, TRANCHES_AGE + [COL_AGE_DEFAUT])

    # Total = somme des 3 tranches SEULEMENT (hors Inconnu)
    # → garantit que <1m + 1-3m + >3m = 100% exactement
    pv["Total"] = pv[TRANCHES_AGE].sum(axis=1)

    key_inf = f"OT {prefix} <1 mois"
    key_mid = f"OT {prefix} 1mois< <3mois"
    key_sup = f"OT {prefix} >3 mois"

    kpis = {}
    for idx in pv.index:
        tot = pv.loc[idx, "Total"]
        if tot == 0:
            # Base vide = aucun OT en retard → <1m parfait, 1-3m et >3m à 0
            kpis.setdefault(key_inf, {})[idx] = 100.0
            kpis.setdefault(key_mid, {})[idx] = 0.0
            kpis.setdefault(key_sup, {})[idx] = 0.0
        else:
            kpis.setdefault(key_inf, {})[idx] = round(pv.loc[idx, "<1 mois"] / tot * 100, 2)
            kpis.setdefault(key_mid, {})[idx] = round(pv.loc[idx, "1 mois < <3 mois"] / tot * 100, 2)
            kpis.setdefault(key_sup, {})[idx] = round(pv.loc[idx, ">3 mois"] / tot * 100, 2)

    result = {}
    for k, d in kpis.items():
        default = 100.0 if "<1 mois" in k else 0.0
        result[k] = pd.Series(d).reindex(posts, fill_value=default)

    return result, pv


# ─── KPIs de performance (Graissage / Inspection / Systématiques) ────────────

def _perf_kpi(df, posts, tw_nums, now_ts, label, require_sopl=True):
    """
    Calcule un KPI de performance préventive.

    Numérateur   : OT clôturés (CLOT/TCLO) sur les TW donnés.
    Dénominateur : OT contenant SOPL (si require_sopl) sur les TW donnés,
                   dont la date planifiée <= now_ts.
    """
    base = (
        df["_tw_num"].isin(tw_nums)
        & df["Date de début planifiée"].notna()
        & (df["Date de début planifiée"] <= now_ts)
    )
    filt_num = df["Statut OT"].isin(STATUT_CLOT) & base
    filt_den = ((df["Contient SOPL"] == 1) & base) if require_sopl else base

    num = df[filt_num].groupby("Poste travail princ.")["Ordre"].count()
    den = df[filt_den].groupby("Poste travail princ.")["Ordre"].count()

    kpi_df = pd.DataFrame({"_n": num, "_d": den}).reindex(posts, fill_value=0)
    kpi_df[label] = np.where(
        kpi_df["_d"] == 0, 100.0, (kpi_df["_n"] / kpi_df["_d"]) * 100
    )
    return kpi_df


# ─── Backlog caractérisé ─────────────────────────────────────────────────────

def _backlog_carac(df, posts, statut, require_no_sopl, keywords, label):
    """
    Calcule le taux de backlog caractérisé.

    Base = Statut donné + (hors SOPL si require_no_sopl) + Plan d'entretien != 0.
    Caractérisé = contient un des mots-clés dans 'Statut utilisateur'.
    """
    pat = '|'.join(keywords)
    mask = (~df["is_correctif"]) & (df["Statut OT"] == statut)
    if require_no_sopl:
        mask &= (df["Contient SOPL"] == 0)

    df_sub = df[mask].copy()
    df_sub["_carac"] = df_sub["Statut utilisateur"].str.contains(
        pat, na=False
    ).map({True: "CARACTERISE", False: "NON CARACTERISE"})

    pv = pd.pivot_table(
        df_sub,
        index="Poste travail princ.",
        columns="_carac",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(posts, fill_value=0)

    pv = _ensure_columns(pv, ["CARACTERISE", "NON CARACTERISE"])
    pv["Total"] = pv["CARACTERISE"] + pv["NON CARACTERISE"]
    pv[label]   = ckpi(pv["CARACTERISE"], pv["Total"])

    return pv


# ─── KPI OT coûts égaux ──────────────────────────────────────────────────────

def _calc_ot_cor_egal(df, posts):
    """
    KPI : % des OT correctifs clôturés et confirmés
    dont le coût budgété = coût réel (tolérance 0,01).
    """
    mask = (
        df["is_correctif"]
        & df["Statut OT"].isin(STATUT_CLOT)
        & df["Statut système"].str.contains("CONF", na=False)
    )
    df_clot = df[mask].copy()

    _bud_c  = pd.to_numeric(df_clot["Total coûts budgétés"], errors="coerce")
    _reel_c = pd.to_numeric(df_clot["Total coûts réels"], errors="coerce")

    df_clot["_egal"] = np.where(
        np.isclose(_bud_c, _reel_c, atol=0.01),
        "OUI",
        "NON",
    )

    pv = pd.pivot_table(
        df_clot,
        index="Poste travail princ.",
        columns="_egal",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(posts, fill_value=0)

    pv = _ensure_columns(pv, ["OUI", "NON"])
    pv["Total"]       = pv["OUI"] + pv["NON"]
    pv["OT_COR_EGAL"] = ckpi(pv["NON"], pv["Total"])
    return pv


# ─── Fonction principale ─────────────────────────────────────────────────────

def calc_kpis(df_i, av_i, now_ts, posts):
    """
    Calcule l'ensemble des KPIs pour chaque poste de travail.

    Parameters
    ----------
    df_i   : DataFrame des ordres de travail.
    av_i   : DataFrame des avis.
    now_ts : timestamp de référence (now).
    posts  : liste des postes de travail à indexer.

    Returns
    -------
    dict contenant :
        - 'dfp'         : copie du DataFrame OT.
        - 'avf'         : copie du DataFrame avis.
        - 'ckdf'        : DataFrame des KPIs (lignes = postes, colonnes = KPIs).
        - 'pv_prep'     : pivot brut âge préparation.
        - 'pv_plan'     : pivot brut âge planification.
        - 'pv_exec'     : pivot brut âge exécution.
        - 'ot_confime'  : pivot OT confirmés.
        - 'ot_cor_egal' : pivot OT coûts égaux.
    """
    res = {}
    df  = df_i.copy()
    av  = av_i.copy()
    res['dfp'] = df

    # ── 1. TAUX RÉALISATION CORRECTIF ────────────────────────────────────
    filt_cor = df["is_correctif"] & (df["Contient SOPL"] == 1)
    an = cpiv(df, filt_cor, "Statut OT", posts)
    an = _ensure_columns(an, ["CLOT", "CRÉÉ", "LANC", "TCLO"])
    an["OT_CLOTURES"] = an["CLOT"] + an["TCLO"]
    an["TOTAL_OT"]    = an[["CLOT", "CRÉÉ", "LANC", "TCLO"]].sum(axis=1)
    an["TAUX_REALISATION_CORRECTIF/PT"] = np.where(
        an["TOTAL_OT"] == 0, 100.0,
        ckpi(an["OT_CLOTURES"], an["TOTAL_OT"])
    )

    # ── 2-4. ÂGE PRÉPARATION ─────────────────────────────────────────────
    # Base : CRÉÉ + Backlog prep NON CARAC
    # Age  : |now - Créé le|
    filt_prep = (
        (df["Statut OT"] == "CRÉÉ")
        & (df["Backlog preparation"] == "NON CARACTERISE")
    )
    kpis_prep, pv_prep = _age_kpis(df, filt_prep, "ap", posts, "préparation")

    # ── 5-7. ÂGE PLANIFICATION ───────────────────────────────────────────
    # Base : LANC + hors SOPL + Backlog plan NON CARAC
    # Age  : |now - Date planifiée|
    filt_plan = (
        (df["Statut OT"] == "LANC")
        & (df["Contient SOPL"] == 0)
        & (df["Backlog planification"] == "NON CARACTERISE")
    )
    kpis_plan, pv_plan = _age_kpis(df, filt_plan, "alp", posts, "planification")

    # ── 8-10. ÂGE EXÉCUTION ──────────────────────────────────────────────
    # Base : LANC + SOPL
    # Age  : |now - Date planifiée|
    filt_exec = (
        (df["Statut OT"] == "LANC")
        & (df["Contient SOPL"] == 1)
    )
    kpis_exec, pv_exec = _age_kpis(df, filt_exec, "aex", posts, "exécution")

    # ── 11. PERFORMANCE GRAISSAGE (TW=350) ───────────────────────────────
    g_df = _perf_kpi(df, posts, [350], now_ts, "Performance Graissage")

    # ── 12. PERFORMANCE INSPECTION (TW=290/300/310) ──────────────────────
    ins_df = _perf_kpi(df, posts, [290, 300, 310], now_ts, "Performance Inspection")

    # ── 13. PERFORMANCE SYSTÉMATIQUES (TW=360) ───────────────────────────
    sys_df = _perf_kpi(df, posts, [360], now_ts, "Performance Systématiques")

    # ── 14. TAUX APPROBATION AVIS ────────────────────────────────────────
    avf = av.copy()
    res['avf'] = avf
    tca = pd.pivot_table(
        avf,
        index="Poste travail princ.",
        columns="Statut utilisateur",
        values="Avis",
        aggfunc="count",
        fill_value=0,
    ).reindex(posts, fill_value=0)
    tca["APRV"]  = tca.get("APRV", 0)
    tca["Total"] = tca.sum(axis=1)
    tca["Taux d'approbation des Avis"] = ckpi(tca["APRV"], tca["Total"])

    # ── 15. OT LANC ESTIMÉ ───────────────────────────────────────────────
    filt_lanc = (
        df["is_correctif"]
        & (df["Statut OT"] == "LANC")
        & (df["Contient SOPL"] == 0)
    )
    la = pd.pivot_table(
        df[filt_lanc],
        index="Poste travail princ.",
        columns="OT LANC ESTIME",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(posts, fill_value=0)
    la = _ensure_columns(la, ["OUI", "NON"])
    la["Total"]          = la["OUI"] + la["NON"]
    la["OT LANC ESTIME"] = ckpi(la["OUI"], la["Total"])

    # ── 16. BACKLOG PRÉPARATION CARACTÉRISÉ ──────────────────────────────
    # Base = Statut CRÉÉ + Plan d'entretien != 0 (préventif)
    # Caractérisé = contient ATPD/ATMR/ATRS/ATMO/ATER
    pc = _backlog_carac(
        df, posts,
        statut="CRÉÉ",
        require_no_sopl=False,
        keywords=CRPR_KW,
        label="Backlog préparation caractérisé",
    )

    # ── 17. BACKLOG PLANIFICATION CARACTÉRISÉ ────────────────────────────
    # Base = Statut LANC + hors SOPL + Plan d'entretien != 0 (préventif)
    # Caractérisé = contient ATEI/ATAL/ATAS/AGAR/ATHS
    plc = _backlog_carac(
        df, posts,
        statut="LANC",
        require_no_sopl=True,
        keywords=ATPL_KW,
        label="Backlog planification caractérisé",
    )

    # ── 18. OT CONFIRMÉ ──────────────────────────────────────────────────
    pv_conf = pd.pivot_table(
        df[df["Statut OT"].isin(STATUT_CLOT)],
        index="Poste travail princ.",
        columns="OT CONFIME",
        values="Ordre",
        aggfunc="count",
        fill_value=0,
    ).reindex(posts, fill_value=0)
    pv_conf = _ensure_columns(pv_conf, ["OUI", "NON"])
    pv_conf["Total"]      = pv_conf["OUI"] + pv_conf["NON"]
    pv_conf["OT CONFIME"] = ckpi(pv_conf["OUI"], pv_conf["Total"])
    res["ot_confime"]     = pv_conf

    # ── 19. OT_COR_EGAL ──────────────────────────────────────────────────
    # Base : OT correctifs clôturés (CLOT/TCLO) et confirmés (CONF)
    # KPI  : (Budget = Réel) / Total -> maximiser (bonne imputation des coûts)
    res["ot_cor_egal"] = _calc_ot_cor_egal(df, posts)

    # ── 20-21. PLACEHOLDERS ──────────────────────────────────────────────
    fiab_s  = pd.Series(100.0, index=posts)
    avpan_s = pd.Series(100.0, index=posts)

    # ── ASSEMBLAGE FINAL ─────────────────────────────────────────────────
    res['ckdf'] = pd.DataFrame({
        "TAUX_REALISATION_CORRECTIF/PT": an["TAUX_REALISATION_CORRECTIF/PT"],
        # Âge Préparation
        "OT préparation <1 mois":            kpis_prep["OT préparation <1 mois"],
        "OT préparation >3 mois":            kpis_prep["OT préparation >3 mois"],
        "OT préparation 1mois< <3mois":      kpis_prep["OT préparation 1mois< <3mois"],
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
