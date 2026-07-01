# -*- coding: utf-8 -*-
import streamlit as st
import random
import time
from components.styles import inject_custom_css
from components.sidebar import render_sidebar
from components.header import render_header
from components.cards import get_previous_card_values
from core.prepare_data import prepare_data, get_date_from_file
from core.calcul_kpi import calc_kpis
from core.historique import load_historical_kpis, calculate_variations
from core.export_excel import save_kpis_to_excel
from core.constants import CONSIGNES_HSE

st.set_page_config(
    layout="wide",
    page_title="Dashboard KPI",
    page_icon="🏭",
    initial_sidebar_state="expanded"
)

inject_custom_css()

# ── Écran HSE ──
if "hse_affiche" not in st.session_state:
    st.session_state.hse_affiche = False

if not st.session_state.hse_affiche:
    c = random.choice(CONSIGNES_HSE)
    st.markdown("""<div style="min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;background:linear-gradient(135deg,#1a365d,#2d3748,#1a365d);padding:40px">
    <div style="font-size:64px;margin-bottom:20px">🦺</div>
    <h1 style="text-align:center;font-size:46px;color:#fff;font-weight:900;margin:0">HSE - CONSIGNE DE SECURITE</h1>
    <p style="text-align:center;color:rgba(255,255,255,.6);font-size:22px;margin-top:8px;letter-spacing:3px;text-transform:uppercase">Securite - Sante - Environnement</p>
    <div style="background:linear-gradient(135deg,#f6e05e,#ed8936);padding:36px 48px;border-radius:20px;font-size:32px;font-weight:700;text-align:center;margin:40px 0;color:#1a202c;max-width:800px;box-shadow:0 20px 60px rgba(0,0,0,.3)">⚠️ %s</div>
    <h2 style="text-align:center;color:#48bb78;font-size:36px;font-weight:900">Aucun travail n'est plus urgent que la securite</h2>
    <div style="margin-top:40px;width:200px;height:4px;background:rgba(255,255,255,.1);border-radius:2px;overflow:hidden"><div style="width:100%%;height:100%%;background:linear-gradient(90deg,#48bb78,#38a169);border-radius:2px;animation:ld 5.5s ease-in-out forwards"></div></div>
    <style>@keyframes ld{from{width:0}to{width:100%%}}</style></div>""" % c, unsafe_allow_html=True)
    time.sleep(6)
    st.session_state.hse_affiche = True
    st.rerun()
    st.stop()

# ── Sidebar ──
fichier_date = get_date_from_file()

# Première passe : lire les fichiers pour avoir la liste des postes
ot_file = st.sidebar.file_uploader("Fichier OT (.xlsx/.xls)", type=["xlsx", "xls"], key="ot_up")
av_file = st.sidebar.file_uploader("Fichier Avis (.xlsx/.xls)", type=["xlsx", "xls"], key="av_up")

# Postes par défaut (vide tant que pas de fichier)
default_posts = st.session_state.get("posts_disponibles", [])

selected_posts = st.sidebar.multiselect(
    "Postes de travail", options=default_posts, default=default_posts, key="poste_select"
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"📅 **Date** : {fichier_date}")
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="text-align:center;padding:10px;color:rgba(255,255,255,0.5);font-size:11px;">
    Dashboard KPI v1.0<br>Maintenance Industrielle
</div>
""", unsafe_allow_html=True)

# ── Traitement principal ──
if ot_file and av_file:
    try:
        df, avf, apm, now_ts, av_total = prepare_data(ot_file.read(), av_file.read(), fichier_date)

        # Mettre à jour les postes disponibles
        if apm != st.session_state.get("posts_disponibles"):
            st.session_state["posts_disponibles"] = apm
            st.session_state["selected_posts"] = apm
            selected_posts = apm

        # Filtrer les postes sélectionnés
        active_posts = [p for p in selected_posts if p in apm]
        if not active_posts:
            active_posts = apm

        # Calcul KPI
        kpi_data = calc_kpis(df, avf, now_ts, active_posts, av_total)

        # Historique
        hist_df = load_historical_kpis("data/historique.xlsx")

        # Sauvegarder dans session state pour les autres pages
        st.session_state["kpi_data"] = kpi_data
        st.session_state["df"] = df
        st.session_state["hist_df"] = hist_df
        st.session_state["date_str"] = fichier_date
        st.session_state["selected_posts"] = active_posts
        st.session_state["posts_disponibles"] = apm

        # Sauvegarde Excel historique
        save_kpis_to_excel(
            kpi_data["p_rows"], kpi_data["p_cols"],
            kpi_data["q_rows"], kpi_data["q_cols"],
            kpi_data["ano_p_r"], kpi_data["ano_p_c"],
            kpi_data["ano_q_r"], kpi_data["ano_q_c"],
            fichier_date
        )

        # ── Header sur la page d'accueil ──
        prev = get_previous_card_values(hist_df)
        render_header(fichier_date, kpi_data, prev)

        # ── Résumé rapide ──
        from components.tables import render_synthesis_table, render_anomaly_table
        from components.charts import show_pie_pair

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="stl">SCORE PERFORMANCE</div>', unsafe_allow_html=True)
            for poste in active_posts:
                sp = kpi_data["scores_perf"].get(poste, 0)
                c = "#10b981" if sp >= 80 else ("#f59e0b" if sp >= 60 else "#ef4444")
                st.markdown(f'''<div class="car">
                    <div class="cal">{poste}</div>
                    <div class="cab"><div class="caf" style="width:{min(sp,100)}%;background:{c}"></div></div>
                    <div class="cav-out">{sp:.1f}%</div>
                </div>''', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="stl">SCORE QUALITÉ</div>', unsafe_allow_html=True)
            for poste in active_posts:
                sq = kpi_data["scores_qual"].get(poste, 0)
                c = "#3b82f6" if sq >= 80 else ("#f59e0b" if sq >= 60 else "#ef4444")
                st.markdown(f'''<div class="car">
                    <div class="cal">{poste}</div>
                    <div class="cab"><div class="caf" style="width:{min(sq,100)}%;background:{c}"></div></div>
                    <div class="cav-out">{sq:.1f}%</div>
                </div>''', unsafe_allow_html=True)

        # Anomalies résumé
        nb_ano = kpi_data.get("nb_anomalies", 0)
        if nb_ano > 0:
            st.markdown(f'<div class="stl">⚠️ {nb_ano} ANOMALIE(S) DÉTECTÉE(S)</div>', unsafe_allow_html=True)
            all_ano = kpi_data.get("ano_p_r", []) + kpi_data.get("ano_q_r", [])
            render_anomaly_table(all_ano[:10], kpi_data.get("ano_p_c", []))
            if len(all_ano) > 10:
                st.info(f"… et {len(all_ano) - 10} autres. Voir la page Performance/Qualité pour le détail complet.")
        else:
            st.markdown('<div class="stl">✅ AUCUNE ANOMALIE</div>', unsafe_allow_html=True)
            st.markdown('<div class="es">Tous les KPI sont conformes aux cibles.</div>', unsafe_allow_html=True)

        st.markdown('<div class="footer">Dashboard KPI — Maintenance Industrielle</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement : {e}")
        import traceback
        st.code(traceback.format_exc())
else:
    st.markdown("""
    <div style="min-height:60vh;display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <div style="font-size:80px;margin-bottom:20px;">📁</div>
        <h2 style="color:#1e3a5f;font-weight:800;">Chargement des données</h2>
        <p style="color:#64748b;font-size:18px;margin-top:10px;">
            Uploadez les fichiers OT et Avis dans la barre latérale pour démarrer.
        </p>
    </div>
    """, unsafe_allow_html=True)
