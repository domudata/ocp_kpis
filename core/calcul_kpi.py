# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd

from core.constants import MP_KW, MPLAN_KW, QK, PK, CIBLE, LOWER_BETTER


# ============================================================
# UTILITAIRES
# ============================================================

def ckpi(n, d, sz=100):
    """
    Calcul d'un taux en %.

    Règle générale :
        OUI / (OUI + NON)

    Si d == 0 :
        retourne sz (100 par défaut)
    """
    return np.where(
        d == 0,
        sz,
        (n / d) * 100
    )


def cpiv(df: pd.DataFrame, f, c: str, p: list) -> pd.DataFrame:
    """
    Pivot de comptage des Ordres.
    """
    return (
        pd.pivot_table(
            df[f],
            index="Poste travail princ.",
            columns=c,
            values="Ordre",
            aggfunc="count",
            fill_value=0
        )
        .reindex(p, fill_value=0)
    )


def get_text_col(df: pd.DataFrame):
    for c in [
        "Désignation",
        "Designation",
        "Désignation OT",
        "Texte ordre",
        "Texte",
        "Description",
        "Libellé",
        "Libelle"
    ]:
        if c in df.columns:
            return c

    for c in df.columns:
        if df[c].dtype == "object" and any(
            kw in str(c).lower()
            for kw in ["sign", "text", "desc", "libell"]
        ):
            return c

    return None


def build_statut_pivot(
    df_sub: pd.DataFrame,
    posts: list
) -> pd.DataFrame:

    if df_sub.empty:
        return (
            pd.DataFrame(
                index=posts,
                columns=[
                    "CRÉÉ",
                    "LANC",
                    "CLOT",
                    "TCLO",
                    "Total"
                ]
            )
            .fillna(0)
            .astype(int)
        )

    piv = pd.pivot_table(
        df_sub,
        index="Poste travail princ.",
        columns="Statut OT",
        values="Ordre",
        aggfunc="count",
        fill_value=0
    )

    for s in [
        "CRÉÉ",
        "LANC",
        "CLOT",
        "TCLO"
    ]:
        if s not in piv.columns:
            piv[s] = 0

    piv["Total"] = piv[
        ["CRÉÉ", "LANC", "CLOT", "TCLO"]
    ].sum(axis=1)

    return (
        piv
        .reindex(posts, fill_value=0)
        .fillna(0)
        .astype(int)
    )


# ============================================================
# SCORE BINAIRE
# ============================================================

def gscore(k: str, a, t) -> int:

    if pd.isna(a) or pd.isna(t):
        return 0

    # AGE : < 1 mois = plus élevé est meilleur
    if k in [
        "OT préparation <1 mois",
        "OT planification <1 mois",
        "OT exécution <1 mois"
    ]:
        return 1 if a >= 75 else 0

    # AGE : 1-3 mois = plus faible est meilleur
    if k in [
        "OT préparation 1mois< <3mois",
        "OT planification 1mois< <3mois",
        "OT exécution 1mois< <3mois"
    ]:
        return 1 if a <= 15 else 0

    # AGE : >3 mois = plus faible est meilleur
    if k in [
        "OT préparation >3 mois",
        "OT planification >3 mois",
        "OT exécution >3 mois"
    ]:
        return 1 if a <= 5 else 0

    # Réalisation corrective
    if k == "TAUX_REALISATION_CORRECTIF/PT":
        return 1 if a >= 80 else 0

    # Avis
    if k == "Taux d'approbation des Avis":
        return 1 if a >= 90 else 0

    # OUI meilleur
    if k in [
        "OT LANC ESTIME",
        "Backlog préparation caractérisé",
        "Backlog planification caractérisé",
        "OT CONFIME"
    ]:
        return 1 if a >= 95 else 0

    # NON meilleur
    if k == "OT_COR_EGAL":
        return 1 if a <= 5 else 0

    # Maintenance
    if k in [
        "Performance Graissage",
        "Performance Inspection",
        "Performance Systématiques"
    ]:
        return 1 if a >= 95 else 0

    # Fiabilité
    if k in [
        "OT Fiabilité",
        "Total Avis de Panne"
    ]:
        return 1 if a >= 100 else 0

    return 0


def is_lb(k: str) -> bool:
    return k in LOWER_BETTER


# ============================================================
# CODES EXACTS
# ============================================================

CODES_PREP_EXACT = {
    "ATPD",
    "ATMR",
    "ATER",
    "ATRS",
    "ATMO"
}

CODES_PLAN_EXACT = {
    "ATEI",
    "ATAL",
    "ATAS",
    "AGAR",
    "ATHS"
}


def match_exact_token(statut, codes: set) -> bool:

    if statut is None:
        return False

    if isinstance(statut, float) and pd.isna(statut):
        return False

    return (
        str(statut)
        .strip()
        .upper()
        in codes
    )


# ============================================================
# CALCUL PRINCIPAL
# ============================================================

def calc_kpis(
    df_i: pd.DataFrame,
    av_i: pd.DataFrame,
    now_ts,
    posts: list,
    df_toutes_dates: pd.DataFrame = None
) -> dict:

    res = {}

    df = df_i.copy()
    av = av_i.copy()

    res["dfp"] = df

    df_all = (
        df_toutes_dates.copy()
        if df_toutes_dates is not None
        else df
    )

    # ========================================================
    # 1. REALISATION CORRECTIVE
    # ========================================================

    filt_corr = (
        (df["Nº appel pl.entret."].fillna(0) == 0)
        & (df["Contient SOPL"] == 1)
    )

    an = cpiv(
        df,
        filt_corr,
        "Statut OT",
        posts
    )

    for c in [
        "CLOT",
        "CRÉÉ",
        "LANC",
        "TCLO"
    ]:
        an[c] = an.get(c, 0)

    an["OT_CLOTURES"] = (
        an["CLOT"] +
        an["TCLO"]
    )

    an["TOTAL_OT"] = an[
        [
            "CLOT",
            "CRÉÉ",
            "LANC",
            "TCLO"
        ]
    ].sum(axis=1)

    an["TAUX_REALISATION_CORRECTIF/PT"] = np.where(
        an["TOTAL_OT"] == 0,
        100.0,
        ckpi(
            an["OT_CLOTURES"],
            an["TOTAL_OT"]
        )
    )

    # ========================================================
    # 2. EXECUTION AGE
    # ========================================================

    ex = cpiv(
        df,
        (
            (df["Statut OT"] == "LANC")
            &
            (df["Contient SOPL"] == 1)
        ),
        "aex",
        posts
    )

    for c in [
        "<1 mois",
        "1 mois < <3 mois",
        ">3 mois",
        "Inconnu"
    ]:
        ex[c] = ex.get(c, 0)

    # IMPORTANT :
    # Inconnu exclu du dénominateur
    ex["Total"] = ex[
        [
            "<1 mois",
            "1 mois < <3 mois",
            ">3 mois"
        ]
    ].sum(axis=1)

    ex["OT exécution <1 mois"] = ckpi(
        ex["<1 mois"],
        ex["Total"]
    )

    ex["OT exécution 1mois< <3mois"] = ckpi(
        ex["1 mois < <3 mois"],
        ex["Total"],
        0
    )

    ex["OT exécution >3 mois"] = ckpi(
        ex[">3 mois"],
        ex["Total"],
        0
    )

    # ========================================================
    # 3. OT LANC ESTIME
    # ========================================================

    la = pd.pivot_table(
        df[
            (df["Statut OT"] == "LANC")
            &
            (df["Contient SOPL"] == 1)
            &
            (df["Type d'ordre"] == "ZCOR")
        ],
        index="Poste travail princ.",
        columns="OT LANC ESTIME",
        values="Ordre",
        aggfunc="count",
        fill_value=0
    ).reindex(posts, fill_value=0)

    for c in ["OUI", "NON"]:
        la[c] = la.get(c, 0)

    # OUI / (OUI + NON)
    la["Total"] = (
        la["OUI"] +
        la["NON"]
    )

    la["OT LANC ESTIME"] = ckpi(
        la["OUI"],
        la["Total"]
    )

    # ========================================================
    # 4. BACKLOG PREPARATION CARACTERISE
    # ========================================================

    _zcor_all = df_all[
        df_all["Type d'ordre"] == "ZCOR"
    ].copy()

    _zcor_cree_all = _zcor_all[
        _zcor_all["Statut système"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.split()
        .str[0]
        == "CRÉÉ"
    ].copy()

    _zcor_cree_all["_prep_carac"] = np.where(
        _zcor_cree_all[
            "Statut utilisateur"
        ].apply(
            lambda x:
                match_exact_token(
                    x,
                    CODES_PREP_EXACT
                )
        ),
        "CARACTERISE",
        "NON CARACTERISE"
    )

    pc = pd.pivot_table(
        _zcor_cree_all,
        index="Poste travail princ.",
        columns="_prep_carac",
        values="Ordre",
        aggfunc="count",
        fill_value=0
    ).reindex(posts, fill_value=0)

    for c in [
        "CARACTERISE",
        "NON CARACTERISE"
    ]:
        pc[c] = pc.get(c, 0)

    pc["Total"] = (
        pc["CARACTERISE"] +
        pc["NON CARACTERISE"]
    )

    # OUI / (OUI + NON)
    pc["Backlog préparation caractérisé"] = ckpi(
        pc["CARACTERISE"],
        pc["Total"]
    )

    # ========================================================
    # 5. BACKLOG PLANIFICATION CARACTERISE
    # ========================================================

    _zcor_lanc_all = _zcor_all[
        (
            _zcor_all["Statut système"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.split()
            .str[0]
            == "LANC"
        )
        &
        (_zcor_all["Contient SOPL"] == 0)
    ].copy()

    _zcor_lanc_all["_plan_carac"] = np.where(
        _zcor_lanc_all[
            "Statut utilisateur"
        ].apply(
            lambda x:
                match_exact_token(
                    x,
                    CODES_PLAN_EXACT
                )
        ),
        "CARACTERISE",
        "NON CARACTERISE"
    )

    plc = pd.pivot_table(
        _zcor_lanc_all,
        index="Poste travail princ.",
        columns="_plan_carac",
        values="Ordre",
        aggfunc="count",
        fill_value=0
    ).reindex(posts, fill_value=0)

    for c in [
        "CARACTERISE",
        "NON CARACTERISE"
    ]:
        plc[c] = plc.get(c, 0)

    plc["Total"] = (
        plc["CARACTERISE"] +
        plc["NON CARACTERISE"]
    )

    # OUI / (OUI + NON)
    plc["Backlog planification caractérisé"] = ckpi(
        plc["CARACTERISE"],
        plc["Total"]
    )

    # ========================================================
    # 6. AGE PREPARATION
    # ========================================================

    _non_prep_age = _zcor_cree_all[
        _zcor_cree_all["_prep_carac"]
        == "NON CARACTERISE"
    ]

    pr = cpiv(
        _non_prep_age,
        pd.Series(
            True,
            index=_non_prep_age.index
        ),
        "ap",
        posts
    )

    for c in [
        "<1 mois",
        "1 mois < <3 mois",
        ">3 mois",
        "Inconnu"
    ]:
        pr[c] = pr.get(c, 0)

    # ========================================================
    # IMPORTANT :
    # Le dénominateur est UNIQUEMENT :
    #
    # <1 mois + 1-3 mois + >3 mois
    #
    # Inconnu est exclu.
    # ========================================================

    pr["Total"] = pr[
        [
            "<1 mois",
            "1 mois < <3 mois",
            ">3 mois"
        ]
    ].sum(axis=1)

    pr["OT préparation <1 mois"] = ckpi(
        pr["<1 mois"],
        pr["Total"]
    )

    pr["OT préparation 1mois< <3mois"] = ckpi(
        pr["1 mois < <3 mois"],
        pr["Total"],
        0
    )

    pr["OT préparation >3 mois"] = ckpi(
        pr[">3 mois"],
        pr["Total"],
        0
    )

    # ========================================================
    # 7. AGE PLANIFICATION
    # ========================================================

    _non_plan_age = _zcor_lanc_all[
        _zcor_lanc_all["_plan_carac"]
        == "NON CARACTERISE"
    ]

    pl = cpiv(
        _non_plan_age,
        pd.Series(
            True,
            index=_non_plan_age.index
        ),
        "alp",
        posts
    )

    for c in [
        "<1 mois",
        "1 mois < <3 mois",
        ">3 mois",
        "Inconnu"
    ]:
        pl[c] = pl.get(c, 0)

    # Même règle :
    # Inconnu exclu du dénominateur.

    pl["Total"] = pl[
        [
            "<1 mois",
            "1 mois < <3 mois",
            ">3 mois"
        ]
    ].sum(axis=1)

    pl["OT planification <1 mois"] = ckpi(
        pl["<1 mois"],
        pl["Total"]
    )

    pl["OT planification 1mois< <3mois"] = ckpi(
        pl["1 mois < <3 mois"],
        pl["Total"],
        0
    )

    pl["OT planification >3 mois"] = ckpi(
        pl[">3 mois"],
        pl["Total"],
        0
    )

    # ========================================================
    # 8. OT CONFIME
    # ========================================================

    pv_conf = pd.pivot_table(
        df[
            df["Statut OT"].isin(
                ["CLOT", "TCLO"]
            )
        ],
        index="Poste travail princ.",
        columns="OT CONFIME",
        values="Ordre",
        aggfunc="count",
        fill_value=0
    ).reindex(posts, fill_value=0)

    for c in ["OUI", "NON"]:
        pv_conf[c] = pv_conf.get(c, 0)

    # OUI / (OUI + NON
