# -*- coding: utf-8 -*-
from components.tables import render_kpi_table, render_anomaly_table
def render(kpi_data):
    st.markdown('<div class="stl">SYNTHÈSE PERFORMANCE</div>', unsafe_allow_html=True)
    render_kpi_table(kpi_data["prows"], kpi_data["pcols"], "pt")
    st.markdown('<div class="stl">SYNTHÈSE QUALITÉ</div>', unsafe_allow_html=True)
    render_kpi_table(kpi_data["qrows"], kpi_data["qcols"], "qt")
    all_ano = kpi_data.get("ano_p_r", []) + kpi_data.get("ano_q_r", [])
    if all_ano:
        st.markdown('<div class="stl">ANOMALIES DÉTECTÉES</div>', unsafe_allow_html=True)
        render_anomaly_table(all_ano, kpi_data["ano_p_c"])
    else:
        st.markdown('<div class="stl">ANOMALIES DÉTECTÉES</div>', unsafe_allow_html=True)
        st.markdown('<div class="es">✅ Aucune anomalie détectée</div>', unsafe_allow_html=True)
    st.markdown('<div class="footer">Dashboard KPI — Maintenance Industrielle</div>', unsafe_allow_html=True)
