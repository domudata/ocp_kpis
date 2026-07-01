# -*- coding: utf-8 -*-
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="Plan d'action",
    page_icon="🎯",
    initial_sidebar_state="expanded"
)

from components.styles import inject_custom_css

inject_custom_css()


def render(kpi_data, selected_posts):
    all_anomalies = kpi_data.get("ano_p_r", []) + kpi_data.get("ano_q_r", [])
    filtered = [a for a in all_anomalies if a.get("Poste de travail") in selected_posts]

    if not filtered:
        st.markdown('<div class="es">✅ Aucune action requise</div>', unsafe_allow_html=True)
        return

    st.markdown('<div class="stl">PLAN D\'ACTION — %d ANOMALIES</div>' % len(filtered), unsafe_allow_html=True)

    cols = ["N°", "Poste", "KPI", "Valeur", "Cible", "Écart", "Action", "Responsable", "Priorité", "Délai", "Statut"]
    h = '<table class="plan-action-table"><thead><tr>'
    for c in cols:
        h += '<th>%s</th>' % c
    h += '</tr></thead><tbody>'

    for i, a in enumerate(filtered, 1):
        ecart = a.get("Écart", 0)
        abs_ecart = abs(float(ecart)) if ecart else 0
        if abs_ecart > 20:
            priorite = '<span style="color:#dc2626;font-weight:800">HAUTE</span>'
        elif abs_ecart > 10:
            priorite = '<span style="color:#d97706;font-weight:700">MOYENNE</span>'
        else:
            priorite = '<span style="color:#059669;font-weight:600">BASSE</span>'

        h += '<tr>'
        h += '<td>%d</td>' % i
        h += '<td style="font-weight:800">%s</td>' % a.get("Poste de travail", "")
        h += '<td>%s</td>' % a.get("KPI", "")
        h += '<td>%s</td>' % a.get("Valeur", "")
        h += '<td>%s</td>' % a.get("Cible", "")
        h += '<td style="font-weight:700;color:#dc2626">%s</td>' % a.get("Écart", "")
        h += '<td style="text-align:left;font-size:11px">%s</td>' % a.get("Action", "")
        h += '<td>%s</td>' % a.get("Responsable", "")
        h += '<td>%s</td>' % priorite
        h += '<td>À définir</td><td>En cours</td></tr>'

    h += '</tbody></table>'
    st.markdown(h, unsafe_allow_html=True)

    st.markdown("---")
    if st.button("📥 Exporter le plan d'action (Excel)", use_container_width=True):
        try:
            import pandas as pd
            df = pd.DataFrame(filtered)
            df.to_excel("plan_action.xlsx", index=False, sheet_name="Plan d'action")
            st.success("Export Excel généré !")
        except Exception as e:
            st.error(f"Erreur : {e}")


if "kpi_data" not in st.session_state:
    st.warning("⚠️ Veuillez d'abord charger les fichiers depuis la page d'accueil.")
    st.stop()

render(
    st.session_state["kpi_data"],
    st.session_state.get("selected_posts", [])
)
