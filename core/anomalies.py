# -*- coding: utf-8 -*-
import pandas as pd

from core.constants import QK, PK
from core.calcul_kpi import (
    match_exact_token, CODES_PREP_EXACT, CODES_PLAN_EXACT,
    build_avis_zc_population, build_execution_population,
)


# Types d'Avis exclus des calculs Avis
TYPES_AVIS_EXCLUS = {"ZU", "Z4", "ZR", "ZP"}


def _normaliser_type_avis(v) -> str:
    if pd.isna(v):
        return ""
    return str(v).strip().upper()


def _trouver_colonne_type_avis(df: pd.DataFrame):
    candidats = [
        "Type", "Type avis", "Type Avis", "Type d'avis", "Type d’Avis",
        "Type de avis", "Type de Avis", "Type demande", "Type de demande",
        "Catégorie", "Categorie",
    ]
    for c in candidats:
        if c in df.columns:
            return c

    for c in df.columns:
        n = str(c).strip().lower().replace("’", "'")
        if (
            n == "type"
            or "type avis" in n
            or "type d'avis" in n
            or "type de avis" in n
            or "type demande" in n
            or "type de demande" in n
        ):
            return c
    return None


def _avis_hors_types_exclus(avdf: pd.DataFrame) -> pd.DataFrame:
    """Population Avis utilisée pour le KPI et ses anomalies.

    Les Avis ZU/Z4/ZR/ZP sont toujours exclus.
    Si prepare_data.py a déjà créé _avis_type_exclu, on l'utilise.
    Sinon, on détecte automatiquement la colonne Type d'Avis.
    """
    av = avdf.copy()

    if "_avis_type_exclu" in av.columns:
        return av[~av["_avis_type_exclu"].fillna(False)].copy()

    col_type = _trouver_colonne_type_avis(av)
    if col_type is None:
        # Impossible d'identifier le type : ne pas inventer un filtre.
        return av

    types = av[col_type].apply(_normaliser_type_avis)
    return av[~types.isin(TYPES_AVIS_EXCLUS)].copy()


def _avis_anomalies_population(avdf: pd.DataFrame) -> pd.DataFrame:
    """Anomalies Avis :
       Statut système = AOUV
       ET Statut utilisateur = APRQ
       ET type Avis non ZU/Z4/ZR/ZP.
    """
    av = _avis_hors_types_exclus(avdf)

    sys = (
        av["Statut système"].fillna("").astype(str).str.upper().str.strip()
        if "Statut système" in av.columns
        else pd.Series("", index=av.index)
    )
    usr = (
        av["Statut utilisateur"].fillna("").astype(str).str.upper().str.strip()
        if "Statut utilisateur" in av.columns
        else pd.Series("", index=av.index)
    )

    return av[
        sys.str.contains(r"\bAOUV\b", regex=True, na=False)
        & usr.str.contains(r"\bAPRQ\b", regex=True, na=False)
    ].copy()


def _backlogs_non_caracterises(dfp_all: pd.DataFrame, now_ts=None):
    """Reconstruit les populations Backlog préparation/planification.

    Retourne un tuple (non_prep, non_plan, full_prep, full_plan) :
      - non_prep / non_plan : uniquement la part NON CARACTERISE (pour
        l'indicateur Backlog préparation/planification caractérisé) ;
      - full_prep / full_plan : la population COMPLÈTE (CARACTERISE ET
        NON CARACTERISE confondus), pour les indicateurs OT préparation/
        planification <1/1-3/>3 mois (précision explicite : ces
        indicateurs se répartissent sur le TOTAL, pas seulement le non
        caractérisé). full_plan est en outre restreint aux OT dont
        "Date de début planifiée" est déjà passée (<= now_ts)."""
    zcor = dfp_all[dfp_all["Type d'ordre"] == "ZCOR"].copy()

    zcor_cree = zcor[
        (zcor["Statut OT"] == "CRÉÉ")
        | zcor["Statut système"].fillna("").astype(str).str.contains("CRÉÉ|CREE|CRÉE", regex=True, na=False)
    ]
    # CORRIGÉ (bug pandas identifié et reproduit) : sur un DataFrame déjà
    # VIDE (0 ligne), `~df["col"].apply(fonction)` peut renvoyer un
    # résultat mal typé qui, une fois utilisé pour indexer le DataFrame,
    # produit un DataFrame de forme (0, 0) — TOUTES les colonnes
    # disparaissent, provoquant un KeyError plus loin (ex. sur "Poste
    # travail princ.") dans le calcul filtré sur une période étroite
    # (ex. une seule semaine) où aucun ZCOR ne tombe dans la fenêtre.
    if zcor_cree.empty:
        non_prep = zcor_cree
    else:
        non_prep = zcor_cree[~zcor_cree["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PREP_EXACT))]

    zcor_lanc = zcor[
        (
            (zcor["Statut OT"] == "LANC")
            | zcor["Statut système"].fillna("").astype(str).str.contains("LANC", na=False)
        )
        & (zcor["Contient SOPL"] == 0)
    ]
    if zcor_lanc.empty:
        non_plan = zcor_lanc
    else:
        non_plan = zcor_lanc[~zcor_lanc["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT))]

    full_prep = zcor_cree
    full_plan = zcor_lanc

    return non_prep, non_plan, full_prep, full_plan


def build_ano_map(dfp: pd.DataFrame, avf: pd.DataFrame, now_ts,
                   dfp_toutes_dates: pd.DataFrame = None) -> dict:
    """
    Construit le dictionnaire ano_map :
    {kpi_name → pd.Series(index=poste, values=nb_anomalies)}

    dfp_toutes_dates : DataFrame OT sans le filtre de période de la barre
    latérale, utilisé UNIQUEMENT pour les deux indicateurs Backlog
    préparation/planification caractérisé (demande explicite). Si non
    fourni, dfp est réutilisé (comportement inchangé).
    """
    dfp_all = dfp_toutes_dates.copy() if dfp_toutes_dates is not None else dfp

    # ── Populations Backlog préparation/planification — CALCULÉES UNE
    # SEULE FOIS ici, réutilisées à la fois pour l'indicateur Backlog
    # caractérisé ET pour la répartition par âge (SYNCHRONISÉ avec
    # calcul_kpi.py — demande explicite de cohérence KPI / anomalies).
    non_prep, non_plan, full_prep, full_plan = _backlogs_non_caracterises(dfp_all, now_ts)

    ano_map = {}

    ano_map["TAUX_REALISATION_CORRECTIF/PT"] = (
        dfp[(dfp["Nº appel pl.entret."].fillna(0) == 0)
            & (dfp["Contient SOPL"] == 1)
            & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))]
        .groupby("Poste travail princ.")["Ordre"].count()
    )

    # ── OT préparation <1/1-3/>3 mois — SYNCHRONISÉ avec calcul_kpi.py ──
    # Base = full_prep (ZCOR + CRÉÉ), répartie selon l'âge (colonne "ap").
    ano_map["OT préparation <1 mois"] = full_prep[full_prep["ap"] == "<1 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation >3 mois"] = full_prep[full_prep["ap"] == ">3 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation 1mois< <3mois"] = full_prep[full_prep["ap"] == "1 mois < <3 mois"].groupby("Poste travail princ.")["Ordre"].count()

    # ── OT planification <1/1-3/>3 mois — ANOMALIES NON CARACTÉRISÉES (demande explicite) ──
    # Répartition des anomalies de planification (non_plan) par tranche d'âge
    ano_map["OT planification <1 mois"] = non_plan[non_plan["alp"] == "<1 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification >3 mois"] = non_plan[non_plan["alp"] == ">3 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification 1mois< <3mois"] = non_plan[non_plan["alp"] == "1 mois < <3 mois"].groupby("Poste travail princ.")["Ordre"].count()

    # ── OT exécution <1/1-3/>3 mois — NOUVELLE POPULATION (demande explicite) ──
    # Même population que calc_kpis.py : LANC + SOPL==1 + ZCOR + date ≤ now.
    df_exec_ano = build_execution_population(dfp_all, now_ts)
    ano_map["OT exécution <1 mois"] = df_exec_ano[df_exec_ano["aex"] == "<1 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution >3 mois"] = df_exec_ano[df_exec_ano["aex"] == ">3 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution 1mois< <3mois"] = df_exec_ano[df_exec_ano["aex"] == "1 mois < <3 mois"].groupby("Poste travail princ.")["Ordre"].count()

    perf_filt = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))
    ano_map["Performance Graissage"] = dfp[perf_filt & (dfp["_tw_num"] == 350)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Inspection"] = dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Systématiques"] = dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()

    # ── Taux d'approbation des Avis ──
    # ANOMALIES :
    #   Statut système = AOUV
    #   ET Statut utilisateur = APRQ
    #   ET type Avis NOT IN ZU/Z4/ZR/ZP.
    avf_avis = _avis_hors_types_exclus(
        build_avis_zc_population(avf)
    )
    ano_avis = _avis_anomalies_population(avf_avis)

    ano_map["Taux d'approbation des Avis"] = (
        ano_avis
        .groupby("Poste travail princ.")["Avis"]
        .count()
    )

    ano_map["OT LANC ESTIME"] = dfp[(dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 1) & (dfp["Type d'ordre"] == "ZCOR") & (dfp["OT LANC ESTIME"] == "NON")].groupby("Poste travail princ.")["Ordre"].count()

    # ── Backlog préparation/planification — populations déjà calculées ──
    ano_map["Backlog préparation caractérisé"] = non_prep.groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Backlog planification caractérisé"] = non_plan.groupby("Poste travail princ.")["Ordre"].count()

    ano_map["OT CONFIME"] = dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT CONFIME"] == "NON")].groupby("Poste travail princ.")["Ordre"].count()
    _scope_cor_ano = dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["Type d'ordre"] == "ZCOR")].copy()
    _budget_ano = pd.to_numeric(_scope_cor_ano["Total coûts budgétés"], errors="coerce").fillna(0)
    _reel_ano = pd.to_numeric(_scope_cor_ano["Total coûts réels"], errors="coerce").fillna(0)
    ano_map["OT_COR_EGAL"] = _scope_cor_ano[_budget_ano == _reel_ano].groupby("Poste travail princ.")["Ordre"].count()

    return ano_map


def build_ano_rows(vp: list, ano_map: dict, kpi_list: list, fixed_zero: list = None) -> list:
    """Construit la liste de dicts pour le tableau d'anomalies (Performance ou Qualité)."""
    fixed_zero = fixed_zero or []
    rows = []
    for poste in vp:
        r = {"Poste de travail": poste}
        total = 0
        for kpi in kpi_list:
            if kpi in fixed_zero:
                cnt = 0
            else:
                _raw = ano_map.get(kpi, pd.Series()).get(poste, 0)
                try:
                    _f = float(_raw)
                    cnt = 0 if (pd.isna(_f) or _f == float("inf") or _f == float("-inf")) else int(_f)
                except (TypeError, ValueError):
                    cnt = 0
            r[kpi] = cnt
            total += cnt
        r["Total Anomalies"] = total
        rows.append(r)

    tot = {"Poste de travail": "Total"}
    grand = 0
    for kpi in kpi_list:
        s = sum(r[kpi] for r in rows)
        tot[kpi] = s
        grand += s
    tot["Total Anomalies"] = grand
    rows.append(tot)
    return rows


def build_anomaly_dfs(dfp: pd.DataFrame, avf: pd.DataFrame, now_ts,
                       dfp_toutes_dates: pd.DataFrame = None) -> dict:
    """
    Construit les DataFrames détaillés des anomalies (pour liens
    téléchargement CSV dans le plan d'action).
    """
    dfp_all = dfp_toutes_dates.copy() if dfp_toutes_dates is not None else dfp

    non_prep, non_plan, full_prep, full_plan = _backlogs_non_caracterises(dfp_all, now_ts)

    df_exec_det = build_execution_population(dfp_all, now_ts)

    # Population Avis commune KPI/anomalies.
    # Exclusion systématique ZU/Z4/ZR/ZP.
    avf_zc_det = _avis_hors_types_exclus(
        build_avis_zc_population(avf)
    )

    perf_filt = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))

    return {
        "TAUX_REALISATION_CORRECTIF/PT": dfp[(dfp["Nº appel pl.entret."].fillna(0) == 0) & (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))].copy(),
        # SYNCHRONISÉ avec calcul_kpi.py / build_ano_map.
        "OT préparation <1 mois": full_prep[full_prep["ap"] == "<1 mois"].copy(),
        "OT préparation >3 mois": full_prep[full_prep["ap"] == ">3 mois"].copy(),
        "OT préparation 1mois< <3mois": full_prep[full_prep["ap"] == "1 mois < <3 mois"].copy(),
        "OT planification <1 mois": non_plan[non_plan["alp"] == "<1 mois"].copy(),
        "OT planification >3 mois": non_plan[non_plan["alp"] == ">3 mois"].copy(),
        "OT planification 1mois< <3mois": non_plan[non_plan["alp"] == "1 mois < <3 mois"].copy(),
        # Exécution : MÊME POPULATION que build_ano_map (LANC+SOPL==1,
        # sans filtre Type d'ordre, Type de travail ou date).
        "OT exécution <1 mois": df_exec_det[df_exec_det["aex"] == "<1 mois"].copy(),
        "OT exécution >3 mois": df_exec_det[df_exec_det["aex"] == ">3 mois"].copy(),
        "OT exécution 1mois< <3mois": df_exec_det[df_exec_det["aex"] == "1 mois < <3 mois"].copy(),
        "Performance Graissage": dfp[perf_filt & (dfp["_tw_num"] == 350)].copy(),
        "Performance Inspection": dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        "Performance Systématiques": dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        # Avis : AOUV + APRQ, avec exclusion ZU/Z4/ZR/ZP.
        "Taux d'approbation des Avis": _avis_anomalies_population(avf_zc_det),
        "OT LANC ESTIME": dfp[(dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 1) & (dfp["Type d'ordre"] == "ZCOR") & (dfp["OT LANC ESTIME"] == "NON")].copy(),
        "Backlog préparation caractérisé": non_prep.copy(),
        "Backlog planification caractérisé": non_plan.copy(),
        "OT CONFIME": dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT CONFIME"] == "NON")].copy(),
        "OT_COR_EGAL": (lambda _s: _s[pd.to_numeric(_s["Total coûts budgétés"], errors="coerce").fillna(0) == pd.to_numeric(_s["Total coûts réels"], errors="coerce").fillna(0)])(dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["Type d'ordre"] == "ZCOR")]).copy(),
    }
