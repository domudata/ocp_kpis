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

def show_butterfly_comparison(postes: list,
                               perf_prec: list, perf_act: list,
                               qual_prec: list, qual_act: list,
                               titre: str, label_prec: str, label_act: str) -> None:
    """
    CORRIGÉ (demande explicite) : Performance ET Qualité FUSIONNÉES sur
    UN SEUL graphique papillon — 2 barres par poste de chaque côté
    (Performance et Qualité), au lieu de 2 graphiques séparés. Barres
    plus fines (bargap réduit) pour que les 4 séries restent lisibles.
    """
    if not postes:
        st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=postes, x=[-v for v in perf_prec], orientation='h',
        name=f"Performance — {label_prec}", marker=dict(color="#f59e0b", line=dict(color='white', width=0.5)),
        text=[f"{v:.0f}%" for v in perf_prec], textposition='outside',
        textfont=dict(size=11, family='Inter', color='#1e293b'),
        hovertemplate="<b>%{y}</b><br>Performance " + label_prec + " : %{customdata:.1f}%<extra></extra>",
        customdata=perf_prec, offsetgroup="prec",
    ))
    fig.add_trace(go.Bar(
        y=postes, x=[-v for v in qual_prec], orientation='h',
        name=f"Qualité — {label_prec}", marker=dict(color="#8b5cf6", line=dict(color='white', width=0.5)),
        text=[f"{v:.0f}%" for v in qual_prec], textposition='outside',
        textfont=dict(size=11, family='Inter', color='#1e293b'),
        hovertemplate="<b>%{y}</b><br>Qualité " + label_prec + " : %{customdata:.1f}%<extra></extra>",
        customdata=qual_prec, offsetgroup="prec",
    ))
    fig.add_trace(go.Bar(
        y=postes, x=perf_act, orientation='h',
        name=f"Performance — {label_act}", marker=dict(color="#2563eb", line=dict(color='white', width=0.5)),
        text=[f"{v:.0f}%" for v in perf_act], textposition='outside',
        textfont=dict(size=11, family='Inter', color='#1e293b'),
        hovertemplate="<b>%{y}</b><br>Performance " + label_act + " : %{x:.1f}%<extra></extra>",
        offsetgroup="act",
    ))
    fig.add_trace(go.Bar(
        y=postes, x=qual_act, orientation='h',
        name=f"Qualité — {label_act}", marker=dict(color="#14b8a6", line=dict(color='white', width=0.5)),
        text=[f"{v:.0f}%" for v in qual_act], textposition='outside',
        textfont=dict(size=11, family='Inter', color='#1e293b'),
        hovertemplate="<b>%{y}</b><br>Qualité " + label_act + " : %{x:.1f}%<extra></extra>",
        offsetgroup="act",
    ))
    fig.add_vline(x=0, line_color="#1e293b", line_width=1.5)

    fig.update_layout(
        title=dict(text=titre, x=0.5, xanchor='center', font=dict(size=15, color='#1e293b')),
        barmode='group', bargap=0.35, bargroupgap=0.06,
        height=max(350, 46 * len(postes) + 130),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False, fixedrange=True,
                   range=[-130, 130]),
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


def _dessiner_suivi_anomalies(res: dict, key_prefix: str) -> None:
    """Dessine le graphique empilé + détail au clic, à partir d'un
    résultat déjà calculé par calculate_suivi_anomalies_semaine (partagé
    entre Dashboard et Suivi Évolution, avec ou sans filtre de semaine)."""
    par_poste = res["par_poste"]
    if par_poste.empty:
        st.markdown(
            f'<div style="padding:12px;color:#94a3b8;">Aucune extraction enregistrée pour la '
            f'Semaine {res["num_semaine_actuelle"]} pour le moment.</div>',
            unsafe_allow_html=True,
        )
        return

    label_semaine = f"Semaine {res['num_semaine_actuelle']}"
    mode_statique = res["date_prec"] is None
    if mode_statique:
        st.caption(f"📅 {label_semaine} — première extraction de cette semaine : total général affiché, "
                    f"en attente de la prochaine extraction pour voir ce qui aura été traité.")
    else:
        st.caption(f"📅 {label_semaine} (comparée à Semaine {res['num_semaine_precedente']})")

    postes = par_poste["Poste"].tolist()
    anomalies = par_poste["Anomalies semaine"].tolist()
    traitees = par_poste["Anomalies traitees"].tolist()

    fig = go.Figure()
    if not mode_statique:
        fig.add_trace(go.Bar(
            x=postes, y=traitees, name="Traitées depuis la semaine précédente",
            marker=dict(color="#10b981", line=dict(color='white', width=1)),
            text=[str(v) if v > 0 else "" for v in traitees], textposition='inside',
        ))
        fig.add_trace(go.Bar(
            x=postes, y=anomalies, name=f"Restantes — {label_semaine}",
            marker=dict(color="#ef4444", line=dict(color='white', width=1)),
            text=[str(v) for v in anomalies], textposition='inside',
        ))
        barmode = 'stack'
    else:
        fig.add_trace(go.Bar(
            x=postes, y=anomalies, name=f"Total anomalies — {label_semaine}",
            marker=dict(color="#ef4444", line=dict(color='white', width=1)),
            text=[str(v) for v in anomalies], textposition='outside',
        ))
        barmode = 'group'

    fig.update_layout(
        barmode=barmode, height=420,
        xaxis=dict(tickangle=-45, fixedrange=True),
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", fixedrange=True,
                   title="Nombre d'anomalies (total semaine précédente)" if not mode_statique else "Nombre d'anomalies"),
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, x=0.5, xanchor="center"),
        margin=dict(t=20, b=100, l=20, r=20),
    )
    event = st.plotly_chart(
        fig, use_container_width=True, config=PLOTLY_CONFIG,
        on_select="rerun", selection_mode="points", key=f"{key_prefix}_suivi_anom_chart",
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
                    name="Restantes", marker=dict(color="#ef4444"),
                    text=detail["Anomalies semaine"].astype(str), textposition='inside',
                ))
                barmode2 = 'stack'
            else:
                fig2.add_trace(go.Bar(
                    y=detail["KPI"], x=detail["Anomalies semaine"], orientation='h',
                    name="Total", marker=dict(color="#ef4444"),
                    text=detail["Anomalies semaine"].astype(str), textposition='outside',
                ))
                barmode2 = 'group'
            fig2.update_layout(
                barmode=barmode2, height=max(300, 45 * len(detail) + 100),
                yaxis=dict(autorange="reversed", fixedrange=True, automargin=True),
                xaxis=dict(showgrid=True, gridcolor="#F1F5F9", fixedrange=True),
                plot_bgcolor='white', paper_bgcolor='white',
                legend=dict(orientation="h", yanchor="bottom", y=-0.15, x=0.5, xanchor="center"),
                margin=dict(t=20, b=50, l=20, r=20),
            )
            st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG,
                             key=f"{key_prefix}_suivi_anom_detail_{poste_sel}")
        else:
            st.info("Détail indisponible pour ce poste.")
    else:
        st.caption("👆 Cliquez sur les barres d'un poste pour voir le détail par KPI.")


def render_suivi_anomalies_semaine(vp: list, hist_df, now_ts, key_prefix: str,
                                    ano_map_actuel: dict = None) -> None:
    """
    Suivi hebdomadaire des anomalies.

    ano_map_actuel (AJOUTÉ, demande explicite) : si fourni, c'est le
    total "actuel" par poste/KPI qui est utilisé pour la barre "actuelle"
    — calculé EN DIRECT sous le filtre période de la sidebar (celui du
    tableau de bord), au lieu du dernier instantané historique enregistré
    (qui peut dater d'une extraction précédente). La comparaison
    ("traitées") reste basée sur le dernier instantané historique
    disponible pour la semaine précédente. Sans ano_map_actuel, le
    comportement est identique à avant (comparaison entre les 2 derniers
    instantanés historiques).
    """
    from core.historique import calculate_suivi_anomalies_semaine
    from core.constants import QK, PK

    st.markdown('<div class="stl a">🎯 Suivi hebdomadaire des anomalies</div>', unsafe_allow_html=True)

    if hist_df is None or hist_df.empty:
        st.markdown('<div style="padding:12px;color:#94a3b8;">Historique indisponible pour le moment.</div>',
                     unsafe_allow_html=True)
        return

    res = calculate_suivi_anomalies_semaine(hist_df, now_ts, QK, PK)

    if ano_map_actuel is not None:
        # Remplace le total "actuel" par le calcul LIVE sous le filtre
        # période de la sidebar, poste par poste et KPI par KPI.
        st.caption("📌 Le total « actuel » reflète le filtre période sélectionné dans le panneau latéral.")
        tous_kpi = list(QK) + list(PK)
        nouveaux_totaux = {}
        nouveau_detail = {}
        for poste in vp:
            total_poste = 0
            lignes_detail = []
            for kpi in tous_kpi:
                nb = int(ano_map_actuel.get(kpi, {}).get(poste, 0)) if hasattr(ano_map_actuel.get(kpi, {}), "get") else 0
                total_poste += nb
                # "traitées" pour ce KPI : on réutilise, si dispo, la
                # valeur déjà calculée par l'historique (comparaison à la
                # semaine précédente) ; sinon 0 (pas de comparaison possible).
                ancien = None
                if not res["par_poste"].empty and poste in res["detail_par_poste"]:
                    d = res["detail_par_poste"][poste]
                    ligne_kpi = d[d["KPI"] == kpi]
                    if not ligne_kpi.empty:
                        ancien_traite = int(ligne_kpi["Anomalies traitees"].iloc[0])
                        ancien_semaine = int(ligne_kpi["Anomalies semaine"].iloc[0])
                        # "traité" recalculé par rapport au NOUVEAU total actuel
                        ancien = max(0, (ancien_semaine + ancien_traite) - nb)
                lignes_detail.append({"Type": "", "KPI": kpi, "Anomalies semaine": nb,
                                       "Anomalies traitees": ancien or 0})
            nouveaux_totaux[poste] = total_poste
            nouveau_detail[poste] = pd.DataFrame(lignes_detail)

        par_poste_live = pd.DataFrame([
            {"Poste": p, "Anomalies semaine": nouveaux_totaux.get(p, 0),
             "Anomalies traitees": int(nouveau_detail[p]["Anomalies traitees"].sum()) if p in nouveau_detail and not nouveau_detail[p].empty else 0}
            for p in vp
        ]).sort_values("Anomalies semaine", ascending=False)

        res = {
            "num_semaine_actuelle": res["num_semaine_actuelle"],
            "num_semaine_precedente": res["num_semaine_precedente"],
            "date_act": res["date_act"], "date_prec": res["date_prec"],
            "par_poste": par_poste_live, "detail_par_poste": nouveau_detail,
        }

    _dessiner_suivi_anomalies(res, key_prefix)


def render_suivi_anomalies_semaine_filtrable(vp: list, hist_df, now_ts, key_prefix: str) -> None:
    """
    AJOUTÉ (demande explicite, page Suivi Évolution) : même système que
    render_suivi_anomalies_semaine, MAIS avec un filtre par NUMÉRO DE
    SEMAINE (ex. "Semaine 38") qui ne s'applique QU'À CE GRAPHIQUE — les
    autres sections de la page ne sont pas affectées par ce filtre.
    Permet de consulter n'importe quelle semaine passée enregistrée,
    pas seulement la semaine calendaire en cours.
    """
    from core.historique import calculate_suivi_anomalies_semaine
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

    lundi_choisi = pd.Timestamp.fromisocalendar(int(annee_choisie), int(num_choisi), 1)

    res = calculate_suivi_anomalies_semaine(hist_df, lundi_choisi, QK, PK)
    _dessiner_suivi_anomalies(res, f"{key_prefix}_{annee_choisie}_{num_choisi}")
