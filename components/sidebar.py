# -*- coding: utf-8 -*-
"""Barre latérale : filtres et paramètres."""
import streamlit as st


def render_sidebar(posts, fichier_date):
    """
    Affiche la sidebar avec :
      - Sélecteur de postes
      - Upload fichiers OT et Avis
      - Date

    Retourne (selected_posts, ot_file, av_file)
    """
    with st.sidebar:
        st.markdown("### 📂 Fichiers source")

        ot_file = st.file_uploader(
            "Fichier OT (.xlsx/.xls)",
            type=["xlsx", "xls"],
            key="ot_uploader"
        )

        av_file = st.file_uploader(
            "Fichier Avis (.xlsx/.xls)",
            type=["xlsx", "xls"],
            key="av_uploader"
        )

        st.markdown("---")
        st.markdown("### 🔍 Filtres")

        if posts:
            selected_posts = st.multiselect(
                "Postes de travail",
                options=posts,
                default=posts,
                key="poste_select"
            )
        else:
            selected_posts = []
            st.info("Chargez les fichiers pour voir les postes.")

        st.markdown("---")
        st.markdown(f"📅 **Date** : {fichier_date}")

        st.markdown("---")
        st.markdown("""
        <div style="text-align:center;padding:10px;color:rgba(255,255,255,0.5);font-size:11px;">
            Dashboard KPI v1.0<br>
            Maintenance Industrielle
        </div>
        """, unsafe_allow_html=True)

    return selected_posts, ot_file, av_file
