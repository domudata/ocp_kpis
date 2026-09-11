# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core.constants import LOWER_BETTER


def get_previous_card_values(hist_df: pd.DataFrame) -> dict:
    """
    Recupere les valeurs de la periode PRECEDENTE (avant-derniere date
    enregistree) pour les 4 cartes SF1/SF2 Performance/Qualite.

    hist_df schema reel (depuis core/historique.py) :
        colonnes = Date, Poste de travail, <KPI...>, Score Performance
                   OU Score Qualite, _section ("perf"|"qual"), Date_parsed
    """
    prev = {
        "Performance SF1": None, "Qualité SF1": None,
        "Performance SF2": None, "Qualité SF2": None,
    }
    if hist_df is None or hist_df.empty or "Date_parsed" not in hist_df.columns:
        return prev

    try:
        dates_parsed = sorted(hist_df["Date_parsed"].dropna().unique())
        if len(dates_parsed) < 2:
            return prev  # une seule date -> pas de comparaison possible

        prev_date = dates_parsed[-2]
        prev_data = hist_df[hist_df["Date_parsed"] == prev_date]
        prev_perf = prev_data[prev_data["_section"] == "perf"]
        prev_qual = prev_data[prev_data["_section"] == "qual"]

        for section_df, score_col, prefix in [
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
                except (ValueError, TypeError):
                    continue
                if poste.startswith("SF1"):
                    sf1_vals.append(v)
                elif poste.startswith("SF2"):
                    sf2_vals.append(v)
            if sf1_vals:
                prev[f"{prefix} SF1"] = sum(sf1_vals) / len(sf1_vals)
            if sf2_vals:
                prev[f"{prefix} SF2"] = sum(sf2_vals) / len(sf2_vals)
    except Exception:
        pass

    return prev


def format_card_variation(current, previous):
    if previous is None:
        return '<div class="cd">→ 0.0 %</div>'
    diff = current - previous
    if abs(diff) < 0.05:
        return '<div class="cd">→ 0.0 %</div>'
    arrow = "↑" if diff > 0 else "↓"
    color = "#059669" if diff > 0 else "#dc2626"
    return '<div class="cd" style="color:%s">%s %.1f %%</div>' % (color, arrow, abs(diff))


def render_cards(total_ot, avg_p_score, avg_q_score,
                  total_ano, sf1_p, sf1_q, sf2_p, sf2_q,
                  prev_values: dict) -> None:

    var_p1 = format_card_variation(sf1_p,     prev_values.get("Performance SF1"))
    var_q1 = format_card_variation(sf1_q,     prev_values.get("Qualité SF1"))
    var_p2 = format_card_variation(sf2_p,     prev_values.get("Performance SF2"))
    var_q2 = format_card_variation(sf2_q,     prev_values.get("Qualité SF2"))

    # 4 cartes sur une seule ligne (OT Analyses et Anomalies Totales supprimees)
    st.markdown(
        '<div class="cr">'
        '<div class="cc c5"><div class="cv">%.1f%%</div>%s<div class="cl">Performance SF1</div></div>'
        '<div class="cc c6"><div class="cv">%.1f%%</div>%s<div class="cl">Qualite SF1</div></div>'
        '<div class="cc c7"><div class="cv">%.1f%%</div>%s<div class="cl">Performance SF2</div></div>'
        '<div class="cc c8"><div class="cv">%.1f%%</div>%s<div class="cl">Qualite SF2</div></div>'
        '</div>' % (
            sf1_p, var_p1, sf1_q, var_q1,
            sf2_p, var_p2, sf2_q, var_q2
        ),
        unsafe_allow_html=True,
    )
