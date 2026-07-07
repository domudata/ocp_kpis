# -*- coding: utf-8 -*-
import pandas as pd
from core.constants import QK, PK

TW_PREV = [350, 290, 300, 310, 360]
CRPR_KW = ['ATPD','ATMR','ATRS','ATMO','ATER']
ATPL_KW = ['ATEI','ATAL','ATAS','AGAR','ATHS']


def build_ano_map(dfp: pd.DataFrame, avf: pd.DataFrame, now_ts) -> dict:

    ano_map = {}

    # ── 1. TAUX REALISATION CORRECTIF ───────────────────────────────────
    # Anomalie = OT correctifs (Plan==0+SOPL) non clôturés
    ano_map["TAUX_REALISATION_CORRECTIF/PT"] = dfp[
        dfp["is_correctif"] &
        (dfp["Contient SOPL"] == 1) &
        (~dfp["Statut OT"].isin(["CLOT","TCLO"]))
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── 2/3/4. AGE PREP ─────────────────────────────────────────────────
    # Base : CRÉÉ + CRPR + Backlog prep NON CARAC + Date planif ≤ aujourd'hui
    filt_prep = (
        (dfp["Statut OT"] == "CRÉÉ") &
        (dfp["Backlog preparation"] == "CARACTERISE")
    )
    ano_map["OT préparation <1 mois"]       = dfp[filt_prep & (dfp["ap"] == "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation 1mois< <3mois"] = dfp[filt_prep & (dfp["ap"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation >3 mois"]       = dfp[filt_prep & (dfp["ap"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    # ── 5/6/7. AGE PLAN ─────────────────────────────────────────────────
    # Base : LANC + hors SOPL + Backlog plan CARACTERISE
    filt_plan = (
        (dfp["Statut OT"] == "LANC") &
        (dfp["Contient SOPL"] == 0) &
        (dfp["Backlog planification"] == "CARACTERISE")
    )
    ano_map["OT planification <1 mois"]      = dfp[filt_plan & (dfp["alp"] == "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification 1mois< <3mois"] = dfp[filt_plan & (dfp["alp"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification >3 mois"]       = dfp[filt_plan & (dfp["alp"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    # ── 8/9/10. AGE EXEC ────────────────────────────────────────────────
    # Base : LANC + SOPL (sans filtre TW preventifs)
    filt_exec = (
        (dfp["Statut OT"] == "LANC") &
        (dfp["Contient SOPL"] == 1)
    )
    ano_map["OT exécution <1 mois"]          = dfp[filt_exec & (dfp["aex"] == "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution 1mois< <3mois"]    = dfp[filt_exec & (dfp["aex"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution >3 mois"]          = dfp[filt_exec & (dfp["aex"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    # ── 11/12/13. PERFORMANCE PREVENTIF ─────────────────────────────────
    # Anomalie = SOPL non clôturé pour chaque TW
    perf_base = dfp["is_correctif"] if False else pd.Series(True, index=dfp.index)
    filt_perf = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT","TCLO"]))

    ano_map["Performance Graissage"]     = dfp[filt_perf & (dfp["_tw_num"]==350)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Inspection"]    = dfp[filt_perf & (dfp["_tw_num"].isin([290,300,310])) & (dfp["Date de début planifiée"]<=now_ts)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Systématiques"] = dfp[filt_perf & (dfp["_tw_num"]==360) & (dfp["Date de début planifiée"]<=now_ts)].groupby("Poste travail princ.")["Ordre"].count()

    # ── 14. TAUX APPROBATION AVIS ────────────────────────────────────────
    # Anomalie = avis APRQ ou REJT (non encore approuves ou rejetés)
    # Note : avf est deja filtre hors ZU/Z4/ZR/ZP dans prepare_data
    # Anomalie = avis APRQ uniquement (en attente d approbation)
    ano_map["Taux d'approbation des Avis"] = (
        avf[avf["Statut utilisateur"] == "APRQ"]
        .groupby("Poste travail princ.")["Avis"].count()
    )

    # ── 15. OT LANC ESTIME ───────────────────────────────────────────────
    # Anomalie = Plan==0 + LANC + hors SOPL + charge estimee == 0
    ano_map["OT LANC ESTIME"] = dfp[
        dfp["is_correctif"] &
        (dfp["Statut OT"] == "LANC") &
        (dfp["Contient SOPL"] == 0) &
        (dfp["OT LANC ESTIME"] == "NON")
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── 16. BACKLOG PREP CARACTERISE ─────────────────────────────────────
    # Base : CRÉÉ + Plan d'entretien != 0 (préventif)
    # Anomalie = hors ATPD/ATMR/ATRS/ATMO/ATER (NON caracterise)
    pat_crpr_kw = "ATPD|ATMR|ATRS|ATMO|ATER"
    _df_prep_base = dfp[
        (dfp["Statut OT"] == "CRÉÉ") &
        (~dfp["is_correctif"])
    ]
    ano_map["Backlog préparation caractérisé"] = _df_prep_base[
        ~_df_prep_base["Statut utilisateur"].str.contains(pat_crpr_kw, na=False)
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── 17. BACKLOG PLAN CARACTERISE ─────────────────────────────────────
    # Base : LANC + Contient SOPL + Plan d'entretien != 0 (préventif)
    # Anomalie = hors ATEI/ATAL/ATAS/AGAR/ATHS (NON caracterise)
    pat_atpl_kw = "ATEI|ATAL|ATAS|AGAR|ATHS"
    _df_plan_base = dfp[
        (~dfp["is_correctif"]) &
        (dfp["Statut OT"] == "LANC") &
        (dfp["Contient SOPL"] == 1)
    ]
    ano_map["Backlog planification caractérisé"] = _df_plan_base[
        ~_df_plan_base["Statut utilisateur"].str.contains(pat_atpl_kw, na=False)
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── 18. OT CONFIME ───────────────────────────────────────────────────
    # Anomalie = CLOT+TCLO sans confirmation CONF
    ano_map["OT CONFIME"] = dfp[
        dfp["Statut OT"].isin(["CLOT","TCLO"]) &
        (dfp["OT CONFIME"] == "NON")
    ].groupby("Poste travail princ.")["Ordre"].count()

    # ── 19. OT_COR_EGAL ──────────────────────────────────────────────────
    # KPI  = budget == reel / total (EGAL = conforme, objectif = maximiser)
    # Anomalie = budget DIFFERENT du reel (DIFF = pas conforme)
    # OT_COR_EGAL = "EGAL" si bud==reel (conforme) → KPI monte
    #             = "DIFF" si bud!=reel (anomalie) → KPI baisse
    # Anomalie = Plan==0 + CLOT+TCLO + CONF + budget == reel
    # Calcul direct sur colonnes couts (independant de la valeur OT_COR_EGAL)
    _sub_cor = dfp[
        dfp["is_correctif"] &
        dfp["Statut OT"].isin(["CLOT","TCLO"]) &
        dfp["Statut système"].str.contains("CONF", na=False)
    ]
    _bud  = _sub_cor["Total coûts budgétés"].fillna(0)
    _reel = _sub_cor["Total coûts réels"].fillna(0)
    # Anomalie = |bud - reel| < 1 (couts quasi identiques = pas d imputation reelle)
    ano_map["OT_COR_EGAL"] = _sub_cor[(_bud - _reel).abs() < 1].groupby(
        "Poste travail princ.")["Ordre"].count()

    return ano_map


def build_ano_rows(vp, ano_map, kpi_list, fixed_zero=None, ckdf=None):
    """
    ckdf (optionnel) : DataFrame des valeurs KPI par poste. Si fourni, un
    poste dont la valeur est NaN pour un KPI (= aucune donnee / base vide)
    affiche "N/A" au lieu de 0 anomalies, pour ne pas laisser croire a un
    poste "conforme" alors qu il n y a simplement rien a evaluer.
    """
    fixed_zero = fixed_zero or []
    rows = []
    for poste in vp:
        r = {"Poste de travail": poste}
        total = 0
        for kpi in kpi_list:
            has_data = True
            if ckdf is not None and poste in ckdf.index and kpi in ckdf.columns:
                has_data = pd.notna(ckdf.loc[poste, kpi])
            if kpi in fixed_zero:
                cnt = 0
            elif not has_data:
                cnt = None  # pas de donnees -> affiche "N/A"
            else:
                cnt = int(ano_map.get(kpi, pd.Series()).get(poste, 0))
            r[kpi] = cnt if cnt is not None else "N/A"
            if isinstance(cnt, int):
                total += cnt
        r["Total Anomalies"] = total
        rows.append(r)
    tot = {"Poste de travail": "Total"}
    grand = 0
    for kpi in kpi_list:
        s = sum(r[kpi] for r in rows if isinstance(r[kpi], int))
        tot[kpi] = s
        grand += s
    tot["Total Anomalies"] = grand
    rows.append(tot)
    return rows


def build_anomaly_dfs(dfp, avf, now_ts):
    filt_prep = (dfp["Statut OT"]=="CRÉÉ") & (dfp["Backlog preparation"]=="CARACTERISE")
    filt_plan = (dfp["Statut OT"]=="LANC") & (dfp["Contient SOPL"]==0) & (dfp["Backlog planification"]=="CARACTERISE")
    filt_exec = (dfp["Statut OT"]=="LANC") & (dfp["Contient SOPL"]==1)
    filt_perf = (dfp["Contient SOPL"]==1) & (~dfp["Statut OT"].isin(["CLOT","TCLO"]))

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
        "Taux d'approbation des Avis":       avf[avf["Statut utilisateur"]=="APRQ"].copy(),  # Anomalie = APRQ seulement
        "OT LANC ESTIME":                    dfp[dfp["is_correctif"] & (dfp["Statut OT"]=="LANC") & (dfp["Contient SOPL"]==0) & (dfp["OT LANC ESTIME"]=="NON")].copy(),
        "Backlog préparation caractérisé":   dfp[(dfp["Statut OT"]=="CRÉÉ") & (~dfp["is_correctif"]) & ~dfp["Statut utilisateur"].str.contains("ATPD|ATMR|ATRS|ATMO|ATER",na=False)].copy(),
        "Backlog planification caractérisé": dfp[(~dfp["is_correctif"]) & (dfp["Statut OT"]=="LANC") & (dfp["Contient SOPL"]==1) & ~dfp["Statut utilisateur"].str.contains("ATEI|ATAL|ATAS|AGAR|ATHS",na=False)].copy(),
        "OT CONFIME":                        dfp[dfp["Statut OT"].isin(["CLOT","TCLO"]) & (dfp["OT CONFIME"]=="NON")].copy(),
        "OT_COR_EGAL": dfp[
            dfp["is_correctif"] &
            dfp["Statut OT"].isin(["CLOT","TCLO"]) &
            dfp["Statut système"].str.contains("CONF", na=False) &
            ((dfp["Total coûts budgétés"].fillna(0) - dfp["Total coûts réels"].fillna(0)).abs() < 1)
        ].copy(),
    }
