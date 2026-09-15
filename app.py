# -*- coding: utf-8 -*-
import locale
import os
import random
import time
import traceback

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(layout="wide", page_title="Dashboard KPI", initial_sidebar_state="expanded")

# ── Imports protégés
try:
    from core.constants import (
        QK, PK, ALL_KPI, CIBLE, ACT_MAP, KPI_RESP_MAP,
        LOWER_BETTER, CONSIGNES_HSE,
    )
    from core.prepare_data import prepare_data, get_date_from_file
    
    try:
        from core.kpi import calc_kpis, gscore, is_lb
    except ImportError:
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
    from pages.frequence_maintenance import render_frequence_maintenance_tab
    from pages.suivi_hse import render_suivi_hse_tab
    _IMPORT_ERROR = None
except Exception as _e:
    _IMPORT_ERROR = traceback.format_exc()


# ── VERSION DE CALCUL
import hashlib as _hashlib
import os as _os

def _calc_signature():
    h = _hashlib.md5()
    base_dir = _os.path.dirname(_os.path.abspath(__file__))
    found_any = False
    for _f in ("core/kpi.py", "core/calcul_kpi.py", "core/anomalies.py", "core/prepare_data.py"):
        _path = _os.path.join(base_dir, _f)
        try:
            with open(_path, "rb") as _fh:
                h.update(_fh.read())
                found_any = True
        except Exception:
            pass
    if not found_any:
        h.update(str(_os.path.getmtime(_os.path.abspath(__file__))).encode())
    return h.hexdigest()[:12], found_any

CALC_VERSION, _CALC_SIG_OK = _calc_signature()


@st.cache_data(show_spinner="Calcul des KPIs en cours...")
def calc_kpis_cached(df_period, avdf_period, now_ts, apm_tuple, fichier_date, sdt, edt, df_toutes_dates, calc_version=CALC_VERSION):
    return calc_kpis(df_period, avdf_period, now_ts, list(apm_tuple), df_toutes_dates=df_toutes_dates)


# ── FONCTION DE CALCUL DES SCORES PAR DIVISION (SF1 / SF2) ───────────────────
def calc_score_division(postes, liste_kpi, ano_map, ckdf, df_ot=None):
    """
    Calcule le score global d'une division (SF1 / SF2) :
    - Backlog (âges) : Moyenne simple des valeurs des postes.
    - OT Correctif : Ratio (Non / Total OT).
    - OT_COR_EGAL : Calcul SUR PLACE (Oui / Total ZCOR) basé sur Coût réel vs Coût estimé.
    - Autres KPIs : Ratio standard Oui / (Oui + Non).
    """
    if not postes:
        return 0

    total_gscores = 0
    nb_kpis_valides = 0

    for kpi in liste_kpi:
        if kpi not in CIBLE:
            continue

        postes_presents = [p for p in postes if p in ckdf.index]
        if not postes_presents:
            continue

        # 1. KPIs d'âge du backlog : Moyenne simple
        if "préparation" in kpi or "planification" in kpi or "exécution" in kpi:
            vals = [ckdf.loc[p, kpi] for p in postes_presents if kpi in ckdf.columns and pd.notna(ckdf.loc[p, kpi])]
            if vals:
                valeur_globale = sum(vals) / len(vals)
                total_gscores += gscore(kpi, valeur_globale, CIBLE[kpi])
                nb_kpis_valides += 1
            continue

        # 2. Traitement SUR PLACE de OT_COR_EGAL
        if kpi in ("OT_COR_EGAL", "OT Cor Egal") and df_ot is not None and not df_ot.empty:
            mask_zcor = (
                df_ot["Poste travail princ."].isin(postes_presents) &
                df_ot["Type d'ordre"].astype(str).str.contains("ZCOR", case=False, na=False)
            )
            df_zcor = df_ot[mask_zcor]
            tot_vol = len(df_zcor)

            if tot_vol > 0 and "Coût réel" in df_zcor.columns and "Coût estimé" in df_zcor.columns:
                # Évaluation directe sur place : Écart absolu < 0.01
                nb_oui = float(((df_zcor["Coût réel"] - df_zcor["Coût estimé"]).abs() <= 0.01).sum())
                valeur_globale = (nb_oui / tot_vol) * 100.0
            else:
                valeur_globale = 100.0

            total_gscores += gscore(kpi, valeur_globale, CIBLE[kpi])
            nb_kpis_valides += 1
            continue

        # 3. Récupération des anomalies (Non) pour les autres KPIs
        if kpi in ano_map:
            s_anom = ano_map[kpi].reindex(postes_presents).fillna(0)
            nb_non = float(s_anom.sum())
        else:
            nb_non = 0.0

        vals_kpi = [ckdf.loc[p, kpi] for p in postes_presents if kpi in ckdf.columns and pd.notna(ckdf.loc[p, kpi])]
        if not vals_kpi:
            continue

        avg_val = sum(vals_kpi) / len(vals_kpi)

        # 4. Exception OT Correctif
        if kpi == "OT Correctif":
            tot_vol = (nb_non / (avg_val / 100)) if avg_val > 0 else nb_non
            valeur_globale = (nb_non / tot_vol * 100) if tot_vol > 0 else 0.0
        else:
            # 5. Règle standard : Oui / (Oui + Non)
            if is_lb(kpi):
                valeur_globale = avg_val
            else:
                tot_vol = (nb_non / ((100 - avg_val) / 100)) if (100 - avg_val) > 0 else nb_non
                nb_oui = max(0, tot_vol - nb_non)
                valeur_globale = (nb_oui / tot_vol * 100) if tot_vol > 0 else 100.0

        total_gscores += gscore(kpi, valeur_globale, CIBLE[kpi])
        nb_kpis_valides += 1

    return round((total_gscores / nb_kpis_valides) * 100, 2) if nb_kpis_valides > 0 else 0


def main() -> None:
    if _IMPORT_ERROR is not None:
        st.error("❌ Erreur lors du chargement des modules (import). Copiez ce texte :")
        st.code(_IMPORT_ERROR, language="python")
        st.stop()

    try:
        locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')
    except Exception:
        try:
            locale.setlocale(locale.LC_ALL, 'fr_FR')
        except Exception:
            pass

    inject_custom_css()
    st.markdown('<style>[data-testid="stSidebarNav"] { display: none; }</style>', unsafe_allow_html=True)

    fichier_date = get_date_from_file()

    if "hse_affiche" not in st.session_state:
        st.session_state.hse_affiche = False

    if not st.session_state.hse_affiche:
        c = random.choice(CONSIGNES_HSE)
        st.markdown("""
        <div style="min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;background:linear-gradient(135deg,#1a365d,#2d3748,#1a365d);padding:40px">
        <div style="font-size:64px;margin-bottom:20px">&#128282;</div>
        <h1 style="text-align:center;font-size:46px;color:#fff;font-weight:900;margin:0">HSE - CONSIGNE DE SECURITE</h1>
        <p style="text-align:center;color:rgba(255,255,255,.6);font-size:22px;margin-top:8px;letter-spacing:3px;text-transform:uppercase">Securite - Sante - Environnement</p>
        <div style="background:linear-gradient(135deg,#f6e05e,#ed8936);padding:36px 48px;border-radius:20px;font-size:32px;font-weight:700;text-align:center;margin:40px 0;color:#1a202c;max-width:800px;box-shadow:0 20px 60px rgba(0,0,0,.3)">%s</div>
        <h2 style="text-align:center;color:#48bb78;font-size:36px;font-weight:900">Aucun travail n'est plus urgent que la securite</h2>
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
        df_full, av_full, apm, now_ts, avis_complet_full = prepare_data(ot_bytes, av_bytes, fichier_date)
    else:
        df_full, av_full, apm, now_ts = pd.DataFrame(), pd.DataFrame(), [], pd.Timestamp.now()
        avis_complet_full = pd.DataFrame()

    ctx = render_sidebar(fichier_date, apm, df_full, av_full, now_ts)
    vp      = ctx["vp"]
    df_full = ctx["df_full"]
    av_full = ctx["av_full"]
    apm     = ctx["apm"]
    now_ts  = ctx["now_ts"]

    if df_full.empty:
        st.markdown('<div class="es">Veuillez charger les fichiers OT et AVIS via le panneau de filtres.</div>', unsafe_allow_html=True)
        return

    try:
        sdt, edt = ctx["sdt"], ctx["edt"]

        df_period = df_full[df_full["Date de début planifiée"].between(sdt, edt)].copy()
        avdf_period = av_full.copy()
        if "Créé le" in avdf_period.columns:
            avdf_period = avdf_period[avdf_period["Créé le"].between(sdt, edt)]

        res = calc_kpis_cached(df_period, avdf_period, now_ts, tuple(apm), fichier_date, sdt, edt, df_full)

        ckdf_full = res['ckdf']
        dfp_full  = res['dfp']
        avf_full  = res['avf']

        vp_present = [p for p in vp if p in ckdf_full.index]
        ckdf = ckdf_full.loc[vp_present] if vp_present else ckdf_full.iloc[0:0]
        dfp  = dfp_full[dfp_full["Poste travail princ."].isin(vp)]
        avf  = avf_full[avf_full["Poste travail princ."].isin(vp)] if "Poste travail princ." in avf_full.columns else avf_full
        avis_complet = avis_complet_full[avis_complet_full["Poste travail princ."].isin(vp)] if "Poste travail princ." in avis_complet_full.columns else avis_complet_full
        df   = dfp

        pa = {k: round(ckdf[k].mean(skipna=True), 2) for k in QK}
        qa = {k: round(ckdf[k].mean(skipna=True), 2) for k in PK}

        pscores = {}
        qscores = {}
        for poste in ckdf.index:
            r = ckdf.loc[poste]
            valid_q = [k for k in QK if k in r.index and pd.notna(r[k])]
            valid_p = [k for k in PK if k in r.index and pd.notna(r[k])]
            pscores[poste] = (sum(gscore(k, r[k], CIBLE[k]) for k in valid_q) / len(valid_q) * 100) if valid_q else 0
            qscores[poste] = (sum(gscore(k, r[k], CIBLE[k]) for k in valid_p) / len(valid_p) * 100) if valid_p else 0

        # Building anomalies map
        ano_map = build_ano_map(dfp, avf, now_ts, dfp_toutes_dates=df_full)

        sf1_posts = [p for p in vp if str(p).startswith("SF1")]
        sf2_posts = [p for p in vp if str(p).startswith("SF2")]

        # Calcul sur place des divisions SF1 et SF2 avec transmission de dfp
        sf1_p = int(calc_score_division(sf1_posts, QK, ano_map, ckdf, df_ot=dfp))
        sf1_q = int(calc_score_division(sf1_posts, PK, ano_map, ckdf, df_ot=dfp))
        sf2_p = int(calc_score_division(sf2_posts, QK, ano_map, ckdf, df_ot=dfp))
        sf2_q = int(calc_score_division(sf2_posts, PK, ano_map, ckdf, df_ot=dfp))

        ano_p_rows = build_ano_rows(vp, ano_map, QK)
        ano_q_rows = build_ano_rows(vp, ano_map, PK, fixed_zero=["OT Fiabilité", "Total Avis de Panne"])
        ano_p_cols = ["Poste de travail"] + QK + ["Total Anomalies"]
        ano_q_cols = ["Poste de travail"] + PK + ["Total Anomalies"]
        anomaly_dfs = build_anomaly_dfs(dfp, avf, now_ts, dfp_toutes_dates=df_full)

        pcols = ["Poste de travail"] + QK + ["Score Performance"]
        qcols = ["Poste de travail"] + PK + ["Score Qualite"]
        prows, qrows = [], []

        for poste in ckdf.index:
            r = ckdf.loc[poste]
            prw = {"Poste de travail": poste}
            for k in QK:
                prw[k] = "%.1f" % r[k] if k in r.index else "0.0"
            prw["Score Performance"] = "%.2f" % pscores.get(poste, 0)
            prows.append(prw)
            
            qrw = {"Poste de travail": poste}
            for k in PK:
                qrw[k] = "%.1f" % r[k] if k in r.index else "0.0"
            qrw["Score Qualite"] = "%.2f" % qscores.get(poste, 0)
            qrows.append(qrw)

        tot_p = {"Poste de travail": "Total general", "_t": "total"}
        tot_p["Score Performance"] = "%.2f" % calc_score_division(vp, QK, ano_map, ckdf, df_ot=dfp)
        prows.append(tot_p)

        tot_q = {"Poste de travail": "Total general", "_t": "total"}
        tot_q["Score Qualite"] = "%.2f" % calc_score_division(vp, PK, ano_map, ckdf, df_ot=dfp)
        qrows.append(tot_q)

        render_header(fichier_date)
        render_cards(
            len(df), calc_score_division(vp, QK, ano_map, ckdf, df_ot=dfp),
            calc_score_division(vp, PK, ano_map, ckdf, df_ot=dfp), 0,
            sf1_p, sf1_q, sf2_p, sf2_q, {},
        )

        tabs = st.tabs([
            "🏠 Tableau de Bord", "📈 Performance", "✅ Qualite",
            "📂 Backlog", "📋 Suivi & Evolution", "🎯 Plan d'action",
            "🤖 Assistant IA", "🔄 Fréquence Maintenance", "🦺 Suivi HSE",
        ])

        with tabs[0]:
            render_dashboard_tab(vp, pscores, qscores, pa, qa)
        with tabs[1]:
            render_performance_tab(prows, pcols, ano_p_rows, ano_p_cols, pa)
        with tabs[2]:
            render_qualite_tab(qrows, qcols, ano_q_rows, ano_q_cols, qa)

    except Exception as e:
        st.error("Erreur lors de l'exécution : %s" % str(e))

if __name__ == "__main__":
    main()
