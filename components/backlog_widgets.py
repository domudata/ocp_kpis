# -*- coding: utf-8 -*-
"""Widgets spécifiques à la page Backlog."""
import streamlit as st
from core.constants import MP_KW, MPLAN_KW


def render_backlog_summary(df, selected_posts, kpi_data):
    """Affiche un résumé du backlog avec barres de progression."""
    if df.empty:
        st.markdown('<div class="es">Aucune donnée</div>', unsafe_allow_html=True)
        return

    pc = kpi_data.get('pc')
    plc = kpi_data.get('plc')

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="stl">BACKLOG PRÉPARATION</div>', unsafe_allow_html=True)
        if pc is not None and not pc.empty:
            _render_backlog_bars(pc, "Backlog préparation caractérisé", selected_posts)

    with col2:
        st.markdown('<div class="stl">BACKLOG PLANIFICATION</div>', unsafe_allow_html=True)
        if plc is not None and not plc.empty:
            _render_backlog_bars(plc, "Backlog planification caractérisé", selected_posts)


def _render_backlog_bars(piv_df, kpi_col, posts):
    """Barres de progression pour le backlog d'un type."""
    from core.constants import CIBLE

    h = '<div class="ca"><div class="ct">Taux de caractérisation par poste</div>'
    cible = CIBLE.get(kpi_col, 100)

    for poste in posts:
        if poste not in piv_df.index:
            continue
        try:
            val = float(piv_df.loc[poste, kpi_col])
        except (KeyError, TypeError, ValueError):
            val = 0

        # Couleur
        if val >= cible:
            color = "#10b981"
        elif val >= cible * 0.7:
            color = "#f59e0b"
        else:
            color = "#ef4444"

        h += f'''<div class="car">
            <div class="cal">{poste}</div>
            <div class="cab">
                <div class="caf" style="width:{min(val, 100)}%;background:{color}"></div>
                <div class="target-mark" style="left:{cible}%"></div>
            </div>
            <div class="cav-out">{val:.1f}%</div>
            <div class="cav-tgt">/ {cible}%</div>
        </div>'''

    h += '</div>'
    st.markdown(h, unsafe_allow_html=True)


def render_backlog_detail(df, selected_posts, kpi_data):
    """Tableau détaillé du backlog par type de caractérisation."""
    st.markdown('<div class="stl">DÉTAIL PAR TYPE DE CARACTÉRISATION</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Préparation (CRPR)**")
        prep_df = df[
            (df["Statut OT"] == "CRÉÉ") &
            (df["Statut utilisateur"].str.contains("CRPR", case=False, na=False)) &
            (df["Poste travail princ."].isin(selected_posts))
        ] if not df.empty else df
        if "Type Carac Prep" in prep_df.columns and not prep_df.empty:
            type_counts = prep_df["Type Carac Prep"].value_counts()
            st.dataframe(type_counts.reset_index().rename(
                columns={"index": "Type", "Type Carac Prep": "Nombre"}),
                use_container_width=True, hide_index=True
            )
        else:
            st.markdown('<div class="es">Aucune donnée</div>', unsafe_allow_html=True)

    with col2:
        st.markdown("**Planification (ATPL)**")
        plan_df = df[
            (df["Statut OT"] == "CRÉÉ") &
            (df["Statut utilisateur"].str.contains("ATPL", case=False, na=False)) &
            (df["Poste travail princ."].isin(selected_posts))
        ] if not df.empty else df
        if "Type Carac Plan" in plan_df.columns and not plan_df.empty:
            type_counts = plan_df["Type Carac Plan"].value_counts()
            st.dataframe(type_counts.reset_index().rename(
                columns={"index": "Type", "Type Carac Plan": "Nombre"}),
                use_container_width=True, hide_index=True
            )
        else:
            st.markdown('<div class="es">Aucune donnée</div>', unsafe_allow_html=True)
