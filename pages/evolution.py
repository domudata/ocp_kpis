# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd

from core.constants import QK, PK
from components.sparklines import get_sparkline_html, get_comparison_html
from components.tables import html_synthese_table
from components.charts import render_suivi_anomalies_semaine_live


def render_evolution_tab(hist_df: pd.DataFrame, var_df: pd.DataFrame,
                          journal_df: pd.DataFrame, top5_df: pd.DataFrame,
                          bot5_df: pd.DataFrame, synth_perf: dict,
                          synth_qual: dict, vp: list,
                          now_ts: pd.Timestamp = None,
                          df_full: pd.DataFrame = None,
                          av_full: pd.DataFrame = None,
                          apm: list = None) -> None:
    # ── Anomalies par semaine — REFAIT (demande explicite finale) :
    # référence FIXE prise à la 1ère extraction de la semaine ISO en
    # cours, mise à jour à chaque nouvelle extraction DANS LA MÊME
    # semaine (pas de comparaison avec une autre semaine). Barre
    # empilée 2 couleurs + % de traitement.
    render_suivi_anomalies_semaine_live(vp, hist_df, now_ts or pd.Timestamp.today(), "evol")
    st.markdown("---")

    # NOTE : journal_df, top5_df, bot5_df restent acceptés en paramètres
    # (pour ne pas casser l'appel depuis app.py) mais ne sont plus
    # affichés — sections "Journal des variations" et "Dégradations /
    # Améliorations" retirées (demande explicite).

    min_date = var_df["Date precedente"].min() if not var_df.empty else "?"
    max_date = var_df["Date actuelle"].max() if not var_df.empty else "?"

    # Bouton Masquer/Afficher — Synthèse
    if "show_synth" not in st.session_state:
        st.session_state.show_synth = False

    btn_label = "▼ Masquer les détails" if st.session_state.show_synth else "▶ Voir plus de détails"
    if st.button(btn_label, key="btn_synth"):
        st.session_state.show_synth = not st.session_state.show_synth
        st.rerun()

    if st.session_state.show_synth:
        st.markdown(
            f'<div class="stl c">Synthèse d\'évolution Performance entre {min_date} et {max_date}</div>',
            unsafe_allow_html=True,
        )
        if synth_perf and any(any(v.get("diff", "—") != "—" for v in d.values()) for d in synth_perf.values()):
            st.markdown(html_synthese_table(synth_perf, QK, vp), unsafe_allow_html=True)
        else:
            st.markdown('<div style="padding:12px;color:#94a3b8;">Pas assez de données historiques pour calculer la synthèse Performance. Au moins 2 périodes sont nécessaires.</div>', unsafe_allow_html=True)

        st.markdown(
            f'<div class="stl c">Synthèse d\'évolution Qualité entre {min_date} et {max_date}</div>',
            unsafe_allow_html=True,
        )
        if synth_qual and any(any(v.get("diff", "—") != "—" for v in d.values()) for d in synth_qual.values()):
            st.markdown(html_synthese_table(synth_qual, PK, vp), unsafe_allow_html=True)
        else:
            st.markdown('<div style="padding:12px;color:#94a3b8;">Pas assez de données historiques pour calculer la synthèse Qualité. Au moins 2 périodes sont nécessaires.</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Tableau Sparklines — AJOUT du bouton bascule (demande explicite) ──
    # Même style de bouton que ci-dessus, pour masquer/afficher la section
    # sparklines indépendamment de la section Synthèse.
    if "show_sparklines" not in st.session_state:
        st.session_state.show_sparklines = True

    spark_label = "▼ Masquer les Sparklines" if st.session_state.show_sparklines else "▶ Afficher les Sparklines"
    if st.button(spark_label, key="btn_sparklines"):
        st.session_state.show_sparklines = not st.session_state.show_sparklines
        st.rerun()

    if st.session_state.show_sparklines:
        st.markdown('<div class="stl c">Suivi Sparklines par Poste de Travail</div>', unsafe_allow_html=True)

        if not hist_df.empty and "Poste de travail" in hist_df.columns:
            valid_postes = sorted([p for p in vp if p in hist_df["Poste de travail"].unique()])
            perf_df_h = hist_df[(hist_df["_section"] == "perf") & (hist_df["Poste de travail"].isin(valid_postes))]
            qual_df_h = hist_df[(hist_df["_section"] == "qual") & (hist_df["Poste de travail"].isin(valid_postes))]

            h = '<table style="width:100%;border-collapse:collapse;">'
            h += ('<tr style="background:#f1f5f9;">'
                  '<th style="padding:8px;text-align:left;">Poste de travail</th>'
                  '<th style="padding:8px;">Sparkline Performance</th>'
                  '<th style="padding:8px;">Comparaison Performance</th>'
                  '<th style="padding:8px;">Sparkline Qualité</th>'
                  '<th style="padding:8px;">Comparaison Qualité</th>'
                  '</tr>')

            for poste in valid_postes:
                p_data = perf_df_h[perf_df_h["Poste de travail"] == poste].sort_values("Date_parsed")
                q_data = qual_df_h[qual_df_h["Poste de travail"] == poste].sort_values("Date_parsed")
                p_scores = p_data["Score Performance"].astype(float).tolist() if "Score Performance" in p_data.columns else []
                q_scores = q_data["Score Qualite"].astype(float).tolist() if "Score Qualite" in q_data.columns else []

                h += f'<tr style="border-bottom:1px solid #e2e8f0;">'
                h += f'<td style="padding:8px;font-weight:600;">{poste}</td>'
                h += f'<td style="padding:8px;text-align:center;">{get_sparkline_html(p_scores)}</td>'
                h += f'<td style="padding:8px;text-align:center;">{get_comparison_html(p_scores)}</td>'
                h += f'<td style="padding:8px;text-align:center;">{get_sparkline_html(q_scores)}</td>'
                h += f'<td style="padding:8px;text-align:center;">{get_comparison_html(q_scores)}</td>'
                h += '</tr>'

            h += '</table>'
            st.markdown(h, unsafe_allow_html=True)
        else:
            st.markdown('<div style="padding:12px;color:#94a3b8;">Pas assez de données historiques pour générer les sparklines.</div>', unsafe_allow_html=True)
