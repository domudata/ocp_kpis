# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd


# ============================================================
# UTILITAIRE
# ============================================================

def _normalize_text(s):
    return (
        s.fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )


# ============================================================
# SCOPE AGE EXECUTION
# ============================================================

def execution_scope(df: pd.DataFrame) -> pd.Series:
    """
    Population officielle des anomalies Exécution :

        LANC
        + SOPL
        + ZCOR
        + NON CARACTERISE PLANIFICATION
    """

    statut = _normalize_text(
        df["Statut OT"]
    )

    type_ordre = _normalize_text(
        df["Type d'ordre"]
    )

    backlog_plan = _normalize_text(
        df["Backlog planification"]
    )

    return (
        (statut == "LANC")
        &
        (df["Contient SOPL"] == 1)
        &
        (type_ordre == "ZCOR")
        &
        backlog_plan.isin([
            "NON CARACTERISE",
            "NON CARACTÉRISÉ",
            "NON CARACTERISEE",
            "NON CARACTÉRISÉE",
            "NON CARACT",
            "NON CARAC",
            "1"
        ])
    )


# ============================================================
# AGE EXECUTION
# ============================================================

def calculate_execution_age(
    df: pd.DataFrame,
    now_ts
) -> pd.DataFrame:

    df = df.copy()

    dates = pd.to_datetime(
        df["Date de début planifiée"],
        errors="coerce",
        dayfirst=True
    )

    age = (
        (now_ts.year - dates.dt.year) * 12
        +
        (now_ts.month - dates.dt.month)
    )

    df["amex"] = age

    df["aex"] = "Inconnu"

    df.loc[
        dates.notna() & (age <= 1),
        "aex"
    ] = "<1 mois"

    df.loc[
        dates.notna() &
        (age > 1) &
        (age < 3),
        "aex"
    ] = "1 mois < <3 mois"

    df.loc[
        dates.notna() & (age >= 3),
        "aex"
    ] = ">3 mois"

    return df


# ============================================================
# BUILD ANOMALY MAP
# ============================================================

def build_ano_map(
    dfp: pd.DataFrame,
    avf: pd.DataFrame,
    now_ts,
    dfp_toutes_dates=None
):

    df = dfp.copy()

    # ========================================================
    # AGE EXECUTION
    # ========================================================

    df_exec = df[
        execution_scope(df)
    ].copy()

    df_exec = calculate_execution_age(
        df_exec,
        now_ts
    )

    # --------------------------------------------------------
    # <1 mois
    # --------------------------------------------------------

    ano_exec_lt1 = (
        df_exec[
            df_exec["aex"] == "<1 mois"
        ]
        .groupby(
            "Poste travail princ."
        )["Ordre"]
        .count()
    )

    # --------------------------------------------------------
    # 1-3 mois
    # --------------------------------------------------------

    ano_exec_1_3 = (
        df_exec[
            df_exec["aex"] == "1 mois < <3 mois"
        ]
        .groupby(
            "Poste travail princ."
        )["Ordre"]
        .count()
    )

    # --------------------------------------------------------
    # >3 mois
    # --------------------------------------------------------

    ano_exec_gt3 = (
        df_exec[
            df_exec["aex"] == ">3 mois"
        ]
        .groupby(
            "Poste travail princ."
        )["Ordre"]
        .count()
    )

    # ========================================================
    # DICTIONNAIRE ANOMALIES
    # ========================================================

    ano_map = {

        "OT exécution <1 mois":
            ano_exec_lt1,

        "OT exécution 1mois< <3mois":
            ano_exec_1_3,

        "OT exécution >3 mois":
            ano_exec_gt3,
    }

    return ano_map


# ============================================================
# DETAIL ANOMALIES
# ============================================================

def build_anomaly_dfs(
    dfp: pd.DataFrame,
    avf: pd.DataFrame,
    now_ts,
    dfp_toutes_dates=None
):

    df = dfp.copy()

    # ========================================================
    # AGE EXECUTION
    # ========================================================

    df_exec = df[
        execution_scope(df)
    ].copy()

    df_exec = calculate_execution_age(
        df_exec,
        now_ts
    )

    # ========================================================
    # DATAFRAMES PAR PERIODE
    # ========================================================

    df_lt1 = df_exec[
        df_exec["aex"] == "<1 mois"
    ].copy()

    df_1_3 = df_exec[
        df_exec["aex"] == "1 mois < <3 mois"
    ].copy()

    df_gt3 = df_exec[
        df_exec["aex"] == ">3 mois"
    ].copy()

    # ========================================================
    # DICTIONNAIRE
    # ========================================================

    anomaly_dfs = {

        "OT exécution <1 mois":
            df_lt1,

        "OT exécution 1mois< <3mois":
            df_1_3,

        "OT exécution >3 mois":
            df_gt3,
    }

    return anomaly_dfs
