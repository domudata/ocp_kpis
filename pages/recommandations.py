# -*- coding: utf-8 -*-
"""Page Recommandations — conseils par poste et par KPI."""
import streamlit as st
from core.constants import ACT_MAP, KPI_RESP_MAP, CIBLE, LOWER_BETTER


def render(kpi_data, selected_posts):
    """Affiche les recommandations par poste de travail."""
    st.markdown('<div class="stl">RECOMMANDATIONS PAR POSTE</div>', unsafe_allow_html=True)

    all_anomalies = kpi_data.get("ano_p_r", []) + kpi_data.get("ano_q_r", [])
    filtered = [a for a in all_anomalies if a.get("Poste de travail") in selected_posts]

    if not filtered:
        st.markdown('<div class="es">✅ Aucune recommandation — Tous les KPI sont conformes</div>',
                    unsafe_allow_html=True)
        return

    # Grouper par poste
    by_poste = {}
    for a in filtered:
        poste = a.get("Poste de travail", "")
        if poste not in by_poste:
            by_poste[poste] = []
        by_poste[poste].append(a)

    # Afficher par poste
    for poste in sorted(by_poste.keys()):
        anomalies = by_poste[poste]
        nb_anomalies = len(anomalies)

        # Calculer un score de criticité
        max_ecart = max(abs(float(a.get("Écart", 0))) for a in anomalies)
        if max_ecart > 20:
            severity = "🔴 CRITIQUE"
            bg_color = "#fee2e2"
            border_color = "#ef4444"
        elif max_ecart > 10:
            severity = "🟡 ATTENTION"
            bg_color = "#fef3c7"
            border_color = "#f59e0b"
        else:
            severity = "🟢 SURVEILLANCE"
            bg_color = "#d1fae5"
            border_color = "#10b981"

        st.markdown(f'''
        <div style="background:{bg_color};border-left:4px solid {border_color};
                    border-radius:8px;padding:12px 16px;margin-bottom:8px;">
            <div style="font-size:16px;font-weight:800;color:#1e293b;margin-bottom:8px;">
                {poste} — {severity} ({nb_anomalies} anomalie{'s' if nb_anomalies > 1 else ''})
            </div>
        ''', unsafe_allow_html=True)

        # Liste des recommandations
        for a in anomalies:
            kpi = a.get("KPI", "")
            val = a.get("Valeur", "")
            cible = a.get("Cible", "")
            action = a.get("Action", "")
            resp = a.get("Responsable", "")

            st.markdown(f'''
            <div style="background:#fff;border-radius:6px;padding:8px 12px;margin:4px 0;
                        border:1px solid #e2e8f0;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style
