# -*- coding: utf-8 -*-
"""Page Tableau de bord — vue synthétique globale."""
import streamlit as st
from components.tables import render_synthesis_table, render_anomaly_table


def render(kpi_data, hist_df, date_str):
    """Affiche le tableau de bord synthétique."""
    # ── Synthèse Performance ──
    st.markdown('<div class="stl">SYNTHÈSE PERFORMANCE</div>', unsafe_allow_html=True)
    render_synthesis_table(kpi_data["p_rows"], kpi_data["p_cols"], "pt")

    # ── Synthèse Qualité ──
    st.markdown('<div class="stl">SYNTHÈSE QUALITÉ</div>', unsafe_allow_html=True)
    render_synthesis_table(kpi_data["q_rows"], kpi_data["q_cols"], "qt")

    # ── Anomalies ──
    all_anomalies = kpi_data.get("ano_p_r", []) + kpi_data.get("ano_q_r", [])
    if all_anomalies:
        st.markdown('<div class="stl">ANOMALIES DÉTECTÉES</div>', unsafe_allow_html=True)
        render_anomaly_table(all_anomalies, kpi_data.get("ano_p_c", []))
    else:
        st.markdown('<div class="stl">ANOMALIES DÉTECTÉES</div>', unsafe_allow_html=True)
        st.markdown('<div class="es">✅ Aucune anomalie détectée — Tous les KPI sont conformes</div>',
                    unsafe_allow_html=True)
