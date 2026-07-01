# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core.constants import LOWER_BETTER


def get_previous_card_values(hist_df: pd.DataFrame) -> dict:
    prev = {
        "OT Analysés": None, "Score Performance Global": None,
        "Score Qualité Global": None, "Anomalies Totales": None,
        "Performance SF1": None, "Qualité SF1": None,
        "Performance SF2": None, "Qualité SF2": None,
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

    if not prev_perf.empty and "Score Performance" in prev_perf.columns:
        tg = prev_perf[prev_perf["Poste de travail"].astype(str) == "Total general"]
        if not tg.empty:
            try:
                prev["Score Performance Global"] = float(tg.iloc[0]["Score Performance"])
            except Exception:
                pass

    if not prev_qual.empty and "Score Qualite" in prev_qual.columns:
        tg = prev_qual[prev_qual["Poste de travail"].astype(str) == "Total general"]
        if not tg.empty:
            try:
                prev["Score Qualité Global"] = float(tg.iloc[0]["Score Qualite"])
            except Exception:
                pass

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

    return prev


def format_card_variation(current, previous) -> str:
    if previous is None:
        return '<div class="cv-var neutral">➜ 0.0 %</div>'
    try:
        current  = float(current)
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


def render_cards(total_ot, avg_p_score, avg_q_score,
                 total_ano, sf1_p, sf1_q, sf2_p, sf2_q,
                 prev_values: dict) -> None:

    var_ot = format_card_variation(total_ot,      prev_values.get("OT Analysés"))
    var_sp = format_card_variation(avg_p_score,   prev_values.get("Score Performance Global"))
    var_sq = format_card_variation(avg_q_score,   prev_values.get("Score Qualité Global"))
    var_at = format_card_variation(total_ano,      prev_values.get("Anomalies Totales"))
    var_p1 = format_card_variation(sf1_p,         prev_values.get("Performance SF1"))
    var_q1 = format_card_variation(sf1_q,         prev_values.get("Qualité SF1"))
    var_p2 = format_card_variation(sf2_p,         prev_values.get("Performance SF2"))
    var_q2 = format_card_variation(sf2_q,         prev_values.get("Qualité SF2"))

    st.markdown(
        '<div class="cr">'
        '<div class="cc c1"><div class="cv">%d</div>%s<div class="cl">OT Analyses</div></div>'
        '<div class="cc c2"><div class="cv">%.1f%%</div>%s<div class="cl">Score Performance Global</div></div>'
        '<div class="cc c3"><div class="cv">%.1f%%</div>%s<div class="cl">Score Qualite Global</div></div>'
        '<div class="cc c4"><div class="cv">%d</div>%s<div class="cl">Anomalies Totales</div></div>'
        '</div>' % (total_ot, var_ot, avg_p_score, var_sp, avg_q_score, var_sq, total_ano, var_at),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="cr">'
        '<div class="cc c5"><div class="cv">%.1f%%</div>%s<div class="cl">Performance SF1</div></div>'
        '<div class="cc c6"><div class="cv">%.1f%%</div>%s<div class="cl">Qualite SF1</div></div>'
        '<div class="cc c7"><div class="cv">%.1f%%</div>%s<div class="cl">Performance SF2</div></div>'
        '<div class="cc c8"><div class="cv">%.1f%%</div>%s<div class="cl">Qualite SF2</div></div>'
        '</div>' % (sf1_p, var_p1, sf1_q, var_q1, sf2_p, var_p2, sf2_q, var_q2),
        unsafe_allow_html=True,
    )
