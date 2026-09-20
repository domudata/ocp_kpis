# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core.constants import QK, PK, CIBLE, LOWER_BETTER
from components.tables import html_classement
from components.charts import (
    show_hbar_thresholds,
    show_scores_vbar,
    show_weekly_comparison_vbar,
    show_global_scores_summary_vbar,
    render_suivi_anomalies_semaine,
)


def render_dashboard_tab(vp: list, pscores: dict, qscores: dict,
                          pa: dict, qa: dict,
                          hist_df: pd.DataFrame = None,
                          now_ts: pd.Timestamp = None,
                          ano_map: dict = None,
                          ckdf: pd.DataFrame = None,
                          sf1_p: float = None, sf1_q: float = None,
                          sf2_p: float = None, sf2_q: float = None) -> None:
    """
    Rendu de l'onglet Tableau de Bord avec séparation stricte des périmètres :
    - Maroc Chimie (SF1) : Indicateurs Performance/Qualité + Scores globaux verticaux
    - FEED (SF2)         : Indicateurs Performance/Qualité + Scores globaux verticaux
    - Synthèse comparative des 4 scores globaux
    - Comparaison hebdomadaire : 4 graphiques indépendants en barres verticales
    - Suivi des anomalies & Classements
    """
    # ── 0) Résolution des périmètres (SF1 = Maroc Chimie, SF2 = FEED) ──
    postes_mc = [p for p in vp if str(p).startswith("SF1")]
    postes_feed = [p for p in vp if str(p).startswith("SF2")]

    # Calcul des indicateurs dédiés par division
    if ckdf is not None and not ckdf.empty:
        postes_mc_ck = [p for p in postes_mc if p in ckdf.index]
        postes_feed_ck = [p for p in postes_feed if p in ckdf.index]

        pa_mc = {k: round(ckdf.loc[postes_mc_ck, k].mean(skipna=True), 2) for k in QK if k in ckdf.columns} if postes_mc_ck else {}
        qa_mc = {k: round(ckdf.loc[postes_mc_ck, k].mean(skipna=True), 2) for k in PK if k in ckdf.columns} if postes_mc_ck else {}

        pa_feed = {k: round(ckdf.loc[postes_feed_ck, k].mean(skipna=True), 2) for k in QK if k in ckdf.columns} if postes_feed_ck else {}
        qa_feed = {k: round(ckdf.loc[postes_feed_ck, k].mean(skipna=True), 2) for k in PK if k in ckdf.columns} if postes_feed_ck else {}
    else:
        pa_mc = {k: pa[k] for k in QK if k in pa}
        qa_mc = {k: qa[k] for k in PK if k in qa}
        pa_feed = {k: pa[k] for k in QK if k in pa}
        qa_feed = {k: qa[k] for k in PK if k in qa}

    # Scores globaux de division si non fournis
    if sf1_p is None:
        p_vals = [pscores[p] for p in postes_mc if p in pscores]
        sf1_p = round(sum(p_vals) / len(p_vals), 1) if p_vals else 0.0
    if sf1_q is None:
        q_vals = [qscores[p] for p in postes_mc if p in qscores]
        sf1_q = round(sum(q_vals) / len(q_vals), 1) if q_vals else 0.0
    if sf2_p is None:
        p_vals = [pscores[p] for p in postes_feed if p in pscores]
        sf2_p = round(sum(p_vals) / len(p_vals), 1) if p_vals else 0.0
    if sf2_q is None:
        q_vals = [qscores[p] for p in postes_feed if p in qscores]
        sf2_q = round(sum(q_vals) / len(q_vals), 1) if q_vals else 0.0

    # ══════════════════════════════════════════════════════════════════════════
    # 1 & 2) PÉRIMÈTRE 1 : MAROC CHIMIE (SF1)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);'
        'padding:10px 18px;border-radius:10px;color:#fff;font-weight:800;font-size:17px;'
        'margin:8px 0 16px 0;box-shadow:0 3px 10px rgba(30,58,95,0.15);'
        'display:flex;align-items:center;justify-content:space-between;">'
        '<span>🏭 Périmètre : Maroc Chimie</span>'
        f'<span style="font-size:14px;font-weight:600;opacity:0.9;">Score Global : Perf. {sf1_p:.1f}% | Qual. {sf1_q:.1f}%</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not postes_mc:
        st.info("ℹ️ Aucun poste de travail Maroc Chimie sélectionné dans les filtres.")
    else:
        col_mc_p, col_mc_q = st.columns(2)

        # ── Maroc Chimie : Performance ──
        with col_mc_p:
            st.markdown('<div class="stl p">Indicateurs de Performance — Maroc Chimie</div>', unsafe_allow_html=True)
            labels_mc_p = [k for k in QK if k in pa_mc]
            values_mc_p = [pa_mc[k] for k in labels_mc_p]
            if labels_mc_p:
                show_hbar_thresholds(labels_mc_p, values_mc_p, "Taux moyens — Performance (Maroc Chimie)",
                                     cible_map=CIBLE, lower_set=LOWER_BETTER)
            else:
                st.info("Données indicateurs indisponibles.")

            st.markdown('<div class="stl p" style="margin-top:16px;">Score global Performance — Maroc Chimie</div>', unsafe_allow_html=True)
            show_scores_vbar(postes_mc, pscores, "Score Performance par poste — Maroc Chimie",
                             score_global=sf1_p, color_theme="blue")

        # ── Maroc Chimie : Qualité ──
        with col_mc_q:
            st.markdown('<div class="stl q">Indicateurs de Qualité — Maroc Chimie</div>', unsafe_allow_html=True)
            labels_mc_q = [k for k in PK if k in qa_mc]
            values_mc_q = [qa_mc[k] for k in labels_mc_q]
            if labels_mc_q:
                show_hbar_thresholds(labels_mc_q, values_mc_q, "Taux moyens — Qualité (Maroc Chimie)",
                                     cible_map=CIBLE, lower_set=LOWER_BETTER)
            else:
                st.info("Données indicateurs indisponibles.")

            st.markdown('<div class="stl q" style="margin-top:16px;">Score global Qualité — Maroc Chimie</div>', unsafe_allow_html=True)
            show_scores_vbar(postes_mc, qscores, "Score Qualité par poste — Maroc Chimie",
                             score_global=sf1_q, color_theme="green")

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════════
    # 1 & 2) PÉRIMÈTRE 2 : FEED (SF2)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(
        '<div style="background:linear-gradient(135deg,#065f46 0%,#059669 100%);'
        'padding:10px 18px;border-radius:10px;color:#fff;font-weight:800;font-size:17px;'
        'margin:8px 0 16px 0;box-shadow:0 3px 10px rgba(6,95,70,0.15);'
        'display:flex;align-items:center;justify-content:space-between;">'
        '<span>🏭 Périmètre : FEED</span>'
        f'<span style="font-size:14px;font-weight:600;opacity:0.9;">Score Global : Perf. {sf2_p:.1f}% | Qual. {sf2_q:.1f}%</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not postes_feed:
        st.info("ℹ️ Aucun poste de travail FEED sélectionné dans les filtres.")
    else:
        col_feed_p, col_feed_q = st.columns(2)

        # ── FEED : Performance ──
        with col_feed_p:
            st.markdown('<div class="stl p">Indicateurs de Performance — FEED</div>', unsafe_allow_html=True)
            labels_feed_p = [k for k in QK if k in pa_feed]
            values_feed_p = [pa_feed[k] for k in labels_feed_p]
            if labels_feed_p:
                show_hbar_thresholds(labels_feed_p, values_feed_p, "Taux moyens — Performance (FEED)",
                                     cible_map=CIBLE, lower_set=LOWER_BETTER)
            else:
                st.info("Données indicateurs indisponibles.")

            st.markdown('<div class="stl p" style="margin-top:16px;">Score global Performance — FEED</div>', unsafe_allow_html=True)
            show_scores_vbar(postes_feed, pscores, "Score Performance par poste — FEED",
                             score_global=sf2_p, color_theme="blue")

        # ── FEED : Qualité ──
        with col_feed_q:
            st.markdown('<div class="stl q">Indicateurs de Qualité — FEED</div>', unsafe_allow_html=True)
            labels_feed_q = [k for k in PK if k in qa_feed]
            values_feed_q = [qa_feed[k] for k in labels_feed_q]
            if labels_feed_q:
                show_hbar_thresholds(labels_feed_q, values_feed_q, "Taux moyens — Qualité (FEED)",
                                     cible_map=CIBLE, lower_set=LOWER_BETTER)
            else:
                st.info("Données indicateurs indisponibles.")

            st.markdown('<div class="stl q" style="margin-top:16px;">Score global Qualité — FEED</div>', unsafe_allow_html=True)
            show_scores_vbar(postes_feed, qscores, "Score Qualité par poste — FEED",
                             score_global=sf2_q, color_theme="green")

    # ── Synthèse des 4 scores globaux ──
    st.markdown("---")
    show_global_scores_summary_vbar(sf1_p, sf1_q, sf2_p, sf2_q)

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════════
    # 3) COMPARAISON SEMAINE PRÉCÉDENTE / SEMAINE ACTUELLE (4 GRAPHIQUES)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="stl c">📅 Comparaison Hebdomadaire : Semaine Précédente vs Semaine Actuelle</div>', unsafe_allow_html=True)

    if hist_df is None or hist_df.empty or "Poste de travail" not in hist_df.columns:
        st.markdown(
            '<div style="padding:12px;color:#94a3b8;">'
            'Pas assez de données historiques pour comparer deux semaines. '
            'Au moins 2 dates d\'extraction enregistrées sont nécessaires.</div>',
            unsafe_allow_html=True,
        )
    else:
        _now = pd.Timestamp(now_ts) if now_ts is not None else pd.Timestamp.today()
        lundi_actuel = _now.normalize() - pd.Timedelta(days=_now.weekday())
        dimanche_actuel = lundi_actuel + pd.Timedelta(days=6)
        lundi_precedent = lundi_actuel - pd.Timedelta(days=7)
        dimanche_precedent = lundi_actuel - pd.Timedelta(days=1)

        dates_all = hist_df["Date_parsed"].dropna().sort_values()
        dates_semaine_act = dates_all[(dates_all >= lundi_actuel) & (dates_all <= dimanche_actuel)]
        dates_semaine_prec = dates_all[(dates_all >= lundi_precedent) & (dates_all <= dimanche_precedent)]

        date_act_ts = None
        date_prec_ts = None

        if not dates_semaine_act.empty and not dates_semaine_prec.empty:
            date_act_ts = dates_semaine_act.max()
            date_prec_ts = dates_semaine_prec.max()
        else:
            unique_dates = sorted(dates_all.unique())
            if len(unique_dates) >= 2:
                date_act_ts = pd.Timestamp(unique_dates[-1])
                date_prec_ts = pd.Timestamp(unique_dates[-2])

        if date_act_ts is None or date_prec_ts is None:
            st.markdown(
                '<div style="padding:12px;color:#94a3b8;">'
                'Il faut au moins deux extractions distinctes dans l\'historique pour pouvoir '
                'générer les comparaisons hebdomadaires.</div>',
                unsafe_allow_html=True,
            )
        else:
            date_prec = date_prec_ts.strftime("%d/%m/%Y")
            date_act = date_act_ts.strftime("%d/%m/%Y")

            st.markdown(
                f'<div style="margin-bottom:14px;font-size:12px;color:#475569;background:#f1f5f9;'
                f'padding:6px 12px;border-radius:6px;display:inline-block;">'
                f'📅 Périodes comparées : Semaine précédente <b>{date_prec}</b> &nbsp;→&nbsp; '
                f'Semaine actuelle <b>{date_act}</b></div>',
                unsafe_allow_html=True,
            )

            perf_h = hist_df[hist_df["_section"] == "perf"]
            qual_h = hist_df[hist_df["_section"] == "qual"]

            def _get_comparison_data(postes_sub):
                p_valides, p_prec, p_act, q_prec, q_act = [], [], [], [], []
                for poste in postes_sub:
                    pr_act = perf_h[(perf_h["Poste de travail"] == poste) & (perf_h["Date_parsed"] == date_act_ts)]
                    pr_prec = perf_h[(perf_h["Poste de travail"] == poste) & (perf_h["Date_parsed"] == date_prec_ts)]
                    qr_act = qual_h[(qual_h["Poste de travail"] == poste) & (qual_h["Date_parsed"] == date_act_ts)]
                    qr_prec = qual_h[(qual_h["Poste de travail"] == poste) & (qual_h["Date_parsed"] == date_prec_ts)]

                    val_p_act = float(pr_act["Score Performance"].iloc[0]) if not pr_act.empty and "Score Performance" in pr_act.columns else 0.0
                    val_p_prec = float(pr_prec["Score Performance"].iloc[0]) if not pr_prec.empty and "Score Performance" in pr_prec.columns else 0.0
                    val_q_act = float(qr_act["Score Qualite"].iloc[0]) if not qr_act.empty and "Score Qualite" in qr_act.columns else 0.0
                    val_q_prec = float(qr_prec["Score Qualite"].iloc[0]) if not qr_prec.empty and "Score Qualite" in qr_prec.columns else 0.0

                    p_valides.append(poste)
                    p_prec.append(val_p_prec); p_act.append(val_p_act)
                    q_prec.append(val_q_prec); q_act.append(val_q_act)
                return p_valides, p_prec, p_act, q_prec, q_act

            hist_postes = hist_df["Poste de travail"].unique()
            postes_mc_h = sorted([p for p in postes_mc if p in hist_postes])
            postes_feed_h = sorted([p for p in postes_feed if p in hist_postes])

            mc_postes, mc_p_prec, mc_p_act, mc_q_prec, mc_q_act = _get_comparison_data(postes_mc_h)
            feed_postes, feed_p_prec, feed_p_act, feed_q_prec, feed_q_act = _get_comparison_data(postes_feed_h)

            # ── Ligne 1 : Maroc Chimie (Graphiques 1 & 2) ──
            st.markdown("#### 🏭 Maroc Chimie — Comparaison Hebdomadaire")
            col_cmp_mc_p, col_cmp_mc_q = st.columns(2)

            with col_cmp_mc_p:
                st.markdown("**1️⃣ Performance – Maroc Chimie** *(Semaine précédente vs actuelle)*")
                show_weekly_comparison_vbar(
                    mc_postes, mc_p_prec, mc_p_act,
                    f"Performance — Maroc Chimie ({date_prec} vs {date_act})",
                    date_prec, date_act, kpi_type="perf",
                )

            with col_cmp_mc_q:
                st.markdown("**2️⃣ Qualité – Maroc Chimie** *(Semaine précédente vs actuelle)*")
                show_weekly_comparison_vbar(
                    mc_postes, mc_q_prec, mc_q_act,
                    f"Qualité — Maroc Chimie ({date_prec} vs {date_act})",
                    date_prec, date_act, kpi_type="qual",
                )

            # ── Ligne 2 : FEED (Graphiques 3 & 4) ──
            st.markdown("#### 🏭 FEED — Comparaison Hebdomadaire")
            col_cmp_feed_p, col_cmp_feed_q = st.columns(2)

            with col_cmp_feed_p:
                st.markdown("**3️⃣ Performance – FEED** *(Semaine précédente vs actuelle)*")
                show_weekly_comparison_vbar(
                    feed_postes, feed_p_prec, feed_p_act,
                    f"Performance — FEED ({date_prec} vs {date_act})",
                    date_prec, date_act, kpi_type="perf",
                )

            with col_cmp_feed_q:
                st.markdown("**4️⃣ Qualité – FEED** *(Semaine précédente vs actuelle)*")
                show_weekly_comparison_vbar(
                    feed_postes, feed_q_prec, feed_q_act,
                    f"Qualité — FEED ({date_prec} vs {date_act})",
                    date_prec, date_act, kpi_type="qual",
                )

    st.markdown("---")

    # ── 4) Suivi hebdomadaire des anomalies (inchangé) ──
    render_suivi_anomalies_semaine(vp, hist_df, now_ts, "dash", ano_map_actuel=ano_map)

    st.markdown("---")

    # ── 5) Classements ──
    col_rk_p, col_rk_q = st.columns(2)
    with col_rk_p:
        st.markdown('<div class="stl c">Classement Performance</div>', unsafe_allow_html=True)
        st.markdown(html_classement(pscores, "#10b981"), unsafe_allow_html=True)
    with col_rk_q:
        st.markdown('<div class="stl c">Classement Qualité</div>', unsafe_allow_html=True)
        st.markdown(html_classement(qscores, "#3b82f6"), unsafe_allow_html=True)
