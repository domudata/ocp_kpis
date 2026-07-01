# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import random, time, os, base64
from components.styles import inject_custom_css
from components.cards import get_previous_card_values, format_card_variation
from core.prepare_data import prepare_data, get_date_from_file
from core.calcul_kpi import calc_kpis
from core.historique import load_historical_kpis
from core.export_excel import save_kpis_to_excel
from core.constants import CONSIGNES_HSE

# --- FONCTION LOGO DÉPLACÉE ICI POUR ÉVITER LES ERREURS D'IMPORT ---
def get_logo_base64():
    for path in ["log.png", "assets/log.png", "logo.png", "./logo.png", "../logo.png"]:
        if os.path.exists(path):
            try:
                with open(path, "rb") as f: return base64.b64encode(f.read()).decode()
            except Exception: pass
    return None
# ----------------------------------------------------------------

st.set_page_config(layout="wide", page_title="Dashboard KPI", initial_sidebar_state="expanded")
inject_custom_css()

fichier_date = get_date_from_file()

if "hse_affiche" not in st.session_state: st.session_state.hse_affiche = False
if not st.session_state.hse_affiche:
    c = random.choice(CONSIGNES_HSE)
    st.markdown("""<div style="min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;background:linear-gradient(135deg,#1a365d,#2d3748,#1a365d);padding:40px">
    <div style="font-size:64px;margin-bottom:20px">🦺</div>
    <h1 style="text-align:center;font-size:46px;color:#fff;font-weight:900;margin:0">HSE - CONSIGNE DE SECURITE</h1>
    <p style="text-align:center;color:rgba(255,255,255,.6);font-size:22px;margin-top:8px;letter-spacing:3px;text-transform:uppercase">Securite - Sante - Environnement</p>
    <div style="background:linear-gradient(135deg,#f6e05e,#ed8936);padding:36px 48px;border-radius:20px;font-size:32px;font-weight:700;text-align:center;margin:40px 0;color:#1a202c;max-width:800px;box-shadow:0 20px 60px rgba(0,0,0,.3)">⚠️ %s</div>
    <h2 style="text-align:center;color:#48bb78;font-size:36px;font-weight:900">Aucun travail n'est plus urgent que la securite</h2>
    <div style="margin-top:40px;width:200px;height:4px;background:rgba(255,255,255,.1);border-radius:2px;overflow:hidden"><div style="width:100%%;height:100%%;background:linear-gradient(90deg,#48bb78,#38a169);border-radius:2px;animation:ld 5.5s ease-in-out forwards"></div></div>
    <style>@keyframes ld{from{width:0}to{width:100%%}</style></div>"""%c, unsafe_allow_html=True)
    time.sleep(6); st.session_state.hse_affiche = True; st.rerun(); st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 📅 Période")
    c1, c2 = st.columns(2)
    with c1: date_debut = st.date_input("Du", value=pd.to_datetime("2025-01-01"))
    with c2: date_fin = st.date_input("Au", value=pd.Timestamp.today())
    st.markdown("---"); st.markdown("### 🔧 Filtres")
    poste_filter = st.multiselect("Poste de travail", st.session_state.get("posts_dispo", []))
    atelier_filter = st.multiselect("Atelier", st.session_state.get("ateliers_dispo", []))
    division_filter = st.multiselect("Division", st.session_state.get("divisions_dispo", []))
    st.markdown("---"); st.markdown(f"📅 **Date** : {fichier_date}")
    st.markdown("---"); st.markdown("""<div style="text-align:center;padding:10px;color:rgba(255,255,255,0.5);font-size:11px;">Dashboard KPI v1.0<br>Maintenance Industrielle</div>""", unsafe_allow_html=True)

# --- LECTURE AUTO ---
if not os.path.exists("ot.xlsx") or not os.path.exists("avis.xlsx"):
    st.error("Fichiers ot.xlsx et avis.xlsx introuvables dans le répertoire de l'application."); st.stop()

with open("ot.xlsx", "rb") as f: ot_bytes = f.read()
with open("avis.xlsx", "rb") as f: av_bytes = f.read()
df, avf, apm, now_ts = prepare_data(ot_bytes, av_bytes, fichier_date)

COL_ATELIER = next((c for c in df.columns if "atelier" in str(c).lower()), None)
COL_DIVISION = next((c for c in df.columns if "division" in str(c).lower() or "divis" in str(c).lower()), None)

if "filtres_inities" not in st.session_state:
    st.session_state.filtres_inities = True
    st.session_state.posts_dispo = apm
    st.session_state.ateliers_dispo = sorted(df[COL_ATELIER].dropna().unique().tolist()) if COL_ATELIER else []
    st.session_state.divisions_dispo = sorted(df[COL_DIVISION].dropna().unique().tolist()) if COL_DIVISION else []
    st.rerun()

# --- APPLICATION FILTRES ---
df_f = df.copy()
if "Créé le" in df_f.columns:
    df_f = df_f[(df_f["Créé le"] >= pd.Timestamp(date_debut)) & (df_f["Créé le"] <= pd.Timestamp(date_fin).replace(hour=23, minute=59))]
if poste_filter: df_f = df_f[df_f["Poste travail princ."].isin(poste_filter)]
if atelier_filter and COL_ATELIER: df_f = df_f[df_f[COL_ATELIER].isin(atelier_filter)]
if division_filter and COL_DIVISION: df_f = df_f[df_f[COL_DIVISION].isin(division_filter)]
posts = sorted(df_f[df_f["Poste travail princ."].astype(str).str.startswith(("SF1","SF2"),na=False)]["Poste travail princ."].dropna().unique().tolist())
if not posts: posts = sorted(df_f["Poste travail princ."].dropna().unique().tolist())

# --- CALCUL & HISTORIQUE ---
kpis = calc_kpis(df_f, avf, now_ts, posts)
hist_df = load_historical_kpis("data/historique.xlsx")
save_kpis_to_excel(kpis["prows"], kpis["pcols"], kpis["qrows"], kpis["qcols"], kpis["ano_p_r"], kpis["ano_p_c"], kpis["ano_q_r"], kpis["ano_q_c"], fichier_date)

# --- HEADER & CARTES ---
prev = get_previous_card_values(hist_df)
logo_b64 = get_logo_base64()
logo_html = f'<img class="logo" src="data:image/png;base64,{logo_b64}" alt="Logo">' if logo_b64 else ""

sp = kpis["prows"]; sq = kpis["qrows"]
cards = [
    (len(df_f), "OT Analysés", "c1", prev.get("OT Analysés")),
    (round(sp[-2].get("Score Performance",0),1), "Score Perf. Global", "c2", prev.get("Score Performance Global")),
    (round(sq[-2].get("Score Qualite",0),1), "Score Qual. Global", "c3", prev.get("Score Qualité Global")),
    (len(kpis["ano_p_r"])+len(kpis["ano_q_r"]), "Anomalies Totales", "c4", prev.get("Anomalies Totales")),
]
cards_html = "".join(f'<div class="cc {cls}"><div class="cv">{val}</div><div class="cl">{label}</div>{format_card_variation(val, p)}</div>' for val,label,cls,p in cards)

st.markdown(f'<div class="mh">{logo_html}<h1>DASHBOARD KPI</h1><div class="db">{fichier_date}</div></div><div class="cr">{cards_html}</div>', unsafe_allow_html=True)

# --- ONGLETS ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏠 Tableau de Bord","📈 Performance","✅ Qualite","📂 Backlog","📉 Suivi & Evolution","🎯 Plan d' action"])

with tab1:
    from pages.dashboard import render as rd; rd(kpis)
with tab2:
    from pages.performance import render as rp; rp(kpis, posts)
with tab3:
    from pages.qualite import render as rq; rq(kpis, posts)
with tab4:
    from pages.backlog import render as rb; rb(kpis, df_f, posts)
with tab5:
    from pages.evolution import render as re; re(hist_df, kpis, posts)
with tab6:
    from pages.plan_action import render as rpa; rpa(kpis, posts)
