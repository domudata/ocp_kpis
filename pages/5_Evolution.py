# -*- coding: utf-8 -*-
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="Évolution",
    page_icon="📉",
    initial_sidebar_state="expanded"
)

from components.styles import inject_custom_css
from components.tables import render_anomaly_table
from core.historique import calculate_variations, generate_journal, calculate_rankings

inject_custom_css()


def _sens_color(sens):
    if sens == "Amelioration":
        return "background:#d1fae5;color:#065f46;font-weight:700"
    elif sens == "Degradation":
        return "background:#fee2e2;color:#991b1b;font-weight:700"
    return "background:#f8fafc;color:#64748b"


def _show_score_evolution(hist_df, selected_posts):
    import plotly.graph_objects as go

    perf_scores, qual_scores, dates = [], [], []
    for date_val in sorted(hist_df["Date"].unique()):
        date_data = hist_df[(hist_df["Date"] == date_val) &
                            (hist_df["Poste de travail"].isin(selected_posts))]
        perf_rows = date_data[date_data["_section"] == "perf"]
        qual_rows = date_data[date_data["_section"] == "qual"]

        try:
            perf_scores.append(float(perf_rows["Score Performance"].mean()))
        except Exception:
            perf_scores.append(None)
        try:
            qual_scores.append(float(qual_rows["Score Qualite"].mean()))
        except Exception:
            qual_scores.append(None)
        dates.append(date_val)

    if not dates:
        st.markdown('<div class="es">Aucune donnée</div>', unsafe_allow_html=True)
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=perf_scores, name="Performance",
                             line=dict(color="#10b981", width=3), mode='lines+markers'))
    fig.add_trace(go.Scatter(x=dates, y=qual_scores, name="Qualité",
                             line=dict(color="#3b82f6", width=3), mode='lines+markers'))
    fig.add_hline(y=100, line_dash="dash", line_color="#1e3a5f",
                  annotation_text="Cible 100%")
    fig.update_layout(height=400, yaxis=dict(title="Score (%)", range=[0, 110]),
                      legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"))
    st.plotly_chart(fig, use_container_width=True)


def render(hist_df, selected_posts):
    if hist_df.empty:
        st.markdown('<div class="es">⚠️ Aucun historique disponible.</div>', unsafe_allow_html=True)
        return

    var_df = calculate_variations(hist_df)
    if var_df.empty:
        st.markdown('<div class="es">Pas assez de périodes.</div>', unsafe_allow_html=True)
        return

    st.markdown('<div class="stl">JOURNAL DES VARIATIONS (|écart| ≥ 5%)</div>', unsafe_allow_html=True)
    journal = generate_journal(var_df)
    journal = journal[journal["Poste"].isin(selected_posts)]

    if not journal.empty:
        h = '<table class="tw"><thead><tr>'
        for c in journal.columns:
            if c != "Significatif":
                h += '<th>%s</th>' % c
        h += '</tr></thead><tbody>'
        for _, row in journal.iterrows():
            h += '<tr>'
            for c in journal.columns:
                if c == "Significatif":
                    continue
                val = row[c]
                if c == "Sens":
                    h += '<td style="text-align:center;%s">%s</td>' % (_sens_color(val), val)
                elif c == "Poste":
                    h += '<td class="poste-cell">%s</td>' % val
                else:
                    h += '<td style="text-align:center">%s</td>' % val
            h += '</tr>'
        h += '</tbody></table>'
        st.markdown(h, unsafe_allow_html=True)
    else:
        st.markdown('<div class="es">✅ Aucune variation significative</div>', unsafe_allow_html=True)

    st.markdown('<div class="stl">CLASSEMENT DES POSTES</div>', unsafe_allow_html=True)
    var_filtered = var_df[var_df["Poste"].isin(selected_posts)]
    top_amel, top_degrad = calculate_rankings(var_filtered)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🏆 Top 5 Amélioration**")
        if not top_amel.empty:
            h = '<table class="tw pt"><thead><tr><th>Poste</th><th>Score</th></tr></thead><tbody>'
            for _, row in top_amel.iterrows():
                h += '<tr><td class="poste-cell">%s</td><td style="text-align:center;font-weight:700;color:#059669">%.1f</td></tr>' % (row["Poste"], row["Score variation"])
            h += '</tbody></table>'
            st.markdown(h, unsafe_allow_html=True)

    with col2:
        st.markdown("**⚠️ Top 5 Dégradation**")
        if not top_degrad.empty:
            h = '<table class="tw at"><thead><tr><th>Poste</th><th>Score</th></tr></thead><tbody>'
            for _, row in top_degrad.iterrows():
                h += '<tr><td class="poste-cell">%s</td><td style="text-align:center;font-weight:700;color:#dc2626">%.1f</td></tr>' % (row["Poste"], row["Score variation"])
            h += '</tbody></table>'
            st.markdown(h, unsafe_allow_html=True)

    st.markdown('<div class="stl">ÉVOLUTION DES SCORES GLOBAUX</div>', unsafe_allow_html=True)
    _show_score_evolution(hist_df, selected_posts)


if "kpi_data" not in st.session_state:
    st.warning("⚠️ Veuillez d'abord charger les fichiers depuis la page d'accueil.")
    st.stop()

render(
    st.session_state.get("hist_df"),
    st.session_state.get("selected_posts", [])
)
