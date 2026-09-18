# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core.constants import QK, PK, CIBLE, LOWER_BETTER
from components.tables import html_classement
from components.charts import show_grouped_hbar, show_hbar_thresholds
from components.sparklines import get_comparison_html


def render_dashboard_tab(vp: list, pscores: dict, qscores: dict,
                          pa: dict, qa: dict,
                          hist_df: pd.DataFrame = None) -> None:
    # ── Scores globaux par poste : Performance ET Qualité SUR LE MÊME
    # GRAPHIQUE, barres très fines (demande explicite) ──────────────────
    st.markdown('<div class="stl p">Scores globaux par poste — Performance et Qualité</div>', unsafe_allow_html=True)
    show_grouped_hbar(vp, pscores, qscores, "Performance & Qualité par poste", thin=True)

    # ── Comparaison Semaine Actuelle vs Semaine Précédente par poste ────
    # AJOUTÉ (demande explicite). Repose sur hist_df (historique KPI par
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
        dates_dispo = sorted(hist_df["Date_parsed"].dropna().unique())
        if len(dates_dispo) < 2:
            st.markdown(
                '<div style="padding:12px;color:#94a3b8;">'
                'Une seule date d\'extraction disponible pour le moment — '
                'la comparaison apparaîtra dès la 2ᵉ extraction enregistrée.</div>',
                unsafe_allow_html=True,
            )
        else:
            date_prec = pd.Timestamp(dates_dispo[-2]).strftime("%d/%m/%Y")
            date_act = pd.Timestamp(dates_dispo[-1]).strftime("%d/%m/%Y")
            st.markdown(
                f'<div style="margin-bottom:8px;font-size:12px;color:#64748b;">'
                f'📅 Semaine précédente : <b>{date_prec}</b> &nbsp;→&nbsp; '
                f'Semaine actuelle : <b>{date_act}</b></div>',
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
                h = '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
                h += (
                    '<tr style="background:#f1f5f9;">'
                    '<th style="padding:8px;text-align:left;">Poste de travail</th>'
                    '<th style="padding:8px;text-align:center;">Performance — évolution</th>'
                    '<th style="padding:8px;text-align:center;">Qualité — évolution</th>'
                    '</tr>'
                )
                for poste in postes_dispo:
                    p_scores = (
                        perf_h[perf_h["Poste de travail"] == poste]
                        .sort_values("Date_parsed")["Score Performance"]
                        .astype(float).tolist()
                        if "Score Performance" in perf_h.columns else []
                    )
                    q_scores = (
                        qual_h[qual_h["Poste de travail"] == poste]
                        .sort_values("Date_parsed")["Score Qualite"]
                        .astype(float).tolist()
                        if "Score Qualite" in qual_h.columns else []
                    )
                    h += (
                        f'<tr style="border-bottom:1px solid #e2e8f0;">'
                        f'<td style="padding:8px;font-weight:600;">{poste}</td>'
                        f'<td style="padding:8px;text-align:center;">{get_comparison_html(p_scores)}</td>'
                        f'<td style="padding:8px;text-align:center;">{get_comparison_html(q_scores)}</td>'
                        f'</tr>'
                    )
                h += '</table>'
                st.markdown(h, unsafe_allow_html=True)

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
