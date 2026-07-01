# -*- coding: utf-8 -*-
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="Tableau de bord",
    page_icon="📊",
    initial_sidebar_state="expanded"
)

from components.styles import inject_custom_css
from components.header import render_header
from components.cards import get_previous_card_values
from components.tables import render_synthesis_table, render_anomaly_table
from core.historique import load_historical_kpis

inject_custom_css()


def render(kpi_data, hist_df, date_str):
    prev = get_previous_card_values(hist_df)
    render_header(date_str, kpi_data, prev)

    st.markdown('<div class="stl">SYNTHÈSE PERFORMANCE</div>', unsafe_allow_html=True)
    render_synthesis_table(kpi_data["p_rows"], kpi_data["p_cols"], "pt")

    st.markdown('<div class="stl">SYNTHÈSE QUALITÉ</div>', unsafe_allow_html=True)
    render_synthesis_table(kpi_data["q_rows"], kpi_data["q_cols"], "qt")

    all_anomalies = kpi_data.get("ano_p_r", []) + kpi_data.get("ano_q_r", [])
    if all_anomalies:
        st.markdown('<div class="stl">ANOMALIES DÉTECTÉES</div>', unsafe_allow_html=True)
        render_anomaly_table(all_anomalies, kpi_data.get("ano_p_c", []))
    else:
        st.markdown('<div class="stl">ANOMALIES DÉTECTÉES</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="es">✅ Aucune anomalie détectée</div>',
            unsafe_allow_html=True
        )


# ── Point d'entrée Streamlit ──
if "kpi_data" not in st.session_state:
    st.warning("⚠️ Veuillez d'abord charger les fichiers depuis la page d'accueil.")
    st.stop()

render(
    st.session_state["kpi_data"],
    st.session_state.get("hist_df"),
    st.session_state.get("date_str", "")
)
