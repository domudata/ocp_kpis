# -*- coding: utf-8 -*-
import streamlit as st
from components.tables import render_kpi_table, render_anomaly_table, html_statut_pivot
from components.charts import show_pie_pair, show_simple_pie
def render(kpi_data, posts):
    st.markdown('<div class="stl">INDICATEURS DE PERFORMANCE</div>', unsafe_allow_html=True)
    render_kpi_table(kpi_data["prows"], kpi_data["pcols"], "pt")
    st.markdown('<div class="stl">RÉPARTITION PAR STATUT OT</div>', unsafe_allow_html=True)
    an_f = kpi_data['an'].loc[kpi_data['an'].index.isin(posts)]
    if not an_f.empty: show_pie_pair(an_f, "Correctifs")
    if kpi_data.get("ano_p_r"):
        st.markdown('<div class="stl">ANOMALIES PERFORMANCE</div>', unsafe_allow_html=True)
        render_anomaly_table(kpi_data["ano_p_r"], kpi_data["ano_p_c"])
