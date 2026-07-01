# -*- coding: utf-8 -*-
from components.tables import render_kpi_table, render_anomaly_table
from components.charts import show_simple_pie
def render(kpi_data, posts):
    st.markdown('<div class="stl">INDICATEURS DE QUALITÉ</div>', unsafe_allow_html=True)
    render_kpi_table(kpi_data["qrows"], kpi_data["qcols"], "qt")
    st.markdown('<div class="stl">DÉTAIL OT LANC ESTIMÉ</div>', unsafe_allow_html=True)
    la_f = kpi_data['la'][["OUI","NON"]].loc[kpi_data['la'].index.isin(posts)]
    show_simple_pie(la_f, "OT Lancés : Estimés vs Non estimés")
    if kpi_data.get("ano_q_r"):
        st.markdown('<div class="stl">ANOMALIES QUALITÉ</div>', unsafe_allow_html=True)
        render_anomaly_table(kpi_data["ano_q_r"], kpi_data["ano_q_c"])
