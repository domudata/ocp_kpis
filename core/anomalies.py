# -*- coding: utf-8 -*-
import re
import pandas as pd

from core.constants import QK, PK

CODES_PREP_EXACT = {"ATPD", "ATMR", "ATER", "ATRS", "ATMO"}
CODES_PLAN_EXACT = {"ATPL", "ATEI", "ATAL", "ATAS", "AGAR", "ATHS"}
ALL_CARAC_EXACT = CODES_PREP_EXACT | CODES_PLAN_EXACT


def match_exact_token(statut, codes: set) -> bool:
    if statut is None or (isinstance(statut, float) and pd.isna(statut)):
        return False
    words = set(re.findall(r'[A-Za-z0-9]+', str(statut).upper()))
    return bool(words & codes)



def _backlogs_populations(dfp_all: pd.DataFrame):
    """Reconstruit les populations Backlog (préparation, planification, exécution) :
      - zcor_cree     : ZCOR ET Statut système == CRÉÉ (base totale préparation)
      - non_prep      : non caractérisé préparation
      - zcor_lanc     : ZCOR ET Statut système == LANC ET Contient SOPL == 0 (base totale planification)
      - non_plan      : non caractérisé planification
      - zcor_plan_age : ZCOR ET Statut système == LANC ET Statut utilisateur ATPL (stock planification par âge)
      - zcor_exec     : ZCOR ET Statut système == LANC (non clôturé) ET Statut utilisateur SOPL (stock exécution par âge)
    """
    zcor = dfp_all[dfp_all["Type d'ordre"] == "ZCOR"].copy()

    zcor_cree = zcor[
        zcor["Statut système"].fillna("").astype(str).str.strip().str.split().str[0].isin(["CRÉÉ", "CREE"])
    ].copy()
    non_prep = zcor_cree[~zcor_cree["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PREP_EXACT))].copy()

    zcor_lanc = zcor[
        (zcor["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "LANC")
        & (zcor["Contient SOPL"] == 0)
    ].copy()
    non_plan = zcor_lanc[~zcor_lanc["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT))].copy()

    # Planification par âge : LANC + ATPL (définition officielle OCP)
    _contient_atpl = (
        zcor_lanc["Statut utilisateur"].fillna("").astype(str).str.contains("ATPL", case=False, na=False)
        | zcor_lanc["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT))
    )
    zcor_plan_age = zcor_lanc[_contient_atpl].copy()

    # Exécution par âge : LANC + SOPL (définition officielle OCP)
    _statut_lanc_ex = (
        (zcor["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "LANC")
        | (zcor["Statut système"].fillna("").astype(str).str.contains("LANC", na=False)
           & ~zcor["Statut système"].fillna("").astype(str).str.contains("CLOT|TCLO", na=False))
    )
    _non_clot_ex = ~zcor["Statut OT"].isin(["CLOT", "TCLO"]) if "Statut OT" in zcor.columns else True
    _contient_sopl_ex = (
        (zcor["Contient SOPL"] == 1) if "Contient SOPL" in zcor.columns
        else zcor["Statut utilisateur"].fillna("").astype(str).str.contains("SOPL", case=False, na=False)
    )
    zcor_exec = zcor[_statut_lanc_ex & _non_clot_ex & _contient_sopl_ex].copy()

    return zcor_cree, non_prep, zcor_lanc, non_plan, zcor_exec, zcor_plan_age


def _backlogs_non_caracterises(dfp_all: pd.DataFrame):
    _, non_prep, _, non_plan, _, _ = _backlogs_populations(dfp_all)
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

    # ── Populations Backlog préparation/planification (SYNCHRONISÉ avec calcul_kpi.py)
    zcor_cree, non_prep, zcor_lanc, non_plan, zcor_exec, zcor_plan_age = _backlogs_populations(dfp_all)

    _statut_lanc_ano = dfp["Statut système"].fillna("").astype(str).str.contains("LANC", na=False) | (dfp["Statut OT"] == "LANC")
    plan_filt = (dfp["Statut OT"] == "LANC") & (dfp["Statut utilisateur"].str.contains("ATPL", case=False, na=False))
    perf_filt = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))

    ano_map = {}

    ano_map["TAUX_REALISATION_CORRECTIF/PT"] = (
        dfp[(dfp["Nº appel pl.entret."].fillna(0) == 0)
            & (dfp["Contient SOPL"] == 1)
            & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))]
        .groupby("Poste travail princ.")["Ordre"].count()
    )

    # ── Populations postes pour initialiser les séries vides ──
    _all_posts = dfp["Poste travail princ."].dropna().unique() if "Poste travail princ." in dfp.columns else []

    # ── OT préparation <1/1-3/>3 mois — SUR LE BACKLOG COMPLET PRÉPARATION (zcor_cree) ──
    # Cible <1 mois >= 80%. Les anomalies indiquent l'inverse : OT dont l'âge dépasse 1 mois (>= 1 mois).
    ano_map["OT préparation <1 mois"] = zcor_cree[zcor_cree["ap"].isin(["1 mois < <3 mois", ">3 mois"])].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation 1mois< <3mois"] = zcor_cree[zcor_cree["ap"] == "1 mois < <3 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation >3 mois"] = zcor_cree[zcor_cree["ap"] == ">3 mois"].groupby("Poste travail princ.")["Ordre"].count()

    # ── OT planification <1/1-3/>3 mois — SUR LE STOCK PLANIFICATION (zcor_plan_age : LANC + ATPL) ──
    ano_map["OT planification <1 mois"] = zcor_plan_age[zcor_plan_age["alp"].isin(["1 mois < <3 mois", ">3 mois"])].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification 1mois< <3mois"] = zcor_plan_age[zcor_plan_age["alp"] == "1 mois < <3 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification >3 mois"] = zcor_plan_age[zcor_plan_age["alp"] == ">3 mois"].groupby("Poste travail princ.")["Ordre"].count()

    # ── OT exécution <1/1-3/>3 mois (zcor_exec : LANC + SOPL) ──
    ano_map["OT exécution <1 mois"] = zcor_exec[zcor_exec["aex"].isin(["1 mois < <3 mois", ">3 mois"])].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution 1mois< <3mois"] = zcor_exec[zcor_exec["aex"] == "1 mois < <3 mois"].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution >3 mois"] = zcor_exec[zcor_exec["aex"] == ">3 mois"].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["Performance Graissage"] = dfp[perf_filt & (dfp["_tw_num"] == 350)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Inspection"] = dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Systématiques"] = dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()

    # Taux d'approbation des Avis (exclusion ACLO)
    _non_aclo = pd.Series(True, index=avf.index)
    if "Statut système" in avf.columns:
        _non_aclo = _non_aclo & ~avf["Statut système"].fillna("").astype(str).str.contains("ACLO", case=False, na=False)
    if "Statut utilisateur" in avf.columns:
        _non_aclo = _non_aclo & ~avf["Statut utilisateur"].fillna("").astype(str).str.contains("ACLO", case=False, na=False)
    avf_active = avf[_non_aclo]
    avf_tot = avf_active.groupby("Poste travail princ.")["Avis"].count()
    avf_aprv = avf_active[avf_active["Statut utilisateur"].isin(["APRV", "APRV AVAU"])].groupby("Poste travail princ.")["Avis"].count()
    ano_map["Taux d'approbation des Avis"] = avf_tot.sub(avf_aprv, fill_value=0)

    # OT LANC ESTIME : contient LANC, type ZCOR, et Total coûts budgétés == 0 (anomalie)
    _lanc_estime_ano = _statut_lanc_ano & (dfp["Type d'ordre"] == "ZCOR") & (dfp["OT LANC ESTIME"] == "NON")
    ano_map["OT LANC ESTIME"] = dfp[_lanc_estime_ano].groupby("Poste travail princ.")["Ordre"].count()

    # ── Backlog préparation/planification — populations déjà calculées ──
    ano_map["Backlog préparation caractérisé"] = non_prep.groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Backlog planification caractérisé"] = non_plan.groupby("Poste travail princ.")["Ordre"].count()

    ano_map["OT CONFIME"] = dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT CONFIME"] == "NON")].groupby("Poste travail princ.")["Ordre"].count()
    _statut_clot_tclo = dfp["Statut OT"].isin(["CLOT", "TCLO"]) | dfp["Statut système"].str.contains("CLOT|TCLO", na=False)
    _scope_cor_ano = dfp[_statut_clot_tclo & (dfp["Type d'ordre"] == "ZCOR")].copy()
    _budget_ano = pd.to_numeric(_scope_cor_ano["Total coûts budgétés"], errors="coerce").fillna(0)
    _reel_ano = pd.to_numeric(_scope_cor_ano["Total coûts réels"], errors="coerce").fillna(0)
    _is_ano_cor = (_budget_ano == _reel_ano) | (_reel_ano <= 0)
    ano_map["OT_COR_EGAL"] = _scope_cor_ano[_is_ano_cor].groupby("Poste travail princ.")["Ordre"].count()

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

    zcor_cree, non_prep, zcor_lanc, non_plan, zcor_exec, zcor_plan_age = _backlogs_populations(dfp_all)

    _statut_lanc_ano = dfp["Statut système"].fillna("").astype(str).str.contains("LANC", na=False) | (dfp["Statut OT"] == "LANC")
    plan_filt = (dfp["Statut OT"] == "LANC") & (dfp["Statut utilisateur"].str.contains("ATPL", case=False, na=False))
    perf_filt = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))
    _lanc_estime_ano = _statut_lanc_ano & (dfp["Type d'ordre"] == "ZCOR") & (dfp["OT LANC ESTIME"] == "NON")
    return {
        "TAUX_REALISATION_CORRECTIF/PT": dfp[(dfp["Nº appel pl.entret."].fillna(0) == 0) & (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))].copy(),
        # Anomalies <1 mois = inverse du KPI = OT dont l'âge dépasse 1 mois (>= 1 mois)
        "OT préparation <1 mois": zcor_cree[zcor_cree["ap"].isin(["1 mois < <3 mois", ">3 mois"])].copy(),
        "OT préparation 1mois< <3mois": zcor_cree[zcor_cree["ap"] == "1 mois < <3 mois"].copy(),
        "OT préparation >3 mois": zcor_cree[zcor_cree["ap"] == ">3 mois"].copy(),
        "OT planification <1 mois": zcor_plan_age[zcor_plan_age["alp"].isin(["1 mois < <3 mois", ">3 mois"])].copy(),
        "OT planification 1mois< <3mois": zcor_plan_age[zcor_plan_age["alp"] == "1 mois < <3 mois"].copy(),
        "OT planification >3 mois": zcor_plan_age[zcor_plan_age["alp"] == ">3 mois"].copy(),
        "OT exécution <1 mois": zcor_exec[zcor_exec["aex"].isin(["1 mois < <3 mois", ">3 mois"])].copy(),
        "OT exécution 1mois< <3mois": zcor_exec[zcor_exec["aex"] == "1 mois < <3 mois"].copy(),
        "OT exécution >3 mois": zcor_exec[zcor_exec["aex"] == ">3 mois"].copy(),
        "Performance Graissage": dfp[perf_filt & (dfp["_tw_num"] == 350)].copy(),
        "Performance Inspection": dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        "Performance Systématiques": dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        "Taux d'approbation des Avis": (
            lambda _a: _a[
                ~_a["Statut utilisateur"].isin(["APRV", "APRV AVAU"])
                & (~_a["Statut système"].fillna("").astype(str).str.contains("ACLO", case=False, na=False)
                   if "Statut système" in _a.columns else True)
                & (~_a["Statut utilisateur"].fillna("").astype(str).str.contains("ACLO", case=False, na=False)
                   if "Statut utilisateur" in _a.columns else True)
            ]
        )(avf).copy(),
        "OT LANC ESTIME": dfp[_lanc_estime_ano].copy(),
        "Backlog préparation caractérisé": non_prep.copy(),
        "Backlog planification caractérisé": non_plan.copy(),
        "OT CONFIME": dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT CONFIME"] == "NON")].copy(),
        "OT_COR_EGAL": (lambda _s: _s[(pd.to_numeric(_s["Total coûts budgétés"], errors="coerce").fillna(0) == pd.to_numeric(_s["Total coûts réels"], errors="coerce").fillna(0)) | (pd.to_numeric(_s["Total coûts réels"], errors="coerce").fillna(0) <= 0)])(dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"]) | dfp["Statut système"].str.contains("CLOT|TCLO", na=False)) & (dfp["Type d'ordre"] == "ZCOR")]).copy(),
    }
