# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import random
import time
import os
import base64
from datetime import datetime

from components.styles import inject_custom_css
from components.header import render_header
from components.cards import get_previous_card_values
from core.prepare_data import prepare_data, get_date_from_file, read_excel_safe
from core.calcul_kpi import calc_kpis
from core.historique import load_historical_kpis
from core.export_excel import save_kpis_to_excel
from core.constants import CONSIGNES_HSE

st.set_page_config(
    layout="wide",
    page_title="Dashboard KPI",
    page_icon="🏭",
    initial_sidebar_state="expanded"
)

inject_custom_css()

# ══════════════════════════════════════════════════════════════
# ÉCRAN HSE
# ══════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════
# SIDEBAR — FILTRES
# ══════════════════════════════════════════════════════════════
fichier_date = get_date_from_file()

with st.sidebar:
    st.markdown("### 📅 Période")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        date_debut = st.date_input("Du", value=pd.to_datetime("2025-01-01"), key="date_debut")
    with col_d2:
        date_fin = st.date_input("Au", value=pd.Timestamp.today(), key="date_fin")

    st.markdown("---")
    st.markdown("### 🔧 Filtres")

    # Ces selectbox seront remplies après le chargement des données
    poste_filter = st.multiselect("Poste de travail", [], key="poste_filter")
    atelier_filter = st.multiselect("Atelier", [], key="atelier_filter")
    division_filter = st.multiselect("Division", [], key="division_filter")

    st.markdown("---")
    st.markdown(f"📅 **Date données** : {fichier_date}")
    st.markdown("---")
    st.markdown("""
    <div style="text-align:center;padding:10px;color:rgba(255,255,255,0.5);font-size:11px;">
        Dashboard KPI v1.0<br>Maintenance Industrielle
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# CHARGEMENT AUTOMATIQUE DES DONNÉES LOCALES
# ══════════════════════════════════════════════════════════════
OT_PATH = "ot.xlsx"
AV_PATH = "avis.xlsx"

if not os.path.exists(OT_PATH) or not os.path.exists(AV_PATH):
    st.markdown("""
    <div style="min-height:60vh;display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <div style="font-size:80px;margin-bottom:20px;">📁</div>
        <h2 style="color:#1e3a5f;font-weight:800;">Fichiers de données introuvables</h2>
        <p style="color:#64748b;font-size:18px;margin-top:10px;">
            Placez les fichiers <b>ot.xlsx</b> et <b>avis.xlsx</b> dans le répertoire de l'application.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

try:
    with open(OT_PATH, "rb") as f:
        ot_bytes = f.read()
    with open(AV_PATH, "rb") as f:
        av_bytes = f.read()

    df, avf, apm, now_ts, av_total = prepare_data(ot_bytes, av_bytes, fichier_date)

    # ── Détecter colonnes Atelier / Division ──
    COL_ATELIER = None
    COL_DIVISION = None
    for c in df.columns:
        cl = str(c).lower().strip()
        if "atelier" in cl:
            COL_ATELIER = c
        if "division" in cl or "divis" in cl:
            COL_DIVISION = c

    ateliers_dispo = sorted(df[COL_ATELIER].dropna().unique().tolist()) if COL_ATELIER else []
    divisions_dispo = sorted(df[COL_DIVISION].dropna().unique().tolist()) if COL_DIVISION else []

    # ── Mettre à jour les filtres sidebar dynamiquement ──
    if "filtres_inities" not in st.session_state:
        st.session_state.filtres_inities = True
        # Forcer le réaffichage pour peupler les multiselects
        st.rerun()

    # ── Appliquer les filtres ──
    df_filtre = df.copy()

    # Filtre période sur "Créé le"
    if "Créé le" in df_filtre.columns:
        dt_debut = pd.Timestamp(date_debut)
        dt_fin = pd.Timestamp(date_fin).replace(hour=23, minute=59, second=59)
        df_filtre = df_filtre[
            (df_filtre["Créé le"] >= dt_debut) & (df_filtre["Créé le"] <= dt_fin)
        ]

    # Filtre poste
    if poste_filter:
        df_filtre = df_filtre[df_filtre["Poste travail princ."].isin(poste_filter)]

    # Filtre atelier
    if atelier_filter and COL_ATELIER:
        df_filtre = df_filtre[df_filtre[COL_ATELIER].isin(atelier_filter)]

    # Filtre division
    if division_filter and COL_DIVISION:
        df_filtre = df_filtre[df_filtre[COL_DIVISION].isin(division_filter)]

    # Postes actifs après filtrage
    active_posts = sorted(
        df_filtre[df_filtre["Poste travail princ."].astype(str).str.startswith(("SF1", "SF2"), na=False)]
        ["Poste travail princ."].dropna().unique().tolist()
    )
    if not active_posts:
        active_posts = sorted(df_filtre["Poste travail princ."].dropna().unique().tolist())

    # Avis filtrés
    avf_filtre = avf.copy()
    if poste_filter and "Poste travail princ." in avf_filtre.columns:
        avf_filtre = avf_filtre[avf_filtre["Poste travail princ."].isin(poste_filter)]

    # Recalcul av_total filtré
    av_total_filtre = None
    if av_total is not None:
        av_total_filtre = av_total.copy()
        if poste_filter:
            av_total_filtre = av_total_filtre[av_total_filtre.index.isin(poste_filter)]

    # ── Calcul KPI ──
    kpi_data = calc_kpis(df_filtre, avf_filtre, now_ts, active_posts, av_total_filtre)

    # ── Historique ──
    hist_df = load_historical_kpis("data/historique.xlsx")

    # ── Sauvegarde Excel ──
    save_kpis_to_excel(
        kpi_data["p_rows"], kpi_data["p_cols"],
        kpi_data["q_rows"], kpi_data["q_cols"],
        kpi_data["ano_p_r"], kpi_data["ano_p_c"],
        kpi_data["ano_q_r"], kpi_data["ano_q_c"],
        fichier_date
    )

except Exception as e:
    st.error(f"❌ Erreur lors du traitement des données : {e}")
    import traceback
    st.code(traceback.format_exc())
    st.stop()

# ══════════════════════════════════════════════════════════════
# HEADER AVEC LOGO
# ══════════════════════════════════════════════════════════════
prev = get_previous_card_values(hist_df)
render_header(fichier_date, kpi_data, prev)

# ══════════════════════════════════════════════════════════════
# RÉSUMÉ FILTRES APPLIQUÉS
# ══════════════════════════════════════════════════════════════
nb_total = len(df)
nb_filtre = len(df_filtre)
filtres_actifs = []
if date_debut != pd.to_datetime("2025-01-01") or date_fin != pd.Timestamp.today().normalize():
    filtres_actifs.append(f"Période: {date_debut.strftime('%d/%m/%Y')} → {date_fin.strftime('%d/%m/%Y')}")
if poste_filter:
    filtres_actifs.append(f"Postes: {len(poste_filter)} sélectionné(s)")
if atelier_filter:
    filtres_actifs.append(f"Ateliers: {len(atelier_filter)} sélectionné(s)")
if division_filter:
    filtres_actifs.append(f"Divisions: {len(division_filter)} sélectionnée(s)")

if filtres_actifs:
    st.markdown(f'''
    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:8px 16px;
                margin-bottom:8px;font-size:13px;color:#1e40af;">
        🔍 Filtres actifs : {' | '.join(filtres_actifs)}
        &nbsp;—&nbsp; <b>{nb_filtre}</b> OT affichés sur {nb_total}
    </div>''', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# ONGLETS (comme la capture d'écran)
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 Tableau de Bord",
    "📈 Performance",
    "✅ Qualite",
    "📂 Backlog",
    "📉 Suivi & Evolution",
    "🎯 Plan d' action"
])

with tab1:
    from pages.dashboard import render as render_dashboard
    render_dashboard(kpi_data, hist_df, active_posts)

with tab2:
    from pages.performance import render as render_perf
    render_perf(kpi_data, hist_df, active_posts)

with tab3:
    from pages.qualite import render as render_qual
    render_qual(kpi_data, hist_df, active_posts)

with tab4:
    from pages.backlog import render as render_backlog
    render_backlog(kpi_data, df_filtre, active_posts)

with tab5:
    from pages.evolution import render as render_evo
    render_evo(hist_df, kpi_data, active_posts)

with tab6:
    from pages.plan_action import render as render_plan
    render_plan(kpi_data, active_posts)
