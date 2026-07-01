# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd

from core.constants import QK, PK
from components.sparklines import get_sparkline_html, get_comparison_html
from components.tables import html_synthese_table


def render_evolution_tab(hist_df: pd.DataFrame, var_df: pd.DataFrame,
                          journal_df: pd.DataFrame, top5_df: pd.DataFrame,
                          bot5_df: pd.DataFrame, synth_perf: dict,
                          synth_qual: dict, vp: list) -> None:

    min_date = var_df["Date precedente"].min() if not var_df.empty else "?"
    max_date = var_df["Date actuelle"].max()   if not var_df.empty else "?"

    # Bouton Masquer/Afficher
    if "show_synth" not in st.session_state:
        st.session_state.show_synth = False

    btn_label = "▼ Masquer les détails" if st.session_state.show_synth else "▶ Voir plus de détails"
    if st.button(btn_label, key="btn_synth"):
        st.session_state.show_synth = not st.session_state.show_synth
        st.rerun()

    if st.session_state.show_synth:
        st.markdown(
            f'<div class="stl s">Synthèse d\'évolution Performance entre {min_date} et {max_date}</div>',
            unsafe_allow_html=True,
        )
        if synth_perf and any(any(v.get("diff", "—") != "—" for v in d.values()) for d in synth_perf.values()):
            st.markdown(html_synthese_table(synth_perf, QK, vp), unsafe_allow_html=True)
        else:
            st.markdown('<div class="es">Pas assez de donnees historiques pour calculer la synthese Performance. Au moins 2 periodes sont necessaires.</div>', unsafe_allow_html=True)

        st.markdown(
            f'<div class="stl s">Synthèse d\'évolution Qualité entre {min_date} et {max_date}</div>',
            unsafe_allow_html=True,
        )
        if synth_qual and any(any(v.get("diff", "—") != "—" for v in d.values()) for d in synth_qual.values()):
            st.markdown(html_synthese_table(synth_qual, PK, vp), unsafe_allow_html=True)
        else:
            st.markdown('<div class="es">Pas assez de donnees historiques pour calculer la synthese Qualite. Au moins 2 periodes sont necessaires.</div>', unsafe_allow_html=True)

    st.markdown("---")

    # Tableau sparklines
    st.markdown('<div class="stl s">Suivi Sparklines par Poste de Travail</div>', unsafe_allow_html=True)

    if not hist_df.empty and "Poste de travail" in hist_df.columns:
        valid_postes = sorted([p for p in vp if p in hist_df["Poste de travail"].unique()])
        perf_df_h = hist_df[(hist_df["_section"] == "perf") & (hist_df["Poste de travail"].isin(valid_postes))]
        qual_df_h = hist_df[(hist_df["_section"] == "qual") & (hist_df["Poste de travail"].isin(valid_postes))]

        h = '<table class="tw st"><thead><tr>'
        h += '<th>Poste de travail</th><th>Sparkline Performance</th><th>Comparaison Performance</th>'
        h += '<th>Sparkline Qualité</th><th>Comparaison Qualité</th>'
        h += '</tr></thead><tbody>'

        for poste in valid_postes:
            p_data   = perf_df_h[perf_df_h["Poste de travail"] == poste].sort_values("Date_parsed")
            q_data   = qual_df_h[qual_df_h["Poste de travail"] == poste].sort_values("Date_parsed")
            p_scores = p_data["Score Performance"].astype(float).tolist() if "Score Performance" in p_data.columns else []
            q_scores = q_data["Score Qualite"].astype(float).tolist()     if "Score Qualite"     in q_data.columns else []

            h += f'<tr><td style="font-weight:700">{poste}</td>'
            h += f'<td class="spark-cell">{get_sparkline_html(p_scores)}</td>'
            h += f'<td class="spark-cell">{get_comparison_html(p_scores)}</td>'
            h += f'<td class="spark-cell">{get_sparkline_html(q_scores)}</td>'
            h += f'<td class="spark-cell">{get_comparison_html(q_scores)}</td>'
            h += '</tr>'

        h += '</tbody></table>'
        st.markdown(h, unsafe_allow_html=True)
    else:
        st.markdown('<div class="es">Pas assez de données historiques pour générer les sparklines.</div>', unsafe_allow_html=True)

    st.markdown("---")

    # Journal
    st.markdown('<div class="stl s">Journal des variations significatives</div>', unsafe_allow_html=True)
    if not journal_df.empty:
        st.dataframe(
            journal_df[["Date precedente", "Date actuelle", "Poste", "Type",
                         "KPI", "Valeur precedente", "Valeur actuelle", "Ecart %", "Sens"]]
            .reset_index(drop=True),
            use_container_width=True, height=400,
        )
    else:
        st.markdown('<div class="es">Aucune variation significative detectee (ecart >= 5%% entre deux periodes)</div>', unsafe_allow_html=True)

    if not top5_df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="stl p">Top 5 Postes — Amelioration</div>', unsafe_allow_html=True)
            st.dataframe(top5_df, use_container_width=True)
        with c2:
            st.markdown('<div class="stl a">Bottom 5 Postes — Degradation</div>', unsafe_allow_html=True)
            st.dataframe(bot5_df, use_container_width=True)
