# -*- coding: utf-8 -*-
"""Page IA & PowerPoint — génération par intelligence artificielle et export PPT."""
import streamlit as st
from core.ai_generator import generate_action_plan, generate_recommendations
from core.export_ppt import generate_pptx


def render(kpi_data, selected_posts):
    """Affiche la page IA & PowerPoint."""
    st.markdown('<div class="stl">INTELLIGENCE ARTIFICIELLE & POWERPOINT</div>',
                unsafe_allow_html=True)

    # ── Clé API ──
    api_key = st.text_input("Clé API OpenAI", type="password", key="openai_key")
    model = st.selectbox("Modèle", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], key="ai_model")

    if not api_key:
        st.info("Entrez votre clé API OpenAI pour utiliser les fonctionnalités IA.")
        st.markdown("---")

    # ── Génération Plan d'action IA ──
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
                st.warning("Aucune anomalie à traiter ou erreur de génération.")

    with col2:
        st.markdown("### 💡 Recommandations IA")
        if st.button("Générer les recommandations", disabled=not api_key, use_container_width=True):
            with st.spinner("Génération en cours..."):
                result = generate_recommendations(kpi_data, api_key, model)
            if result:
                st.markdown(result)

    # ── Export PowerPoint ──
    st.markdown("---")
    st.markdown('<div class="stl">EXPORT POWERPOINT</div>', unsafe_allow_html=True)

    col_ppt1, col_ppt2 = st.columns(2)
    with col_ppt1:
        if st.button("📊 Générer le PowerPoint", use_container_width=True):
            with st.spinner("Génération du PowerPoint..."):
                ppt_data = {
                    "date": kpi_data.get("date", ""),
                    "p_rows": [r for r in kpi_data.get("p_rows", [])
                               if r.get("Poste de travail") in selected_posts],
                    "p_cols": kpi_data.get("p_cols", []),
                    "q_rows": [r for r in kpi_data.get("q_rows", [])
                               if r.get("Poste de travail") in selected_posts],
                    "q_cols": kpi_data.get("q_cols", []),
                    "ano_p_r": [a for a in kpi_data.get("ano_p_r", [])
                                if a.get("Poste de travail") in selected_posts],
                    "ano_p_c": kpi_data.get("ano_p_c", []),
                }
                result = generate_pptx(ppt_data)
                if result:
                    with open(result, "rb") as f:
                        st.download_button(
                            "📥 Télécharger le PowerPoint",
                            data=f.read(),
                            file_name="Dashboard_KPI.pptx",
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                        )
                else:
                    st.error("La génération PowerPoint a échoué. Vérifiez que python-pptx est installé.")
