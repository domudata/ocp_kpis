# -*- coding: utf-8 -*-
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# Seuil (en %) sous lequel un secteur est considere "mince"
# et regroupe dans "Autres" (detaille dans le 2e camembert)
# Desactiver zoom / pan / barre d outils sur tous les charts
PLOTLY_CONFIG = {
    "staticPlot": False,
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showAxisDragHandles": False,
}

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
            texttemplate="%{label}<br>%{percent:.1%} (%{value})",
            textposition="outside",
            marker=dict(colors=_colors_for(counts.index), line=dict(color="white", width=2)),
        ))
        fig.update_traces(
            hovertemplate="<b>%{label}</b><br>Nombre : %{value}<br>Pourcentage : %{percent}<extra></extra>",
            textfont=dict(size=13, family='Inter, sans-serif'),
        )
        fig.update_layout(
            title=dict(text=title, x=0.5, xanchor='center', font=dict(size=14), y=0.98, yanchor='top'),
            height=450, showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0.5, xanchor="center"),
            margin=dict(t=60, b=70, l=40, r=40),
        )
        # Reduire le domaine du pie pour laisser la place au titre en haut
        fig.update_traces(domain=dict(y=[0.0, 0.85]))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        return

    # ── Pie of pie : principal (grands + "Autres") | detail des minces ──
    main_counts = pd.concat([big, pd.Series({f"Autres ({len(small)})": small.sum()})])

    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "domain"}, {"type": "domain"}]],
        column_widths=[0.60, 0.40],
        subplot_titles=("Répartition principale", f"Détail « Autres » ({small.sum():.0f} OT)"),
        vertical_spacing=0.0,
    )
    # Abaisser les sous-titres pour les separer du titre principal
    for ann in fig.layout.annotations:
        ann.y = 0.90
        ann.font.size = 11
        ann.font.color = "#64748B"

    # Camembert principal ("Autres" en gris) — domaine reduit vers le bas
    main_colors = _colors_for(big.index) + ["#94a3b8"]
    fig.add_trace(go.Pie(
        labels=main_counts.index, values=main_counts.values,
        hole=0.4, sort=False,
        texttemplate="%{label}<br>%{percent:.1%} (%{value})",
        textposition="outside",
        marker=dict(colors=main_colors, line=dict(color="white", width=2)),
        legendgroup="main",
        domain=dict(y=[0.0, 0.80]),
    ), 1, 1)

    # Camembert secondaire : detail des secteurs minces
    small_colors = (TYPE_PALETTE[len(big):] + TYPE_PALETTE)[:len(small)]
    fig.add_trace(go.Pie(
        labels=small.index, values=small.values,
        hole=0.35, sort=False,
        texttemplate="%{label}<br>%{value}",
        textposition="outside",
        marker=dict(colors=small_colors, line=dict(color="white", width=2)),
        legendgroup="detail",
        domain=dict(y=[0.0, 0.80]),
    ), 1, 2)

    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Nombre : %{value}<br>Pourcentage : %{percent}<extra></extra>",
        textfont=dict(size=12, family='Inter, sans-serif'),
    )
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(size=14), y=0.99, yanchor='top'),
        height=470, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0.5, xanchor="center"),
        margin=dict(t=75, b=70, l=30, r=30),
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


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
    # Abaisser les sous-titres pour bien les separer des camemberts
    for ann in fig.layout.annotations:
        ann.y = 0.93
        ann.font.size = 12
        ann.font.color = "#334155"

    # Style unifie avec show_simple_pie : hole 0.4, labels exterieurs,
    # bord blanc fin, hover normalise — domaine reduit vers le bas
    fig.add_trace(go.Pie(
        labels=global_counts.index, values=global_counts.values,
        hole=0.4, sort=False,
        texttemplate="%{label}<br>%{percent:.1%} (%{value})",
        textposition="outside",
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        domain=dict(y=[0.0, 0.82]),
    ), 1, 1)

    pie2 = pd.Series(
        [realised, not_realised],
        index=["Réalisés (CLOT+TCLO)", "Non Réalisés"],
    )
    fig.add_trace(go.Pie(
        labels=pie2.index, values=pie2.values,
        hole=0.4, sort=False,
        texttemplate="%{label}<br>%{percent:.1%} (%{value})",
        textposition="outside",
        marker=dict(colors=["#10b981", "#ef4444"], line=dict(color="white", width=2)),
        domain=dict(y=[0.0, 0.82]),
    ), 1, 2)

    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Nombre : %{value}<br>Pourcentage : %{percent}<extra></extra>",
        textfont=dict(size=12, family='Inter, sans-serif'),
    )
    fig.update_layout(
        height=470, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.10, x=0.5, xanchor="center"),
        margin=dict(t=45, b=70, l=40, r=40),
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


# ═══════════════════════════════════════════════════════════════════════════
# BARRES HORIZONTALES AVEC SEUILS (style rapport OCP SAP PM)
# Rose < seuil1 | Orange >= seuil1 | Vert >= seuil2
# ═══════════════════════════════════════════════════════════════════════════
S1_DEFAULT, S2_DEFAULT = 70, 90
# Couleurs identiques aux cellules Total des tableaux :
# rouge < s1 | jaune s1-s2 | vert >= s2
C_LOW, C_MID, C_HIGH = "#ef4444", "#f59e0b", "#10b981"


def _bar_color_for(label, value, cible_map=None, lower_set=None, s1=S1_DEFAULT, s2=S2_DEFAULT):
    """
    Couleur d'une barre cohérente avec le coloriage des cellules du tableau :
    - Si `label` est un KPI connu (present dans cible_map) : utilise sa VRAIE
      cible et son sens (LOWER_BETTER ou non), comme dans components/tables.py.
    - Sinon (ex: nom de poste, score) : utilise les seuils generiques s1/s2.
    """
    try:
        v = float(value)
    except (ValueError, TypeError):
        return C_LOW

    if cible_map and label in cible_map:
        target = cible_map[label]
        is_lower = bool(lower_set) and label in lower_set
        if is_lower:
            # Plus bas = mieux (ex: >3 mois cible <=5%, 1-3 mois cible <=15%)
            return C_HIGH if v <= target else C_LOW
        else:
            # Plus haut = mieux (ex: <1 mois cible >=80%)
            if v >= target:
                return C_HIGH
            return C_MID if v >= target * 0.9 else C_LOW

    # Pas de cible connue (score global, poste...) → seuils generiques
    return C_HIGH if v >= s2 else (C_MID if v >= s1 else C_LOW)


def show_hbar_thresholds(labels, values, title, s1=S1_DEFAULT, s2=S2_DEFAULT,
                          suffix="%", cible_map=None, lower_set=None) -> None:
    """
    Barres horizontales par element avec 2 lignes de seuil pointillees
    (s1 orange, s2 vert) — meme presentation que le rapport SAP PM OCP.

    Si `cible_map` (ex: core.constants.CIBLE) et `lower_set` (ex: LOWER_BETTER)
    sont fournis, la couleur de CHAQUE barre suit sa propre cible (coherent
    avec le coloriage des cellules du tableau KPI), au lieu des seuils
    generiques s1/s2 appliques uniformement.
    """
    if len(labels) == 0:
        st.markdown('<div class="es">Aucune donnee</div>', unsafe_allow_html=True)
        return

    colors = [
        _bar_color_for(lbl, v, cible_map, lower_set, s1, s2)
        for lbl, v in zip(labels, values)
    ]

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation='h',
        marker=dict(color=colors, line=dict(color='white', width=1)),
        text=[f"{v:.0f}{suffix}" for v in values],
        textposition='outside',
        textfont=dict(size=13, family='Inter, sans-serif', color='#1e293b'),
        hovertemplate="<b>%{y}</b><br>%{x:.1f}" + suffix + "<extra></extra>",
    ))

    # Lignes de seuil pointillees + marqueurs (reperes visuels génériques)
    fig.add_vline(x=s1, line_dash="dash", line_color=C_MID, line_width=2)
    fig.add_vline(x=s2, line_dash="dash", line_color=C_HIGH, line_width=2)
    fig.add_annotation(x=s1, y=1.04, yref="paper", text=f"▼ {s1}{suffix}",
                       showarrow=False, font=dict(color=C_MID, size=14, family='Inter'))
    fig.add_annotation(x=s2, y=1.04, yref="paper", text=f"▼ {s2}{suffix}",
                       showarrow=False, font=dict(color=C_HIGH, size=14, family='Inter'))

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(size=16, color='#1e293b')),
        height=max(300, 40 * len(labels) + 120),
        xaxis=dict(range=[0, 115], showgrid=False, showticklabels=False, zeroline=False, fixedrange=True),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12, family='Inter', color='#1e293b'), fixedrange=True, automargin=True),
        plot_bgcolor='white', paper_bgcolor='white',
        margin=dict(t=90, b=20, l=20, r=50),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


def show_statut_hbar(piv_df: pd.DataFrame, title: str,
                      s1=S1_DEFAULT, s2=S2_DEFAULT) -> None:
    """
    Taux de realisation (CLOT+TCLO / total) PAR POSTE de travail,
    en barres horizontales avec seuils — remplace les camemberts globaux.
    """
    for c in ["CRÉÉ", "LANC", "CLOT", "TCLO"]:
        if c not in piv_df.columns:
            piv_df[c] = 0
    tot = piv_df[["CRÉÉ", "LANC", "CLOT", "TCLO"]].sum(axis=1)
    rea = piv_df["CLOT"] + piv_df["TCLO"]

    mask = tot > 0
    taux = (rea[mask] / tot[mask] * 100).round(1).sort_values(ascending=False)

    if taux.empty:
        st.markdown('<div class="es">Aucune donnee</div>', unsafe_allow_html=True)
        return

    show_hbar_thresholds(taux.index.tolist(), taux.values.tolist(),
                         f"{title} — Taux de réalisation par poste", s1, s2)


def show_grouped_hbar(vp, pscores: dict, qscores: dict, title: str,
                       s1=S1_DEFAULT, s2=S2_DEFAULT) -> None:
    """
    Comparaison Performance / Qualite PAR POSTE en barres horizontales
    groupees, avec lignes de seuil s1/s2 (style rapport OCP).
    """
    postes = [p for p in vp if p in pscores or p in qscores]
    if not postes:
        st.markdown('<div class="es">Aucune donnee</div>', unsafe_allow_html=True)
        return

    p_vals = [round(pscores.get(p, 0), 1) for p in postes]
    q_vals = [round(qscores.get(p, 0), 1) for p in postes]

    def _score_colors(vals):
        return [C_HIGH if v >= s2 else (C_MID if v >= s1 else C_LOW) for v in vals]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=p_vals, y=postes, orientation='h', name='Performance',
        marker=dict(color=_score_colors(p_vals), line=dict(color='white', width=1)),
        text=[f"{v:.0f}%" for v in p_vals], textposition='outside',
        textfont=dict(size=11, family='Inter'),
        hovertemplate="<b>%{y}</b><br>Performance : %{x:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=q_vals, y=postes, orientation='h', name='Qualité',
        marker=dict(color=_score_colors(q_vals), line=dict(color='white', width=1),
                    pattern=dict(shape="/", size=4, solidity=0.35)),
        text=[f"{v:.0f}%" for v in q_vals], textposition='outside',
        textfont=dict(size=11, family='Inter'),
        hovertemplate="<b>%{y}</b><br>Qualité : %{x:.1f}%<extra></extra>",
    ))

    fig.add_vline(x=s1, line_dash="dash", line_color=C_MID, line_width=2)
    fig.add_vline(x=s2, line_dash="dash", line_color=C_HIGH, line_width=2)
    fig.add_annotation(x=s1, y=1.03, yref="paper", text=f"▼ {s1}%",
                       showarrow=False, font=dict(color=C_MID, size=14, family='Inter'))
    fig.add_annotation(x=s2, y=1.03, yref="paper", text=f"▼ {s2}%",
                       showarrow=False, font=dict(color=C_HIGH, size=14, family='Inter'))

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(size=16, color='#1e293b')),
        barmode='group', bargap=0.25, bargroupgap=0.08,
        height=max(350, 52 * len(postes) + 130),
        xaxis=dict(range=[0, 115], showgrid=False, showticklabels=False, zeroline=False, fixedrange=True),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12, family='Inter', color='#1e293b'), fixedrange=True, automargin=True),
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation="h", yanchor="bottom", y=-0.08, x=0.5, xanchor="center"),
        margin=dict(t=90, b=60, l=20, r=50),
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


def show_scores_hbar(vp, scores: dict, title, s1=S1_DEFAULT, s2=S2_DEFAULT):
    """
    Barres horizontales des scores PAR POSTE (une seule serie),
    colorees selon le score (rouge/jaune/vert). Pour afficher
    Performance et Qualite separement cote a cote.
    """
    postes = [p for p in vp if p in scores]
    if not postes:
        st.markdown('<div class="es">Aucune donnee</div>', unsafe_allow_html=True)
        return
    vals = [round(scores.get(p, 0), 1) for p in postes]
    show_hbar_thresholds(postes, vals, title, s1, s2)
