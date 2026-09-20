# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core.constants import QK, PK, CIBLE, LOWER_BETTER
from components.tables import html_classement
from components.charts import show_grouped_hbar, show_hbar_thresholds, show_butterfly_comparison, render_suivi_anomalies_semaine


def render_dashboard_tab(vp: list, pscores: dict, qscores: dict,
                          pa: dict, qa: dict,
                          hist_df: pd.DataFrame = None,
                          now_ts: pd.Timestamp = None,
                          ano_map: dict = None) -> None:
    # ── 1) Taux moyens par KPI — EN PREMIER (demande explicite) ─────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="stl p">Indicateurs de Performance</div>', unsafe_allow_html=True)
        labels = [k for k in QK if k in pa]
        values = [pa[k] for k in labels]
        show_hbar_thresholds(labels, values, "Taux moyens — Performance",
                             cible_map=CIBLE, lower_set=LOWER_BETTER)
    with col2:
        st.markdown('<div class="stl q">Indicateurs de Qualité</div>', unsafe_allow_html=True)
        labels = [k for k in PK if k in qa]
        values = [qa[k] for k in labels]
        show_hbar_thresholds(labels, values, "Taux moyens — Qualité",
                             cible_map=CIBLE, lower_set=LOWER_BETTER)

    st.markdown("---")

    # ── 2) Score global par poste ET comparaison semaine précédente/
    # actuelle CÔTE À CÔTE (demande explicite) ──────────────────────────
    # AJOUTÉ (demande explicite) : bouton bascule UNIQUE Maroc Chimie
    # (SF1) / FEEDS (SF2), qui filtre LES DEUX graphiques ci-dessous
    # simultanément — un seul graphique par côté est affiché à la fois
    # (pas les deux divisions superposées).
    division_dash = st.radio(
        "Division", ["🏭 Maroc Chimie", "🏭 FEEDS"],
        horizontal=True, label_visibility="collapsed", key="dash_division_toggle",
    )
    prefixe_div = "SF1" if division_dash == "🏭 Maroc Chimie" else "SF2"
    vp_div = [p for p in vp if str(p).startswith(prefixe_div)]

    col_score, col_compar = st.columns(2)

    with col_score:
        st.markdown(f'<div class="stl p">Scores globaux par poste — {division_dash}</div>', unsafe_allow_html=True)
        show_grouped_hbar(vp_div, pscores, qscores, f"Performance & Qualité — {division_dash}", thin=True)

    with col_compar:
        st.markdown('<div class="stl c">Comparaison Semaine Actuelle vs Semaine Précédente</div>', unsafe_allow_html=True)

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

            dates_all = hist_df["Date_parsed"].dropna()
            dates_semaine_act = dates_all[(dates_all >= lundi_actuel) & (dates_all <= dimanche_actuel)]
            dates_semaine_prec = dates_all[(dates_all >= lundi_precedent) & (dates_all <= dimanche_precedent)]

            if dates_semaine_act.empty or dates_semaine_prec.empty:
                st.markdown(
                    '<div style="padding:12px;color:#94a3b8;">'
                    f'Semaine actuelle ({lundi_actuel:%d/%m}–{dimanche_actuel:%d/%m}) : '
                    f'{"aucune" if dates_semaine_act.empty else len(dates_semaine_act.unique())} extraction(s). '
                    f'Semaine précédente ({lundi_precedent:%d/%m}–{dimanche_precedent:%d/%m}) : '
                    f'{"aucune" if dates_semaine_prec.empty else len(dates_semaine_prec.unique())} extraction(s). '
                    'Il faut au moins une extraction dans chacune des deux semaines pour comparer.</div>',
                    unsafe_allow_html=True,
                )
            else:
                date_act_ts = dates_semaine_act.max()
                date_prec_ts = dates_semaine_prec.max()
                date_prec = date_prec_ts.strftime("%d/%m/%Y")
                date_act = date_act_ts.strftime("%d/%m/%Y")
                st.markdown(
                    f'<div style="margin-bottom:8px;font-size:11px;color:#64748b;">'
                    f'📅 Préc. : <b>{date_prec}</b> &nbsp;→&nbsp; Actuelle : <b>{date_act}</b></div>',
                    unsafe_allow_html=True,
                )

                perf_h = hist_df[hist_df["_section"] == "perf"]
                qual_h = hist_df[hist_df["_section"] == "qual"]
                postes_dispo = sorted([p for p in vp_div if p in hist_df["Poste de travail"].unique()])

                if not postes_dispo:
                    st.markdown(
                        '<div style="padding:12px;color:#94a3b8;">Aucun poste du périmètre sélectionné '
                        'ne dispose d\'historique.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    postes_valides, perf_prec, perf_act, qual_prec, qual_act = [], [], [], [], []
                    for poste in postes_dispo:
                        p_row_act = perf_h[(perf_h["Poste de travail"] == poste) & (perf_h["Date_parsed"] == date_act_ts)]
                        p_row_prec = perf_h[(perf_h["Poste de travail"] == poste) & (perf_h["Date_parsed"] == date_prec_ts)]
                        q_row_act = qual_h[(qual_h["Poste de travail"] == poste) & (qual_h["Date_parsed"] == date_act_ts)]
                        q_row_prec = qual_h[(qual_h["Poste de travail"] == poste) & (qual_h["Date_parsed"] == date_prec_ts)]

                        val_p_act = float(p_row_act["Score Performance"].iloc[0]) if not p_row_act.empty and "Score Performance" in p_row_act.columns else 0.0
                        val_p_prec = float(p_row_prec["Score Performance"].iloc[0]) if not p_row_prec.empty and "Score Performance" in p_row_prec.columns else 0.0
                        val_q_act = float(q_row_act["Score Qualite"].iloc[0]) if not q_row_act.empty and "Score Qualite" in q_row_act.columns else 0.0
                        val_q_prec = float(q_row_prec["Score Qualite"].iloc[0]) if not q_row_prec.empty and "Score Qualite" in q_row_prec.columns else 0.0

                        postes_valides.append(poste)
                        perf_prec.append(val_p_prec); perf_act.append(val_p_act)
                        qual_prec.append(val_q_prec); qual_act.append(val_q_act)

                    show_butterfly_comparison(
                        postes_valides, perf_prec, perf_act, qual_prec, qual_act,
                        f"Performance & Qualité — {division_dash}", f"Préc. ({date_prec})", f"Actuelle ({date_act})",
                    )

    st.markdown("---")

    # ── 3) Suivi hebdomadaire des anomalies (bar empilée 2 couleurs,
    # gère l'état "1ère semaine" statique — voir components/charts.py) ──
    render_suivi_anomalies_semaine(vp, hist_df, now_ts, "dash", ano_map_actuel=ano_map)

    st.markdown("---")

    # ── Classements (inchangés) ──────────────────────────────────────────
    st.markdown('<div class="stl c">Classement Performance</div>', unsafe_allow_html=True)
    st.markdown(html_classement(pscores, "#10b981"), unsafe_allow_html=True)

    st.markdown('<div class="stl c">Classement Qualité</div>', unsafe_allow_html=True)
    st.markdown(html_classement(qscores, "#3b82f6"), unsafe_allow_html=True)
