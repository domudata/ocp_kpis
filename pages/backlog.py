# -*- coding: utf-8 -*-
from components.charts import show_simple_pie
def render(kpi_data, df, posts):
    pc_f = kpi_data['pc'][["CARACTERISE","NON CARACTERISE"]].loc[kpi_data['pc'].index.isin(posts)]
    plc_f = kpi_data['plc'][["CARACTERISE","NON CARACTERISE"]].loc[kpi_data['plc'].index.isin(posts)]
    c1, c2 = st.columns(2)
    with c1: show_simple_pie(pc_f, "Backlog Préparation", keep_non_carac=True)
    with c2: show_simple_pie(plc_f, "Backlog Planification", keep_non_carac=True)
