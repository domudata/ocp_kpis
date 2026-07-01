# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show_pie_pair(piv_df, title_prefix):
    global_counts = piv_df[["CRÉÉ","LANC","CLOT","TCLO"]].sum(); global_counts = global_counts[global_counts > 0]
    realised = global_counts.get("CLOT", 0) + global_counts.get("TCLO", 0); not_realised = global_counts.sum() - realised
    if global_counts.empty: st.markdown('<div class="es">Aucune donnee</div>', unsafe_allow_html=True); return
    colors = ["#8b5cf6", "#f59e0b", "#10b981", "#3b82f6"]
    fig = make_subplots(rows=1, cols=2, specs=[[{"type":"domain"},{"type":"domain"}]], subplot_titles=(f"{title_prefix} — Par Statut OT", f"{title_prefix} — Réalisés vs Non Réalisés"))
    fig.add_trace(go.Pie(labels=global_counts.index, values=global_counts.values, hole=0.4, textinfo='percent+label', texttemplate='%{label}<br>%{percent:.1%}<br>(%{value})', textposition='inside', insidetextorientation='radial', textfont=dict(size=14, color='white', family='Inter, sans-serif'), marker=dict(colors=colors, line=dict(color='#FFFFFF', width=3))), 1, 1)
    pie2_data = pd.Series([realised, not_realised], index=["Réalisés (CLOT+TCLO)", "Non Réalisés"])
    fig.add_trace(go.Pie(labels=pie2_data.index, values=pie2_data.values, hole=0.5, textinfo='percent+label', texttemplate='%{label}<br>%{percent:.1%}<br>(%{value})', textposition='inside', insidetextorientation='radial', textfont=dict(size=14, color='white', family='Inter, sans-serif'), marker=dict(colors=["#10b981", "#8b5cf6"], line=dict(color='#FFFFFF', width=3))), 1, 2)
    fig.update_layout(margin=dict(t=80, b=20, l=20, r=20), height=450, legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0.5, xanchor="center"))
    st.plotly_chart(fig, use_container_width=True)

def show_simple_pie(piv_df, title, keep_non_carac=False):
    if not keep_non_carac and "NON CARACTERISE" in piv_df.columns: piv_df = piv_df.drop(columns=["NON CARACTERISE"])
    counts = piv_df.sum(); counts = counts[counts > 0]
    if counts.empty: st.markdown('<div class="es">Aucune donnee</div>', unsafe_allow_html=True); return
    color_map = {"CARACTERISE": "#10b981", "NON CARACTERISE": "#f97316"}
    type_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#14b8a6', '#6366f1', '#0ea5e9', '#d946ef', '#a855f7']
    colors = []; palette_idx = 0
    for c in counts.index:
        c_str = str(c)
        if c_str in color_map: colors.append(color_map[c_str])
        else: colors.append(type_palette[palette_idx % len(type_palette)]); palette_idx += 1
    total_sum = counts.sum(); pull_list = [0.05 if (v/total_sum)*100 < 10 else 0 for v in counts.values]
    fig = go.Figure(go.Pie(labels=counts.index, values=counts.values, hole=0.4, sort=False, textinfo="percent", textposition="outside", pull=pull_list, marker=dict(colors=colors, line=dict(color="white", width=2))))
    fig.update_traces(hovertemplate="<b>%{label}</b><br>Nombre : %{value}<br>Pourcentage : %{percent}<extra></extra>", textfont=dict(size=13, family='Inter, sans-serif'))
    fig.update_layout(title=dict(text=title, x=0.5, xanchor='center', font=dict(size=16)), height=500, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.15, x=0.5, xanchor="center"), margin=dict(t=80, b=80, l=40, r=40))
    st.plotly_chart(fig, use_container_width=True)
