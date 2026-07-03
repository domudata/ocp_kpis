# -*- coding: utf-8 -*-
import streamlit as st

from core.constants import PK, CIBLE, ACT_MAP
from components.tables import html_table, html_anomaly_table, html_actions_table


def render_qualite_tab(qrows: list, qcols: list,
                        ano_q_rows: list, ano_q_cols: list,
                        qa: dict) -> None:

    # ── Toggle entre les 2 tableaux (Détail / Anomalies) ────────────────
    choix = st.radio(
        "Affichage",
        ["📊 Détail des indicateurs", "⚠️ Anomalies par KPI et Poste"],
        horizontal=True,
        label_visibility="collapsed",
        key="qual_table_choice",
    )

    if choix == "📊 Détail des indicateurs":
        st.markdown('<div class="stl q">Détail des indicateurs de Qualité</div>', unsafe_allow_html=True)
        st.markdown(html_table(qrows, qcols, "qt", ["Score Qualite"]), unsafe_allow_html=True)
    else:
        st.markdown('<div class="stl a">Nombre d\'anomalies par KPI et Poste (à traiter pour atteindre 100%)</div>', unsafe_allow_html=True)
        st.markdown(html_anomaly_table(ano_q_rows, ano_q_cols, "at"), unsafe_allow_html=True)

    st.markdown('<div class="stl a">Actions recommandées — Qualité</div>', unsafe_allow_html=True)
    st.markdown(html_actions_table(PK, qa, CIBLE, ACT_MAP), unsafe_allow_html=True)
