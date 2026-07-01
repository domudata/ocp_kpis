# -*- coding: utf-8 -*-
"""Page Backlog — analyse du backlog préparation et planification."""
import streamlit as st
import pandas as pd
from components.backlog_widgets import render_backlog_summary, render_backlog_detail
from components.charts import show_simple_pie, show_pie_pair
from components.tables import html_statut_pivot


def render(kpi_data, df, selected_posts):
    """Affiche la page Backlog."""
    # ── Résumé ──
    render_backlog_summary(df, selected_posts, kpi_data)

    # ── Détail par type ──
    render_backlog_detail(df, selected_posts, kpi_data)

    # ── Pie charts ──
    st.markdown('<div class="stl">RÉPARTITION DU BACKLOG</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    pc = kpi_data.get('pc')
    if pc is not None:
        pc_filtered = pc[["CARACTERISE", "NON CARACTERISE"]].loc[pc.index.isin(selected_posts)]
        with col1:
            show_simple_pie(pc_filtered, "Backlog Préparation", keep_non_carac=True)

    plc = kpi_data.get('plc')
    if plc is not None:
        plc_filtered = plc[["CARACTERISE", "NON CARACTERISE"]].loc[plc.index.isin(selected_posts)]
        with col2:
            show_simple_pie(plc_filtered, "Backlog Planification", keep_non_carac=True)

    # ── Statut des OT en backlog (CRÉÉ) ──
    st.markdown('<div class="stl">STATUT DES OT EN BACKLOG</div>', unsafe_allow_html=True)
    from core.calcul_kpi import build_statut_pivot
    crea_df = df[(df["Statut OT"] == "CRÉÉ") & (df["Poste travail princ."].isin(selected_posts))]
    if not crea_df.empty:
        piv = build_statut_pivot(crea_df, selected_posts)
        st.markdown(html_statut_pivot(piv, "st"), unsafe_allow_html=True)
