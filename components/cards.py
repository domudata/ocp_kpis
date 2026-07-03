# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core.constants import LOWER_BETTER


def get_previous_card_values(hist_df: pd.DataFrame) -> dict:
    prev = {
        "OT Analysés": None, "Anomalies Totales": None,
        "Performance SF1": None, "Qualité SF1": None,
        "Performance SF2": None, "Qualité SF2": None,
    }
    if hist_df is None or hist_df.empty:
        return prev
    try:
        dates = sorted(hist_df["Date"].unique())
        if len(dates) >= 2:
            prev_date = dates[-2]
            prev_rows = hist_df[hist_df["Date"] == prev_date]
            for k in prev.keys():
                match = prev_rows[prev_rows["Metric"] == k]
                if not match.empty:
                    prev[k] = float(match.iloc[0]["Value"])
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

    var_ot = format_card_variation(total_ot,  prev_values.get("OT Analysés"))
    var_at = format_card_variation(total_ano, prev_values.get("Anomalies Totales"))
    var_p1 = format_card_variation(sf1_p,     prev_values.get("Performance SF1"))
    var_q1 = format_card_variation(sf1_q,     prev_values.get("Qualité SF1"))
    var_p2 = format_card_variation(sf2_p,     prev_values.get("Performance SF2"))
    var_q2 = format_card_variation(sf2_q,     prev_values.get("Qualité SF2"))

    # Toutes les 6 cartes sur une seule ligne
    st.markdown(
        '<div class="cr">'
        '<div class="cc c1"><div class="cv">%d</div>%s<div class="cl">OT Analyses</div></div>'
        '<div class="cc c4"><div class="cv">%d</div>%s<div class="cl">Anomalies Totales</div></div>'
        '<div class="cc c5"><div class="cv">%.1f%%</div>%s<div class="cl">Performance SF1</div></div>'
        '<div class="cc c6"><div class="cv">%.1f%%</div>%s<div class="cl">Qualite SF1</div></div>'
        '<div class="cc c7"><div class="cv">%.1f%%</div>%s<div class="cl">Performance SF2</div></div>'
        '<div class="cc c8"><div class="cv">%.1f%%</div>%s<div class="cl">Qualite SF2</div></div>'
        '</div>' % (
            total_ot, var_ot, total_ano, var_at,
            sf1_p, var_p1, sf1_q, var_q1,
            sf2_p, var_p2, sf2_q, var_q2
        ),
        unsafe_allow_html=True,
    )
