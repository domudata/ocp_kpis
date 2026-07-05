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


# ── VERSION DE CALCUL ────────────────────────────────────────────────────────
# IMPORTANT : incrementer ce numero a CHAQUE modification de core/calcul_kpi.py,
# core/prepare_data.py ou core/anomalies.py.
# Streamlit ne hash que le code de la fonction decoree par @st.cache_data,
# PAS les fonctions internes appelees — sans ce numero, le cache continuerait
# de servir les valeurs calculees avec l ANCIEN code apres un deploiement.
CALC_VERSION = "v2.0"


@st.cache_data(show_spinner="Calcul des KPIs en cours...")
def calc_kpis_cached(df_period, avdf_period, now_ts, apm_tuple, fichier_date, sdt, edt, calc_version=CALC_VERSION):
    """
    Wrapper cache autour de calc_kpis().
    Cle de cache = (contenu de df_period/avdf_period, now_ts, apm_tuple, fichier_date, sdt, edt, calc_version).
    Le recalcul ne se declenche que si :
      - date.txt change (fichier_date change -> prepare_data change -> df_full change)
      - la periode (sdt/edt) change
      - les donnees sources (ot.xlsx / avis.xlsx) changent
      - CALC_VERSION est incremente (nouvelle version des formules)
    Changer la SELECTION DE POSTES (vp) ne redeclenche PAS ce calcul,
    car on calcule ici sur TOUS les postes (apm) puis on filtre ensuite dans main().
    """
    return calc_kpis(df_period, avdf_period, now_ts, list(apm_tuple))


def main() -> None:
    try:
        locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')
    except Exception:
        try:
            locale.setlocale(locale.LC_ALL, 'fr_FR')
        except Exception:
            pass

    inject_custom_css()
    st.markdown(
        '<style>[data-testid="stSidebarNav"] { display: none; }</style>',
        unsafe_allow_html=True
    )
    st.markdown("""
    <style>
    .cr { display:flex; flex-wrap:nowrap; gap:8px; margin-bottom:8px; overflow-x:auto; }
    .cc { flex:1 1 0; min-width:0; padding:10px 8px; text-align:center; background:#fff;
          border-radius:8px; border-left:3px solid #cbd5e1; box-shadow:0 1px 3px rgba(0,0,0,0.06); }
    .cc .cv { font-size:18px; font-weight:800; line-height:1.1; white-space:nowrap; }
    .cc .cd { font-size:10px; color:#f59e0b; margin:2px 0; }
    .cc .cl { font-size:10px; font-weight:700; color:#475569; text-transform:uppercase;
              white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .c1 { border-left-color:#3b82f6; } .c1 .cv{color:#3b82f6;}
    .c4 { border-left-color:#ef4444; } .c4 .cv{color:#ef4444;}
    .c5 { border-left-color:#14b8a6; } .c5 .cv{color:#14b8a6;}
    .c6 { border-left-color:#8b5cf6; } .c6 .cv{color:#8b5cf6;}
    .c7 { border-left-color:#f59e0b; } .c7 .cv{color:#f59e0b;}
    .c8 { border-left-color:#f97316; } .c8 .cv{color:#f97316;}
    @media (max-width: 768px) { .cc .cv { font-size:14px; } .cc .cl { font-size:8px; } }
    </style>
    """, unsafe_allow_html=True)
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
        <div style="margin-top:40px;width:200px;height:4px;background:rgba(255,255,255,.1);border-radius:2px;overflow:hidden">
        <div style="width:100%%;height:100%%;background:linear-gradient(90deg,#48bb78,#38a169);border-radius:2px;animation:ld 5.5s ease-in-out forwards"></div>
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

    ctx = render_sidebar(fichier_date, apm, df_full, av_full, now_ts)
    vp      = ctx["vp"]
    df_full = ctx["df_full"]
    av_full = ctx["av_full"]
    apm     = ctx["apm"]
    now_ts  = ctx["now_ts"]

    if df_full.empty:
        st.markdown('<div class="es">Veuillez charger les fichiers OT et AVIS via le panneau de filtres.</div>', unsafe_allow_html=True)
        st.markdown('<div class="footer">Bureau Methodes Maroc Chimie 2026</div>', unsafe_allow_html=True)
        return

    try:
        sdt, edt = ctx["sdt"], ctx["edt"]

        # ── Filtre par DATE uniquement (periode) sur TOUS les postes ───────
        # Le filtre par poste (vp) est applique APRES le calcul en cache,
        # pour que changer la selection de postes ne redeclenche PAS
        # tout le calcul lourd (pivot_table / groupby sur ~130k lignes).
        df_period = df_full[
            df_full["Date de début planifiée"].between(sdt, edt)
        ].copy()

        avdf_period = av_full.copy()
        if "Créé le" in avdf_period.columns:
            avdf_period = avdf_period[avdf_period["Créé le"].between(sdt, edt)]

        # ── Calcul KPIs (mis en cache, ne tourne que si date.txt/periode change) ──
        # calc_kpis() calcule correctement TOUS les KPIs incluant :
        # - OT CONFIME  (via pivot Statut système contient CONF)
        # - OT_COR_EGAL (via logique budget==reel, colonne OT_COR_EGAL=EGAL/DIFF)
        # - Age Prep/Plan/Exec en valeurs brutes (taux reel par tranche)
        # NE PAS recalculer ces KPIs ici — utiliser directement res['ckdf']
        res = calc_kpis_cached(df_period, avdf_period, now_ts, tuple(apm), fichier_date, sdt, edt)

        ckdf_full = res['ckdf']   # TOUS les postes (apm)
        dfp_full  = res['dfp']
        avf_full  = res['avf']

        # ── Filtre par postes selectionnes (vp) : simple filtrage, instantane ──
        vp_present = [p for p in vp if p in ckdf_full.index]
        ckdf = ckdf_full.loc[vp_present] if vp_present else ckdf_full.iloc[0:0]
        dfp  = dfp_full[dfp_full["Poste travail princ."].isin(vp)]
        avf  = avf_full[avf_full["Poste travail princ."].isin(vp)] if "Poste travail princ." in avf_full.columns else avf_full
        df   = dfp

        # mean() ignore nativement les NaN (skipna=True) : une cellule vide
        # (OT absent) n'est pas comptee dans la moyenne du KPI.
        pa = {k: round(ckdf[k].mean(skipna=True), 2) for k in QK}
        qa = {k: round(ckdf[k].mean(skipna=True), 2) for k in PK}

        pscores = {}
        qscores = {}
        for poste in ckdf.index:
            r = ckdf.loc[poste]
            # Exclure les KPIs NaN (cellule vide = OT absent) du calcul :
            # score = nb KPIs conformes / nb KPIs NON-NaN × 100
            valid_q = [k for k in QK if k in r.index and pd.notna(r[k])]
            valid_p = [k for k in PK if k in r.index and pd.notna(r[k])]
            pscores[poste] = (sum(gscore(k, r[k], CIBLE[k]) for k in valid_q) / len(valid_q) * 100) if valid_q else 0
            qscores[poste] = (sum(gscore(k, r[k], CIBLE[k]) for k in valid_p) / len(valid_p) * 100) if valid_p else 0

        sf1_posts = [p for p in vp if str(p).startswith("SF1")]
        sf2_posts = [p for p in vp if str(p).startswith("SF2")]
        sf1_p = np.nanmean([pscores[p] for p in sf1_posts]) if sf1_posts else 0
        sf1_q = np.nanmean([qscores[p] for p in sf1_posts]) if sf1_posts else 0
        sf2_p = np.nanmean([pscores[p] for p in sf2_posts]) if sf2_posts else 0
        sf2_q = np.nanmean([qscores[p] for p in sf2_posts]) if sf2_posts else 0

        ano_map    = build_ano_map(dfp, avf, now_ts)
        ano_p_rows = build_ano_rows(vp, ano_map, QK)
        ano_q_rows = build_ano_rows(vp, ano_map, PK, fixed_zero=["OT Fiabilité","Total Avis de Panne"])
        ano_p_cols = ["Poste de travail"] + QK + ["Total Anomalies"]
        ano_q_cols = ["Poste de travail"] + PK + ["Total Anomalies"]
        anomaly_dfs = build_anomaly_dfs(dfp, avf, now_ts)

        pcols = ["Poste de travail"] + QK + ["Score Performance"]
        qcols = ["Poste de travail"] + PK + ["Score Qualite"]
        prows = []
        qrows = []

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

        cible_p = {"Poste de travail": "CIBLE", "_t": "cible"}
        for k in QK:
            cible_p[k] = "%.0f" % CIBLE.get(k, 100)
        cible_p["Score Performance"] = "100"
        prows.append(cible_p)

        cible_q = {"Poste de travail": "CIBLE", "_t": "cible"}
        for k in PK:
            cible_q[k] = "%.0f" % CIBLE.get(k, 100)
        cible_q["Score Qualite"] = "100"
        qrows.append(cible_q)

        # Total general = moyenne directe des valeurs par KPI (NaN exclus)
        tot_p = {"Poste de travail": "Total general", "_t": "total"}
        for k in QK:
            vals = []
            for rw in prows:
                if k in rw and rw.get("_t") not in ("cible","total"):
                    try:
                        fv = float(rw[k])
                        if pd.notna(fv):        # exclure les NaN
                            vals.append(fv)
                    except Exception:
                        pass
            tot_p[k] = "%.1f" % (sum(vals) / len(vals)) if vals else "nan"
        tot_p["Score Performance"] = "%.2f" % (sum(pscores.values()) / len(pscores)) if pscores else "0.00"
        prows.append(tot_p)

        tot_q = {"Poste de travail": "Total general", "_t": "total"}
        for k in PK:
            vals = []
            for rw in qrows:
                if k in rw and rw.get("_t") not in ("cible","total"):
                    try:
                        fv = float(rw[k])
                        if pd.notna(fv):        # exclure les NaN
                            vals.append(fv)
                    except Exception:
                        pass
            tot_q[k] = "%.1f" % (sum(vals) / len(vals)) if vals else "nan"
        tot_q["Score Qualite"] = "%.2f" % (sum(qscores.values()) / len(qscores)) if qscores else "0.00"
        qrows.append(tot_q)

        save_kpis_to_excel(
            prows, pcols, qrows, qcols,
            ano_p_rows, ano_p_cols, ano_q_rows, ano_q_cols,
            fichier_date,
        )

        hist_filepath = os.path.join("kpis", "indicateurs_kpis.xlsx")
        hist_df  = load_historical_kpis(hist_filepath)
        var_df   = calculate_variations(hist_df)
        journal_df = generate_journal(var_df)
        top5_df, bot5_df = calculate_rankings(var_df)

        synth_perf = {}
        synth_qual = {}
        if not var_df.empty and "Date precedente" in var_df.columns:
            for poste in vp:
                synth_perf[poste] = {}
                synth_qual[poste] = {}
                pv = var_df[var_df["Poste"] == poste]
                for kpi in QK:
                    kpi_v = pv[pv["KPI"] == kpi]
                    synth_perf[poste][kpi] = {"diff": "%+.1f" % kpi_v.iloc[-1]["Ecart"]} if not kpi_v.empty else {"diff": "---"}
                for kpi in PK:
                    kpi_v = pv[pv["KPI"] == kpi]
                    synth_qual[poste][kpi] = {"diff": "%+.1f" % kpi_v.iloc[-1]["Ecart"]} if not kpi_v.empty else {"diff": "---"}

        plan_actions_rows = []
        for poste in vp:
            if poste not in ckdf.index:
                continue
            poste_data = ckdf.loc[poste]
            for kpi in ALL_KPI:
                actual  = float(poste_data.get(kpi, 100))
                target  = CIBLE.get(kpi, 100)
                nb_anom = int(ano_map.get(kpi, pd.Series()).get(poste, 0))
                lower   = is_lb(kpi)
                # Ecart SIGNE : positif = conforme, negatif = non conforme
                # (sens inverse pour les KPIs LOWER_BETTER)
                ecart = (target - actual) if lower else (actual - target)
                # 0 anomalie → ecart force a 0
                if nb_anom == 0:
                    ecart = 0.0
                conforme = (actual <= target) if lower else (actual >= target)
                # Statut a 3 etats :
                #   0 anomalie                → NON (vert)
                #   anomalies + sous cible    → OUI (rouge)
                #   anomalies + cible atteinte→ OUI (vert)
                if nb_anom == 0:
                    status = "non_vert"
                elif conforme:
                    status = "oui_vert"
                else:
                    status = "oui_rouge"
                # Inclure la ligne si anomalies OU si sous cible
                if nb_anom > 0 or not conforme:
                    plan_actions_rows.append({
                        "poste":       poste,
                        "kpi":         kpi,
                        "needs_action": nb_anom > 0,
                        "status":      status,
                        "ecart":       ecart,
                        "nb_anom":     nb_anom,
                        "responsable": KPI_RESP_MAP.get(kpi, "Non assigne"),
                        "action":      ACT_MAP.get(kpi, ""),
                        "delai":       "",
                    })

        sf1_rows = [r for r in plan_actions_rows if str(r["poste"]).startswith("SF1")]
        sf2_rows = [r for r in plan_actions_rows if str(r["poste"]).startswith("SF2")]

        _pa_valid = [v for v in pa.values() if pd.notna(v)]
        _qa_valid = [v for v in qa.values() if pd.notna(v)]
        avg_p_score  = sum(_pa_valid) / len(_pa_valid) if _pa_valid else 0
        avg_q_score  = sum(_qa_valid) / len(_qa_valid) if _qa_valid else 0
        total_ano_p  = sum(r["Total Anomalies"] for r in ano_p_rows if r.get("Poste de travail") != "Total")
        total_ano_q  = sum(r["Total Anomalies"] for r in ano_q_rows if r.get("Poste de travail") != "Total")
        total_ot     = len(df)

        render_header(fichier_date)
        prev_values = get_previous_card_values(hist_df)
        render_cards(
            total_ot, avg_p_score, avg_q_score, total_ano_p + total_ano_q,
            sf1_p, sf1_q, sf2_p, sf2_q, prev_values,
        )

        tabs = st.tabs([
            "Tableau de Bord",
            "Performance",
            "Qualite",
            "Backlog",
            "Suivi & Evolution",
            "Plan d'action",
        ])

        with tabs[0]:
            render_dashboard_tab(vp, pscores, qscores, pa, qa)
        with tabs[1]:
            render_performance_tab(prows, pcols, ano_p_rows, ano_p_cols, pa)
        with tabs[2]:
            render_qualite_tab(qrows, qcols, ano_q_rows, ano_q_cols, qa)
        with tabs[3]:
            render_backlog_page(dfp, vp)
        with tabs[4]:
            render_evolution_tab(
                hist_df, var_df, journal_df, top5_df, bot5_df,
                synth_perf, synth_qual, vp,
            )
        with tabs[5]:
            # ── Bouton export PowerPoint (dynamique selon filtre poste) ──
            try:
                from core.export_pptx import build_presentation
                pptx_bytes = build_presentation(
                    vp, ckdf, ano_map, pa, qa, pscores, qscores,
                    hist_df, fichier_date,
                )
                _ent = "Maroc_Chimie" if all(str(p).startswith("SF1") for p in vp) else \
                       ("FEEDS" if all(str(p).startswith("SF2") for p in vp) else "OCP")
                st.download_button(
                    "📊 Exporter la présentation PowerPoint",
                    data=pptx_bytes,
                    file_name=f"Presentation_KPIs_{_ent}_{fichier_date.replace('/','-')}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
            except Exception as _e:
                st.caption(f"Export PowerPoint indisponible : {_e}")

            render_plan_action_tab(plan_actions_rows, sf1_rows, sf2_rows, anomaly_dfs)

    except Exception as e:
        st.error("Erreur lors du chargement des donnees : %s" % str(e))
        st.markdown('<div class="es">Veuillez verifier que les fichiers ot.xlsx et avis.xlsx sont presents.</div>', unsafe_allow_html=True)

    st.markdown('<div class="footer">Bureau Methodes Maroc Chimie 2026</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
