# -*- coding: utf-8 -*-
import streamlit as st

from core.constants import QK, CIBLE, ACT_MAP
from components.tables import html_table, html_anomaly_table, html_actions_table


def render_performance_tab(prows: list, pcols: list,
                            ano_p_rows: list, ano_p_cols: list,
                            pa: dict) -> None:
    st.markdown('<div class="stl p">Detail des indicateurs de Performance</div>', unsafe_allow_html=True)
    st.markdown(html_table(prows, pcols, "pt", ["Score Performance"]), unsafe_allow_html=True)

    st.markdown('<div class="stl a">Nombre d\'anomalies par KPI et Poste (à traiter pour atteindre 100%)</div>', unsafe_allow_html=True)
    st.markdown(html_anomaly_table(ano_p_rows, ano_p_cols, "at"), unsafe_allow_html=True)

    st.markdown('<div class="stl a">Actions recommandees — Performance</div>', unsafe_allow_html=True)
    st.markdown(html_actions_table(QK, pa, CIBLE, ACT_MAP), unsafe_allow_html=True)
