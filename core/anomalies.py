# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd


# ============================================================
# UTILITAIRE
# ============================================================

def _normalize_text(s):
    """
    Normalisation robuste des colonnes texte.
    """
    return (
        s.fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )


def _get_series(df, column, default=""):
    """
    Retourne une colonne si elle existe.
    Sinon retourne une série vide de même longueur.
    """
    if column in df.columns:
        return df[column]

    return pd.Series(
        [default] * len(df),
        index=df.index
    )


# ============================================================
# SCOPE AGE EXECUTION
# ============================================================

def execution_scope(df: pd.DataFrame) -> pd.Series:
    """
    Population OFFICIELLE des anomalies Exécution.

    Règles :

        Statut OT = LANC
        ET Contient SOPL = 1
        ET Type d'ordre = ZCOR
        ET Backlog planification = NON CARACTERISE

    Cette population doit être exactement la même
    que celle utilisée dans calcul_kpi.py.
    """

    statut = _normalize_text(
        _get_series(df, "Statut OT")
    )

    type_ordre = _normalize_text(
        _get_series(df, "Type d'ordre")
    )

    backlog_plan = _normalize_text(
        _get_series(df, "Backlog planification")
    )

    contient_sopl = pd.to_numeric(
        _get_series(df, "Contient SOPL", 0),
        errors="coerce"
    ).fillna(0)

    non_caracterise = backlog_plan.isin([
        "NON CARACTERISE",
        "NON CARACTÉRISÉ",
        "NON CARACTERISEE",
        "NON CARACTÉRISÉE",
        "NON CARACT",
        "NON CARAC",
        "1",
    ])

    return (
        (statut == "LANC")
        &
        (contient_sopl == 1)
        &
        (type_ordre == "ZCOR")
        &
        non_caracterise
    )


# ============================================================
# AGE EXECUTION
# ============================================================

def calculate_execution_age(
    df: pd.DataFrame,
    now_ts
) -> pd.DataFrame:
    """
    Utilise en priorité la colonne 'aex' déjà calculée
    dans prepare_data.py.

    Cela évite que le KPI et les anomalies utilisent
    deux calculs d'âge différents.

    Si 'aex' n'existe pas, on le recalcule à partir de
    Date de début planifiée.
    """

    df = df.copy()

    # --------------------------------------------------------
    # PRIORITE : colonne aex déjà calculée dans prepare_data
    # --------------------------------------------------------

    if "aex" in df.columns:
        df["aex"] = (
            df["aex"]
            .fillna("Inconnu")
            .astype(str)
            .str.strip()
        )

        return df

    # --------------------------------------------------------
    # FALLBACK : calcul de l'âge
    # --------------------------------------------------------

    dates = pd.to_datetime(
        _get_series(df, "Date de début planifiée"),
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
        dates.notna()
        & (age > 1)
        & (age < 3),
        "aex"
    ] = "1 mois < <3 mois"

    df.loc[
        dates.notna() & (age >= 3),
        "aex"
    ] = ">3 mois"

    return df


# ============================================================
# PREPARATION EXECUTION
# ============================================================

def _get_execution_dataframe(
    dfp: pd.DataFrame,
    now_ts
) -> pd.DataFrame:
    """
    Construit UNE SEULE population d'exécution.

    Cette population est ensuite utilisée par :
        - build_ano_map()
        - build_anomaly_dfs()
        - build_ano_rows()

    Cela garantit que les nombres affichés sont cohérents.
    """

    if dfp is None or dfp.empty:
        return pd.DataFrame()

    df = dfp.copy()

    mask = execution_scope(df)

    df_exec = df.loc[mask].copy()

    if df_exec.empty:
        return df_exec

    df_exec = calculate_execution_age(
        df_exec,
        now_ts
    )

    return df_exec


# ============================================================
# BUILD ANOMALY MAP
# ============================================================

def build_ano_map(
    dfp: pd.DataFrame,
    avf: pd.DataFrame,
    now_ts,
    dfp_toutes_dates=None
):
    """
    Retourne le nombre d'anomalies par KPI et par poste.

    Pour l'exécution :

        <1 mois
        1 mois < <3 mois
        >3 mois

    IMPORTANT :
    Le même df_exec est utilisé pour les trois catégories.
    """

    df_exec = _get_execution_dataframe(
        dfp,
        now_ts
    )

    # ========================================================
    # <1 MOIS
    # ========================================================

    if not df_exec.empty:

        ano_exec_lt1 = (
            df_exec[
                df_exec["aex"] == "<1 mois"
            ]
            .groupby(
                "Poste travail princ."
            )["Ordre"]
            .count()
        )

    else:
        ano_exec_lt1 = pd.Series(
            dtype="int64"
        )

    # ========================================================
    # 1-3 MOIS
    # ========================================================

    if not df_exec.empty:

        ano_exec_1_3 = (
            df_exec[
                df_exec["aex"] == "1 mois < <3 mois"
            ]
            .groupby(
                "Poste travail princ."
            )["Ordre"]
            .count()
        )

    else:
        ano_exec_1_3 = pd.Series(
            dtype="int64"
        )

    # ========================================================
    # >3 MOIS
    # ========================================================

    if not df_exec.empty:

        ano_exec_gt3 = (
            df_exec[
                df_exec["aex"] == ">3 mois"
            ]
            .groupby(
                "Poste travail princ."
            )["Ordre"]
            .count()
        )

    else:
        ano_exec_gt3 = pd.Series(
            dtype="int64"
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
# BUILD ANOMALY ROWS
# ============================================================

def build_ano_rows(
    postes,
    ano_map,
    liste_kpi,
    fixed_zero=None
):
    """
    Construit le tableau :

        Poste de travail
        KPI 1
        KPI 2
        ...
        Total Anomalies

    Format attendu par app.py.

    Exemple :

        SF101 | 2 | 1 | 0 | 3
        SF102 | 0 | 3 | 1 | 4
        ...
        Total | ...

    fixed_zero :
        KPI forcés à 0.
    """

    if postes is None:
        postes = []

    if fixed_zero is None:
        fixed_zero = []

    # --------------------------------------------------------
    # Normalisation
    # --------------------------------------------------------

    postes = list(postes)
    liste_kpi = list(liste_kpi)

    rows = []

    # ========================================================
    # UNE LIGNE PAR POSTE
    # ========================================================

    for poste in postes:

        row = {
            "Poste de travail": poste
        }

        total = 0

        for kpi in liste_kpi:

            # ------------------------------------------------
            # KPI forcé à zéro
            # ------------------------------------------------

            if kpi in fixed_zero:

                value = 0

            else:

                series = ano_map.get(
                    kpi,
                    pd.Series(dtype="int64")
                )

                try:
                    value = series.get(
                        poste,
                        0
                    )

                    if pd.isna(value):
                        value = 0

                    value = int(value)

                except Exception:
                    value = 0

            row[kpi] = value

            total += value

        row["Total Anomalies"] = int(total)

        rows.append(row)

    # ========================================================
    # TOTAL GENERAL
    # ========================================================

    total_row = {
        "Poste de travail": "Total"
    }

    total_general = 0

    for kpi in liste_kpi:

        kpi_total = 0

        for row in rows:

            try:
                value = int(
                    row.get(kpi, 0)
                )

            except Exception:
                value = 0

            kpi_total += value

        total_row[kpi] = int(kpi_total)

        total_general += kpi_total

    total_row["Total Anomalies"] = int(
        total_general
    )

    rows.append(total_row)

    return rows


# ============================================================
# DETAIL ANOMALIES
# ============================================================

def build_anomaly_dfs(
    dfp: pd.DataFrame,
    avf: pd.DataFrame,
    now_ts,
    dfp_toutes_dates=None
):
    """
    Retourne les DataFrames détaillés des anomalies.

    Les mêmes règles que build_ano_map() sont utilisées.
    """

    df_exec = _get_execution_dataframe(
        dfp,
        now_ts
    )

    # ========================================================
    # DATAFRAME <1 MOIS
    # ========================================================

    if not df_exec.empty:

        df_lt1 = df_exec[
            df_exec["aex"] == "<1 mois"
        ].copy()

    else:

        df_lt1 = df_exec.copy()

    # ========================================================
    # DATAFRAME 1-3 MOIS
    # ========================================================

    if not df_exec.empty:

        df_1_3 = df_exec[
            df_exec["aex"] == "1 mois < <3 mois"
        ].copy()

    else:

        df_1_3 = df_exec.copy()

    # ========================================================
    # DATAFRAME >3 MOIS
    # ========================================================

    if not df_exec.empty:

        df_gt3 = df_exec[
            df_exec["aex"] == ">3 mois"
        ].copy()

    else:

        df_gt3 = df_exec.copy()

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
