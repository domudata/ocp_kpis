# -*- coding: utf-8 -*-
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# Seuil (en %) sous lequel un secteur est considere "mince"
# et regroupe dans "Autres" (detaille dans le 2e camembert)
SMALL_SLICE_PCT = 8.0

COLOR_MAP = {"CARACTERISE": "#10b981", "NON CARACTERISE": "#f97316"}
TYPE_PALETTE = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4',
                '#14b8a6', '#6366f1', '#0ea5e9', '#d946ef', '#a855f7']


def _colors_for(labels):
    colors, idx = [], 0
    for c in labels:
        if str(c) in COLOR_MAP:
            colors.append(COLOR_MAP[str(c)])
        else:
            colors.append(TYPE_PALETTE[idx % len(TYPE_PALETTE)])
            idx += 1
    return colors


def show_simple_pie(piv_df: pd.DataFrame, title: str, keep_non_carac: bool = False) -> None:
    """
    Camembert clair avec technique "pie of pie" :
    - les secteurs >= SMALL_SLICE_PCT restent sur le camembert principal
    - les secteurs minces (< SMALL_SLICE_PCT) sont regroupes en "Autres"
      et detailles dans un second camembert a droite
    """
    if not keep_non_carac and "NON CARACTERISE" in piv_df.columns:
        piv_df = piv_df.drop(columns=["NON CARACTERISE"])

    counts = piv_df.sum()
    counts = counts[counts > 0].sort_values(ascending=False)

    if counts.empty:
        st.markdown('<div class="es">Aucune donnee</div>', unsafe_allow_html=True)
        return

    total = counts.sum()
    pcts  = counts / total * 100

    big   = counts[pcts >= SMALL_SLICE_PCT]
    small = counts[pcts <  SMALL_SLICE_PCT]

    # ── Cas simple : pas assez de secteurs minces → camembert unique ──
    if len(small) < 2:
        fig = go.Figure(go.Pie(
            labels=counts.index, values=counts.values,
            hole=0.4, sort=False,
            textinfo="label+percent+value",
            texttemplate="%{label}<br>%{percent:.1%} (%{value})",
            textposition="outside",
            marker=dict(colors=_colors_for(counts.index), line=dict(color="white", width=2)),
        ))
        fig.update_traces(
            hovertemplate="<b>%{label}</b><br>Nombre : %{value}<br>Pourcentage : %{percent}<extra></extra>",
            textfont=dict(size=13, family='Inter, sans-serif'),
        )
        fig.update_layout(
            title=dict(text=title, x=0.5, xanchor='center', font=dict(size=16)),
            height=480, showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, x=0.5, xanchor="center"),
            margin=dict(t=80, b=80, l=40, r=40),
        )
        st.plotly_chart(fig, use_container_width=True)
        return

    # ── Pie of pie : principal (grands + "Autres") | detail des minces ──
    main_counts = pd.concat([big, pd.Series({f"Autres ({len(small)})": small.sum()})])

    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "domain"}, {"type": "domain"}]],
        column_widths=[0.60, 0.40],
        subplot_titles=("Répartition principale", f"Détail « Autres » ({small.sum():.0f} OT)"),
    )

    # Camembert principal
    main_colors = _colors_for(big.index) + ["#94a3b8"]   # "Autres" en gris
    fig.add_trace(go.Pie(
        labels=main_counts.index, values=main_counts.values,
        hole=0.4, sort=False,
        textinfo="label+percent",
        texttemplate="%{label}<br>%{percent:.1%} (%{value})",
        textposition="outside",
        marker=dict(colors=main_colors, line=dict(color="white", width=2)),
        domain=dict(x=[0.0, 0.55]),
        legendgroup="main",
    ), 1, 1)

    # Camembert secondaire : detail des secteurs minces
    small_colors = TYPE_PALETTE[len(big) % len(TYPE_PALETTE):] + TYPE_PALETTE
    fig.add_trace(go.Pie(
        labels=small.index, values=small.values,
        hole=0.35, sort=False,
        textinfo="label+percent",
        texttemplate="%{label}<br>%{value}",
        textposition="outside",
        marker=dict(colors=small_colors[:len(small)], line=dict(color="white", width=2)),
        domain=dict(x=[0.68, 1.0]),
        legendgroup="detail",
    ), 1, 2)

    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Nombre : %{value}<br>Pourcentage : %{percent}<extra></extra>",
        textfont=dict(size=12, family='Inter, sans-serif'),
    )
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(size=16)),
        height=500, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, x=0.5, xanchor="center"),
        margin=dict(t=90, b=90, l=30, r=30),
    )
    st.plotly_chart(fig, use_container_width=True)


def show_pie_pair(piv_df: pd.DataFrame, title_prefix: str) -> None:
    """2 camemberts : par statut OT | realises vs non realises."""
    global_counts = piv_df[["CRÉÉ", "LANC", "CLOT", "TCLO"]].sum()
    global_counts = global_counts[global_counts > 0]
    realised     = global_counts.get("CLOT", 0) + global_counts.get("TCLO", 0)
    not_realised = global_counts.sum() - realised

    if global_counts.empty:
        st.markdown('<div class="es">Aucune donnee</div>', unsafe_allow_html=True)
        return

    colors = ["#8b5cf6", "#f59e0b", "#10b981", "#3b82f6"]
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "domain"}, {"type": "domain"}]],
        subplot_titles=(
            f"{title_prefix} — Par Statut OT",
            f"{title_prefix} — Réalisés vs Non Réalisés",
        ),
    )

    fig.add_trace(go.Pie(
        labels=global_counts.index, values=global_counts.values, hole=0.4,
        textinfo='percent+label',
        texttemplate='%{label}<br>%{percent:.1%}<br>(%{value})',
        textposition='inside', insidetextorientation='radial',
        textfont=dict(size=14, color='white', family='Inter, sans-serif'),
        marker=dict(colors=colors, line=dict(color='#FFFFFF', width=3)),
    ), 1, 1)

    pie2 = pd.Series(
        [realised, not_realised],
        index=["Réalisés (CLOT+TCLO)", "Non Réalisés"],
    )
    fig.add_trace(go.Pie(
        labels=pie2.index, values=pie2.values, hole=0.5,
        textinfo='percent+label',
        texttemplate='%{label}<br>%{percent:.1%}<br>(%{value})',
        textposition='inside', insidetextorientation='radial',
        textfont=dict(size=14, color='white', family='Inter, sans-serif'),
        marker=dict(colors=["#10b981", "#8b5cf6"], line=dict(color='#FFFFFF', width=3)),
    ), 1, 2)

    fig.update_layout(
        margin=dict(t=80, b=20, l=20, r=20), height=450,
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0.5, xanchor="center"),
    )
    st.plotly_chart(fig, use_container_width=True)
