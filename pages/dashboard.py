# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core.constants import QK, PK, CIBLE, LOWER_BETTER
from components.tables import html_classement
from components.charts import show_grouped_hbar, show_hbar_thresholds, show_butterfly_comparison
from components.sparklines import get_comparison_html
from core.historique import calculate_taux_traitement


def render_dashboard_tab(vp: list, pscores: dict, qscores: dict,
                          pa: dict, qa: dict,
                          hist_df: pd.DataFrame = None,
                          now_ts: pd.Timestamp = None) -> None:
    # ── Scores globaux par poste : Performance ET Qualité SUR LE MÊME
    # GRAPHIQUE (demande explicite) — barres épaisses, largeur maîtrisée ──
    st.markdown('<div class="stl p">Scores globaux par poste — Performance et Qualité</div>', unsafe_allow_html=True)
    show_grouped_hbar(vp, pscores, qscores, "Performance & Qualité par poste", thin=True)

    # ── Comparaison Semaine Actuelle vs Semaine Précédente par poste ────
    # CORRIGÉ (demande explicite, style "photo 2") : graphique "papillon"
    # au lieu du tableau HTML — semaine précédente à gauche, semaine
    # actuelle à droite, un axe central par poste.
    # date d'extraction) : "semaine actuelle" = dernière date enregistrée,
    # "semaine précédente" = avant-dernière. Réutilise get_comparison_html
    # (même logique que l'onglet Suivi & Évolution) pour une présentation
    # cohérente dans toute l'application.
    st.markdown('<div class="stl c">Comparaison Semaine Actuelle vs Semaine Précédente</div>', unsafe_allow_html=True)

    if hist_df is None or hist_df.empty or "Poste de travail" not in hist_df.columns:
        st.markdown(
            '<div style="padding:12px;color:#94a3b8;">'
            'Pas assez de données historiques pour comparer deux semaines. '
            'Au moins 2 dates d\'extraction enregistrées sont nécessaires.</div>',
            unsafe_allow_html=True,
        )
    else:
        # CORRIGÉ (demande explicite) : semaine calendaire ISO, du LUNDI
        # au DIMANCHE — plus les 2 dernières dates d'extraction quelles
        # qu'elles soient, mais la vraie "semaine actuelle" (contenant
        # aujourd'hui) et la vraie "semaine précédente" (les 7 jours
        # juste avant). Pour chaque semaine, on prend la DERNIÈRE date
        # d'extraction disponible qui y tombe (une semaine peut avoir 0,
        # 1 ou plusieurs extractions).
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
                f'<div style="margin-bottom:8px;font-size:12px;color:#64748b;">'
                f'📅 Semaine précédente ({lundi_precedent:%d/%m}–{dimanche_precedent:%d/%m}) : '
                f'extraction du <b>{date_prec}</b> &nbsp;→&nbsp; '
                f'Semaine actuelle ({lundi_actuel:%d/%m}–{dimanche_actuel:%d/%m}) : '
                f'extraction du <b>{date_act}</b></div>',
                unsafe_allow_html=True,
            )

            perf_h = hist_df[hist_df["_section"] == "perf"]
            qual_h = hist_df[hist_df["_section"] == "qual"]
            postes_dispo = sorted([p for p in vp if p in hist_df["Poste de travail"].unique()])

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
                    "Performance & Qualité", f"Préc. ({date_prec})", f"Actuelle ({date_act})",
                )

    # ── Système de suivi hebdomadaire : taux de traitement des anomalies
    # (demande explicite) — semaine actuelle vs semaine précédente,
    # lundi->dimanche, au niveau général ET par poste de travail.
    st.markdown('<div class="stl a">🎯 Taux de traitement des anomalies (semaine vs semaine précédente)</div>', unsafe_allow_html=True)
    if hist_df is None or hist_df.empty:
        st.markdown(
            '<div style="padding:12px;color:#94a3b8;">Historique indisponible pour le moment.</div>',
            unsafe_allow_html=True,
        )
    else:
        res_traitement = calculate_taux_traitement(hist_df, now_ts or pd.Timestamp.today(), QK, PK)
        d = res_traitement["dates"]
        if res_traitement["general"] is None:
            st.markdown(
                f'<div style="padding:12px;color:#94a3b8;">'
                f'Il faut au moins une extraction dans la semaine actuelle '
                f'({d["lundi_actuel"]:%d/%m}–{d["dimanche_actuel"]:%d/%m}) ET dans la semaine '
                f'précédente ({d["lundi_precedent"]:%d/%m}–{d["dimanche_precedent"]:%d/%m}) '
                f'pour calculer le taux de traitement.</div>',
                unsafe_allow_html=True,
            )
        else:
            g = res_traitement["general"]
            couleur = "#10b981" if g["taux_pct"] >= 0 else "#ef4444"
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    f'<div style="text-align:center;padding:14px;background:{couleur}12;border-radius:10px;">'
                    f'<div style="font-size:11px;color:#64748b;font-weight:700;">TAUX DE TRAITEMENT GÉNÉRAL</div>'
                    f'<div style="font-size:32px;font-weight:800;color:{couleur};">{g["taux_pct"]:.1f}%</div></div>',
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f'<div style="text-align:center;padding:14px;background:#f1f5f9;border-radius:10px;">'
                    f'<div style="font-size:11px;color:#64748b;font-weight:700;">ANOMALIES SEMAINE PRÉCÉDENTE</div>'
                    f'<div style="font-size:32px;font-weight:800;color:#1e293b;">{g["anomalies_prec"]}</div></div>',
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    f'<div style="text-align:center;padding:14px;background:#f1f5f9;border-radius:10px;">'
                    f'<div style="font-size:11px;color:#64748b;font-weight:700;">ANOMALIES SEMAINE ACTUELLE</div>'
                    f'<div style="font-size:32px;font-weight:800;color:#1e293b;">{g["anomalies_act"]}</div></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            st.markdown("**Détail par poste de travail :**")
            par_poste_aff = res_traitement["par_poste"][res_traitement["par_poste"]["Poste"].isin(vp)]
            st.dataframe(par_poste_aff, use_container_width=True, hide_index=True,
                         height=min(400, 45 + 35 * len(par_poste_aff)))

    st.markdown("---")

    # ── Taux moyens par KPI (couleur = respect de la VRAIE cible de chaque KPI) ──
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

    # ── Classements (inchangés) ──────────────────────────────────────────
    st.markdown('<div class="stl c">Classement Performance</div>', unsafe_allow_html=True)
    st.markdown(html_classement(pscores, "#10b981"), unsafe_allow_html=True)

    st.markdown('<div class="stl c">Classement Qualité</div>', unsafe_allow_html=True)
    st.markdown(html_classement(qscores, "#3b82f6"), unsafe_allow_html=True)
