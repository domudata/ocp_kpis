# -*- coding: utf-8 -*-
"""
NOUVEAU (demande explicite du 26/09) — suivi du taux de traitement du
Backlog Caractérisation (Préparation / Planification), par code.

Ce module est volontairement séparé de core/historique.py pour ne pas
toucher aux fonctions existantes qui y sont déjà éprouvées.

Principe : chaque extraction (chargement d'un nouveau ot.xlsx/avis.xlsx)
sauvegarde dans l'historique GitHub (kpis/indicateurs_kpis.xlsx) 2
nouvelles sections — "BACKLOG CARACT PREP" et "BACKLOG CARACT PLANIF" —
un nombre d'OT par poste et par code (ATPD, ATMR, ... / ATEI, ATAL, ...).
À chaque nouvelle extraction, on compare l'AVANT-DERNIÈRE extraction
sauvegardée (référence) à la DERNIÈRE (état actuel) : un OT caractérisé
qui a été traité (résolu / n'apparaît plus avec ce code) fait baisser le
compteur de ce code, ce qui fait monter le % traité.
"""
import pandas as pd


def calculate_traitement_backlog_caract(hist_df: pd.DataFrame,
                                         codes_prep: list,
                                         codes_planif: list) -> dict:
    """
    Compare les 2 dernières extractions enregistrées dans l'historique
    pour les sections "backlog_carac_prep" / "backlog_carac_planif".

    Pour chaque code (ATPD, ATMR, ... pour Prep ; ATEI, ATAL, ... pour
    Planif), agrégé sur tous les postes :
        traité      = max(0, valeur_extraction_précédente - valeur_actuelle)
        pct_traité  = traité / valeur_extraction_précédente * 100

    S'il n'existe qu'UNE SEULE extraction enregistrée (premier lancement
    après activation de cette fonctionnalité), il n'y a pas encore de
    référence : "precedent" est None et pct_traité = 0 pour tous les
    codes — le graphique se remplira correctement à la prochaine
    extraction.

    Retourne :
        {
          "prep":   {code: {"precedent": int|None, "actuel": int,
                             "traite": int, "pct_traite": float}, ...},
          "planif": {code: {...}, ...},
          "date_prec": Timestamp|None,
          "date_act":  Timestamp|None,
        }
    """
    resultat = {"prep": {}, "planif": {}, "date_prec": None, "date_act": None}

    if hist_df is None or hist_df.empty or "_section" not in hist_df.columns:
        return resultat

    for section, codes, cle in (
        ("backlog_carac_prep", codes_prep, "prep"),
        ("backlog_carac_planif", codes_planif, "planif"),
    ):
        sub = hist_df[hist_df["_section"] == section]
        if sub.empty or "Date_parsed" not in sub.columns:
            continue

        dates = sub["Date_parsed"].dropna().sort_values().unique()
        if len(dates) == 0:
            continue

        date_act = pd.Timestamp(dates[-1])
        date_prec = pd.Timestamp(dates[-2]) if len(dates) >= 2 else None

        row_act = sub[sub["Date_parsed"] == date_act]
        row_prec = sub[sub["Date_parsed"] == date_prec] if date_prec is not None else pd.DataFrame()

        for code in codes:
            if code not in row_act.columns:
                actuel = 0
            else:
                actuel = int(pd.to_numeric(row_act[code], errors="coerce").fillna(0).sum())

            if date_prec is not None and code in row_prec.columns:
                precedent = int(pd.to_numeric(row_prec[code], errors="coerce").fillna(0).sum())
                traite = max(0, precedent - actuel)
                pct_traite = round(traite / precedent * 100, 1) if precedent > 0 else 0.0
            else:
                precedent = None
                traite = 0
                pct_traite = 0.0

            resultat[cle][code] = {
                "precedent": precedent,
                "actuel": actuel,
                "traite": traite,
                "pct_traite": pct_traite,
            }

        resultat["date_act"] = date_act
        resultat["date_prec"] = date_prec

    return resultat
