# -*- coding: utf-8 -*-
import pandas as pd

from core.constants import QK, PK

def build_ano_map(dfp: pd.DataFrame, avf: pd.DataFrame, now_ts) -> dict:
    """
    Construit le dictionnaire ano_map :
    {kpi_name → pd.Series(index=poste, values=nb_anomalies)}
    """
    # REVERT : test empirique defavorable a la version "CRPR n'importe ou"
    # (cf. calcul_kpi.py) -> on garde Statut OT==CRÉÉ.
    prep_filt = (dfp["Statut OT"] == "CRÉÉ") & (dfp["Statut utilisateur"].str.contains(r"\bCRPR\b", case=False, na=False))
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

    ano_map["OT préparation <1 mois"] = dfp[prep_filt & (dfp["ap"] != "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation >3 mois"] = dfp[prep_filt & (dfp["ap"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT préparation 1mois< <3mois"] = dfp[prep_filt & (dfp["ap"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["OT planification <1 mois"] = dfp[plan_filt & (dfp["alp"] != "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification >3 mois"] = dfp[plan_filt & (dfp["alp"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT planification 1mois< <3mois"] = dfp[plan_filt & (dfp["alp"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["OT exécution <1 mois"] = dfp[exec_filt & (dfp["aex"] != "<1 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution >3 mois"] = dfp[exec_filt & (dfp["aex"] == ">3 mois")].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["OT exécution 1mois< <3mois"] = dfp[exec_filt & (dfp["aex"] == "1 mois < <3 mois")].groupby("Poste travail princ.")["Ordre"].count()

    ano_map["Performance Graissage"] = dfp[perf_filt & (dfp["_tw_num"] == 350)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Inspection"] = dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()
    ano_map["Performance Systématiques"] = dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].groupby("Poste travail princ.")["Ordre"].count()

    # Avis approuvés = APRV SEUL (formule officielle SAP PM : "Nombre d'avis
    # approuvés (statut utilisateur APRV) / Total des avis créés"). Total =
    # avis avec un Statut utilisateur pertinent (APRQ/APRV/APRV AVAU)
    # uniquement — exclut les avis à Statut utilisateur vide (déjà transformés
    # en OT ou hors périmètre du workflow d'approbation), ET exclut REJT
    # (sur demande explicite : un avis rejeté n'est ni une anomalie ni pris
    # en compte dans le taux d'approbation).
    avf_pertinent = avf[avf["Statut utilisateur"].isin(["APRQ", "APRV", "APRV AVAU"])]
    avf_tot = avf_pertinent.groupby("Poste travail princ.")["Avis"].count()
    avf_aprv = avf[avf["Statut utilisateur"] == "APRV"].groupby("Poste travail princ.")["Avis"].count()
    ano_map["Taux d'approbation des Avis"] = avf_tot.sub(avf_aprv, fill_value=0)

    ano_map["OT LANC ESTIME"] = dfp[(dfp["Statut OT"] == "LANC") & (dfp["Type d'ordre"] == "ZCOR") & (dfp["Contient SOPL"] == 1) & (dfp["OT LANC ESTIME"] == "NON")].groupby("Poste travail princ.")["Ordre"].count()

    # ── Backlog préparation caractérisé (CORRIGÉ) ──
    # Filtre aligné sur le pivot `pc` de calcul_kpi.py :
    # Statut OT = CRÉÉ ET Statut utilisateur contient CRPR (= prep_filt).
    # Avant : filtrait uniquement Statut OT = CRÉÉ, ce qui comptait des OT
    # hors périmètre "préparation" et faussait le Total.
    ano_map["Backlog préparation caractérisé"] = dfp[prep_filt & (dfp["Backlog preparation"] == "NON CARACTERISE")].groupby("Poste travail princ.")["Ordre"].count()

    # ── Backlog planification caractérisé (CORRIGÉ) ──
    # Filtre aligné sur le pivot `plc` de calcul_kpi.py :
    # Statut OT = LANC ET Statut utilisateur contient ATPL (= plan_filt).
    # Avant : filtrait sur Contient SOPL == 0, ce qui ne correspond pas
    # à la règle métier et faussait le Total.
    ano_map["Backlog planification caractérisé"] = dfp[(dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 0) & (dfp["Backlog planification"] == "NON CARACTERISE")].groupby("Poste travail princ.")["Ordre"].count()

    # OT CONFIME et OT_COR_EGAL : déjà indépendants (chacun sa propre colonne),
    # cohérents avec la séparation appliquée dans calcul_kpi.py. Inchangé.
    ano_map["OT CONFIME"] = dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT CONFIME"] == "NON")].groupby("Poste travail princ.")["Ordre"].count()
    # OT_COR_EGAL restreint aux OT correctifs (Type d'ordre == "ZCOR"),
    # conforme a la formule officielle "OT correctifs clotures".
    ano_map["OT_COR_EGAL"] = dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["Type d'ordre"] == "ZCOR") & (dfp["OT_COR_EGAL"] == "OUI")].groupby("Poste travail princ.")["Ordre"].count()

    return ano_map

def build_ano_rows(vp: list, ano_map: dict, kpi_list: list, fixed_zero: list = None) -> list:
    """Construit la liste de dicts pour le tableau d'anomalies (Performance ou Qualité).

    Le total par poste (r["Total Anomalies"]) et la ligne "Total" en bas de
    tableau sont de simples sommes des valeurs de ano_map : ils redeviennent
    corrects automatiquement dès lors que ano_map lui-même est correct
    (cf. corrections des filtres Backlog ci-dessus). Logique de calcul du
    total inchangée, aucun bug structurel identifié ici.
    """
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

    # Ligne Total (somme colonne par colonne sur les lignes "poste" ci-dessus)
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
    """
    Construit les DataFrames détaillés des anomalies (pour liens téléchargement CSV
    dans le plan d'action).
    """
    # REVERT : test empirique defavorable a la version "CRPR n'importe ou"
    # (cf. calcul_kpi.py) -> on garde Statut OT==CRÉÉ.
    prep_filt = (dfp["Statut OT"] == "CRÉÉ") & (dfp["Statut utilisateur"].str.contains(r"\bCRPR\b", case=False, na=False))
    plan_filt = (dfp["Statut OT"] == "LANC") & (dfp["Statut utilisateur"].str.contains("ATPL", case=False, na=False))
    exec_filt = (dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 1)
    perf_filt = (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))

    return {
        "TAUX_REALISATION_CORRECTIF/PT": dfp[(dfp["Nº appel pl.entret."].fillna(0) == 0) & (dfp["Contient SOPL"] == 1) & (~dfp["Statut OT"].isin(["CLOT", "TCLO"]))].copy(),
        "OT préparation <1 mois": dfp[prep_filt & (dfp["ap"] != "<1 mois")].copy(),
        "OT préparation >3 mois": dfp[prep_filt & (dfp["ap"] == ">3 mois")].copy(),
        "OT préparation 1mois< <3mois": dfp[prep_filt & (dfp["ap"] == "1 mois < <3 mois")].copy(),
        "OT planification <1 mois": dfp[plan_filt & (dfp["alp"] != "<1 mois")].copy(),
        "OT planification >3 mois": dfp[plan_filt & (dfp["alp"] == ">3 mois")].copy(),
        "OT planification 1mois< <3mois": dfp[plan_filt & (dfp["alp"] == "1 mois < <3 mois")].copy(),
        "OT exécution <1 mois": dfp[exec_filt & (dfp["aex"] != "<1 mois")].copy(),
        "OT exécution >3 mois": dfp[exec_filt & (dfp["aex"] == ">3 mois")].copy(),
        "OT exécution 1mois< <3mois": dfp[exec_filt & (dfp["aex"] == "1 mois < <3 mois")].copy(),
        "Performance Graissage": dfp[perf_filt & (dfp["_tw_num"] == 350)].copy(),
        "Performance Inspection": dfp[perf_filt & (dfp["_tw_num"].isin([290, 300, 310])) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        "Performance Systématiques": dfp[perf_filt & (dfp["_tw_num"] == 360) & (dfp["Date de début planifiée"] <= now_ts)].copy(),
        "Taux d'approbation des Avis": avf[avf["Statut utilisateur"].isin(["APRQ", "APRV AVAU"])].copy(),
        "OT LANC ESTIME": dfp[(dfp["Statut OT"] == "LANC") & (dfp["Type d'ordre"] == "ZCOR") & (dfp["Contient SOPL"] == 1) & (dfp["OT LANC ESTIME"] == "NON")].copy(),
        # CORRIGÉ : mêmes filtres prep_filt / plan_filt que ci-dessus (cf. build_ano_map)
        "Backlog préparation caractérisé": dfp[prep_filt & (dfp["Backlog preparation"] == "NON CARACTERISE")].copy(),
        "Backlog planification caractérisé": dfp[(dfp["Statut OT"] == "LANC") & (dfp["Contient SOPL"] == 0) & (dfp["Backlog planification"] == "NON CARACTERISE")].copy(),
        "OT CONFIME": dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["OT CONFIME"] == "NON")].copy(),
        "OT_COR_EGAL": dfp[(dfp["Statut OT"].isin(["CLOT", "TCLO"])) & (dfp["Type d'ordre"] == "ZCOR") & (dfp["OT_COR_EGAL"] == "OUI")].copy(),
    }
