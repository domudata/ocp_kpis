# -*- coding: utf-8 -*-
import streamlit as st

from core.constants import QK, CIBLE, ACT_MAP
from components.tables import html_table, html_anomaly_table, html_actions_table


def render_performance_tab(prows: list, pcols: list,
                            ano_p_rows: list, ano_p_cols: list,
                            pa: dict) -> None:

    # ── Toggle entre les 2 tableaux (Détail / Anomalies) ────────────────
    choix = st.radio(
        "Affichage",
        ["📊 Détail des indicateurs", "⚠️ Anomalies par KPI et Poste"],
        horizontal=True,
        label_visibility="collapsed",
        key="perf_table_choice",
    )

    if choix == "📊 Détail des indicateurs":
        st.markdown('<div class="stl p">Détail des indicateurs de Performance</div>', unsafe_allow_html=True)
        st.markdown(html_table(prows, pcols, "pt", ["Score Performance"]), unsafe_allow_html=True)
    else:
        st.markdown('<div class="stl a">Nombre d\'anomalies par KPI et Poste (à traiter pour atteindre 100%)</div>', unsafe_allow_html=True)
        st.markdown(html_anomaly_table(ano_p_rows, ano_p_cols, "at"), unsafe_allow_html=True)

    st.markdown('<div class="stl a">Actions recommandées — Performance</div>', unsafe_allow_html=True)
    st.markdown(html_actions_table(QK, pa, CIBLE, ACT_MAP), unsafe_allow_html=True)
