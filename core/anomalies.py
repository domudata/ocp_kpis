# -*- coding: utf-8 -*-
import pandas as pd

from core.constants import QK, PK
from core.calcul_kpi import match_exact_token, CODES_PREP_EXACT, CODES_PLAN_EXACT


def _backlogs_non_caracterises(dfp_all: pd.DataFrame):
    """Reconstruit les deux populations NON CARACTERISE (préparation et
    planification) selon la logique convenue :
      - Préparation  : ZCOR ET Statut système == CRÉÉ
      - Planification: ZCOR ET Statut système == LANC ET Contient SOPL == 0
    Correspondance EXACTE (aucune addition avant/après le code).

    Retourne les DataFrames complets (avec colonnes ap/alp intactes), afin
    que le module appelant puisse aussi bien compter le total (indicateur
    Backlog caractérisé) que répartir par âge (indicateurs OT préparation/
    planification <1/1-3/>3 mois) — EXACTEMENT la même population utilisée
    dans calcul_kpi.py pour ces deux familles d'indicateurs."""
    zcor = dfp_all[dfp_all["Type d'ordre"] == "ZCOR"].copy()

    zcor_cree = zcor[
        zcor["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "CRÉÉ"
    ]
    non_prep = zcor_cree[~zcor_cree["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PREP_EXACT))]

    zcor_lanc = zcor[
        (zcor["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "LANC")
        & (zcor["Contient SOPL"] == 0)
    ]
    non_plan = zcor_lanc[~zcor_lanc["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT))]
    return non_prep, non_plan


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
    non_prep, non_plan = _backlogs_non_caracterises(dfp_all)

    plan_filt = (dfp["Statut OT"] == "LANC") & (dfp["Statut utilisateur"].str.contains("ATPL", case=False, na=False))
    exec_filt = (dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 1)
    perf_filt = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))

    ano_map = {}

    ano_map["TAUX_REALISATION_CORRECTIF/PT"] = (
        dfp[(dfp["Nº appel pl.entret."].fillna(0) == 0)
            & (dfp["Contient SOPL"] == 1)
            & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))]
        .groupby("Poste travail princ.")["Ordre"].count()
    )

    # ── OT préparation <1/1-3/>3 mois — SYNCHRONISÉ avec calcul_kpi.py ──
    # Base = non_prep (NON CARACTERISE du Backlog préparation), pas
    # l'ancien périmètre indépendant (Statut OT=CRÉÉ + contient CRPR).
    ano_map["OT préparation <1 mois"] = non_prep[non_prep["ap"] != "<1 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation >3 mois"] = non_prep[non_prep["ap"] == ">3 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation 1mois< <3mois"] = non_prep[non_prep["ap"] == "1 mois < <3 mois"].groupby("Poste travail princ.")["Ordre"].count()

    # ── OT planification <1/1-3/>3 mois — SYNCHRONISÉ avec calcul_kpi.py ──
    # Base = non_plan (NON CARACTERISE du Backlog planification).
    ano_map["OT planification <1 mois"] = non_plan[non_plan["alp"] != "<1 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification >3 mois"] = non_plan[non_plan["alp"] == ">3 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification 1mois< <3mois"] = non_plan[non_plan["alp"] == "1 mois < <3 mois"].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["OT exécution <1 mois"] = dfp[exec_filt & (dfp["aex"] != "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution >3 mois"] = dfp[exec_filt & (dfp["aex"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution 1mois< <3mois"] = dfp[exec_filt & (dfp["aex"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["Performance Graissage"] = dfp[perf_filt & (dfp["_tw_num"] == 350)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Inspection"] = dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Systématiques"] = dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()

    # NOTE : filtre ZU/Z4/ZR/ZP retiré (voir calcul_kpi.py) — avf est déjà
    # restreint à ces types en amont dans prepare_data.py.
    avf_tot = avf.groupby("Poste travail princ.")["Avis"].count()
    avf_aprv = avf[avf["Statut utilisateur"].isin(["APRV", "APRV AVAU"])].groupby("Poste travail princ.")["Avis"].count()
    ano_map["Taux d'approbation des Avis"] = avf_tot.sub(avf_aprv, fill_value=0)

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
            cnt = 0 if kpi in fixed_zero else int(ano_map.get(kpi, pd.Series()).get(poste, 0))
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

    non_prep, non_plan = _backlogs_non_caracterises(dfp_all)

    plan_filt = (dfp["Statut OT"] == "LANC") & (dfp["Statut utilisateur"].str.contains("ATPL", case=False, na=False))
    exec_filt = (dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 1)
    perf_filt = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))

    avf_filtre = avf[~avf["Type d'avis"].isin(["ZU", "Z4", "ZR", "ZP"])] if "Type d'avis" in avf.columns else avf

    return {
        "TAUX_REALISATION_CORRECTIF/PT": dfp[(dfp["Nº appel pl.entret."].fillna(0) == 0) & (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))].copy(),
        # SYNCHRONISÉ avec calcul_kpi.py / build_ano_map : base = NON CARACTERISE.
        "OT préparation <1 mois": non_prep[non_prep["ap"] != "<1 mois"].copy(),
        "OT préparation >3 mois": non_prep[non_prep["ap"] == ">3 mois"].copy(),
        "OT préparation 1mois< <3mois": non_prep[non_prep["ap"] == "1 mois < <3 mois"].copy(),
        "OT planification <1 mois": non_plan[non_plan["alp"] != "<1 mois"].copy(),
        "OT planification >3 mois": non_plan[non_plan["alp"] == ">3 mois"].copy(),
        "OT planification 1mois< <3mois": non_plan[non_plan["alp"] == "1 mois < <3 mois"].copy(),
        "OT exécution <1 mois": dfp[exec_filt & (dfp["aex"] != "<1 mois")].copy(),
        "OT exécution >3 mois": dfp[exec_filt & (dfp["aex"] == ">3 mois")].copy(),
        "OT exécution 1mois< <3mois": dfp[exec_filt & (dfp["aex"] == "1 mois < <3 mois")].copy(),
        "Performance Graissage": dfp[perf_filt & (dfp["_tw_num"] == 350)].copy(),
        "Performance Inspection": dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        "Performance Systématiques": dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        "Taux d'approbation des Avis": avf_filtre[~avf_filtre["Statut utilisateur"].isin(["APRV", "APRV AVAU"])].copy(),
        "OT LANC ESTIME": dfp[(dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 1) & (dfp["Type d'ordre"] == "ZCOR") & (dfp["OT LANC ESTIME"] == "NON")].copy(),
        "Backlog préparation caractérisé": non_prep.copy(),
        "Backlog planification caractérisé": non_plan.copy(),
        "OT CONFIME": dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT CONFIME"] == "NON")].copy(),
        "OT_COR_EGAL": (lambda _s: _s[pd.to_numeric(_s["Total coûts budgétés"], errors="coerce").fillna(0) == pd.to_numeric(_s["Total coûts réels"], errors="coerce").fillna(0)])(dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["Type d'ordre"] == "ZCOR")]).copy(),
    }
