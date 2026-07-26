# -*- coding: utf-8 -*-
import locale
import os
import random
import time

import numpy as np
import pandas as pd
import streamlit as st

# ── Config (doit être la 1ère instruction Streamlit) ──────────────────────
st.set_page_config(layout="wide", page_title="Dashboard KPI", initial_sidebar_state="expanded")

# ── Imports internes ──────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────
def main() -> None:
    # Locale
    try:
        locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')
    except Exception:
        try:
            locale.setlocale(locale.LC_ALL, 'fr_FR')
        except Exception:
            pass

    inject_custom_css()
    fichier_date = get_date_from_file()

    # ── Écran HSE ─────────────────────────────────────────────────────────
    if "hse_affiche" not in st.session_state:
        st.session_state.hse_affiche = False

    if not st.session_state.hse_affiche:
        c = random.choice(CONSIGNES_HSE)
        st.markdown("""
        <div style="text-align:center;">
        <h1>🦺</h1>
        <h2>HSE - CONSIGNE DE SECURITE</h2>
        <h4>Securite - Sante - Environnement</h4>
        <p>⚠️ %s</p>
        <p><em>Aucun travail n'est plus urgent que la securite</em></p>
        </div>
        <style>
        @keyframes ld{from{width:0}to{width:100%%}}
        </style>
        """ % c, unsafe_allow_html=True)
        time.sleep(6)
        st.session_state.hse_affiche = True
        st.rerun()
        st.stop()

    # ── Chargement des données persistées ─────────────────────────────────
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

    # ── Sidebar + filtres ─────────────────────────────────────────────────
    ctx = render_sidebar(fichier_date, apm, df_full, av_full, now_ts)
    vp = ctx["vp"]
    df_full = ctx["df_full"]
    av_full = ctx["av_full"]
    apm = ctx["apm"]
    now_ts = ctx["now_ts"]

    if df_full.empty:
        st.markdown(
            '<div style="text-align:center;padding:2rem;">📁 Veuillez charger les fichiers '
            'OT et AVIS via le panneau de filtres.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="text-align:center;color:gray;">Bureau Méthodes Maroc Chimie – '
            '© 2026 Tous droits réservés</div>',
            unsafe_allow_html=True,
        )
        return

    try:
        sdt, edt = ctx["sdt"], ctx["edt"]

        # ── DataFrames filtrés ────────────────────────────────────────────
        df = df_full[
            df_full["Poste travail princ."].isin(vp)
            & df_full["Date de début planifiée"].between(sdt, edt)
        ].copy()

        avdf = av_full[av_full["Poste travail princ."].isin(vp)].copy()
        if "Créé le" in avdf.columns:
            avdf = avdf[avdf["Créé le"].between(sdt, edt)]

        df_dash = df_full[df_full["Poste travail princ."].isin(vp)].copy()
        avdf_dash = av_full[av_full["Poste travail princ."].isin(vp)].copy()

        # ── Calcul KPI ────────────────────────────────────────────────────
        res = calc_kpis(df, avdf, now_ts, vp)
        res_d = calc_kpis(df_dash, avdf_dash, now_ts, vp)

        ckdf = res['ckdf']
        dfp = res['dfp']
        avf = res['avf']

        # Moyenne réelle du KPI sur les postes affichés (sert aussi de
        # référence pour le Total general des tables Performance/Qualite,
        # cf. correction plus bas).
        pa = {k: round(ckdf[k].mean(), 2) for k in QK}
        qa = {k: round(ckdf[k].mean(), 2) for k in PK}

        # Score horizontal par poste (TPGM : nb indicateurs atteignant
        # l'objectif / nb total d'indicateurs, cf. classeur de définitions).
        pscores = {}
        qscores = {}
        for poste in ckdf.index:
            r = ckdf.loc[poste]
            pscores[poste] = (
                sum(gscore(k, r[k], CIBLE[k]) for k in QK if k in r.index) / len(QK) * 100
            ) if QK else 0
            qscores[poste] = (
                sum(gscore(k, r[k], CIBLE[k]) for k in PK if k in r.index) / len(PK) * 100
            ) if PK else 0

        sf1_posts = [p for p in vp if str(p).startswith("SF1")]
        sf2_posts = [p for p in vp if str(p).startswith("SF2")]
        sf1_p = np.mean([pscores[p] for p in sf1_posts]) if sf1_posts else 0
        sf1_q = np.mean([qscores[p] for p in sf1_posts]) if sf1_posts else 0
        sf2_p = np.mean([pscores[p] for p in sf2_posts]) if sf2_posts else 0
        sf2_q = np.mean([qscores[p] for p in sf2_posts]) if sf2_posts else 0

        # ── Anomalies ─────────────────────────────────────────────────────
        ano_map = build_ano_map(dfp, avf, now_ts)
        ano_p_rows = build_ano_rows(vp, ano_map, QK)
        ano_q_rows = build_ano_rows(vp, ano_map, PK, fixed_zero=["OT Fiabilité", "Total Avis de Panne"])
        ano_p_cols = ["Poste de travail"] + QK + ["Total Anomalies"]
        ano_q_cols = ["Poste de travail"] + PK + ["Total Anomalies"]
        anomaly_dfs = build_anomaly_dfs(dfp, avf, now_ts)

        # ── Lignes tableaux KPI ───────────────────────────────────────────
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

        # Lignes Cible
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

        # ── Ligne Total general (CORRIGÉ) ──────────────────────────────────
        # AVANT : chaque colonne KPI comptait le % de postes conformes
        # (vert/orange) via gscore -> une "compliance rate", pas la vraie
        # valeur du KPI. Résultat incohérent avec pa/qa (utilisés pour les
        # cartes et le tableau de bord) : deux nombres différents pour le
        # même KPI selon l'onglet consulté.
        # APRÈS : chaque colonne KPI reprend directement pa[k]/qa[k], la
        # moyenne réelle du KPI sur les postes affichés -> même valeur
        # partout dans l'application pour un même KPI.
        # Le Score Performance / Score Qualite du Total general reste
        # inchangé : moyenne des scores par poste (pscores/qscores).
        tot_p = {"Poste de travail": "Total general", "_t": "total"}
        for k in QK:
            tot_p[k] = "%.1f" % pa.get(k, 0)
        tot_p["Score Performance"] = "%.2f" % (sum(pscores.values()) / len(pscores)) if pscores else "0.00"
        prows.append(tot_p)

        tot_q = {"Poste de travail": "Total general", "_t": "total"}
        for k in PK:
            tot_q[k] = "%.1f" % qa.get(k, 0)
        tot_q["Score Qualite"] = "%.2f" % (sum(qscores.values()) / len(qscores)) if qscores else "0.00"
        qrows.append(tot_q)

        # ── Export historique ─────────────────────────────────────────────
        save_kpis_to_excel(
            prows, pcols, qrows, qcols,
            ano_p_rows, ano_p_cols, ano_q_rows, ano_q_cols,
            fichier_date,
        )

        # ── Historique & variations ───────────────────────────────────────
        hist_filepath = os.path.join("kpis", "indicateurs_kpis.xlsx")
        hist_df = load_historical_kpis(hist_filepath)
        var_df = calculate_variations(hist_df)
        journal_df = generate_journal(var_df)
        top5_df, bot5_df = calculate_rankings(var_df)

        # ── Synthèse évolution ────────────────────────────────────────────
        synth_perf = {}
        synth_qual = {}
        if not var_df.empty and "Date precedente" in var_df.columns:
            for poste in vp:
                synth_perf[poste] = {}
                synth_qual[poste] = {}
                pv = var_df[var_df["Poste"] == poste]
                for kpi in QK:
                    kpi_v = pv[pv["KPI"] == kpi]
                    synth_perf[poste][kpi] = (
                        {"diff": "%+.1f" % kpi_v.iloc[-1]["Ecart"]} if not kpi_v.empty else {"diff": "—"}
                    )
                for kpi in PK:
                    kpi_v = pv[pv["KPI"] == kpi]
                    synth_qual[poste][kpi] = (
                        {"diff": "%+.1f" % kpi_v.iloc[-1]["Ecart"]} if not kpi_v.empty else {"diff": "—"}
                    )

        # ── Plan d'actions ────────────────────────────────────────────────
        plan_actions_rows = []
        for poste in vp:
            if poste not in ckdf.index:
                continue
            poste_data = ckdf.loc[poste]
            for kpi in ALL_KPI:
                actual = float(poste_data.get(kpi, 100))
                target = CIBLE.get(kpi, 100)
                lower = is_lb(kpi)
                needs_action = actual > target if lower else actual < target
                ecart = actual - target
                nb_anom = int(ano_map.get(kpi, pd.Series()).get(poste, 0))
                if needs_action or nb_anom > 0:
                    plan_actions_rows.append({
                        "poste": poste, "kpi": kpi,
                        "needs_action": needs_action, "ecart": ecart,
                        "nb_anom": nb_anom,
                        "responsable": KPI_RESP_MAP.get(kpi, "Non assigné"),
                        "action": ACT_MAP.get(kpi, ""), "delai": "",
                    })

        sf1_rows = [r for r in plan_actions_rows if str(r["poste"]).startswith("SF1")]
        sf2_rows = [r for r in plan_actions_rows if str(r["poste"]).startswith("SF2")]

        # ── Métriques globales ────────────────────────────────────────────
        avg_p_score = sum(pa.values()) / len(pa) if pa else 0
        avg_q_score = sum(qa.values()) / len(qa) if qa else 0
        total_ano_p = sum(r["Total Anomalies"] for r in ano_p_rows if r.get("Poste de travail") != "Total")
        total_ano_q = sum(r["Total Anomalies"] for r in ano_q_rows if r.get("Poste de travail") != "Total")
        total_ot = len(df)

        # ── Rendu ─────────────────────────────────────────────────────────
        render_header(fichier_date)

        prev_values = get_previous_card_values(hist_df)
        render_cards(
            total_ot, avg_p_score, avg_q_score, total_ano_p + total_ano_q,
            sf1_p, sf1_q, sf2_p, sf2_q, prev_values,
        )

        tabs = st.tabs([
            "🏠 Tableau de Bord", "📈 Performance", "✅ Qualite",
            "📂 Backlog", "📋 Suivi & Evolution", "🎯 Plan d'action",
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
            render_plan_action_tab(plan_actions_rows, sf1_rows, sf2_rows, anomaly_dfs)

    except Exception as e:
        st.error("Erreur lors du chargement des donnees : %s" % str(e))
        st.markdown(
            '<div style="text-align:center;">Veuillez verifier que les fichiers ot.xlsx '
            'et avis.xlsx sont presents dans le repertoire.</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="text-align:center;color:gray;">Bureau Méthodes Maroc Chimie – '
        '© 2026 Tous droits réservés</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
