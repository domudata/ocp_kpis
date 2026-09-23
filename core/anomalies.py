# -*- coding: utf-8 -*-
import pandas as pd

from core.constants import QK, PK
from core.calcul_kpi import match_exact_token, CODES_PREP_EXACT, CODES_PLAN_EXACT


def _backlogs_non_caracterises(dfp_all: pd.DataFrame, now_ts=None):
    """Reconstruit les populations Backlog préparation/planification.

    Retourne un tuple (non_prep, non_plan, full_prep, full_plan) :
      - non_prep / non_plan : partie NON CARACTERISE (pour Backlog carac KPI).
        Utilise le filtre Date planifiée ≤ now_ts (spec §3/§4).
      - full_prep : TOUS les ZCOR+CRÉÉ SANS filtre date planifiée — pour les
        KPI d'âge préparation ("ap" = depuis "Créé le", disponible même sans
        date planifiée). Sans ce split, les OT sans date planifiée sont exclus
        et tous les KPI d'âge préparation reviennent à 100%.
      - full_plan : ZCOR+LANC+SOPL==0 + Date planifiée ≤ now_ts — pour les
        KPI d'âge planification ("alp" mesure le retard vs date planifiée ;
        seuls les OT dont la date est passée ont un retard calculable).
    """
    zcor = dfp_all[dfp_all["Type d'ordre"] == "ZCOR"].copy()

    # ── Préparation base (CRÉÉ) ──
    _cree_base_filt = (
        zcor["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "CRÉÉ"
    )
    _cree_base = zcor[_cree_base_filt]

    # Backlog prep caractérisé : + filtre date planifiée
    if now_ts is not None:
        _zcor_cree_backlog = _cree_base[_cree_base["Date de début planifiée"] <= now_ts]
    else:
        _zcor_cree_backlog = _cree_base

    if _zcor_cree_backlog.empty:
        non_prep = _zcor_cree_backlog
    else:
        non_prep = _zcor_cree_backlog[~_zcor_cree_backlog["Statut utilisateur"].apply(
            lambda x: match_exact_token(x, CODES_PREP_EXACT)
        )]

    # KPI âge préparation : SANS filtre date planifiée
    full_prep = _cree_base

    # ── Planification base (LANC + SOPL==0) ──
    _lanc_filt = (
        (zcor["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "LANC")
        & (zcor["Contient SOPL"] == 0)
    )
    _lanc_base = zcor[_lanc_filt]

    # Backlog plan caractérisé ET KPI âge plan : + filtre date planifiée
    if now_ts is not None:
        _zcor_lanc_filt = _lanc_base[_lanc_base["Date de début planifiée"] <= now_ts]
    else:
        _zcor_lanc_filt = _lanc_base

    if _zcor_lanc_filt.empty:
        non_plan = _zcor_lanc_filt
    else:
        non_plan = _zcor_lanc_filt[~_zcor_lanc_filt["Statut utilisateur"].apply(
            lambda x: match_exact_token(x, CODES_PLAN_EXACT)
        )]

    # KPI âge planification : SANS filtre date planifiée (synchronisé avec calcul_kpi.py)
    full_plan = _lanc_base

    return non_prep, non_plan, full_prep, full_plan


def build_ano_map(dfp: pd.DataFrame, avf: pd.DataFrame, now_ts,
                   dfp_toutes_dates: pd.DataFrame = None,
                   avf_approve: pd.DataFrame = None) -> dict:
    """
    Construit le dictionnaire ano_map :
    {kpi_name → pd.Series(index=poste, values=nb_anomalies)}

    dfp_toutes_dates : DataFrame OT sans le filtre de période de la barre
    latérale, utilisé UNIQUEMENT pour les deux indicateurs Backlog
    préparation/planification caractérisé (demande explicite). Si non
    fourni, dfp est réutilisé (comportement inchangé).
    avf_approve : DataFrame des avis pour AVIS APPROUVE (spec §20 :
    exclut ACLO + exclut ZU/Z4/ZR/ZP). Si non fourni, avf est réutilisé.
    """
    dfp_all = dfp_toutes_dates.copy() if dfp_toutes_dates is not None else dfp
    _avf_ap = avf_approve if avf_approve is not None else avf

    # ── Populations Backlog préparation/planification — CALCULÉES UNE
    # SEULE FOIS ici, réutilisées à la fois pour l'indicateur Backlog
    # caractérisé ET pour la répartition par âge (SYNCHRONISÉ avec
    # calcul_kpi.py — demande explicite de cohérence KPI / anomalies).
    non_prep, non_plan, full_prep, full_plan = _backlogs_non_caracterises(dfp_all, now_ts)

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
    ano_map["OT préparation <1 mois"] = full_prep[full_prep["ap"] == "<1 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation >3 mois"] = full_prep[full_prep["ap"] == ">3 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation 1mois< <3mois"] = full_prep[full_prep["ap"] == "1 mois < <3 mois"].groupby("Poste travail princ.")["Ordre"].count()

    # ── OT planification <1/1-3/>3 mois — SYNCHRONISÉ avec calcul_kpi.py ──
    ano_map["OT planification <1 mois"] = full_plan[full_plan["alp"] == "<1 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification >3 mois"] = full_plan[full_plan["alp"] == ">3 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification 1mois< <3mois"] = full_plan[full_plan["alp"] == "1 mois < <3 mois"].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["OT exécution <1 mois"] = dfp[exec_filt & (dfp["aex"] == "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution >3 mois"] = dfp[exec_filt & (dfp["aex"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution 1mois< <3mois"] = dfp[exec_filt & (dfp["aex"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["Performance Graissage"] = dfp[perf_filt & (dfp["_tw_num"] == 350)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Inspection"] = dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Systématiques"] = dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()

    # ── AVIS APPROUVE — anomalie = Statut utilisateur == "APRQ" (spec §20) ──
    # Population : avf_approve (exclut ACLO + exclut ZU/Z4/ZR/ZP).
    ano_map["Taux d'approbation des Avis"] = (
        _avf_ap[_avf_ap["Statut utilisateur"].fillna("").str.strip() == "APRQ"]
        .groupby("Poste travail princ.")["Avis"].count()
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
                       dfp_toutes_dates: pd.DataFrame = None,
                       avf_approve: pd.DataFrame = None) -> dict:
    """
    Construit les DataFrames détaillés des anomalies (pour liens
    téléchargement CSV dans le plan d'action).
    avf_approve : population AVIS APPROUVE (spec §20). Rétrocompatible.
    """
    dfp_all = dfp_toutes_dates.copy() if dfp_toutes_dates is not None else dfp
    _avf_ap = avf_approve if avf_approve is not None else avf

    non_prep, non_plan, full_prep, full_plan = _backlogs_non_caracterises(dfp_all, now_ts)

    plan_filt = (dfp["Statut OT"] == "LANC") & (dfp["Statut utilisateur"].str.contains("ATPL", case=False, na=False))
    exec_filt = (dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 1)
    perf_filt = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))

    return {
        "TAUX_REALISATION_CORRECTIF/PT": dfp[(dfp["Nº appel pl.entret."].fillna(0) == 0) & (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))].copy(),
        "OT préparation <1 mois": full_prep[full_prep["ap"] == "<1 mois"].copy(),
        "OT préparation >3 mois": full_prep[full_prep["ap"] == ">3 mois"].copy(),
        "OT préparation 1mois< <3mois": full_prep[full_prep["ap"] == "1 mois < <3 mois"].copy(),
        "OT planification <1 mois": full_plan[full_plan["alp"] == "<1 mois"].copy(),
        "OT planification >3 mois": full_plan[full_plan["alp"] == ">3 mois"].copy(),
        "OT planification 1mois< <3mois": full_plan[full_plan["alp"] == "1 mois < <3 mois"].copy(),
        "OT exécution <1 mois": dfp[exec_filt & (dfp["aex"] == "<1 mois")].copy(),
        "OT exécution >3 mois": dfp[exec_filt & (dfp["aex"] == ">3 mois")].copy(),
        "OT exécution 1mois< <3mois": dfp[exec_filt & (dfp["aex"] == "1 mois < <3 mois")].copy(),
        "Performance Graissage": dfp[perf_filt & (dfp["_tw_num"] == 350)].copy(),
        "Performance Inspection": dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        "Performance Systématiques": dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        # Anomalies AVIS APPROUVE = avis en statut APRQ (spec §20)
        "Taux d'approbation des Avis": _avf_ap[_avf_ap["Statut utilisateur"].fillna("").str.strip() == "APRQ"].copy(),
        "OT LANC ESTIME": dfp[(dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 1) & (dfp["Type d'ordre"] == "ZCOR") & (dfp["OT LANC ESTIME"] == "NON")].copy(),
        "Backlog préparation caractérisé": non_prep.copy(),
        "Backlog planification caractérisé": non_plan.copy(),
        "OT CONFIME": dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT CONFIME"] == "NON")].copy(),
        "OT_COR_EGAL": (lambda _s: _s[pd.to_numeric(_s["Total coûts budgétés"], errors="coerce").fillna(0) == pd.to_numeric(_s["Total coûts réels"], errors="coerce").fillna(0)])(dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["Type d'ordre"] == "ZCOR")]).copy(),
    }

