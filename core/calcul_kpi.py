# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np  # Indispensable pour np.abs
from core.constants import QK, PK

TW_PREV = [350, 290, 300, 310, 360]
CRPR_KW = ['ATPD','ATMR','ATRS','ATMO','ATER']
ATPL_KW = ['ATEI','ATAL','ATAS','AGAR','ATHS']


def build_ano_map(dfp: pd.DataFrame, avf: pd.DataFrame, now_ts) -> dict:

    ano_map = {}
    
    # Préparation des motifs regex à partir des constantes
    pat_crpr_kw = '|'.join(CRPR_KW)
    pat_atpl_kw = '|'.join(ATPL_KW)

    # ── 1. TAUX REALISATION CORRECTIF ───────────────────────────────────
    ano_map["TAUX_REALISATION_CORRECTIF/PT"] = dfp[
        dfp["is_correctif"] &
        (dfp["Contient SOPL"] == 1) &
        (~dfp["Statut OT"].isin(["CLOT","TCLO"]))
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── 2/3/4. AGE PREP ─────────────────────────────────────────────────
    filt_prep = (
        (dfp["Statut OT"] == "CRÉÉ") &
        (dfp["Backlog preparation"] == "NON CARACTERISE")
    )
    ano_map["OT préparation <1 mois"]       = dfp[filt_prep & (dfp["ap"] == "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation 1mois< <3mois"] = dfp[filt_prep & (dfp["ap"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation >3 mois"]       = dfp[filt_prep & (dfp["ap"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    # ── 5/6/7. AGE PLAN ─────────────────────────────────────────────────
    filt_plan = (
        (dfp["Statut OT"] == "LANC") &
        (dfp["Contient SOPL"] == 0) &
        (dfp["Backlog planification"] == "NON CARACTERISE")
    )
    ano_map["OT planification <1 mois"]      = dfp[filt_plan & (dfp["alp"] == "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification 1mois< <3mois"] = dfp[filt_plan & (dfp["alp"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification >3 mois"]       = dfp[filt_plan & (dfp["alp"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    # ── 8/9/10. AGE EXEC ────────────────────────────────────────────────
    filt_exec = (
        (dfp["Statut OT"] == "LANC") &
        (dfp["Contient SOPL"] == 1)
    )
    ano_map["OT exécution <1 mois"]          = dfp[filt_exec & (dfp["aex"] == "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution 1mois< <3mois"]    = dfp[filt_exec & (dfp["aex"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution >3 mois"]          = dfp[filt_exec & (dfp["aex"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    # ── 11/12/13. PERFORMANCE PREVENTIF ─────────────────────────────────
    filt_perf = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT","TCLO"]))

    ano_map["Performance Graissage"]     = dfp[filt_perf & (dfp["_tw_num"]==350)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Inspection"]    = dfp[filt_perf & (dfp["_tw_num"].isin([290,300,310])) & (dfp["Date de début planifiée"]<=now_ts)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Systématiques"] = dfp[filt_perf & (dfp["_tw_num"]==360) & (dfp["Date de début planifiée"]<=now_ts)].groupby("Poste travail princ.")["Ordre"].count()

    # ── 14. TAUX APPROBATION AVIS ────────────────────────────────────────
    ano_map["Taux d'approbation des Avis"] = (
        avf[avf["Statut utilisateur"] == "APRQ"]
        .groupby("Poste travail princ.")["Avis"].count()
    )

    # ── 15. OT LANC ESTIME ───────────────────────────────────────────────
    ano_map["OT LANC ESTIME"] = dfp[
        dfp["is_correctif"] &
        (dfp["Statut OT"] == "LANC") &
        (dfp["Contient SOPL"] == 0) &
        (dfp["OT LANC ESTIME"] == "NON")
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── 16. BACKLOG PREP CARACTERISE ─────────────────────────────────────
    _df_prep_base = dfp[
        (dfp["Statut OT"] == "CRÉÉ") &
        (~dfp["is_correctif"])
    ]
    ano_map["Backlog préparation caractérisé"] = _df_prep_base[
        ~_df_prep_base["Statut utilisateur"].str.contains(pat_crpr_kw, na=False)
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── 17. BACKLOG PLAN CARACTERISE ─────────────────────────────────────
    _df_plan_base = dfp[
        (~dfp["is_correctif"]) &
        (dfp["Statut OT"] == "LANC") &
        (dfp["Contient SOPL"] == 0)
    ]
    ano_map["Backlog planification caractérisé"] = _df_plan_base[
        ~_df_plan_base["Statut utilisateur"].str.contains(pat_atpl_kw, na=False)
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── 18. OT CONFIME ───────────────────────────────────────────────────
    ano_map["OT CONFIME"] = dfp[
        dfp["Statut OT"].isin(["CLOT","TCLO"]) &
        (dfp["OT CONFIME"] == "NON")
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── 19. OT_COR_EGAL ──────────────────────────────────────────────────
    # Anomalie = Plan==0 + CLOT+TCLO + CONF + |bud-reel| < 1 (quasi identiques)
    _sub_cor = dfp[
        dfp["is_correctif"] &
        dfp["Statut OT"].isin(["CLOT","TCLO"]) &
        dfp["Statut système"].str.contains("CONF", na=False)
    ]
    
    # CONVERSION EXPLICITE EN FLOAT (essentiel pour les uls mathématiques)
    _bud_c  = pd.to_numeric(_sub_cor["Total coûts budgétés"], errors="coerce")
    _reel_c = pd.to_numeric(_sub_cor["Total coûts réels"], errors="coerce")
    
    # Logique inverse du KPI : KPI "Bon" si >= 1, donc Anomalie si < 1
    # Note: Les NaN (données manquantes) seront logiquement inclus dans les anomalies
    _is_anomaly = ~(_bud_c.sub(_reel_c).abs() >= 1)
    
    ano_map["OT_COR_EGAL"] = _sub_cor[_is_anomaly].groupby(
        "Poste travail princ.")["Ordre"].count()

    return ano_map


def build_ano_rows(vp, ano_map, kpi_list, fixed_zero=None):
    fixed_zero = fixed_zero or []
    rows = []
    for poste in vp:
        r = {"Poste de travail": poste}
        total = 0
        for kpi in kpi_list:
            cnt = 0 if kpi in fixed_zero else int(
                ano_map.get(kpi, pd.Series()).get(poste, 0)
            )
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


def build_anomaly_dfs(dfp, avf, now_ts):
    filt_prep = (dfp["Statut OT"]=="CRÉÉ") & (dfp["Backlog preparation"]=="NON CARACTERISE")
    filt_plan = (dfp["Statut OT"]=="LANC") & (dfp["Contient SOPL"]==0) & (dfp["Backlog planification"]=="NON CARACTERISE")
    filt_exec = (dfp["Statut OT"]=="LANC") & (dfp["Contient SOPL"]==1)
    filt_perf = (dfp["Contient SOPL"]==1) & (~dfp["Statut OT"].isin(["CLOT","TCLO"]))

    # ul spécifique pour OT_COR_EGAL avec CONVERSION EN FLOAT
    _df_cor_base = dfp[
        dfp["is_correctif"] &
        dfp["Statut OT"].isin(["CLOT","TCLO"]) &
        dfp["Statut système"].str.contains("CONF", na=False)
    ].copy()
    
    # CONVERSION EXPLICITE EN FLOAT AVANT LE UL DE L'ECART
    _bud_c  = pd.to_numeric(_df_cor_base["Total coûts budgétés"], errors="coerce")
    _reel_c = pd.to_numeric(_df_cor_base["Total coûts réels"], errors="coerce")
    _is_anomaly = ~(_bud_c.sub(_reel_c).abs() >= 1)
    _ano_cor_egal = _df_cor_base[_is_anomaly].copy()

    # Utilisation des constantes pour les mots-clés
    pat_crpr_kw = '|'.join(CRPR_KW)
    pat_atpl_kw = '|'.join(ATPL_KW)

    return {
        "TAUX_REALISATION_CORRECTIF/PT":     dfp[dfp["is_correctif"] & (dfp["Contient SOPL"]==1) & (~dfp["Statut OT"].isin(["CLOT","TCLO"]))].copy(),
        "OT préparation <1 mois":            dfp[filt_prep & (dfp["ap"] == "<1 mois")].copy(),
        "OT préparation >3 mois":            dfp[filt_prep & (dfp["ap"] == ">3 mois")].copy(),
        "OT préparation 1mois< <3mois":      dfp[filt_prep & (dfp["ap"] == "1 mois < <3 mois")].copy(),
        "OT planification <1 mois":          dfp[filt_plan & (dfp["alp"] == "<1 mois")].copy(),
        "OT planification >3 mois":          dfp[filt_plan & (dfp["alp"] == ">3 mois")].copy(),
        "OT planification 1mois< <3mois":    dfp[filt_plan & (dfp["alp"] == "1 mois < <3 mois")].copy(),
        "OT exécution <1 mois":              dfp[filt_exec & (dfp["aex"] == "<1 mois")].copy(),
        "OT exécution >3 mois":              dfp[filt_exec & (dfp["aex"] == ">3 mois")].copy(),
        "OT exécution 1mois< <3mois":        dfp[filt_exec & (dfp["aex"] == "1 mois < <3 mois")].copy(),
        "Performance Graissage":             dfp[filt_perf & (dfp["_tw_num"]==350)].copy(),
        "Performance Inspection":            dfp[filt_perf & (dfp["_tw_num"].isin([290,300,310])) & (dfp["Date de début planifiée"]<=now_ts)].copy(),
        "Performance Systématiques":         dfp[filt_perf & (dfp["_tw_num"]==360) & (dfp["Date de début planifiée"]<=now_ts)].copy(),
        "Taux d'approbation des Avis":       avf[avf["Statut utilisateur"]=="APRQ"].copy(),
        "OT LANC ESTIME":                    dfp[dfp["is_correctif"] & (dfp["Statut OT"]=="LANC") & (dfp["Contient SOPL"]==0) & (dfp["OT LANC ESTIME"]=="NON")].copy(),
        "Backlog préparation caractérisé":   dfp[(dfp["Statut OT"]=="CRÉÉ") & (~dfp["is_correctif"]) & ~dfp["Statut utilisateur"].str.contains(pat_crpr_kw, na=False)].copy(),
        "Backlog planification caractérisé": dfp[(~dfp["is_correctif"]) & (dfp["Statut OT"]=="LANC") & (dfp["Contient SOPL"]==0) & ~dfp["Statut utilisateur"].str.contains(pat_atpl_kw, na=False)].copy(),
        "OT CONFIME":                        dfp[dfp["Statut OT"].isin(["CLOT","TCLO"]) & (dfp["OT CONFIME"]=="NON")].copy(),
        "OT_COR_EGAL":                       _ano_cor_egal,  # Utilisation de la dataframe filtrée avec les floats
    }
