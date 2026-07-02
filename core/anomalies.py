# -*- coding: utf-8 -*-
import pandas as pd

from core.constants import QK, PK


def build_ano_map(dfp: pd.DataFrame, avf: pd.DataFrame, now_ts) -> dict:

    prep_filt = (dfp["Statut OT"] == "CRÉÉ") & (dfp["Statut utilisateur"].str.contains("CRPR", na=False))
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

    ano_map["OT préparation <1 mois"]       = dfp[prep_filt & (dfp["ap"] != "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation >3 mois"]        = dfp[prep_filt & (dfp["ap"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation 1mois< <3mois"]  = dfp[prep_filt & (dfp["ap"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["OT planification <1 mois"]      = dfp[plan_filt & (dfp["alp"] != "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification >3 mois"]       = dfp[plan_filt & (dfp["alp"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification 1mois< <3mois"] = dfp[plan_filt & (dfp["alp"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["OT exécution <1 mois"]          = dfp[exec_filt & (dfp["aex"] != "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution >3 mois"]           = dfp[exec_filt & (dfp["aex"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution 1mois< <3mois"]     = dfp[exec_filt & (dfp["aex"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["Performance Graissage"]     = dfp[perf_filt & (dfp["_tw_num"] == 350)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Inspection"]    = dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Systématiques"] = dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()

    # ── Taux approbation avis : anomalie = avis APRQ ou REJT uniquement ──
    ano_map["Taux d'approbation des Avis"] = (
        avf[avf["Statut utilisateur"].isin(["APRQ", "REJT"])]
        .groupby("Poste travail princ.")["Avis"].count()
    )

    ano_map["OT LANC ESTIME"] = dfp[(dfp["Statut OT"] == "LANC") & (dfp["OT LANC ESTIME"] == "NON")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Backlog préparation caractérisé"]   = dfp[(dfp["Statut OT"] == "CRÉÉ") & (dfp["Backlog preparation"] == "NON CARACTERISE")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Backlog planification caractérisé"] = dfp[(dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 0) & (dfp["Backlog planification"] == "NON CARACTERISE")].groupby("Poste travail princ.")["Ordre"].count()

    # ── OT CONFIME : anomalie = clôturés NON confirmés ──
    ano_map["OT CONFIME"] = dfp[
        (dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT CONFIME"] == "NON")
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── OT_COR_EGAL : anomalie = clôturés où coûts réels ≠ budgétés ──
    ano_map["OT_COR_EGAL"] = dfp[
        (dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT_COR_EGAL"] == "NON")
    ].groupby("Poste travail princ.")["Ordre"].count()

    return ano_map


def build_ano_rows(vp: list, ano_map: dict, kpi_list: list, fixed_zero: list = None) -> list:
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


def build_anomaly_dfs(dfp: pd.DataFrame, avf: pd.DataFrame, now_ts) -> dict:
    prep_filt = (dfp["Statut OT"] == "CRÉÉ") & (dfp["Statut utilisateur"].str.contains("CRPR", na=False))
    plan_filt = (dfp["Statut OT"] == "LANC") & (dfp["Statut utilisateur"].str.contains("ATPL", case=False, na=False))
    exec_filt = (dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 1)
    perf_filt = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))

    return {
        "TAUX_REALISATION_CORRECTIF/PT":      dfp[(dfp["Nº appel pl.entret."].fillna(0) == 0) & (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))].copy(),
        "OT préparation <1 mois":             dfp[prep_filt & (dfp["ap"] != "<1 mois")].copy(),
        "OT préparation >3 mois":             dfp[prep_filt & (dfp["ap"] == ">3 mois")].copy(),
        "OT préparation 1mois< <3mois":       dfp[prep_filt & (dfp["ap"] == "1 mois < <3 mois")].copy(),
        "OT planification <1 mois":           dfp[plan_filt & (dfp["alp"] != "<1 mois")].copy(),
        "OT planification >3 mois":           dfp[plan_filt & (dfp["alp"] == ">3 mois")].copy(),
        "OT planification 1mois< <3mois":     dfp[plan_filt & (dfp["alp"] == "1 mois < <3 mois")].copy(),
        "OT exécution <1 mois":               dfp[exec_filt & (dfp["aex"] != "<1 mois")].copy(),
        "OT exécution >3 mois":               dfp[exec_filt & (dfp["aex"] == ">3 mois")].copy(),
        "OT exécution 1mois< <3mois":         dfp[exec_filt & (dfp["aex"] == "1 mois < <3 mois")].copy(),
        "Performance Graissage":              dfp[perf_filt & (dfp["_tw_num"] == 350)].copy(),
        "Performance Inspection":             dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        "Performance Systématiques":          dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        # ── Corrections ──
        "Taux d'approbation des Avis":        avf[avf["Statut utilisateur"].isin(["APRQ", "REJT"])].copy(),
        "OT LANC ESTIME":                     dfp[(dfp["Statut OT"] == "LANC") & (dfp["OT LANC ESTIME"] == "NON")].copy(),
        "Backlog préparation caractérisé":    dfp[(dfp["Statut OT"] == "CRÉÉ") & (dfp["Backlog preparation"] == "NON CARACTERISE")].copy(),
        "Backlog planification caractérisé":  dfp[(dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 0) & (dfp["Backlog planification"] == "NON CARACTERISE")].copy(),
        "OT CONFIME":                         dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT CONFIME"] == "NON")].copy(),
        "OT_COR_EGAL":                        dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT_COR_EGAL"] == "NON")].copy(),
    }
