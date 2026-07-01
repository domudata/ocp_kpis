# -*- coding: utf-8 -*-
"""Page Performance — KPIs de performance détaillés."""
import streamlit as st
import pandas as pd
from core.constants import QK, CIBLE, LOWER_BETTER
from components.tables import html_statut_pivot, render_synthesis_table, render_anomaly_table
from components.charts import show_pie_pair, show_bar_comparison


def render(kpi_data, hist_df, selected_posts):
    """Affiche la page Performance détaillée."""
    # ── Tableau complet ──
    st.markdown('<div class="stl">INDICATEURS DE PERFORMANCE</div>', unsafe_allow_html=True)
    render_synthesis_table(kpi_data["p_rows"], kpi_data["p_cols"], "pt")

    # ── Graphiques par KPI ──
    st.markdown('<div class="stl">ANALYSE PAR KPI</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    # Extraire les valeurs par poste pour les principaux KPI
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

    # ── Pie charts par type ──
    st.markdown('<div class="stl">RÉPARTITION PAR STATUT</div>', unsafe_allow_html=True)

    an_piv = kpi_data.get('an_piv')
    if an_piv is not None:
        an_filtered = an_piv.loc[an_piv.index.isin(selected_posts)]
        col_a, col_b = st.columns(2)
        with col_a:
            show_pie_pair(an_filtered, "Correctifs (TAUX_RÉALISATION)")
        with col_b:
            from components.charts import show_simple_pie
            pr = kpi_data.get('pr')
            if pr is not None:
                pr_filtered = pr[["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]].loc[
                    pr.index.isin(selected_posts)]
                show_simple_pie(pr_filtered, "Âge préparation des OT")

    # ── Anomalies Performance ──
    if kpi_data.get("ano_p_r"):
        st.markdown('<div class="stl">ANOMALIES PERFORMANCE</div>', unsafe_allow_html=True)
        render_anomaly_table(kpi_data["ano_p_r"], kpi_data["ano_p_c"])
