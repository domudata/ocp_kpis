# -*- coding: utf-8 -*-
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="IA & PowerPoint",
    page_icon="🤖",
    initial_sidebar_state="expanded"
)

from components.styles import inject_custom_css
from core.ai_generator import generate_action_plan, generate_recommendations
from core.export_ppt import generate_pptx

inject_custom_css()


def render(kpi_data, selected_posts):
    st.markdown('<div class="stl">INTELLIGENCE ARTIFICIELLE & POWERPOINT</div>', unsafe_allow_html=True)

    api_key = st.text_input("Clé API OpenAI", type="password", key="openai_key")
    model = st.selectbox("Modèle", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], key="ai_model")

    if not api_key:
        st.info("Entrez votre clé API OpenAI.")
        st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🤖 Plan d'Action IA")
        if st.button("Générer le plan d'action", disabled=not api_key, use_container_width=True):
            all_anomalies = kpi_data.get("ano_p_r", []) + kpi_data.get("ano_q_r", [])
            filtered = [a for a in all_anomalies if a.get("Poste de travail") in selected_posts]
            with st.spinner("Génération en cours..."):
                result = generate_action_plan(filtered, api_key, model)
            if result:
                st.markdown(result)
            else:
                st.warning("Aucune anomalie ou erreur.")

    with col2:
        st.markdown("### 💡 Recommandations IA")
        if st.button("Générer les recommandations", disabled=not api_key, use_container_width=True):
            with st.spinner("Génération en cours..."):
                result = generate_recommendations(kpi_data, api_key, model)
            if result:
                st.markdown(result)

    st.markdown("---")
    st.markdown('<div class="stl">EXPORT POWERPOINT</div>', unsafe_allow_html=True)

    if st.button("📊 Générer le PowerPoint", use_container_width=True):
        with st.spinner("Génération du PowerPoint..."):
            ppt_data = {
                "date": st.session_state.get("date_str", ""),
                "p_rows": [r for r in kpi_data.get("p_rows", []) if r.get("Poste de travail") in selected_posts],
                "p_cols": kpi_data.get("p_cols", []),
                "q_rows": [r for r in kpi_data.get("q_rows", []) if r.get("Poste de travail") in selected_posts],
                "q_cols": kpi_data.get("q_cols", []),
                "ano_p_r": [a for a in kpi_data.get("ano_p_r", []) if a.get("Poste de travail") in selected_posts],
                "ano_p_c": kpi_data.get("ano_p_c", []),
            }
            result = generate_pptx(ppt_data)
            if result:
                with open(result, "rb") as f:
                    st.download_button(
                        "📥 Télécharger le PowerPoint", data=f.read(),
                        file_name="Dashboard_KPI.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
            else:
                st.error("Échec. Vérifiez que python-pptx est installé.")


if "kpi_data" not in st.session_state:
    st.warning("⚠️ Veuillez d'abord charger les fichiers depuis la page d'accueil.")
    st.stop()

render(
    st.session_state["kpi_data"],
    st.session_state.get("selected_posts", [])
)
