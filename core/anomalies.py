# -*- coding: utf-8 -*-
"""Détection des anomalies sur les KPI."""
from core.constants import CIBLE, LOWER_BETTER, KPI_RESP_MAP, ACT_MAP


def detect_anomalies(rows, cols, kpi_list, section_type):
    """
    Parcourt les lignes KPI et flag les écarts par rapport à la cible.

    Paramètres
    ----------
    rows : list[dict] — lignes du tableau (sans Total general ni CIBLE)
    cols : list[str] — colonnes du tableau
    kpi_list : list[str] — KPIs de cette section
    section_type : str — "Performance" ou "Qualite"

    Retourne
    --------
    anomaly_rows : list[dict]
    anomaly_cols : list[str]
    """
    anomaly_cols = ["Poste de travail", "KPI", "Valeur", "Cible", "Écart", "Statut", "Action", "Responsable"]
    anomaly_rows = []

    for row in rows:
        poste = row.get("Poste de travail", "")
        if poste in ("Total general", "CIBLE", "", "nan", "None"):
            continue

        for kpi in kpi_list:
            try:
                val = float(row.get(kpi, 0))
            except (ValueError, TypeError):
                continue

            cible = CIBLE.get(kpi, 100)

            if kpi in LOWER_BETTER:
                # Pour les KPI "lower is better" : anomalie si valeur > cible
                ecart = val - cible
                statut = "NON CONFORME" if ecart > 0.5 else "CONFORME"
            else:
                # Pour les KPI "higher is better" : anomalie si valeur < cible
                ecart = val - cible
                statut = "NON CONFORME" if ecart < -0.5 else "CONFORME"

            if statut == "NON CONFORME":
                anomaly_rows.append({
                    "Poste de travail": poste,
                    "KPI": kpi,
                    "Valeur": round(val, 2),
                    "Cible": cible,
                    "Écart": round(ecart, 2),
                    "Statut": statut,
                    "Action": ACT_MAP.get(kpi, ""),
                    "Responsable": KPI_RESP_MAP.get(kpi, "")
                })

    return anomaly_rows, anomaly_cols
