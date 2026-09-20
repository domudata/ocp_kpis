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
        st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)
        return

    total = counts.sum()
    pcts = counts / total * 100

    big = counts[pcts >= SMALL_SLICE_PCT]
    small = counts[pcts < SMALL_SLICE_PCT]

    # ── Cas simple : pas assez de secteurs minces → camembert unique ──
    if len(small) < 2:
        fig = go.Figure(go.Pie(
            labels=counts.index, values=counts.values,
            hole=0.4, sort=False,
            texttemplate="%{label} %{percent:.1%} (%{value})",
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
            # CORRIGÉ : masque proprement les labels qui ne rentrent pas
            # (tranches minuscules) au lieu de les laisser se chevaucher.
            uniformtext_minsize=9, uniformtext_mode='hide',
        )
        # Reduire le domaine du pie pour laisser la place au titre en haut
        fig.update_traces(domain=dict(y=[0.0, 0.82]))
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
        ann.y = 0.95
        ann.font.size = 11
        ann.font.color = "#64748B"

    # Camembert principal ("Autres" en gris) — domaine reduit vers le bas
    main_colors = _colors_for(big.index) + ["#94a3b8"]
    fig.add_trace(go.Pie(
        labels=main_counts.index, values=main_counts.values,
        hole=0.4, sort=False,
        texttemplate="%{label} %{percent:.1%} (%{value})",
        textposition="outside",
        marker=dict(colors=main_colors, line=dict(color="white", width=2)),
        legendgroup="main",
        domain=dict(y=[0.0, 0.76]),
    ), 1, 1)

    # Camembert secondaire : detail des secteurs minces
    small_colors = (TYPE_PALETTE[len(big):] + TYPE_PALETTE)[:len(small)]
    fig.add_trace(go.Pie(
        labels=small.index, values=small.values,
        hole=0.35, sort=False,
        texttemplate="%{label} %{value}",
        textposition="outside",
        marker=dict(colors=small_colors, line=dict(color="white", width=2)),
        legendgroup="detail",
        domain=dict(y=[0.0, 0.76]),
    ), 1, 2)

    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Nombre : %{value}<br>Pourcentage : %{percent}<extra></extra>",
        textfont=dict(size=12, family='Inter, sans-serif'),
    )
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(size=14), y=0.99, yanchor='top'),
        height=470, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0.5, xanchor="center"),
        margin=dict(t=80, b=70, l=30, r=30),
        # CORRIGÉ : masque proprement les labels qui ne rentrent pas.
        uniformtext_minsize=9, uniformtext_mode='hide',
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

def show_pie_pair(piv_df: pd.DataFrame, title_prefix: str) -> None:
    """2 camemberts : par statut OT | realises vs non realises."""
    global_counts = piv_df[["CRÉÉ", "LANC", "CLOT", "TCLO"]].sum()
    global_counts = global_counts[global_counts > 0]
    realised = global_counts.get("CLOT", 0) + global_counts.get("TCLO", 0)
    not_realised = global_counts.sum() - realised

    if global_counts.empty:
        st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)
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
    # CORRIGÉ : sous-titres remontés (y=0.97 au lieu de 0.93) ET domaine
    # des camemberts réduit (0.72 au lieu de 0.82) pour créer un vrai
    # espace tampon entre le titre et les labels "outside" des tranches
    # minuscules (ex: CRÉÉ à 0.1%, LANC à 1.6%), qui remontaient jusque
    # dans la zone du titre et se chevauchaient avec lui.
    for ann in fig.layout.annotations:
        ann.y = 0.97
        ann.font.size = 12
        ann.font.color = "#334155"

    # Style unifie avec show_simple_pie : hole 0.4, labels exterieurs,
    # bord blanc fin, hover normalise — domaine reduit vers le bas
    fig.add_trace(go.Pie(
        labels=global_counts.index, values=global_counts.values,
        hole=0.4, sort=False,
        texttemplate="%{label} %{percent:.1%} (%{value})",
        textposition="outside",
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        domain=dict(y=[0.0, 0.72]),
    ), 1, 1)

    pie2 = pd.Series(
        [realised, not_realised],
        index=["Réalisés (CLOT+TCLO)", "Non Réalisés"],
    )
    fig.add_trace(go.Pie(
        labels=pie2.index, values=pie2.values,
        hole=0.4, sort=False,
        texttemplate="%{label} %{percent:.1%} (%{value})",
        textposition="outside",
        marker=dict(colors=["#10b981", "#ef4444"], line=dict(color="white", width=2)),
        domain=dict(y=[0.0, 0.72]),
    ), 1, 2)

    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Nombre : %{value}<br>Pourcentage : %{percent}<extra></extra>",
        textfont=dict(size=12, family='Inter, sans-serif'),
    )
    fig.update_layout(
        height=500, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.10, x=0.5, xanchor="center"),
        margin=dict(t=55, b=70, l=40, r=40),
        # CORRIGÉ : c'est le fix principal — Plotly masque proprement tout
        # label qui ne rentre pas dans l'espace disponible plutôt que de
        # les laisser se superposer/chevaucher. Les tranches minuscules
        # sans label visible restent lisibles via la légende et le hover.
        uniformtext_minsize=9, uniformtext_mode='hide',
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
        st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)
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
        st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)
        return

    show_hbar_thresholds(taux.index.tolist(), taux.values.tolist(),
                          f"{title} — Taux de réalisation par poste", s1, s2)

def show_grouped_hbar(vp, pscores: dict, qscores: dict, title: str,
                       s1=S1_DEFAULT, s2=S2_DEFAULT, thin: bool = False) -> None:
    """
    Comparaison Performance / Qualite PAR POSTE en barres horizontales
    groupees, avec lignes de seuil s1/s2 (style rapport OCP).

    CORRIGÉ (retour utilisateur) : les barres précédentes, une fois
    étirées sur toute la largeur du conteneur, paraissaient trop longues
    et trop fines. Deux changements :
      - bargap/bargroupgap réduits (barres plus ÉPAISSES) ;
      - le graphique n'est plus étiré sur toute la largeur de l'écran
        (use_container_width=False, largeur fixe raisonnable), pour que
        des barres courtes restent visuellement courtes.
    """
    postes = [p for p in vp if p in pscores or p in qscores]
    if not postes:
        st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)
        return

    p_vals = [round(pscores.get(p, 0), 1) for p in postes]
    q_vals = [round(qscores.get(p, 0), 1) for p in postes]

    def _score_colors(vals):
        return [C_HIGH if v >= s2 else (C_MID if v >= s1 else C_LOW) for v in vals]

    bargap = 0.10 if thin else 0.25
    bargroupgap = 0.04 if thin else 0.08
    largeur_fixe = 780
    par_poste = 46 if thin else 52
    bar_line_w = 1

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=p_vals, y=postes, orientation='h', name='Performance',
        marker=dict(color=_score_colors(p_vals), line=dict(color='white', width=bar_line_w)),
        text=[f"{v:.0f}%" for v in p_vals], textposition='outside',
        textfont=dict(size=10 if thin else 11, family='Inter'),
        hovertemplate="<b>%{y}</b><br>Performance : %{x:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=q_vals, y=postes, orientation='h', name='Qualité',
        marker=dict(color=_score_colors(q_vals), line=dict(color='white', width=bar_line_w),
                    pattern=dict(shape="/", size=4, solidity=0.35)),
        text=[f"{v:.0f}%" for v in q_vals], textposition='outside',
        textfont=dict(size=10 if thin else 11, family='Inter'),
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
        barmode='group', bargap=bargap, bargroupgap=bargroupgap,
        height=max(350, par_poste * len(postes) + 130),
        xaxis=dict(range=[0, 115], showgrid=False, showticklabels=False, zeroline=False, fixedrange=True),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12, family='Inter', color='#1e293b'), fixedrange=True, automargin=True),
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation="h", yanchor="bottom", y=-0.08, x=0.5, xanchor="center"),
        margin=dict(t=90, b=60, l=20, r=50),
        width=largeur_fixe if thin else None,
    )
    st.plotly_chart(fig, use_container_width=not thin, config=PLOTLY_CONFIG)

def show_butterfly_single_domain(postes: list, valeurs_prec: list, valeurs_act: list,
                                  titre: str, label_prec: str, label_act: str,
                                  couleur_prec: str, couleur_act: str) -> None:
    """AJOUTÉ (demande explicite) : graphique papillon pour UN SEUL
    domaine (Performance OU Qualité), destiné à être affiché à côté de
    l'autre domaine (2 graphiques séparés, l'un à côté de l'autre) au
    lieu de les fusionner sur un même graphique."""
    if not postes:
        st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=postes, x=[-v for v in valeurs_prec], orientation='h',
        name=label_prec, marker=dict(color=couleur_prec, line=dict(color='white', width=0.5)),
        text=[f"{v:.0f}%" for v in valeurs_prec], textposition='outside',
        textfont=dict(size=12, family='Inter', color='black'),
        hovertemplate="<b>%{y}</b><br>" + label_prec + " : %{customdata:.1f}%<extra></extra>",
        customdata=valeurs_prec,
    ))
    fig.add_trace(go.Bar(
        y=postes, x=valeurs_act, orientation='h',
        name=label_act, marker=dict(color=couleur_act, line=dict(color='white', width=0.5)),
        text=[f"{v:.0f}%" for v in valeurs_act], textposition='outside',
        textfont=dict(size=12, family='Inter', color='black'),
        hovertemplate="<b>%{y}</b><br>" + label_act + " : %{x:.1f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#1e293b", line_width=1.5)

    fig.update_layout(
        title=dict(text=titre, x=0.5, xanchor='center', font=dict(size=14, color='#1e293b')),
        barmode='overlay', bargap=0.18,
        height=max(350, 42 * len(postes) + 120),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False, fixedrange=True,
                   range=[-115, 115]),
        yaxis=dict(autorange="reversed", tickfont=dict(size=11, family='Inter', color='#1e293b'),
                   fixedrange=True, automargin=True),
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation="h", yanchor="bottom", y=-0.10, x=0.5, xanchor="center", font=dict(size=10)),
        margin=dict(t=50, b=50, l=20, r=20),
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


def show_butterfly_comparison(postes: list,
                               perf_prec: list, perf_act: list,
                               qual_prec: list, qual_act: list,
                               titre: str, label_prec: str, label_act: str) -> None:
    """
    Graphique papillon Performance/Qualité fusionnées.
    CORRIGÉ (demande explicite) :
      - texte des pourcentages À L'EXTÉRIEUR des barres, en NOIR (retour
        en arrière sur le "inside/blanc" précédent) ;
      - barres plus ÉPAISSES (bargap réduit) ;
      - palette harmonisée par PAIRES de teintes (clair=précédente,
        foncé=actuelle) au lieu de couleurs disparates : bleu pour
        Performance, vert pour Qualité.
    """
    if not postes:
        st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=postes, x=[-v for v in perf_prec], orientation='h',
        name=f"Performance — {label_prec}", marker=dict(color="#93c5fd", line=dict(color='white', width=0.5)),
        text=[f"{v:.0f}%" for v in perf_prec], textposition='inside', insidetextanchor='start',
        textfont=dict(size=12, family='Inter', color='black'),
        hovertemplate="<b>%{y}</b><br>Performance " + label_prec + " : %{customdata:.1f}%<extra></extra>",
        customdata=perf_prec, offsetgroup="prec",
    ))
    fig.add_trace(go.Bar(
        y=postes, x=[-v for v in qual_prec], orientation='h',
        name=f"Qualité — {label_prec}", marker=dict(color="#86efac", line=dict(color='white', width=0.5)),
        text=[f"{v:.0f}%" for v in qual_prec], textposition='inside', insidetextanchor='start',
        textfont=dict(size=12, family='Inter', color='black'),
        hovertemplate="<b>%{y}</b><br>Qualité " + label_prec + " : %{customdata:.1f}%<extra></extra>",
        customdata=qual_prec, offsetgroup="prec",
    ))
    fig.add_trace(go.Bar(
        y=postes, x=perf_act, orientation='h',
        name=f"Performance — {label_act}", marker=dict(color="#1d4ed8", line=dict(color='white', width=0.5)),
        text=[f"{v:.0f}%" for v in perf_act], textposition='outside',
        textfont=dict(size=12, family='Inter', color='black'),
        hovertemplate="<b>%{y}</b><br>Performance " + label_act + " : %{x:.1f}%<extra></extra>",
        offsetgroup="act",
    ))
    fig.add_trace(go.Bar(
        y=postes, x=qual_act, orientation='h',
        name=f"Qualité — {label_act}", marker=dict(color="#15803d", line=dict(color='white', width=0.5)),
        text=[f"{v:.0f}%" for v in qual_act], textposition='outside',
        textfont=dict(size=12, family='Inter', color='black'),
        hovertemplate="<b>%{y}</b><br>Qualité " + label_act + " : %{x:.1f}%<extra></extra>",
        offsetgroup="act",
    ))
    fig.add_vline(x=0, line_color="#1e293b", line_width=1.5)

    fig.update_layout(
        title=dict(text=titre, x=0.5, xanchor='center', font=dict(size=15, color='#1e293b')),
        barmode='group', bargap=0.18, bargroupgap=0.04,
        height=max(380, 56 * len(postes) + 130),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False, fixedrange=True,
                   range=[-140, 140]),
        yaxis=dict(autorange="reversed", tickfont=dict(size=11, family='Inter', color='#1e293b'),
                   fixedrange=True, automargin=True),
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation="h", yanchor="bottom", y=-0.10, x=0.5, xanchor="center", font=dict(size=10)),
        margin=dict(t=60, b=60, l=20, r=20),
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
        st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)
        return
    vals = [round(scores.get(p, 0), 1) for p in postes]
    show_hbar_thresholds(postes, vals, title, s1, s2)


def _dessiner_barre_horizontale_semaine_division(postes_div, par_poste, detail_par_poste,
                                                   key_prefix) -> None:
    """Dessine UN graphique bar HORIZONTAL (système hebdomadaire par
    semaine calendaire, page Suivi Évolution) pour une division (SF1 ou
    SF2), avec le nombre traité affiché à l'extérieur de la barre."""
    sous = par_poste[par_poste["Poste"].isin(postes_div)] if not par_poste.empty else par_poste
    if sous.empty:
        st.markdown('<div style="padding:12px;color:#94a3b8;">Aucun poste.</div>', unsafe_allow_html=True)
        return

    sous = sous.sort_values("Anomalies semaine", ascending=False)
    postes_tries = sous["Poste"].tolist()
    anomalies = sous["Anomalies semaine"].tolist()
    traitees = sous["Anomalies traitees"].tolist()
    textes = [f"{a} ({t} traité)" if t > 0 else f"{a}" for a, t in zip(anomalies, traitees)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=postes_tries, x=anomalies, orientation='h', name="Anomalies de la semaine",
        marker=dict(color="#f97316", line=dict(color='white', width=1)),
        text=textes, textposition='outside', textfont=dict(size=12, family='Inter', color='black'),
    ))
    fig.update_layout(
        height=max(320, 38 * len(postes_tries) + 100),
        yaxis=dict(autorange="reversed", tickfont=dict(size=11, family='Inter'), fixedrange=True, automargin=True),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", fixedrange=True, title="Nombre d'anomalies"),
        plot_bgcolor='white', paper_bgcolor='white',
        margin=dict(t=20, b=40, l=20, r=60),
    )
    event = st.plotly_chart(
        fig, use_container_width=True, config=PLOTLY_CONFIG,
        on_select="rerun", selection_mode="points", key=f"{key_prefix}_chart",
    )

    points = event.selection.points if event and event.selection else []
    if points:
        poste_sel = points[0].get("y")
        detail = detail_par_poste.get(poste_sel)
        if detail is not None and not detail.empty:
            st.markdown(f"**🔍 Détail par KPI — {poste_sel}**")
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                y=detail["KPI"], x=detail["Anomalies semaine"], orientation='h',
                marker=dict(color="#f97316"),
                text=detail["Anomalies semaine"].astype(str), textposition='outside',
                textfont=dict(color='black'),
            ))
            fig2.update_layout(
                height=max(280, 36 * len(detail) + 90),
                yaxis=dict(autorange="reversed", fixedrange=True, automargin=True),
                xaxis=dict(showgrid=True, gridcolor="#F1F5F9", fixedrange=True),
                plot_bgcolor='white', paper_bgcolor='white',
                margin=dict(t=20, b=40, l=20, r=40),
            )
            st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG,
                             key=f"{key_prefix}_detail_{poste_sel}")
        else:
            st.info("Détail indisponible pour ce poste.")
    else:
        st.caption("👆 Cliquez sur une barre pour voir le détail par KPI.")


def _dessiner_suivi_anomalies(res: dict, key_prefix: str) -> None:
    """
    CORRIGÉ (demande explicite) : SÉPARÉ en 2 graphiques bar HORIZONTAUX
    côte à côte — SF1 = « Maroc Chimie » à gauche, SF2 = « FEEDS » à
    droite — au lieu d'un seul graphique vertical mélangeant les 2
    divisions. Cycle hebdomadaire : compte les anomalies de la semaine
    en cours ; au 1er jour de la semaine suivante, compare pour afficher
    combien ont été traitées durant la semaine précédente."""
    par_poste = res["par_poste"]
    if par_poste.empty:
        st.markdown(
            f'<div style="padding:12px;color:#94a3b8;">Aucune extraction enregistrée pour la '
            f'Semaine {res["num_semaine_actuelle"]} pour le moment.</div>',
            unsafe_allow_html=True,
        )
        return

    label_semaine = f"Semaine {res['num_semaine_actuelle']}"
    total_anomalies = int(par_poste["Anomalies semaine"].sum())
    total_traite = int(par_poste["Anomalies traitees"].sum())
    st.markdown(
        f'<div style="margin-bottom:6px;">'
        f'<span style="font-size:13px;color:#334155;">📅 <b>{label_semaine}</b> — '
        f'<b style="color:#f97316;">{total_anomalies}</b> anomalie(s) &nbsp;|&nbsp; '
        f'<b style="color:#10b981;">{total_traite}</b> traitée(s)</span></div>',
        unsafe_allow_html=True,
    )

    tous_postes = par_poste["Poste"].tolist()
    postes_sf1 = [p for p in tous_postes if str(p).startswith("SF1")]
    postes_sf2 = [p for p in tous_postes if str(p).startswith("SF2")]

    col_sf1, col_sf2 = st.columns(2)
    with col_sf1:
        st.markdown("**🏭 Maroc Chimie (SF1)**")
        _dessiner_barre_horizontale_semaine_division(
            postes_sf1, par_poste, res["detail_par_poste"], f"{key_prefix}_sf1",
        )
    with col_sf2:
        st.markdown("**🏭 FEEDS (SF2)**")
        _dessiner_barre_horizontale_semaine_division(
            postes_sf2, par_poste, res["detail_par_poste"], f"{key_prefix}_sf2",
        )


def _dessiner_barre_horizontale_division(postes_div, total_actuel, total_reference,
                                          reference_disponible, tous_kpi, ano_map_actuel,
                                          key_prefix) -> None:
    """Dessine UN graphique bar HORIZONTAL pour une division (SF1 ou SF2),
    avec le pourcentage traité affiché À L'EXTÉRIEUR de la barre — sauf
    si la valeur est 100% ET qu'il s'agit du mode référence (rien à
    afficher de significatif dans ce cas précis)."""
    if not postes_div:
        st.markdown('<div style="padding:12px;color:#94a3b8;">Aucun poste.</div>', unsafe_allow_html=True)
        return

    postes_tries = sorted(postes_div, key=lambda p: total_actuel.get(p, 0), reverse=True)
    valeurs = [total_actuel.get(p, 0) for p in postes_tries]

    textes = []
    for p, act in zip(postes_tries, valeurs):
        if reference_disponible:
            ref = total_reference.get(p, 0)
            if ref > 0:
                pct_traite = max(0, round((ref - act) / ref * 100))
                textes.append(f"{act} ({pct_traite}% traité)")
            else:
                textes.append(f"{act}")
        else:
            textes.append(f"{act}")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=postes_tries, x=valeurs, orientation='h', name="Anomalies (période filtrée)",
        marker=dict(color="#f97316", line=dict(color='white', width=1)),
        text=textes, textposition='outside', textfont=dict(size=12, family='Inter', color='black'),
    ))
    fig.update_layout(
        height=max(320, 38 * len(postes_tries) + 100),
        yaxis=dict(autorange="reversed", tickfont=dict(size=11, family='Inter'), fixedrange=True, automargin=True),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", fixedrange=True, title="Nombre d'anomalies"),
        plot_bgcolor='white', paper_bgcolor='white',
        margin=dict(t=20, b=40, l=20, r=60),
    )
    event = st.plotly_chart(
        fig, use_container_width=True, config=PLOTLY_CONFIG,
        on_select="rerun", selection_mode="points", key=f"{key_prefix}_chart",
    )

    points = event.selection.points if event and event.selection else []
    if points:
        poste_sel = points[0].get("y")
        st.markdown(f"**🔍 Détail par KPI — {poste_sel}**")
        detail_kpis, detail_act = [], []
        for kpi in tous_kpi:
            d = ano_map_actuel.get(kpi, {})
            nb = int(d.get(poste_sel, 0)) if hasattr(d, "get") else 0
            if nb == 0:
                continue
            detail_kpis.append(kpi)
            detail_act.append(nb)
        if detail_kpis:
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                y=detail_kpis, x=detail_act, orientation='h',
                marker=dict(color="#f97316"),
                text=[str(v) for v in detail_act], textposition='outside',
                textfont=dict(color='black'),
            ))
            fig2.update_layout(
                height=max(280, 36 * len(detail_kpis) + 90),
                yaxis=dict(autorange="reversed", fixedrange=True, automargin=True),
                xaxis=dict(showgrid=True, gridcolor="#F1F5F9", fixedrange=True),
                plot_bgcolor='white', paper_bgcolor='white',
                margin=dict(t=20, b=40, l=20, r=40),
            )
            st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG,
                             key=f"{key_prefix}_detail_{poste_sel}")
        else:
            st.info("Aucune anomalie pour ce poste sur la période sélectionnée.")
    else:
        st.caption("👆 Cliquez sur une barre pour voir le détail par KPI.")


def render_suivi_anomalies_semaine(vp: list, hist_df, now_ts, key_prefix: str,
                                    ano_map_actuel: dict = None, division: str = None) -> None:
    """
    Suivi des anomalies sous le filtre période actif (sidebar).
    CORRIGÉ (demande explicite) : si `division` est fourni ("SF1" ou
    "SF2"), un SEUL graphique bar horizontal est affiché pour cette
    division uniquement (respecte le bouton bascule Maroc Chimie/FEEDS
    de la page). Sans `division`, affiche les 2 côte à côte comme avant.
    Comparaison contre le dernier instantané historique enregistré ;
    pourcentage traité affiché à l'extérieur de la barre.
    """
    from core.constants import QK, PK

    st.markdown('<div class="stl a">🎯 Suivi des anomalies (période sélectionnée)</div>', unsafe_allow_html=True)

    if ano_map_actuel is None:
        st.markdown('<div style="padding:12px;color:#94a3b8;">Données live indisponibles.</div>',
                     unsafe_allow_html=True)
        return

    tous_kpi = list(QK) + list(PK)

    def _get(ano_map, kpi, poste):
        d = ano_map.get(kpi, {})
        return int(d.get(poste, 0)) if hasattr(d, "get") else 0

    total_actuel = {p: sum(_get(ano_map_actuel, k, p) for k in tous_kpi) for p in vp}

    reference_disponible = False
    total_reference = {}
    date_reference = None
    if hist_df is not None and not hist_df.empty and "_section" in hist_df.columns:
        sub = hist_df[hist_df["_section"].isin(["ano_perf", "ano_qual"])]
        dates_dispo = sub["Date_parsed"].dropna().sort_values().unique()
        if len(dates_dispo) >= 1:
            date_reference = pd.Timestamp(dates_dispo[-1])
            reference_disponible = True
            row_ref = sub[sub["Date_parsed"] == date_reference].set_index("Poste de travail")
            row_ref = row_ref[~row_ref.index.duplicated(keep="last")]
            for poste in vp:
                if poste in row_ref.index:
                    total_reference[poste] = sum(
                        int(row_ref.loc[poste, kpi]) for kpi in tous_kpi
                        if kpi in row_ref.columns and pd.notna(row_ref.loc[poste, kpi])
                    )
                else:
                    total_reference[poste] = 0

    if reference_disponible and date_reference is not None:
        st.caption(f"📅 Référence : dernier instantané enregistré du {date_reference:%d/%m/%Y}. "
                    f"Le pourcentage indique la part déjà traitée depuis cette référence.")
    else:
        st.caption("📌 Aucune extraction antérieure enregistrée — ce total sert de RÉFÉRENCE. "
                    "Le pourcentage traité apparaîtra dès la prochaine extraction.")

    if division in ("SF1", "SF2"):
        postes_div = [p for p in vp if str(p).startswith(division)]
        label_div = "Maroc Chimie (SF1)" if division == "SF1" else "FEEDS (SF2)"
        st.markdown(f"**🏭 {label_div}**")
        _dessiner_barre_horizontale_division(
            postes_div, total_actuel, total_reference, reference_disponible,
            tous_kpi, ano_map_actuel, f"{key_prefix}_{division.lower()}",
        )
        return

    postes_sf1 = [p for p in vp if str(p).startswith("SF1")]
    postes_sf2 = [p for p in vp if str(p).startswith("SF2")]

    col_sf1, col_sf2 = st.columns(2)
    with col_sf1:
        st.markdown("**🏭 Maroc Chimie (SF1)**")
        _dessiner_barre_horizontale_division(
            postes_sf1, total_actuel, total_reference, reference_disponible,
            tous_kpi, ano_map_actuel, f"{key_prefix}_sf1",
        )
    with col_sf2:
        st.markdown("**🏭 FEEDS (SF2)**")
        _dessiner_barre_horizontale_division(
            postes_sf2, total_actuel, total_reference, reference_disponible,
            tous_kpi, ano_map_actuel, f"{key_prefix}_sf2",
        )




def render_suivi_anomalies_semaine_filtrable(vp: list, hist_df, now_ts, key_prefix: str) -> None:
    """
    CORRIGÉ (demande explicite) : pour la semaine sélectionnée, compare
    DÉSORMAIS le début de CETTE semaine à sa dernière extraction connue
    (se met à jour au fil des extractions de la semaine), au lieu de la
    comparer à la semaine précédente. Filtre par numéro de semaine
    (ex. "Semaine 38"), n'affecte que ce graphique.
    """
    from core.historique import calculate_suivi_semaine_intra
    from core.constants import QK, PK

    st.markdown('<div class="stl a">🎯 Suivi hebdomadaire des anomalies</div>', unsafe_allow_html=True)

    if hist_df is None or hist_df.empty or "_section" not in hist_df.columns:
        st.markdown('<div style="padding:12px;color:#94a3b8;">Historique indisponible pour le moment.</div>',
                     unsafe_allow_html=True)
        return

    sub = hist_df[hist_df["_section"].isin(["ano_perf", "ano_qual"])]
    dates_dispo = sub["Date_parsed"].dropna().sort_values().unique()
    if len(dates_dispo) == 0:
        st.markdown('<div style="padding:12px;color:#94a3b8;">Aucune extraction d\'anomalies enregistrée pour le moment.</div>',
                     unsafe_allow_html=True)
        return

    semaines_vues = sorted({
        (pd.Timestamp(d).isocalendar().year, pd.Timestamp(d).isocalendar().week)
        for d in dates_dispo
    }, reverse=True)
    labels_semaines = [f"Semaine {num} ({annee})" for annee, num in semaines_vues]

    choix = st.selectbox(
        "🔎 Filtrer ce graphique par semaine (n'affecte que ce graphique)",
        labels_semaines, index=0, key=f"{key_prefix}_filtre_semaine",
    )
    idx_choisi = labels_semaines.index(choix)
    annee_choisie, num_choisi = semaines_vues[idx_choisi]

    res = calculate_suivi_semaine_intra(hist_df, int(annee_choisie), int(num_choisi), QK, PK)
    _dessiner_suivi_anomalies(res, f"{key_prefix}_{annee_choisie}_{num_choisi}")


def render_suivi_anomalies_semaine_live(vp: list, hist_df, now_ts, key_prefix: str) -> None:
    """
    REFAIT (demande explicite, clarification finale) :
      - PAS de comparaison entre semaines différentes.
      - Pour LA semaine ISO en cours (celle de now_ts) : la RÉFÉRENCE
        (baseline) = la PREMIÈRE extraction connue de cette semaine —
        elle reste FIXE tant qu'on est dans cette même semaine.
      - À chaque NOUVELLE extraction reçue DANS LA MÊME semaine, on
        recalcule combien ont été TRAITÉES depuis cette référence fixe.
      - Affichage : UNE SEULE barre empilée par poste, 2 couleurs (vert
        = traité, orange = restant), % de traitement affiché au-dessus.
      - Tous les postes sont affichés, y compris ceux à 0.
      - Quand une nouvelle semaine ISO commence, une NOUVELLE référence
        est prise automatiquement (cycle recommence).
    """
    from core.historique import calculate_suivi_semaine_intra
    from core.constants import QK, PK

    st.markdown('<div class="stl a">🎯 Anomalies par semaine</div>', unsafe_allow_html=True)

    if hist_df is None or hist_df.empty or "_section" not in hist_df.columns:
        st.markdown('<div style="padding:12px;color:#94a3b8;">Historique indisponible pour le moment.</div>',
                     unsafe_allow_html=True)
        return

    _now = pd.Timestamp(now_ts) if now_ts is not None else pd.Timestamp.today()
    annee_actuelle = _now.isocalendar().year
    num_actuel = _now.isocalendar().week

    res = calculate_suivi_semaine_intra(hist_df, int(annee_actuelle), int(num_actuel), QK, PK)
    par_poste = res["par_poste"]

    if par_poste.empty:
        st.markdown(
            f'<div style="padding:12px;color:#94a3b8;">Aucune extraction enregistrée pour la '
            f'Semaine {num_actuel} pour le moment.</div>',
            unsafe_allow_html=True,
        )
        return

    label_semaine = f"Semaine {num_actuel}"
    mode_statique = res["date_prec"] is None

    if mode_statique:
        st.caption(f"📅 {label_semaine} — première extraction : total de référence affiché "
                    f"(fixe), en attente d'une nouvelle extraction cette même semaine pour "
                    f"voir le traitement.")
    else:
        st.caption(f"📅 {label_semaine} — référence du {res['date_prec']:%d/%m}, dernière "
                    f"extraction du {res['date_act']:%d/%m}.")

    postes_vp = [p for p in vp if p in par_poste["Poste"].values]
    sous = par_poste[par_poste["Poste"].isin(postes_vp)].copy() if postes_vp else par_poste.copy()
    sous["Baseline"] = sous["Anomalies semaine"] + sous["Anomalies traitees"]
    sous = sous.sort_values("Baseline", ascending=False)

    postes = sous["Poste"].tolist()
    restant = sous["Anomalies semaine"].tolist()
    traite = sous["Anomalies traitees"].tolist()
    baseline = sous["Baseline"].tolist()

    fig = go.Figure()
    if mode_statique:
        fig.add_trace(go.Bar(
            x=postes, y=baseline, name=f"Anomalies {label_semaine} (référence)",
            marker=dict(color="#f97316", line=dict(color='white', width=1)),
            text=[str(v) for v in baseline], textposition='outside',
            textfont=dict(color='black', size=11),
        ))
        barmode = 'group'
    else:
        fig.add_trace(go.Bar(
            x=postes, y=traite, name="Traitées",
            marker=dict(color="#10b981", line=dict(color='white', width=1)),
            text=[str(v) if v > 0 else "" for v in traite], textposition='inside',
            textfont=dict(color='white', size=10),
        ))
        fig.add_trace(go.Bar(
            x=postes, y=restant, name="Restantes",
            marker=dict(color="#f97316", line=dict(color='white', width=1)),
            text=[str(v) for v in restant], textposition='inside',
            textfont=dict(color='white', size=10),
        ))
        for p, b, t in zip(postes, baseline, traite):
            pct = round(t / b * 100) if b > 0 else 0
            fig.add_annotation(x=p, y=b, text=f"{pct}%", showarrow=False, yshift=14,
                               font=dict(size=11, color='black'))
        barmode = 'stack'

    fig.update_layout(
        barmode=barmode, height=440,
        xaxis=dict(tickangle=-45, fixedrange=True),
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", fixedrange=True, title="Nombre d'anomalies"),
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation="h", yanchor="bottom", y=-0.32, x=0.5, xanchor="center"),
        margin=dict(t=40, b=110, l=20, r=20),
    )
    event = st.plotly_chart(
        fig, use_container_width=True, config=PLOTLY_CONFIG,
        on_select="rerun", selection_mode="points", key=f"{key_prefix}_chart_semaine",
    )

    points = event.selection.points if event and event.selection else []
    if points:
        poste_sel = points[0].get("x")
        detail = res["detail_par_poste"].get(poste_sel)
        if detail is not None and not detail.empty:
            st.markdown(f"**🔍 Détail par KPI — {poste_sel}**")
            fig2 = go.Figure()
            if not mode_statique:
                fig2.add_trace(go.Bar(
                    y=detail["KPI"], x=detail["Anomalies traitees"], orientation='h',
                    name="Traitées", marker=dict(color="#10b981"),
                    text=detail["Anomalies traitees"].astype(str), textposition='inside',
                ))
                fig2.add_trace(go.Bar(
                    y=detail["KPI"], x=detail["Anomalies semaine"], orientation='h',
                    name="Restantes", marker=dict(color="#f97316"),
                    text=detail["Anomalies semaine"].astype(str), textposition='inside',
                ))
                bm2 = 'stack'
            else:
                fig2.add_trace(go.Bar(
                    y=detail["KPI"], x=detail["Anomalies semaine"], orientation='h',
                    name="Référence", marker=dict(color="#f97316"),
                    text=detail["Anomalies semaine"].astype(str), textposition='outside',
                    textfont=dict(color='black'),
                ))
                bm2 = 'group'
            fig2.update_layout(
                barmode=bm2, height=max(280, 36 * len(detail) + 90),
                yaxis=dict(autorange="reversed", fixedrange=True, automargin=True),
                xaxis=dict(showgrid=True, gridcolor="#F1F5F9", fixedrange=True),
                plot_bgcolor='white', paper_bgcolor='white',
                margin=dict(t=20, b=40, l=20, r=40),
            )
            st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG,
                             key=f"{key_prefix}_detail_{poste_sel}")
        else:
            st.info("Détail indisponible pour ce poste.")
    else:
        st.caption("👆 Cliquez sur une barre pour voir le détail par KPI.")
