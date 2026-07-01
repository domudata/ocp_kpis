# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components

from components.tables import html_plan_actions_table


def render_plan_action_tab(plan_actions_rows: list, sf1_rows: list,
                            sf2_rows: list, anomaly_dfs: dict) -> None:
    st.markdown('<div class="stl a">📋 Plan d\'action</div>', unsafe_allow_html=True)

    col_pdf, col_metrics = st.columns([1, 3])
    with col_pdf:
        if st.button("📥 Télécharger en PDF", use_container_width=True):
            components.html("<script>window.print();</script>", height=0, width=0)

    with col_metrics:
        mc1, mc2, mc3 = st.columns(3)
        with mc1: st.metric("🔔 Total Actions Requises", len(plan_actions_rows))
        with mc2: st.metric("🏭 Actions SF1", len(sf1_rows))
        with mc3: st.metric("🏭 Actions SF2", len(sf2_rows))

    st.write("")

    st.markdown(
        html_plan_actions_table(sf1_rows, "SF1 — Plan d'Actions", "#3b82f6", anomaly_dfs),
        unsafe_allow_html=True,
    )
    st.markdown(
        html_plan_actions_table(sf2_rows, "SF2 — Plan d'Actions", "#10b981", anomaly_dfs),
        unsafe_allow_html=True,
    )

    if not plan_actions_rows:
        st.markdown(
            '<div class="es">🎉 Aucune anomalie détectée. Tous les KPIs sont aux normes !</div>',
            unsafe_allow_html=True,
        )
