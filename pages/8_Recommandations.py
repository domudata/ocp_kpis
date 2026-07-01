# -*- coding: utf-8 -*-
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="Recommandations",
    page_icon="💡",
    initial_sidebar_state="expanded"
)

from components.styles import inject_custom_css

inject_custom_css()


def render(kpi_data, selected_posts):
    st.markdown('<div class="stl">RECOMMANDATIONS PAR POSTE</div>', unsafe_allow_html=True)

    all_anomalies = kpi_data.get("ano_p_r", []) + kpi_data.get("ano_q_r", [])
    filtered = [a for a in all_anomalies if a.get("Poste de travail") in selected_posts]

    if not filtered:
        st.markdown('<div class="es">✅ Aucune recommandation</div>', unsafe_allow_html=True)
        return

    by_poste = {}
    for a in filtered:
        poste = a.get("Poste de travail", "")
        by_poste.setdefault(poste, []).append(a)

    for poste in sorted(by_poste.keys()):
        anomalies = by_poste[poste]
        nb = len(anomalies)
        max_ecart = max(abs(float(a.get("Écart", 0))) for a in anomalies)

        if max_ecart > 20:
            severity, bg, border = "🔴 CRITIQUE", "#fee2e2", "#ef4444"
        elif max_ecart > 10:
            severity, bg, border = "🟡 ATTENTION", "#fef3c7", "#f59e0b"
        else:
            severity, bg, border = "🟢 SURVEILLANCE", "#d1fae5", "#10b981"

        st.markdown(f'''
        <div style="background:{bg};border-left:4px solid {border};border-radius:8px;
                    padding:12px 16px;margin-bottom:8px;">
            <div style="font-size:16px;font-weight:800;color:#1e293b;margin-bottom:8px;">
                {poste} — {severity} ({nb} anomalie{'s' if nb > 1 else ''})
            </div>
        ''', unsafe_allow_html=True)

        for a in anomalies:
            st.markdown(f'''
            <div style="background:#fff;border-radius:6px;padding:8px 12px;margin:4px 0;
                        border:1px solid #e2e8f0;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-weight:700;color:#1e3a5f">{a.get("KPI","")}</span>
                    <span style="font-weight:800;color:#dc2626">{a.get("Valeur","")} / {a.get("Cible","")}</span>
                </div>
                <div style="margin-top:4px;font-size:13px;color:#475569;">➜ {a.get("Action","")}</div>
                <div style="margin-top:2px;font-size:12px;color:#94a3b8;">👤 {a.get("Responsable","")}</div>
            </div>
            ''', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


if "kpi_data" not in st.session_state:
    st.warning("⚠️ Veuillez d'abord charger les fichiers depuis la page d'accueil.")
    st.stop()

render(
    st.session_state["kpi_data"],
    st.session_state.get("selected_posts", [])
)
