# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd

from core.constants import QK, PK
from core.historique import evaluate_trend_last_n
from components.sparklines import get_sparkline_html, get_comparison_html, render_sparkline_table, render_anomaly_sparkline_table
from components.tables import html_synthese_table

def render_evolution_tab(hist_df: pd.DataFrame, var_df: pd.DataFrame,
                          journal_df: pd.DataFrame, top5_df: pd.DataFrame,
                          bot5_df: pd.DataFrame, synth_perf: dict,
                          synth_qual: dict, vp: list) -> None:

    min_date = var_df["Date precedente"].min() if not var_df.empty else "?"
    max_date = var_df["Date actuelle"].max() if not var_df.empty else "?"

    # Bouton Masquer/Afficher
    if "show_synth" not in st.session_state:
        st.session_state.show_synth = False

    btn_label = "▼ Masquer les détails" if st.session_state.show_synth else "▶ Voir plus de détails"
    if st.button(btn_label, key="btn_synth"):
        st.session_state.show_synth = not st.session_state.show_synth
        st.rerun()

    if st.session_state.show_synth:
        st.markdown(
            f'<h4>Synthèse d\'évolution Performance entre {min_date} et {max_date}</h4>',
            unsafe_allow_html=True,
        )
        if synth_perf and any(any(v.get("diff", "—") != "—" for v in d.values()) for d in synth_perf.values()):
            st.markdown(html_synthese_table(synth_perf, QK, vp), unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#94a3b8;">Pas assez de données historiques pour calculer la synthèse Performance. Au moins 2 périodes sont nécessaires.</div>', unsafe_allow_html=True)

        st.markdown(
            f'<h4>Synthèse d\'évolution Qualité entre {min_date} et {max_date}</h4>',
            unsafe_allow_html=True,
        )
        if synth_qual and any(any(v.get("diff", "—") != "—" for v in d.values()) for d in synth_qual.values()):
            st.markdown(html_synthese_table(synth_qual, PK, vp), unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#94a3b8;">Pas assez de données historiques pour calculer la synthèse Qualité. Au moins 2 périodes sont nécessaires.</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── NOUVEAU : bouton de bascule Suivi par KPI / Suivi par nombre d'anomalies ──
    if "evo_mode" not in st.session_state:
        st.session_state.evo_mode = "kpi"

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "📊 Suivi par KPI",
            key="btn_mode_kpi",
            type="primary" if st.session_state.evo_mode == "kpi" else "secondary",
            use_container_width=True,
        ):
            st.session_state.evo_mode = "kpi"
            st.rerun()
    with c2:
        if st.button(
            "🔺 Suivi par nombre d'anomalies",
            key="btn_mode_ano",
            type="primary" if st.session_state.evo_mode == "ano" else "secondary",
            use_container_width=True,
        ):
            st.session_state.evo_mode = "ano"
            st.rerun()

    st.markdown("---")

    if st.session_state.evo_mode == "kpi":
        # ── Sparklines PAR KPI (pas seulement le score agrégé) ──
        st.markdown('<h4>📈 Suivi Sparklines par KPI — Performance</h4>', unsafe_allow_html=True)
        st.markdown(render_sparkline_table(hist_df, QK, "Performance"), unsafe_allow_html=True)

        st.markdown('<h4 style="margin-top:16px;">✅ Suivi Sparklines par KPI — Qualité</h4>', unsafe_allow_html=True)
        st.markdown(render_sparkline_table(hist_df, PK, "Qualite"), unsafe_allow_html=True)

    else:
        # ── Sparklines PAR NOMBRE D'ANOMALIES ──
        st.markdown('<h4>🔺 Suivi Sparklines — Anomalies Performance</h4>', unsafe_allow_html=True)
        st.markdown(render_anomaly_sparkline_table(hist_df, QK, "ano_perf"), unsafe_allow_html=True)

        st.markdown('<h4 style="margin-top:16px;">🔺 Suivi Sparklines — Anomalies Qualité</h4>', unsafe_allow_html=True)
        st.markdown(render_anomaly_sparkline_table(hist_df, PK, "ano_qual"), unsafe_allow_html=True)

    st.markdown("---")

    # ── Score global (ancien tableau agrégé par poste, conservé) ──
    st.markdown('<h4>Suivi Sparklines — Score global par Poste de Travail</h4>', unsafe_allow_html=True)

    if not hist_df.empty and "Poste de travail" in hist_df.columns:
        valid_postes = sorted([p for p in vp if p in hist_df["Poste de travail"].unique()])
        perf_df_h = hist_df[(hist_df["_section"] == "perf") & (hist_df["Poste de travail"].isin(valid_postes))]
        qual_df_h = hist_df[(hist_df["_section"] == "qual") & (hist_df["Poste de travail"].isin(valid_postes))]

        h = '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
        h += ('<tr style="background:#f1f5f9;"><th style="padding:6px;text-align:left;">Poste de travail</th>'
              '<th style="padding:6px;">Sparkline Performance</th><th style="padding:6px;">Comparaison Performance</th>'
              '<th style="padding:6px;">Sparkline Qualité</th><th style="padding:6px;">Comparaison Qualité</th></tr>')

        for poste in valid_postes:
            p_data = perf_df_h[perf_df_h["Poste de travail"] == poste].sort_values("Date_parsed")
            q_data = qual_df_h[qual_df_h["Poste de travail"] == poste].sort_values("Date_parsed")
            p_scores = p_data["Score Performance"].astype(float).tolist() if "Score Performance" in p_data.columns else []
            q_scores = q_data["Score Qualite"].astype(float).tolist() if "Score Qualite" in q_data.columns else []

            h += f'<tr style="border-top:1px solid #e2e8f0;"><td style="padding:6px;font-weight:600;">{poste}</td>'
            h += f'<td style="text-align:center;">{get_sparkline_html(p_scores)}</td>'
            h += f'<td style="text-align:center;">{get_comparison_html(p_scores)}</td>'
            h += f'<td style="text-align:center;">{get_sparkline_html(q_scores)}</td>'
            h += f'<td style="text-align:center;">{get_comparison_html(q_scores)}</td>'
            h += '</tr>'

        h += '</table>'
        st.markdown(h, unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#94a3b8;">Pas assez de données historiques pour générer les sparklines.</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── NOUVEAU : évaluation sur les N dernières valeurs (pas juste les 2 dernières) ──
    st.markdown('<h4>🔍 Évaluation sur les dernières périodes enregistrées</h4>', unsafe_allow_html=True)
    n_periodes = st.slider(
        "Nombre de dernières périodes à comparer", min_value=2, max_value=10, value=5,
        key="slider_n_periodes",
        help="Compare la 1ère et la dernière valeur sur cette fenêtre glissante, au lieu de comparer uniquement les 2 dernières périodes.",
    )

    if st.session_state.evo_mode == "kpi":
        trend_perf = evaluate_trend_last_n(hist_df, "perf", QK, n=n_periodes)
        trend_qual = evaluate_trend_last_n(hist_df, "qual", PK, n=n_periodes)
        trend_df = pd.concat([trend_perf, trend_qual], ignore_index=True) if not trend_perf.empty or not trend_qual.empty else pd.DataFrame()
    else:
        trend_perf = evaluate_trend_last_n(hist_df, "ano_perf", QK + ["Total Anomalies"], n=n_periodes)
        trend_qual = evaluate_trend_last_n(hist_df, "ano_qual", PK + ["Total Anomalies"], n=n_periodes)
        trend_df = pd.concat([trend_perf, trend_qual], ignore_index=True) if not trend_perf.empty or not trend_qual.empty else pd.DataFrame()

    if trend_df.empty:
        st.markdown(
            f'<div style="color:#94a3b8;">Pas assez de données pour évaluer une tendance sur {n_periodes} périodes. '
            f'Enregistrez plus de dates pour activer cette analyse.</div>',
            unsafe_allow_html=True,
        )
    else:
        if vp:
            trend_df = trend_df[trend_df["Poste"].isin(vp)]
        degrad = trend_df[trend_df["Tendance"] == "Dégradation"].sort_values("Écart %")
        amelio = trend_df[trend_df["Tendance"] == "Amélioration"].sort_values("Écart %", ascending=False)

        tc1, tc2 = st.columns(2)
        with tc1:
            st.markdown(f'<b>🔴 Dégradations sur les {n_periodes} dernières périodes ({len(degrad)})</b>', unsafe_allow_html=True)
            if not degrad.empty:
                st.dataframe(
                    degrad[["Poste", "KPI", "Nb valeurs", "Première", "Dernière", "Écart %"]].head(15).reset_index(drop=True),
                    use_container_width=True, height=350,
                )
            else:
                st.markdown('<div style="color:#94a3b8;">Aucune dégradation détectée.</div>', unsafe_allow_html=True)
        with tc2:
            st.markdown(f'<b>🟢 Améliorations sur les {n_periodes} dernières périodes ({len(amelio)})</b>', unsafe_allow_html=True)
            if not amelio.empty:
                st.dataframe(
                    amelio[["Poste", "KPI", "Nb valeurs", "Première", "Dernière", "Écart %"]].head(15).reset_index(drop=True),
                    use_container_width=True, height=350,
                )
            else:
                st.markdown('<div style="color:#94a3b8;">Aucune amélioration détectée.</div>', unsafe_allow_html=True)

    st.markdown("---")

    # Journal
    st.markdown('<h4>Journal des variations significatives</h4>', unsafe_allow_html=True)
    if not journal_df.empty:
        st.dataframe(
            journal_df[["Date precedente", "Date actuelle", "Poste", "Type",
                        "KPI", "Valeur precedente", "Valeur actuelle", "Ecart %", "Sens"]]
            .reset_index(drop=True),
            use_container_width=True, height=400,
        )
    else:
        st.markdown('<div style="color:#94a3b8;">Aucune variation significative détectée (écart ≥ 5% entre deux périodes)</div>', unsafe_allow_html=True)

    if not top5_df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<b>Top 5 Postes — Amélioration</b>', unsafe_allow_html=True)
            st.dataframe(top5_df, use_container_width=True)
        with c2:
            st.markdown('<b>Bottom 5 Postes — Dégradation</b>', unsafe_allow_html=True)
            st.dataframe(bot5_df, use_container_width=True)
