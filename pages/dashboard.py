# -*- coding: utf-8 -*-
import streamlit as st

from core.constants import QK, PK, CIBLE, LOWER_BETTER
from components.tables import html_classement
from components.charts import show_scores_hbar, show_hbar_thresholds


def render_dashboard_tab(vp: list, pscores: dict, qscores: dict,
                          pa: dict, qa: dict) -> None:
    # ── Scores globaux par poste : Performance | Qualité côte à côte ─────
    st.markdown('<div class="stl p">Scores globaux par poste</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        show_scores_hbar(vp, pscores, "Performance par poste")
    with c2:
        show_scores_hbar(vp, qscores, "Qualité par poste")

    # ── Taux moyens par KPI (couleur = respect de la VRAIE cible de chaque KPI) ──
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="stl p">Indicateurs de Performance</div>', unsafe_allow_html=True)
        labels = [k for k in QK if k in pa]
        values = [pa[k] for k in labels]
        show_hbar_thresholds(labels, values, "Taux moyens — Performance",
                             cible_map=CIBLE, lower_set=LOWER_BETTER)
    with col2:
        st.markdown('<div class="stl q">Indicateurs de Qualité</div>', unsafe_allow_html=True)
        labels = [k for k in PK if k in qa]
        values = [qa[k] for k in labels]
        show_hbar_thresholds(labels, values, "Taux moyens — Qualité",
                             cible_map=CIBLE, lower_set=LOWER_BETTER)

    # ── Classements (inchangés) ──────────────────────────────────────────
    st.markdown('<div class="stl c">Classement Performance</div>', unsafe_allow_html=True)
    st.markdown(html_classement(pscores, "#10b981"), unsafe_allow_html=True)

    st.markdown('<div class="stl c">Classement Qualité</div>', unsafe_allow_html=True)
    st.markdown(html_classement(qscores, "#3b82f6"), unsafe_allow_html=True)
