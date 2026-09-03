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
    from pages.maintenance_predictive import render_maintenance_predictive_tab
    _IMPORT_ERROR = None
except Exception as _e:
    _IMPORT_ERROR = traceback.format_exc()


# ── VERSION DE CALCUL (automatique) ──────────────────────────────────────────
import hashlib as _hashlib
import os as _os

def _calc_signature():
    h = _hashlib.md5()
    base_dir = _os.path.dirname(_os.path.abspath(__file__))
    found_any = False
    for _f in ("core/calcul_kpi.py", "core/anomalies.py", "core/prepare_data.py"):
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
def calc_kpis_cached(df_period, avdf_period, now_ts, apm_tuple, fichier_date, sdt, edt, calc_version=CALC_VERSION):
    return calc_kpis(df_period, avdf_period, now_ts, list(apm_tuple))


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
    st.markdown(
        '<style>[data-testid="stSidebarNav"] { display: none; }</style>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <style>
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stToolbarActions"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    header { visibility: hidden !important; }
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

        df_period = df_full[
            df_full["Date de début planifiée"].between(sdt, edt)
        ].copy()

        avdf_period = av_full.copy()
        if "Créé le" in avdf_period.columns:
            avdf_period = avdf_period[avdf_period["Créé le"].between(sdt, edt)]

        res = calc_kpis_cached(df_period, avdf_period, now_ts, tuple(apm), fichier_date, sdt, edt)

        ckdf_full = res['ckdf']
        nd_full = res.get('nd', {})
        dfp_full  = res['dfp']
        avf_full  = res['avf']

        vp_present = [p for p in vp if p in ckdf_full.index]
        ckdf = ckdf_full.loc[vp_present] if vp_present else ckdf_full.iloc[0:0]
        dfp  = dfp_full[dfp_full["Poste travail princ."].isin(vp)]
        avf  = avf_full[avf_full["Poste travail princ."].isin(vp)] if "Poste travail princ." in avf_full.columns else avf_full
        df   = dfp

        pa = {k: round(ckdf[k].mean(skipna=True), 2) for k in QK}
        qa = {k: round(ckdf[k].mean(skipna=True), 2) for k in PK}

        # ── Score Performance / Qualite PAR POSTE ───────────────────────────
        # Règle UNIFORME appliquée partout dans ce fichier : pour chaque
        # cellule KPI, gscore() renvoie 0 (rouge / non conforme) ou 1
        # (conforme / non rouge). Les valeurs NaN (KPI indisponible pour ce
        # poste) sont exclues du calcul. Score = somme des 0/1 / nombre de
        # KPI valides × 100.
        pscores = {}
        qscores = {}
        for poste in ckdf.index:
            r = ckdf.loc[poste]
            valid_q = [k for k in QK if k in r.index and pd.notna(r[k])]
            valid_p = [k for k in PK if k in r.index and pd.notna(r[k])]
            pscores[poste] = (sum(gscore(k, r[k], CIBLE[k]) for k in valid_q) / len(valid_q) * 100) if valid_q else 0
            qscores[poste] = (sum(gscore(k, r[k], CIBLE[k]) for k in valid_p) / len(valid_p) * 100) if valid_p else 0

        sf1_posts = [p for p in vp if str(p).startswith("SF1")]
        sf2_posts = [p for p in vp if str(p).startswith("SF2")]

        # ── Score PAR DIVISION (SF1/SF2) — INCHANGÉ, conservé pour le
        # Total general et toute autre utilisation ────────────────────────
        # CORRIGÉ : même règle uniforme — gscore() appliqué sur CHAQUE
        # cellule (poste × KPI) individuellement, puis somme des 0/1 sur
        # le nombre total de cellules KPI valides.
        def calc_score_division(postes, liste_kpi):
            total = 0
            nombre_kpi = 0

            for poste in postes:
                if poste not in ckdf.index:
                    continue

                r = ckdf.loc[poste]

                for kpi in liste_kpi:
                    if kpi not in r.index:
                        continue

                    val = r[kpi]

                    if pd.isna(val):
                        continue

                    total += gscore(
                        kpi,
                        float(val),
                        CIBLE[kpi]
                    )

                    nombre_kpi += 1

            return round(
                (total / nombre_kpi) * 100,
                2
            ) if nombre_kpi else 0

        # ── Score des CARTES SF1/SF2 basé sur le taux d'anomalie ────────────
        # Pour chaque KPI : on compte le nombre de cellules NON en anomalie
        # (nb_total - nb_anomalies), directement — pas via "100 - taux
        # d'anomalie" (les deux donnent le même résultat mathématiquement
        # pour les KPI "plus haut = mieux", mais ce calcul direct est plus
        # clair). Pour les KPI "plus bas = mieux", l'anomalie correspond
        # déjà à la mauvaise tranche : on garde donc le taux d'anomalie
        # lui-même comme valeur à comparer, pas son complément.
        # Utilisé UNIQUEMENT pour sf1_p/sf1_q/sf2_p/sf2_q — le score par
        # poste individuel (pscores/qscores) et le Total general (plus
        # bas, via calc_score_division) restent sur l'ancienne méthode.
        ano_map = build_ano_map(dfp, avf, now_ts)

        def calc_score_anomalie(postes, liste_kpi):
            total = 0
            nb_kpi = 0
            for kpi in liste_kpi:
                nb_anom = sum(int(ano_map.get(kpi, pd.Series()).get(p, 0)) for p in postes)
                if kpi in nd_full:
                    _num, den = nd_full[kpi]
                    nb_total = sum(int(den.get(p, 0)) for p in postes if p in den.index)
                else:
                    nb_total = 0
                if nb_total <= 0:
                    continue
                lower = is_lb(kpi)
                if lower:
                    # "Plus bas = mieux" : l'anomalie EST la valeur
                    # sémantique (être dans la mauvaise tranche).
                    valeur_a_comparer = nb_anom / nb_total * 100
                else:
                    # "Plus haut = mieux" : on compte directement les
                    # cellules NON en anomalie (conformes).
                    nb_non_anom = nb_total - nb_anom
                    valeur_a_comparer = nb_non_anom / nb_total * 100
                s = gscore(kpi, valeur_a_comparer, CIBLE[kpi])
                total += s
                nb_kpi += 1
            return round((total / nb_kpi) * 100, 2) if nb_kpi else 0

        sf1_p = calc_score_anomalie(sf1_posts, QK)
        sf1_q = calc_score_anomalie(sf1_posts, PK)
        sf2_p = calc_score_anomalie(sf2_posts, QK)
        sf2_q = calc_score_anomalie(sf2_posts, PK)

        ano_p_rows = build_ano_rows(vp, ano_map, QK)
        ano_q_rows = build_ano_rows(vp, ano_map, PK, fixed_zero=["OT Fiabilité","Total Avis de Panne"])
        ano_p_cols = ["Poste de travail"] + QK + ["Total Anomalies"]
        ano_q_cols = ["Poste de travail"] + PK + ["Total Anomalies"]
        anomaly_dfs = build_anomaly_dfs(dfp, avf, now_ts)

        with st.sidebar:
            with st.expander("📥 Export anomalies (OT + Avis)", expanded=False):
                try:
                    from core.export_anomalies import build_anomalies_workbook
                    _xlsx_bytes = build_anomalies_workbook(anomaly_dfs, KPI_RESP_MAP, ACT_MAP)
                    st.download_button(
                        "⬇️ Télécharger le fichier anomalies (.xlsx)",
                        data=_xlsx_bytes,
                        file_name=f"anomalies_OT_Avis_{fichier_date.replace('/','-')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                    st.caption(
                        "Contient 2 feuilles : Anomalies OT et Anomalies Avis, "
                        "avec Responsable et Action recommandée, filtrées selon "
                        "la période / poste / atelier / division sélectionnés."
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

        # ── Total general PAR KPI ────────────────────────────────────────
        # RE-CORRIGÉ (sur nouvelle demande explicite) : les 9 KPI d'âge
        # (Préparation/Planification/Exécution × <1mois/1-3mois/>3mois)
        # reviennent à une MOYENNE SIMPLE des valeurs (pas gscore), pour
        # garantir que les 3 tranches somment à 100% sur la ligne Total
        # general — propriété perdue avec le passage au gscore uniforme
        # demandé précédemment. Tous les AUTRES KPI restent en gscore
        # (comptage de cellules conformes / cellules valides × 100).
        _AGE_KPIS = {
            "OT préparation <1 mois", "OT préparation 1mois< <3mois", "OT préparation >3 mois",
            "OT planification <1 mois", "OT planification 1mois< <3mois", "OT planification >3 mois",
            "OT exécution <1 mois", "OT exécution 1mois< <3mois", "OT exécution >3 mois",
        }
        tot_p = {"Poste de travail": "Total general", "_t": "total"}
        for k in QK:
            if k in _AGE_KPIS:
                vals = []
                for rw in prows:
                    if k in rw and rw.get("_t") not in ("cible", "total"):
                        try:
                            fv = float(rw[k])
                            if pd.notna(fv):
                                vals.append(fv)
                        except Exception:
                            pass
                tot_p[k] = ("%.1f" % (sum(vals) / len(vals))) if vals else "nan"
            else:
                cc = tc = 0
                for rw in prows:
                    if k in rw and rw.get("_t") not in ("cible", "total"):
                        try:
                            fv = float(rw[k])
                            if pd.notna(fv):
                                cc += gscore(k, fv, CIBLE.get(k, 100))
                                tc += 1
                        except Exception:
                            pass
                tot_p[k] = ("%.1f" % ((cc / tc) * 100)) if tc > 0 else "nan"

        # ── Score Performance du Total general ──────────────────────────
        # INCHANGÉ : reste calculé DIRECTEMENT sur toutes les cellules KPI
        # Performance de tous les postes sélectionnés, via
        # calc_score_division(vp, QK) — n'utilise PAS les valeurs tot_p[k]
        # ci-dessus (donc pas affecté par la moyenne des KPI d'âge).
        tot_p["Score Performance"] = "%.2f" % calc_score_division(vp, QK)
        prows.append(tot_p)

        tot_q = {"Poste de travail": "Total general", "_t": "total"}
        for k in PK:
            cc = tc = 0
            for rw in qrows:
                if k in rw and rw.get("_t") not in ("cible", "total"):
                    try:
                        fv = float(rw[k])
                        if pd.notna(fv):
                            cc += gscore(k, fv, CIBLE.get(k, 100))
                            tc += 1
                    except Exception:
                        pass
            tot_q[k] = ("%.1f" % ((cc / tc) * 100)) if tc > 0 else "nan"

        # ── Score Qualite du Total general ──────────────────────────────
        # Même principe : directement sur toutes les cellules KPI Qualité
        # de tous les postes sélectionnés, via calc_score_division.
        tot_q["Score Qualite"] = "%.2f" % calc_score_division(vp, PK)
        qrows.append(tot_q)

        save_kpis_to_excel(
            prows, pcols, qrows, qcols,
            ano_p_rows, ano_p_cols, ano_q_rows, ano_q_cols,
            fichier_date,
        )

        hist_filepath = os.path.join("kpis", "indicateurs_kpis.xlsx")
        try:
            from core.github_publish import upload_file as _gh_upload, is_configured as _gh_configured
            if _gh_configured() and os.path.exists(hist_filepath):
                with open(hist_filepath, "rb") as _hf:
                    _hist_bytes = _hf.read()
                _ok, _msg = _gh_upload(
                    "kpis/indicateurs_kpis.xlsx", _hist_bytes,
                    f"Historique KPI — {fichier_date}",
                )
                if _ok:
                    st.sidebar.success(f"☁️ Historique publié sur GitHub ({fichier_date})")
                else:
                    st.sidebar.warning(f"⚠️ Historique non publié sur GitHub : {_msg}")
        except Exception as _e:
            st.sidebar.warning(f"⚠️ Publication historique impossible : {_e}")

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

        # ── avg_p_score / avg_q_score (cartes du dashboard) ─────────────
        # Reprend directement le Score Performance/Qualite du Total
        # general déjà calculé ci-dessus (via calc_score_division) —
        # garantit le même chiffre affiché dans les cartes et les tableaux.
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
            "🤖 Assistant IA",
            "🔧 Maintenance Prédictive",
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
            _hist_path = os.path.join("kpis", "indicateurs_kpis.xlsx")
            n_dates = 0
            if not hist_df.empty and "Date" in hist_df.columns:
                n_dates = hist_df["Date"].nunique()

            with st.expander(f"📁 Historique : {n_dates} date(s) enregistrée(s) — cliquez pour gérer", expanded=(n_dates < 2)):
                if n_dates < 2:
                    st.info(
                        "ℹ️ Il faut **au moins 2 dates** pour calculer des variations. "
                        "Actuellement, l'historique contient %d date(s).\n\n"
                        "**Comment ajouter une date à l'historique permanent :**\n"
                        "1. Chargez une nouvelle extraction (date.txt + ot.xlsx + avis.xlsx)\n"
                        "2. Téléchargez le fichier historique mis à jour ci-dessous\n"
                        "3. Committez-le sur GitHub dans le dossier `kpis/`\n"
                        "4. L'app le rechargera automatiquement au prochain démarrage" % n_dates
                    )
                if os.path.exists(_hist_path):
                    with open(_hist_path, "rb") as _hf:
                        st.download_button(
                            "⬇️ Télécharger l'historique (indicateurs_kpis.xlsx)",
                            data=_hf.read(),
                            file_name="indicateurs_kpis.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                    st.caption(
                        "Après téléchargement : placez ce fichier dans `kpis/indicateurs_kpis.xlsx` "
                        "sur GitHub (glisser-déposer dans le dossier + Commit)."
                    )
                else:
                    st.warning("Aucun fichier historique généré pour l'instant.")

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

            from core.publish_reports import generate_and_publish_all_postes
            from core.github_publish import is_configured as _github_configured
            from core.github_publish import debug_config as _github_debug_config

            st.caption(f"🔧 Config GitHub détectée : {_github_debug_config()}")

            if not _github_configured():
                st.caption(
                    "⚠️ Publication GitHub non configurée (GITHUB_TOKEN / GITHUB_REPO "
                    "absents des secrets). Les rapports seront générés mais pas publiés."
                )

            _col_pub, _col_dry = st.columns(2)
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

            if _launch_publish or _launch_dry:
                _progress = st.progress(0, text="Démarrage...")
                _status_area = st.empty()

                def _on_progress(i, n, poste):
                    _progress.progress(i / n, text=f"[{i + 1}/{n}] {poste}...")

                _results = generate_and_publish_all_postes(
                    ckdf, pscores, qscores, ano_map, dfp, avf, now_ts,
                    date_str=fichier_date, postes=list(vp),
                    dry_run=_launch_dry, progress_callback=_on_progress,
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
                                _pa_resp = _requests.post(_pa_url, json={}, timeout=15)
                                if _pa_resp.status_code in (200, 201, 202):
                                    st.success("☁️ Synchronisation OneDrive déclenchée (Power Automate).")
                                else:
                                    st.warning(f"⚠️ Power Automate a répondu {_pa_resp.status_code} : {_pa_resp.text[:200]}")
                            except Exception as _pa_e:
                                st.warning(f"⚠️ Impossible de déclencher Power Automate : {_pa_e}")
                        else:
                            st.caption(
                                "ℹ️ Ajoutez POWER_AUTOMATE_WEBHOOK_URL dans les secrets pour "
                                "déclencher automatiquement la synchronisation OneDrive ici."
                            )

            render_plan_action_tab(plan_actions_rows, sf1_rows, sf2_rows, anomaly_dfs, fichier_date=fichier_date, poste_stars=poste_stars)

        with tabs[6]:
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

        with tabs[7]:
            try:
                render_maintenance_predictive_tab("feature_dataset.csv")
            except Exception as _e:
                st.error(f"Maintenance prédictive indisponible : {_e}")

    except Exception as e:
        st.error("Erreur lors du chargement des donnees : %s" % str(e))
        st.markdown('<div class="es">Veuillez verifier que les fichiers ot.xlsx et avis.xlsx sont presents.</div>', unsafe_allow_html=True)

    st.markdown('<div class="footer">Bureau Methodes Maroc Chimie 2026</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
