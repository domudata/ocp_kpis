# -*- coding: utf-8 -*-
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="Qualité",
    page_icon="✅",
    initial_sidebar_state="expanded"
)

from components.styles import inject_custom_css
from components.tables import render_synthesis_table, render_anomaly_table
from components.charts import show_bar_comparison, show_simple_pie
from core.constants import PK, CIBLE

inject_custom_css()


def render(kpi_data, selected_posts):
    st.markdown('<div class="stl">INDICATEURS DE QUALITÉ</div>', unsafe_allow_html=True)
    render_synthesis_table(kpi_data["q_rows"], kpi_data["q_cols"], "qt")

    st.markdown('<div class="stl">ANALYSE PAR KPI</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    import pandas as pd
    for i, kpi in enumerate(PK):
        vals = pd.Series(dtype=float)
        for row in kpi_data["q_rows"]:
            poste = row.get("Poste de travail", "")
            if poste in ("Total general", "CIBLE") or poste not in selected_posts:
                continue
            try:
                vals[poste] = float(row[kpi])
            except (KeyError, TypeError, ValueError):
                pass
        if not vals.empty:
            with col1 if i % 2 == 0 else col2:
                show_bar_comparison(kpi, vals, CIBLE.get(kpi, 100))

    la = kpi_data.get('la')
    if la is not None:
        st.markdown('<div class="stl">DÉTAIL OT LANC ESTIMÉ</div>', unsafe_allow_html=True)
        la_filtered = la[["OUI", "NON"]].loc[la.index.isin(selected_posts)]
        show_simple_pie(la_filtered, "OT Lancés : Estimés vs Non estimés")

    conf = kpi_data.get('conf')
    if conf is not None:
        st.markdown('<div class="stl">DÉTAIL OT CONFIRMÉS</div>', unsafe_allow_html=True)
        conf_filtered = conf[["OUI", "NON"]].loc[conf.index.isin(selected_posts)]
        show_simple_pie(conf_filtered, "OT Clos : Confirmés vs Non confirmés")

    if kpi_data.get("ano_q_r"):
        st.markdown('<div class="stl">ANOMALIES QUALITÉ</div>', unsafe_allow_html=True)
        render_anomaly_table(kpi_data["ano_q_r"], kpi_data["ano_q_c"])


if "kpi_data" not in st.session_state:
    st.warning("⚠️ Veuillez d'abord charger les fichiers depuis la page d'accueil.")
    st.stop()

render(
    st.session_state["kpi_data"],
    st.session_state.get("selected_posts", [])
)
