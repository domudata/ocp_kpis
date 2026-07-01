# -*- coding: utf-8 -*-
import streamlit as st

from core.constants import QK, PK, CIBLE
from components.tables import (
    html_grouped_bars, html_kpi_bars, html_classement,
)


def render_dashboard_tab(vp: list, pscores: dict, qscores: dict,
                          pa: dict, qa: dict) -> None:
    st.markdown('<div class="stl p">Scores globaux par poste</div>', unsafe_allow_html=True)
    st.markdown(html_grouped_bars(vp, pscores, qscores, "Comparaison Performance / Qualite par poste"), unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="stl p">Indicateurs de Performance</div>', unsafe_allow_html=True)
        st.markdown(html_kpi_bars(QK, pa, CIBLE, "Taux moyens — Performance", "#10b981", "#8b5cf6"), unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="stl q">Indicateurs de Qualite</div>', unsafe_allow_html=True)
        st.markdown(html_kpi_bars(PK, qa, CIBLE, "Taux moyens — Qualite", "#3b82f6", "#8b5cf6"), unsafe_allow_html=True)

    st.markdown('<div class="stl c">Classement Performance</div>', unsafe_allow_html=True)
    st.markdown(html_classement(pscores, "#10b981"), unsafe_allow_html=True)

    st.markdown('<div class="stl c">Classement Qualite</div>', unsafe_allow_html=True)
    st.markdown(html_classement(qscores, "#3b82f6"), unsafe_allow_html=True)
