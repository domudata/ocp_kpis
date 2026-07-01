# -*- coding: utf-8 -*-
"""Composant d'en-tête du dashboard avec logo et cartes KPI."""
import os
import base64
import streamlit as st
from components.cards import format_card_variation


def get_logo_base64():
    """Charge et encode le logo en base64."""
    for path in ["assets/logo.png", "logo.png", "./logo.png", "../logo.png"]:
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode()
            except Exception:
                pass
    return None


def render_header(date_str, kpi_data, prev_values=None):
    """
    Affiche le header complet : logo + titre + date + 8 cartes KPI.

    Paramètres
    ----------
    date_str : str — date du dashboard
    kpi_data : dict — résultat de calc_kpis
    prev_values : dict — valeurs précédentes pour les variations (issue de get_previous_card_values)
    """
    logo_b64 = get_logo_base64()
    logo_html = f'<img class="logo" src="data:image/png;base64,{logo_b64}" alt="Logo">' if logo_b64 else ""

    # Valeurs actuelles
    nb_ot = kpi_data.get("nb_ot", 0)
    scores_perf = kpi_data.get("scores_perf", {})
    scores_qual = kpi_data.get("scores_qual", {})
    nb_anomalies = kpi_data.get("nb_anomalies", 0)

    # Moyennes SF1 / SF2
    sf1_perf = _avg_by_prefix(scores_perf, "SF1")
    sf2_perf = _avg_by_prefix(scores_perf, "SF2")
    sf1_qual = _avg_by_prefix(scores_qual, "SF1")
    sf2_qual = _avg_by_prefix(scores_qual, "SF2")

    score_perf_global = _avg_dict(scores_perf)
    score_qual_global = _avg_dict(scores_qual)

    if prev_values is None:
        prev_values = {}

    # 8 cartes
    cards = [
        (nb_ot, "OT Analysés", "c1", prev_values.get("OT Analysés")),
        (round(score_perf_global, 1), "Score Performance Global", "c2", prev_values.get("Score Performance Global")),
        (round(score_qual_global, 1), "Score Qualité Global", "c3", prev_values.get("Score Qualité Global")),
        (nb_anomalies, "Anomalies Totales", "c4", prev_values.get("Anomalies Totales")),
        (round(sf1_perf, 1), "Performance SF1", "c5", prev_values.get("Performance SF1")),
        (round(sf1_qual, 1), "Qualité SF1", "c6", prev_values.get("Qualité SF1")),
        (round(sf2_perf, 1), "Performance SF2", "c7", prev_values.get("Performance SF2")),
        (round(sf2_qual, 1), "Qualité SF2", "c8", prev_values.get("Qualité SF2")),
    ]

    cards_html = ""
    for val, label, cls, prev in cards:
        var_html = format_card_variation(val, prev)
        cards_html += f'''<div class="cc {cls}">
            <div class="cv">{val}</div>
            <div class="cl">{label}</div>
            {var_html}
        </div>'''

    st.markdown(f'''
    <div class="mh">
        {logo_html}
        <h1>DASHBOARD KPI</h1>
        <div class="db">{date_str}</div>
    </div>
    <div class="cr">{cards_html}</div>
    ''', unsafe_allow_html=True)


def _avg_dict(d):
    """Moyenne des valeurs d'un dict."""
    vals = [v for v in d.values() if v is not None]
    return sum(vals) / len(vals) if vals else 0


def _avg_by_prefix(d, prefix):
    """Moyenne des valeurs d'un dict dont les clés commencent par prefix."""
    vals = [v for k, v in d.items() if k.startswith(prefix) and v is not None]
    return sum(vals) / len(vals) if vals else 0
