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

# ── Imports proteges : affiche l erreur REELLE dans l app si un import
# echoue, au lieu du message generique "redacted" de Streamlit Cloud.
try:
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
    from pages.frequence_maintenance import render_frequence_maintenance_tab
    from pages.suivi_hse import render_suivi_hse_tab
    _IMPORT_ERROR = None
except Exception as _e:
    _IMPORT_ERROR = traceback.format_exc()


# ── VERSION DE CALCUL (automatique) ──────────────────────────────────────────
import hashlib as _hashlib
import os as _os

def _calc_signature():
    try:
        h = _hashlib.md5()
        base_dir = _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else _os.getcwd()
        found_any = False
        for _f in ("core/calcul_kpi.py", "core/anomalies.py", "core/prepare_data.py", "core/controle_kpi.py"):
            _path = _os.path.join(base_dir, _f)
            try:
                with open(_path, "rb") as _fh:
                    h.update(_fh.read())
                    found_any = True
            except Exception:
                pass
        if not found_any:
            target = _os.path.abspath(__file__) if "__file__" in globals() else "app.py"
            try:
                h.update(str(_os.path.getmtime(target)).encode())
            except Exception:
                h.update(b"default")
        return h.hexdigest()[:12], found_any
    except Exception:
        return "default", False

CALC_VERSION, _CALC_SIG_OK = _calc_signature()


@st.cache_data(show_spinner="Calcul des KPIs en cours...")
def calc_kpis_cached(_df_period, _avdf_period, now_ts, apm_tuple, fichier_date, sdt, edt, _df_toutes_dates, calc_version=CALC_VERSION):
    return calc_kpis(_df_period, _avdf_period, now_ts, list(apm_tuple), df_toutes_dates=_df_toutes_dates)


@st.cache_data(show_spinner="Chargement et préparation des données...")
def get_prepared_data(fichier_date, ot_mtime, av_mtime, calc_version=CALC_VERSION):
    ot_bytes = av_bytes = None
    if os.path.exists("ot.xlsx") and os.path.exists("avis.xlsx"):
        with open("ot.xlsx", "rb") as f:
            ot_bytes = f.read()
        with open("avis.xlsx", "rb") as f:
            av_bytes = f.read()
    if ot_bytes and av_bytes:
        return prepare_data(ot_bytes, av_bytes, fichier_date, calc_version=calc_version)
    return pd.DataFrame(), pd.DataFrame(), [], pd.Timestamp.today().normalize(), pd.DataFrame()


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
    st.markdown("""
    <style>
    [data-testid="stSidebarNav"],
    [data-testid="stSidebarNavItems"],
    [data-testid="stSidebarNavSeparator"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stToolbarActions"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    header { visibility: hidden !important; }
    /* CORRIGÉ : le bouton "◀ ▶" qui affiche/masque le sidebar vit dans le
       même conteneur que le header masqué ci-dessus. Sans cette règle, si
       le sidebar se replie (fréquent sur petit écran / mobile), il devient
       impossible de le rouvrir — le bouton étant lui aussi invisible. */
    [data-testid="collapsedControl"] {
        visibility: visible !important;
        display: block !important;
        position: fixed !important;
        top: 0.5rem !important;
        left: 0.5rem !important;
        z-index: 999999 !important;
    }
    footer { visibility: hidden !important; }
    .stAppDeployButton { display: none !important; }
    .viewerBadge_container__1QSob { display: none !important; }
    </style>
    """, unsafe_allow_html=True)
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
        st.session_state.hse_affiche = True

    ot_mtime = os.path.getmtime("ot.xlsx") if os.path.exists("ot.xlsx") else 0
    av_mtime = os.path.getmtime("avis.xlsx") if os.path.exists("avis.xlsx") else 0
    df_full, av_full, apm, now_ts, avis_complet_full = get_prepared_data(fichier_date, ot_mtime, av_mtime, calc_version=CALC_VERSION)

    ctx = render_sidebar(fichier_date, apm, df_full, av_full, now_ts)
    vp      = ctx["vp"]
    df_full = ctx["df_full"]
    av_full = ctx["av_full"]
    apm     = ctx["apm"]
    now_ts  = ctx["now_ts"]
    if not ctx.get("avis_complet_full", pd.DataFrame()).empty:
        avis_complet_full = ctx["avis_complet_full"]

    if df_full.empty:
        st.markdown('<div class="es">Veuillez charger les fichiers OT et AVIS via le panneau de filtres.</div>', unsafe_allow_html=True)
        st.markdown('<div class="footer">Bureau Methodes Maroc Chimie 2026</div>', unsafe_allow_html=True)
        return

    try:
        sdt, edt = ctx["sdt"], ctx["edt"]

        # Date de filtrage : Date de début planifiée en priorité, avec repli sur Créé le (notamment pour les OT en création)
        if "Date de début planifiée" in df_full.columns and "Créé le" in df_full.columns:
            _date_filtre_ot = df_full["Date de début planifiée"].fillna(df_full["Créé le"])
        elif "Date de début planifiée" in df_full.columns:
            _date_filtre_ot = df_full["Date de début planifiée"]
        else:
            _date_filtre_ot = pd.Series(pd.NaT, index=df_full.index)

        df_period = df_full[_date_filtre_ot.between(sdt, edt)].copy()

        avdf_period = av_full.copy()
        if "Créé le" in avdf_period.columns:
            avdf_period = avdf_period[avdf_period["Créé le"].between(sdt, edt)]

        # Application du filtre de période de la sidebar à l'ensemble des indicateurs (Backlogs & Âges inclus selon demande explicite)
        res = calc_kpis_cached(df_period, avdf_period, now_ts, tuple(apm), fichier_date, sdt, edt, df_period)

        ckdf_full = res['ckdf']
        nd_full = res.get('nd', {})
        dfp_full  = res['dfp']
        avf_full  = res['avf']

        vp_present = [p for p in vp if p in ckdf_full.index]
        ckdf = ckdf_full.loc[vp_present] if vp_present else ckdf_full.iloc[0:0]
        dfp  = dfp_full[dfp_full["Poste travail princ."].isin(vp)]
        avf  = avf_full[avf_full["Poste travail princ."].isin(vp)] if "Poste travail princ." in avf_full.columns else avf_full
        avis_complet = (
            avis_complet_full[avis_complet_full["Poste travail princ."].isin(vp)]
            if "Poste travail princ." in avis_complet_full.columns else avis_complet_full
        )
        df   = dfp

        pa = {k: round(ckdf[k].mean(skipna=True), 2) for k in QK}
        qa = {k: round(ckdf[k].mean(skipna=True), 2) for k in PK}

        def score_from_totals_01(kpi_dict, kpi_list):
            valides = [k for k in kpi_list if k in kpi_dict and pd.notna(kpi_dict[k])]
            if not valides:
                return 0.0
            total_1 = sum(gscore(k, kpi_dict[k], CIBLE.get(k, 100)) for k in valides)
            return round((total_1 / len(valides)) * 100, 2)

        def get_kpi_total(posts, kpi):
            if kpi in nd_full and posts:
                n_s, d_s = nd_full[kpi]
                p_sub = [p for p in posts if p in n_s.index]
                if p_sub:
                    sn = n_s.loc[p_sub].sum()
                    sd = d_s.loc[p_sub].sum()
                    default_val = 0.0 if is_lb(kpi) else 100.0
                    return (sn / sd * 100.0) if sd > 0 else default_val
            p_sub = [p for p in posts if p in ckdf.index]
            if p_sub and kpi in ckdf.columns:
                return float(ckdf.loc[p_sub, kpi].mean(skipna=True))
            return 0.0 if is_lb(kpi) else 100.0

        # ── Score Performance / Qualite PAR POSTE (méthode 0 et 1) ──
        pscores = {}
        qscores = {}
        for poste in ckdf.index:
            r = ckdf.loc[poste]
            pscores[poste] = score_from_totals_01({k: r[k] for k in QK if k in r.index}, QK)
            qscores[poste] = score_from_totals_01({k: r[k] for k in PK if k in r.index}, PK)

        sf1_posts = [p for p in vp if str(p).startswith("SF1")]
        sf2_posts = [p for p in vp if str(p).startswith("SF2")]

        # ── Score des CARTES SF1/SF2 — CALCUL DIRECT SUR LE TOTAL GÉNÉRAL (méthode 0 et 1) ──
        # Applique la règle 0/1 directement sur le Total général de chaque division
        sf1_p_vals = {k: get_kpi_total(sf1_posts, k) for k in QK}
        sf1_q_vals = {k: get_kpi_total(sf1_posts, k) for k in PK}
        sf1_p = round(score_from_totals_01(sf1_p_vals, QK), 1) if sf1_posts else None
        sf1_q = round(score_from_totals_01(sf1_q_vals, PK), 1) if sf1_posts else None

        sf2_p_vals = {k: get_kpi_total(sf2_posts, k) for k in QK}
        sf2_q_vals = {k: get_kpi_total(sf2_posts, k) for k in PK}
        sf2_p = round(score_from_totals_01(sf2_p_vals, QK), 1) if sf2_posts else None
        sf2_q = round(score_from_totals_01(sf2_q_vals, PK), 1) if sf2_posts else None

        ano_map = build_ano_map(dfp, avf, now_ts, dfp_toutes_dates=df_period)

        ano_p_rows = build_ano_rows(
            vp, ano_map, QK,
            fixed_zero=["OT préparation <1 mois", "OT planification <1 mois", "OT exécution <1 mois"]
        )
        ano_q_rows = build_ano_rows(vp, ano_map, PK, fixed_zero=["OT Fiabilité","Total Avis de Panne"])
        ano_p_cols = ["Poste de travail"] + QK + ["Total Anomalies"]
        ano_q_cols = ["Poste de travail"] + PK + ["Total Anomalies"]
        anomaly_dfs = build_anomaly_dfs(dfp, avf, now_ts, dfp_toutes_dates=df_period)

        with st.sidebar:
            with st.expander("📥 Export anomalies & Audit OUI/NON", expanded=False):
                # 1. Export 3 feuilles unifié conforme à la demande OCP
                try:
                    from core.controle_kpi import build_table_controle_complete, build_anomalies_excel_unified
                    _tbl_ctrl = build_table_controle_complete(df_period, avdf_period, now_ts, df_full=df_period)
                    _tbl_ctrl_filtered = _tbl_ctrl[_tbl_ctrl["Poste travail princ."].isin(vp)] if vp else _tbl_ctrl
                    _unified_xlsx = build_anomalies_excel_unified(_tbl_ctrl_filtered)
                    st.download_button(
                        "⬇️ Audit OUI/NON & Synthèse (3 Feuilles .xlsx)",
                        data=_unified_xlsx,
                        file_name=f"audit_anomalies_3_feuilles_{fichier_date.replace('/','-')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="primary",
                    )
                    st.caption(
                        "Source unique : 1. NON_DETAIL (anomalies + motifs), "
                        "2. ANOMALIES_KPI_POSTE, 3. SYNTHESE_KPI."
                    )
                except Exception as _e_u:
                    st.caption(f"Export 3 feuilles indisponible : {_e_u}")

                st.markdown("---")

                # 2. Export opérationnel avec Responsables et Actions recommandées
                try:
                    from core.export_anomalies import build_anomalies_workbook
                    _xlsx_bytes = build_anomalies_workbook(anomaly_dfs, KPI_RESP_MAP, ACT_MAP)
                    st.download_button(
                        "⬇️ Plan d'action anomalies (.xlsx)",
                        data=_xlsx_bytes,
                        file_name=f"anomalies_OT_Avis_{fichier_date.replace('/','-')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                    st.caption(
                        "Contient 2 feuilles : Anomalies OT et Anomalies Avis, "
                        "avec Responsable et Action recommandée."
                    )
                except Exception as _e:
                    st.caption(f"Export indisponible : {_e}")

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

        # ── Total general Performance (conforme à la version consolidée, somme des âges = 100%) ──
        tot_p = {"Poste de travail": "Total general", "_t": "total"}
        for k in QK:
            tot_p[k] = "%.1f" % get_kpi_total(vp_present, k)

        tot_p_vals = {k: float(tot_p[k]) for k in QK if k in tot_p}
        tot_p["Score Performance"] = "%.2f" % score_from_totals_01(tot_p_vals, QK)
        prows.append(tot_p)

        # ── Total general Qualité (méthode 0 et 1) ──
        tot_q = {"Poste de travail": "Total general", "_t": "total"}
        for k in PK:
            tot_q[k] = "%.1f" % get_kpi_total(vp_present, k)

        tot_q_vals = {k: float(tot_q[k]) for k in PK if k in tot_q}
        tot_q["Score Qualite"] = "%.2f" % score_from_totals_01(tot_q_vals, PK)
        qrows.append(tot_q)

        _saved_key = f"_saved_{fichier_date}"
        if not st.session_state.get(_saved_key):
            save_kpis_to_excel(
                prows, pcols, qrows, qcols,
                ano_p_rows, ano_p_cols, ano_q_rows, ano_q_cols,
                fichier_date,
            )
            st.session_state[_saved_key] = True

        from core.export_excel import charger_historique_depuis_github
        hist_df, _hist_msg = charger_historique_depuis_github()
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
                ecart = (target - actual) if lower else (actual - target)
                if nb_anom == 0:
                    ecart = 0.0
                conforme = (actual <= target) if lower else (actual >= target)
                if nb_anom == 0:
                    status = "non_vert"
                elif conforme:
                    status = "oui_vert"
                else:
                    status = "oui_rouge"
                if nb_anom > 0:
                    plan_actions_rows.append({
                        "poste":       poste,
                        "kpi":         kpi,
                        "needs_action": nb_anom > 0,
                        "status":      status,
                        "ecart":       ecart,
                        "nb_anom":     nb_anom,
                        "actual":      actual,
                        "target":      target,
                        "responsable": KPI_RESP_MAP.get(kpi, "Non assigne"),
                        "action":      ACT_MAP.get(kpi, ""),
                        "delai":       "",
                    })

        sf1_rows = [r for r in plan_actions_rows if str(r["poste"]).startswith("SF1")]
        sf2_rows = [r for r in plan_actions_rows if str(r["poste"]).startswith("SF2")]

        poste_stars = {}
        for poste in vp:
            ps = pscores.get(poste)
            qs = qscores.get(poste)
            vals = [v for v in (ps, qs) if v is not None and pd.notna(v)]
            if vals:
                score_global = sum(vals) / len(vals)
                stars = round(score_global / 20)
                stars = max(0, min(5, stars))
            else:
                score_global = None
                stars = 0
            poste_stars[poste] = {"score": score_global, "stars": stars}

        try:
            avg_p_score = float(tot_p["Score Performance"])
        except Exception:
            avg_p_score = 0
        try:
            avg_q_score = float(tot_q["Score Qualite"])
        except Exception:
            avg_q_score = 0
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
            "🏠 Tableau de Bord",
            "📈 Performance",
            "✅ Qualite",
            "📂 Backlog",
            "📋 Suivi & Evolution",
            "🎯 Plan d'action",
            "🔎 Audit des calculs KPI",
            "🤖 Assistant IA",
            "🔄 Fréquence Maintenance",
            "🦺 Suivi HSE",
        ])

        with tabs[0]:
            render_dashboard_tab(vp, pscores, qscores, pa, qa)
        with tabs[1]:
            render_performance_tab(prows, pcols, ano_p_rows, ano_p_cols, pa)
        with tabs[2]:
            render_qualite_tab(qrows, qcols, ano_q_rows, ano_q_cols, qa)
        with tabs[3]:
            try:
                render_backlog_page(dfp, vp, df_toutes_dates=df_period)
            except TypeError:
                render_backlog_page(dfp, vp)
        with tabs[4]:
            n_dates = 0
            if not hist_df.empty and "Date" in hist_df.columns:
                n_dates = hist_df["Date"].nunique()

            with st.expander(f"📁 Historique : {n_dates} date(s) enregistrée(s) — cliquez pour détails", expanded=(n_dates < 2)):
                st.caption(f"Source : GitHub — {_hist_msg}")
                if n_dates < 2:
                    st.info(
                        "ℹ️ Il faut **au moins 2 dates** pour calculer des variations. "
                        "Actuellement, l'historique contient %d date(s).\n\n"
                        "**L'enregistrement est désormais automatique** : à chaque chargement "
                        "d'une extraction avec une nouvelle date dans `date.txt`, la date est "
                        "ajoutée directement à `kpis/indicateurs_kpis.xlsx` sur GitHub — "
                        "aucune action manuelle n'est nécessaire." % n_dates
                    )
                else:
                    st.success(
                        f"✅ {n_dates} dates enregistrées sur GitHub. "
                        f"Chaque nouvelle extraction (nouvelle date dans `date.txt`) est ajoutée automatiquement."
                    )
                try:
                    from core.github_publish import download_file as _gh_dl
                    _bytes_hist, _err_hist = _gh_dl("kpis/indicateurs_kpis.xlsx")
                    if _bytes_hist:
                        st.download_button(
                            "⬇️ Télécharger l'historique complet (indicateurs_kpis.xlsx)",
                            data=_bytes_hist, file_name="indicateurs_kpis.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                except Exception as _e_dl:
                    st.caption(f"Téléchargement indisponible : {_e_dl}")

            render_evolution_tab(
                hist_df, var_df, journal_df, top5_df, bot5_df,
                synth_perf, synth_qual, vp,
            )
        with tabs[5]:
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

            st.markdown("---")
            st.markdown("#### 📤 Rapports KPI par poste (PDF + Excel)")

            _publication_ok = True
            try:
                from core.publish_reports import generate_and_publish_all_postes
                from core.github_publish import is_configured as _github_configured
                from core.github_publish import debug_config as _github_debug_config
                st.caption(f"🔧 Config GitHub détectée : {_github_debug_config()}")
            except Exception as _e_imp:
                _publication_ok = False
                st.error(
                    f"❌ Module de publication des rapports indisponible : {_e_imp}\n\n"
                    f"Le plan d'action reste consultable ci-dessous."
                )

            if _publication_ok and not _github_configured():
                st.caption(
                    "⚠️ Publication GitHub non configurée (GITHUB_TOKEN / GITHUB_REPO "
                    "absents des secrets). Les rapports seront générés mais pas publiés."
                )

            _col_pub, _col_dry = st.columns(2) if _publication_ok else (None, None)
            _launch_publish = _launch_dry = False
            if _publication_ok:
              with _col_pub:
                _launch_publish = st.button(
                    f"🚀 Générer et publier les rapports ({len(vp)} poste(s))",
                    use_container_width=True, type="primary", key="btn_publish_all",
                )
              with _col_dry:
                _launch_dry = st.button(
                    "🧪 Générer seulement (test, sans publier)",
                    use_container_width=True, key="btn_dry_all",
                )

            if _publication_ok and (_launch_publish or _launch_dry):
                _progress = st.progress(0, text="Démarrage...")
                _status_area = st.empty()

                def _on_progress(i, n, poste):
                    _progress.progress(i / n, text=f"[{i + 1}/{n}] {poste}...")

                _results = generate_and_publish_all_postes(
                    ckdf, pscores, qscores, ano_map, dfp, avf, now_ts,
                    date_str=fichier_date, postes=list(vp),
                    dry_run=_launch_dry, progress_callback=_on_progress,
                    dfp_toutes_dates=df_full,
                )
                _progress.progress(1.0, text="Terminé.")

                _ok_pdf = sum(1 for r in _results if r.get("pdf"))
                _ok_xlsx = sum(1 for r in _results if r.get("xlsx"))
                _ok_pub = sum(1 for r in _results if r.get("pdf_published"))

                with _status_area.container():
                    if _launch_dry:
                        st.success(
                            f"✅ Génération test terminée : {_ok_pdf}/{len(_results)} PDF, "
                            f"{_ok_xlsx}/{len(_results)} Excel."
                        )
                    else:
                        st.success(
                            f"✅ {_ok_pub}/{len(_results)} postes publiés sur GitHub "
                            f"(presentation/<poste>/) — {_ok_pdf} PDF, "
                            f"{_ok_xlsx} Excel générés."
                        )
                    with st.expander("Détail par poste"):
                        for r in _results:
                            _icons = "".join([
                                "📄" if r.get("pdf") else "❌",
                                "📈" if r.get("xlsx") else "❌",
                            ])
                            st.caption(f"{_icons}  **{r['poste']}** — " + " / ".join(r.get("messages", [])))

                    if not _launch_dry and _ok_pub > 0:
                        try:
                            _pa_url = st.secrets.get("POWER_AUTOMATE_WEBHOOK_URL")
                        except Exception:
                            _pa_url = None
                        if _pa_url:
                            try:
                                import requests as _requests

                                try:
                                    _repo = st.secrets.get("GITHUB_REPO", "")
                                    _branch = st.secrets.get("GITHUB_BRANCH", "main")
                                except Exception:
                                    _repo, _branch = "", "main"

                                _fichiers = []
                                for _r in _results:
                                    if not _r.get("pdf_published"):
                                        continue
                                    _dossier = "".join(
                                        c if c.isalnum() or c in "-_" else "_"
                                        for c in str(_r["poste"])
                                    )
                                    _base = f"presentation/{_dossier}"
                                    _entree = {
                                        "poste": _r["poste"],
                                        "dossier": _dossier,
                                        "pdf": f"{_base}/rapport.pdf",
                                        "pdf_url": (
                                            f"https://raw.githubusercontent.com/{_repo}/{_branch}/{_base}/rapport.pdf"
                                            if _repo else ""
                                        ),
                                    }
                                    if _r.get("xlsx_published"):
                                        _entree["xlsx"] = f"{_base}/anomalies.xlsx"
                                        _entree["xlsx_url"] = (
                                            f"https://raw.githubusercontent.com/{_repo}/{_branch}/{_base}/anomalies.xlsx"
                                            if _repo else ""
                                        )
                                    _fichiers.append(_entree)

                                _payload = {
                                    "date_extraction": fichier_date,
                                    "dossier_onedrive": "presentation",
                                    "repo": _repo,
                                    "branche": _branch,
                                    "nb_postes": len(_fichiers),
                                    "fichiers": _fichiers,
                                }

                                _pa_resp = _requests.post(_pa_url, json=_payload, timeout=30)
                                if _pa_resp.status_code in (200, 201, 202):
                                    st.success(
                                        f"☁️ Enregistrement OneDrive déclenché : {len(_fichiers)} rapport(s) "
                                        f"envoyé(s) vers `{_payload['dossier_onedrive']}`."
                                    )
                                    with st.expander("Détail de ce qui a été transmis à Power Automate"):
                                        st.json(_payload)
                                else:
                                    st.warning(f"⚠️ Power Automate a répondu {_pa_resp.status_code} : {_pa_resp.text[:200]}")
                            except Exception as _pa_e:
                                st.warning(f"⚠️ Impossible de déclencher Power Automate : {_pa_e}")
                        else:
                            st.warning(
                                "⚠️ Les rapports sont publiés sur GitHub mais **pas encore copiés vers OneDrive** : "
                                "le secret `POWER_AUTOMATE_WEBHOOK_URL` est absent. Ajoutez-le dans les secrets "
                                "Streamlit (voir la procédure de création du flux dans la documentation du projet)."
                            )

            render_plan_action_tab(plan_actions_rows, sf1_rows, sf2_rows, anomaly_dfs, fichier_date=fichier_date, poste_stars=poste_stars)

        with tabs[6]:
            try:
                from pages.audit_kpi import render_audit_kpi_tab
                render_audit_kpi_tab(df_period, avdf_period, now_ts, df_full=df_period, vp=list(vp), fichier_date=fichier_date)
            except Exception as _e_aud:
                st.error(f"Audit des calculs KPI indisponible : {_e_aud}")

        with tabs[7]:
            try:
                from ai_assistant import render_ai_assistant
                _entity = "Maroc Chimie" if all(str(p).startswith("SF1") for p in vp) else \
                          ("FEEDS" if all(str(p).startswith("SF2") for p in vp) else "OCP — Maroc Chimie & FEEDS")
                render_ai_assistant(
                    _entity, vp, pa, qa, pscores, qscores, ano_map,
                    fichier_date, CIBLE,
                )
            except Exception as _e:
                st.error(f"Assistant IA indisponible : {_e}")

        with tabs[8]:
            try:
                render_frequence_maintenance_tab(df_full)
            except Exception as _e:
                st.error(f"Fréquence de maintenance indisponible : {_e}")

        with tabs[9]:
            try:
                render_suivi_hse_tab(dfp, avis_complet, vp, fichier_date)
            except Exception as _e:
                st.error(f"Suivi HSE indisponible : {_e}")

    except Exception as e:
        st.error("Erreur lors du chargement des donnees : %s" % str(e))
        st.markdown('<div class="es">Veuillez verifier que les fichiers ot.xlsx et avis.xlsx sont presents.</div>', unsafe_allow_html=True)

    st.markdown('<div class="footer">Bureau Methodes Maroc Chimie 2026</div>', unsafe_allow_html=True)


try:
    main()
except Exception as _app_err:
    st.error(f"❌ Erreur d'exécution de l'application : {_app_err}")
    st.code(traceback.format_exc(), language="python")
