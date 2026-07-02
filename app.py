# -*- coding: utf-8 -*-
import locale
import os
import random
import time

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(layout="wide", page_title="Dashboard KPI", initial_sidebar_state="expanded")

from core.constants import (
    QK, PK, ALL_KPI, CIBLE, ACT_MAP, KPI_RESP_MAP,
    LOWER_BETTER, CONSIGNES_HSE,
)
from core.prepare_data import prepare_data, get_date_from_file
from core.calcul_kpi import calc_kpis, gscore, is_lb
from core.anomalies import build_ano_map, build_ano_rows, build_anomaly_dfs
from core.historique import (
    load_historical_kpis, calculate_variations,
    generate_journal, calculate_rankings,
)
from core.export_excel import save_kpis_to_excel

from components.styles import inject_custom_css
from components.header import render_header
from components.cards import get_previous_card_values, render_cards
from components.sidebar import render_sidebar

from pages.dashboard import render_dashboard_tab
from pages.performance import render_performance_tab
from pages.qualite import render_qualite_tab
from pages.backlog import render_backlog_page
from pages.evolution import render_evolution_tab
from pages.plan_action import render_plan_action_tab


def main() -> None:
    try:
        locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')
    except Exception:
        try:
            locale.setlocale(locale.LC_ALL, 'fr_FR')
        except Exception:
            pass

    inject_custom_css()
    fichier_date = get_date_from_file()

    if "hse_affiche" not in st.session_state:
        st.session_state.hse_affiche = False

    if not st.session_state.hse_affiche:
        c = random.choice(CONSIGNES_HSE)
        st.markdown("""
        <div style="min-height:100vh;display:flex;flex-direction:column;align-items:center;
             justify-content:center;background:linear-gradient(135deg,#1a365d,#2d3748,#1a365d);padding:40px">
          <div style="font-size:64px;margin-bottom:20px">🦺</div>
          <h1 style="text-align:center;font-size:46px;color:#fff;font-weight:900;margin:0">
            HSE - CONSIGNE DE SECURITE</h1>
          <p style="text-align:center;color:rgba(255,255,255,.6);font-size:22px;margin-top:8px;
             letter-spacing:3px;text-transform:uppercase">Securite - Sante - Environnement</p>
          <div style="background:linear-gradient(135deg,#f6e05e,#ed8936);padding:36px 48px;
               border-radius:20px;font-size:32px;font-weight:700;text-align:center;margin:40px 0;
               color:#1a202c;max-width:800px;box-shadow:0 20px 60px rgba(0,0,0,.3)">⚠️ %s</div>
          <h2 style="text-align:center;color:#48bb78;font-size:36px;font-weight:900">
            Aucun travail n'est plus urgent que la securite</h2>
          <div style="margin-top:40px;width:200px;height:4px;background:rgba(255,255,255,.1);
               border-radius:2px;overflow:hidden">
            <div style="width:100%%;height:100%%;background:linear-gradient(90deg,#48bb78,#38a169);
                 border-radius:2px;animation:ld 5.5s ease-in-out forwards"></div>
          </div>
          <style>@keyframes ld{from{width:0}to{width:100%%}}</style>
        </div>""" % c, unsafe_allow_html=True)
        time.sleep(6)
        st.session_state.hse_affiche = True
        st.rerun()
        st.stop()

    ot_bytes = av_bytes = None
    if os.path.exists("ot.xlsx") and os.path.exists("avis.xlsx"):
        with open("ot.xlsx", "rb") as f:
            ot_bytes = f.read()
        with open("avis.xlsx", "rb") as f:
            av_bytes = f.read()

    if ot_bytes and av_bytes:
        df_full, av_full, apm, now_ts = prepare_data(ot_bytes, av_bytes, fichier_date)
    else:
        df_full, av_full, apm, now_ts = pd.DataFrame(), pd.DataFrame(), [], pd.Timestamp.now()

    ctx     = render_sidebar(fichier_date, apm, df_full, av_full, now_ts)
    vp      = ctx["vp"]
    df_full = ctx["df_full"]
    av_full = ctx["av_full"]
    apm     = ctx["apm"]
    now_ts  = ctx["now_ts"]

    if df_full.empty:
        st.markdown('<div class="es">📁 Veuillez charger les fichiers OT et AVIS via le panneau de filtres.</div>', unsafe_allow_html=True)
        st.markdown('<div class="footer">Bureau Méthodes Maroc Chimie – © 2026 Tous droits réservés</div>', unsafe_allow_html=True)
        return

    try:
        sdt, edt = ctx["sdt"], ctx["edt"]

        df = df_full[
            df_full["Poste travail princ."].isin(vp)
            & df_full["Date de début planifiée"].between(sdt, edt)
        ].copy()

        avdf = av_full[av_full["Poste travail princ."].isin(vp)].copy()
        if "Créé le" in avdf.columns:
            avdf = avdf[avdf["Créé le"].between(sdt, edt)]

        df_dash   = df_full[df_full["Poste travail princ."].isin(vp)].copy()
        avdf_dash = av_full[av_full["Poste travail princ."].
