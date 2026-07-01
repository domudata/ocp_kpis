# -*- coding: utf-8 -*-
"""Cartes KPI avec calcul et affichage des variations."""
import streamlit as st


def get_previous_card_values(hist_df):
    """Récupère les valeurs précédentes des 8 KPI du header depuis hist_df.
    La 'valeur précédente' = avant-dernière date enregistrée dans le fichier historique.
    """
    prev = {
        "OT Analysés": None,
        "Score Performance Global": None,
        "Score Qualité Global": None,
        "Anomalies Totales": None,
        "Performance SF1": None,
        "Qualité SF1": None,
        "Performance SF2": None,
        "Qualité SF2": None,
    }

    if hist_df is None or hist_df.empty or "Date_parsed" not in hist_df.columns:
        return prev

    dates_parsed = sorted(hist_df["Date_parsed"].dropna().unique())
    if len(dates_parsed) < 2:
        return prev

    prev_date = dates_parsed[-2]
    prev_data = hist_df[hist_df["Date_parsed"] == prev_date]
    prev_perf = prev_data[prev_data["_section"] == "perf"]
    prev_qual = prev_data[prev_data["_section"] == "qual"]

    # Score Performance Global
    if not prev_perf.empty and "Score Performance" in prev_perf.columns:
        tg = prev_perf[prev_perf["Poste de travail"].astype(str) == "Total general"]
        if not tg.empty:
            try:
                prev["Score Performance Global"] = float(tg.iloc[0]["Score Performance"])
            except Exception:
                pass

    # Score Qualité Global
    if not prev_qual.empty and "Score Qualite" in prev_qual.columns:
        tg = prev_qual[prev_qual["Poste de travail"].astype(str) == "Total general"]
        if not tg.empty:
            try:
                prev["Score Qualité Global"] = float(tg.iloc[0]["Score Qualite"])
            except Exception:
                pass

    # Moyennes SF1 / SF2
    for section_df, score_col, key_prefix in [
        (prev_perf, "Score Performance", "Performance"),
        (prev_qual, "Score Qualite", "Qualité"),
    ]:
        if score_col not in section_df.columns:
            continue
        sf1_vals, sf2_vals = [], []
        for _, row in section_df.iterrows():
            poste = str(row.get("Poste de travail", ""))
            if poste in ("Total general", "CIBLE", "", "nan", "None"):
                continue
            try:
                v = float(row[score_col])
            except Exception:
                continue
            if poste.startswith("SF1"):
                sf1_vals.append(v)
            elif poste.startswith("SF2"):
                sf2_vals.append(v)
        if sf1_vals:
            prev[f"{key_prefix} SF1"] = sum(sf1_vals) / len(sf1_vals)
        if sf2_vals:
            prev[f"{key_prefix} SF2"] = sum(sf2_vals) / len(sf2_vals)

    # OT Analysés et Anomalies Totales ne sont pas stockés dans hist_df
    return prev


def format_card_variation(current, previous):
    """Génère le HTML de la variation à afficher sous la valeur d'une carte KPI."""
    if previous is None:
        return '<div class="cv-var neutral">➜ 0.0 %</div>'
    try:
        current = float(current)
        previous = float(previous)
    except (ValueError, TypeError):
        return '<div class="cv-var neutral">➜ 0.0 %</div>'
    if previous == 0:
        return '<div class="cv-var neutral">➜ 0.0 %</div>'

    pct = ((current - previous) / previous) * 100
    if pct > 0.05:
        return '<div class="cv-var positive">▲ +%.1f %%</div>' % pct
    elif pct < -0.05:
        return '<div class="cv-var negative">▼ −%.1f %%</div>' % abs(pct)
    else:
        return '<div class="cv-var neutral">➜ 0.0 %</div>'
