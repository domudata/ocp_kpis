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
    from core.onedrive_loader import load_data_from_onedrive
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
    _IMPORT_ERROR = None
except Exception as _e:
    _IMPORT_ERROR = traceback.format_exc()


# ── VERSION DE CALCUL (automatique) ──────────────────────────────────────────
# Le cache @st.cache_data ne hash QUE le code de calc_kpis_cached (1 ligne),
# PAS le code interne de calc_kpis() / _age_kpis() / build_ano_map() ni les
# filtres filt_prep/plan/exec definis dans calcul_kpi.py et anomalies.py.
# Pour que TOUTE modification de ces fichiers invalide le cache automatiquement,
# on calcule un hash de leur contenu et on l injecte dans la cle de cache.
import hashlib as _hashlib
import os as _os

def _calc_signature():
    """
    Hash du contenu des fichiers de calcul → invalide le cache si modifies.
    Utilise le chemin ABSOLU (base = dossier de app.py) pour fonctionner
    quel que soit le repertoire de travail au demarrage de Streamlit Cloud.
    """
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
        # Aucun fichier trouve : ne jamais renvoyer un hash "silencieusement
        # constant" -> utiliser un hash base sur mtime comme filet de securite
        # pour au moins detecter un changement de deploiement/reboot.
        h.update(str(_os.path.getmtime(_os.path.abspath(__file__))).encode())
    return h.hexdigest()[:12], found_any

CALC_VERSION, _CALC_SIG_OK = _calc_signature()


@st.cache_data(show_spinner="Calcul des KPIs en cours...")
def calc_kpis_cached(df_period, avdf_period, now_ts, apm_tuple, fichier_date, sdt, edt, calc_version=CALC_VERSION):
    """
    Wrapper cache autour de calc_kpis().
    Cle de cache = (df_period, avdf_period, now_ts, apm_tuple, fichier_date, sdt, edt, calc_version).
    calc_version = hash du contenu de calcul_kpi.py / anomalies.py / prepare_data.py,
    donc TOUTE modification de ces fichiers (filtres, formules) invalide le cache
    automatiquement au redemarrage — plus besoin d incrementer un numero a la main.
    Changer la SELECTION DE POSTES (vp) ne redeclenche PAS ce calcul,
    car on calcule ici sur TOUS les postes (apm) puis on filtre ensuite dans main().
    """
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

    # Masquer la barre d'outils Streamlit (Share/étoile/crayon/GitHub/menu),
    # le bandeau "Manage app", le menu principal et le footer
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

    # ── Chargement des données : OneDrive (automatique) en priorité,
    # fichiers locaux (ot.xlsx/avis.xlsx uploadés manuellement) en secours ──
    ot_bytes = av_bytes = None
    od_ot, od_av, od_date, od_error = load_data_from_onedrive()

    if od_ot is not None and od_av is not None:
        ot_bytes, av_bytes = od_ot, od_av
        if od_date:
            fichier_date = od_date
        st.sidebar.success(f"☁️ Données chargées depuis OneDrive ({fichier_date})")
    else:
        if od_error:
            st.sidebar.warning(
                f"⚠️ Échec du chargement OneDrive : {od_error} "
                "Utilisation des fichiers locaux si disponibles."
            )
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

        def calc_score_division(postes, liste_kpi):
            score = 0
            nb = 0

            for kpi in liste_kpi:
                valeurs = []

                for poste in postes:
                    if poste in ckdf.index:
                        val = ckdf.loc[poste, kpi]
                        if pd.notna(val):
                            valeurs.append(float(val))

                if valeurs:
                    moyenne = sum(valeurs) / len(valeurs)
                    score += gscore(kpi, moyenne, CIBLE[kpi])
                    nb += 1

            return round(score / nb * 100, 2) if nb else 0

        sf1_p = calc_score_division(sf1_posts, QK)
        sf1_q = calc_score_division(sf1_posts, PK)
        sf2_p = calc_score_division(sf2_posts, QK)
        sf2_q = calc_score_division(sf2_posts, PK)

        ano_map    = build_ano_map(dfp, avf, now_ts)
        ano_p_rows = build_ano_rows(vp, ano_map, QK)
        ano_q_rows = build_ano_rows(vp, ano_map, PK, fixed_zero=["OT Fiabilité","Total Avis de Panne"])
        ano_p_cols = ["Poste de travail"] + QK + ["Total Anomalies"]
        ano_q_cols = ["Poste de travail"] + PK + ["Total Anomalies"]
        anomaly_dfs = build_anomaly_dfs(dfp, avf, now_ts)

        # ── Export sidebar : classeur complet des anomalies (OT + Avis) ──
        # Respecte automatiquement le perimetre filtre courant (periode,
        # poste, atelier, division) car anomaly_dfs est construit a partir
        # de dfp/avf deja restreints a la selection active.
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

        # Total general par KPI (CORRIGÉ) :
        # - Pour les KPI d'âge (Préparation/Planification/Exécution × 3 tranches) :
        #   MOYENNE SIMPLE, pas gscore. Au niveau de chaque poste, les 3 tranches
        #   (<1 mois + 1-3 mois + >3 mois) somment déjà à 100% ; la moyenne
        #   conserve cette propriété (linéarité), donc les 3 totaux somment
        #   aussi à 100. Un comptage gscore indépendant sur chaque tranche
        #   casserait cette contrainte.
        # - Pour tous les autres KPI : gscore (rouge=0/sinon=1), comme convenu.
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

        # ── Score Performance du Total general (CORRIGÉ) ───────────────────
        # AVANT : moyenne des pscores par poste (sum(pscores.values())/len(pscores)).
        # APRÈS : calculé DIRECTEMENT sur les valeurs de la ligne Total general
        # (tot_p[k]) via gscore (rouge=0/sinon=1), sans passer par la moyenne
        # des scores par poste.
        score_total = 0
        nb_kpi = 0

        for k in QK:
            try:
                val = float(tot_p[k])
                if pd.notna(val):
                    score_total += gscore(k, val, CIBLE[k])
                    nb_kpi += 1
            except Exception:
                pass

        tot_p["Score Performance"] = "%.2f" % ((score_total / nb_kpi) * 100 if nb_kpi else 0)
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

        # ── Score Qualite du Total general (CORRIGÉ) ───────────────────────
        # Même principe que Score Performance ci-dessus : calculé
        # directement sur les valeurs de la ligne Total general (tot_q[k])
        # via gscore, sans passer par la moyenne des qscores par poste.
        score_total = 0
        nb_kpi = 0

        for k in PK:
            try:
                val = float(tot_q[k])
                if pd.notna(val):
                    score_total += gscore(k, val, CIBLE[k])
                    nb_kpi += 1
            except Exception:
                pass

        tot_q["Score Qualite"] = "%.2f" % ((score_total / nb_kpi) * 100 if nb_kpi else 0)
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
                # N'inclure une ligne QUE s'il y a au moins 1 anomalie.
                # 0 anomalie = rien a signaler, la ligne n'apparait pas.
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

        # ── Score étoiles par poste (0 à 5 ★) ────────────────────────────
        # Score global = moyenne(Score Performance, Score Qualite) du poste,
        # converti sur une echelle de 5 etoiles (100% = 5 etoiles).
        poste_stars = {}
        for poste in vp:
            ps = pscores.get(poste)
            qs = qscores.get(poste)
            vals = [v for v in (ps, qs) if v is not None and pd.notna(v)]
            if vals:
                score_global = sum(vals) / len(vals)
                stars = round(score_global / 20)  # 0-100% -> 0-5
                stars = max(0, min(5, stars))
            else:
                score_global = None
                stars = 0
            poste_stars[poste] = {"score": score_global, "stars": stars}

        # CORRIGÉ : avg_p_score/avg_q_score (cartes) utilisaient encore la
        # moyenne simple de pa/qa. Pour être cohérent avec tot_p/tot_q
        # (déjà basés sur gscore), on reprend directement le Score
        # Performance/Qualite du Total general déjà calculé ci-dessus —
        # même chiffre affiché dans les cartes et dans les tableaux.
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
            # ── Gestion de l'historique (persistance via GitHub) ─────────────
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

            # ── NOUVEAU : génération + publication de tous les rapports
            # KPI par poste (PPTX + PDF + Excel anomalies) sur GitHub,
            # dans presentation/<poste>/. Bouton MANUEL (pas automatique
            # à chaque recalcul) : mesuré à ~1.6s/poste rien que pour la
            # génération locale (PPTX+PDF), plus le temps d'upload GitHub
            # par fichier — trop lent pour tourner à chaque interaction
            # Streamlit (qui relance le script à chaque clic).
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

    except Exception as e:
        st.error("Erreur lors du chargement des donnees : %s" % str(e))
        st.markdown('<div class="es">Veuillez verifier que les fichiers ot.xlsx et avis.xlsx sont presents.</div>', unsafe_allow_html=True)

    st.markdown('<div class="footer">Bureau Methodes Maroc Chimie 2026</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
