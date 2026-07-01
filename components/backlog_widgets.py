# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd

from components.charts import show_pie_pair, show_simple_pie
from components.tables import html_generic_pivot, html_statut_pivot
from core.calcul_kpi import build_statut_pivot, get_text_col


def render_backlog_tab(dfp: pd.DataFrame, vp: list) -> None:
    """Rendu complet de l'onglet Backlog."""

    # ── Caractérisation Backlog Préparation ──
    prep_backlog_df = dfp[dfp["Statut OT"] == "CRÉÉ"].copy()
    plan_backlog_df = dfp[dfp["Statut OT"] == "LANC"].copy()

    piv_carac_prep_stat = pd.pivot_table(
        prep_backlog_df, index="Poste travail princ.", columns="Backlog preparation",
        values="Ordre", aggfunc="count", fill_value=0,
    ).reindex(vp, fill_value=0)

    prep_carac_df = prep_backlog_df[prep_backlog_df["Backlog preparation"] == "CARACTERISE"]
    piv_carac_prep_type = pd.pivot_table(
        prep_carac_df, index="Poste travail princ.", columns="Type Carac Prep",
        values="Ordre", aggfunc="count", fill_value=0,
    ).reindex(vp, fill_value=0)

    piv_carac_plan_stat = pd.pivot_table(
        plan_backlog_df, index="Poste travail princ.", columns="Backlog planification",
        values="Ordre", aggfunc="count", fill_value=0,
    ).reindex(vp, fill_value=0)

    plan_carac_df = plan_backlog_df[plan_backlog_df["Backlog planification"] == "CARACTERISE"]
    piv_carac_plan_type = pd.pivot_table(
        plan_carac_df, index="Poste travail princ.", columns="Type Carac Plan",
        values="Ordre", aggfunc="count", fill_value=0,
    ).reindex(vp, fill_value=0)

    text_col  = get_text_col(dfp)
    oms_df_sub = dfp[dfp[text_col].astype(str).str.contains("OMS", case=False, na=False)] if text_col else pd.DataFrame()
    thm_df_sub = dfp[dfp[text_col].astype(str).str.contains("THERMO|THERMOGRAPH", case=False, na=False)] if text_col else pd.DataFrame()
    piv_oms  = build_statut_pivot(oms_df_sub, vp)
    piv_thm  = build_statut_pivot(thm_df_sub, vp)
    piv_all  = build_statut_pivot(dfp, vp)

    # ── Rendu ──
    st.markdown('<div class="stl c">Caractérisation Backlog Préparation</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([0.5, 0.5], vertical_alignment="center")
    with c1:
        st.markdown(html_generic_pivot(piv_carac_prep_stat, "omt", "Synthèse Caractérisé / Non Caractérisé"), unsafe_allow_html=True)
    with c2:
        show_simple_pie(piv_carac_prep_stat, "Répartition Globale Caractérisé / Non Caractérisé", keep_non_carac=True)
        show_simple_pie(piv_carac_prep_type, "Répartition par Type de Caractérisation", keep_non_carac=False)

    st.markdown('<div class="stl c">Caractérisation Backlog Planification</div>', unsafe_allow_html=True)
    c5, c6 = st.columns([0.5, 0.5], vertical_alignment="center")
    with c5:
        st.markdown(html_generic_pivot(piv_carac_plan_stat, "omt", "Synthèse Caractérisé / Non Caractérisé"), unsafe_allow_html=True)
    with c6:
        show_simple_pie(piv_carac_plan_stat, "Répartition Globale Caractérisé / Non Caractérisé", keep_non_carac=True)
        show_simple_pie(piv_carac_plan_type, "Répartition par Type de Caractérisation", keep_non_carac=False)

    st.markdown('<div class="stl p">Statuts OT par Poste de Travail</div>', unsafe_allow_html=True)

    st.markdown('<div class="stl s">OT OMS par Poste et Statut OT</div>', unsafe_allow_html=True)
    c_oms1, c_oms2 = st.columns([0.5, 0.5], vertical_alignment="center")
    with c_oms1:
        st.markdown(html_statut_pivot(piv_oms, "omt"), unsafe_allow_html=True)
    with c_oms2:
        show_pie_pair(piv_oms, "OT OMS")

    st.markdown('<div class="stl s">OT Thermographie par Poste et Statut OT</div>', unsafe_allow_html=True)
    c_thm1, c_thm2 = st.columns([0.5, 0.5], vertical_alignment="center")
    with c_thm1:
        st.markdown(html_statut_pivot(piv_thm, "tht"), unsafe_allow_html=True)
    with c_thm2:
        show_pie_pair(piv_thm, "OT Thermographie")

    st.markdown('<div class="stl s">Tous les OT par Poste et Statut OT</div>', unsafe_allow_html=True)
    c_all1, c_all2 = st.columns([0.5, 0.5], vertical_alignment="center")
    with c_all1:
        st.markdown(html_statut_pivot(piv_all, "pt"), unsafe_allow_html=True)
    with c_all2:
        show_pie_pair(piv_all, "Tous les OT")
