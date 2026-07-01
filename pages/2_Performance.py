# -*- coding: utf-8 -*-
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="Performance",
    page_icon="📈",
    initial_sidebar_state="expanded"
)

from components.styles import inject_custom_css
from components.tables import html_statut_pivot, render_synthesis_table, render_anomaly_table
from components.charts import show_pie_pair, show_bar_comparison, show_simple_pie
from core.constants import QK, CIBLE

inject_custom_css()


def render(kpi_data, selected_posts):
    st.markdown('<div class="stl">INDICATEURS DE PERFORMANCE</div>', unsafe_allow_html=True)
    render_synthesis_table(kpi_data["p_rows"], kpi_data["p_cols"], "pt")

    st.markdown('<div class="stl">ANALYSE PAR KPI</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    import pandas as pd
    for i, kpi in enumerate(QK):
        vals = pd.Series(dtype=float)
        for row in kpi_data["p_rows"]:
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

    st.markdown('<div class="stl">RÉPARTITION PAR STATUT</div>', unsafe_allow_html=True)
    an_piv = kpi_data.get('an_piv')
    if an_piv is not None:
        an_filtered = an_piv.loc[an_piv.index.isin(selected_posts)]
        col_a, col_b = st.columns(2)
        with col_a:
            show_pie_pair(an_filtered, "Correctifs")
        with col_b:
            pr = kpi_data.get('pr')
            if pr is not None:
                pr_filtered = pr[["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]].loc[
                    pr.index.isin(selected_posts)]
                show_simple_pie(pr_filtered, "Âge préparation des OT")

    if kpi_data.get("ano_p_r"):
        st.markdown('<div class="stl">ANOMALIES PERFORMANCE</div>', unsafe_allow_html=True)
        render_anomaly_table(kpi_data["ano_p_r"], kpi_data["ano_p_c"])


if "kpi_data" not in st.session_state:
    st.warning("⚠️ Veuillez d'abord charger les fichiers depuis la page d'accueil.")
    st.stop()

render(
    st.session_state["kpi_data"],
    st.session_state.get("selected_posts", [])
)
