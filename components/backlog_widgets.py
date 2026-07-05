# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np

from components.charts import show_pie_pair, show_simple_pie
from components.tables import html_generic_pivot, html_statut_pivot
from core.calcul_kpi import build_statut_pivot, get_text_col

# Mots cles caracterisation d apres PDF OCP
CRPR_KW = ['ATPD', 'ATMR', 'ATRS', 'ATMO', 'ATER']
ATPL_KW = ['ATEI', 'ATAL', 'ATAS', 'AGAR', 'ATHS']
TW_PREV = [350, 290, 300, 310, 360]


def render_backlog_tab(dfp: pd.DataFrame, vp: list) -> None:
    """Rendu complet de l onglet Backlog."""

    # ── Filtres de base ──────────────────────────────────────────────────
    # OT correctif = Plan entretien == 0
    df_correctif = dfp[dfp['is_correctif']].copy() if 'is_correctif' in dfp.columns else dfp.copy()

    pat_prep = '|'.join(CRPR_KW)
    pat_plan = '|'.join(ATPL_KW)

    # ── Backlog Preparation ──────────────────────────────────────────────
    # Base : CREE + CRPR + hors SOPL
    # Num  : contient ATPD/ATMR/ATRS/ATMO/ATER
    # Den  : total base
    df_prep = df_correctif[
        (df_correctif['Statut OT'] == 'CRÉÉ') &
        df_correctif['Statut utilisateur'].str.contains(r'CRPR', case=False, na=False) &
        (df_correctif['Contient SOPL'] == 0)
    ].copy()
    df_prep['Carac Prep'] = df_prep['Statut utilisateur'].str.contains(
        pat_prep, na=False
    ).map({True: 'CARACTERISE', False: 'NON CARACTERISE'})

    # Type de caracterisation
    df_prep['Type Carac Prep'] = df_prep['Statut utilisateur'].apply(
        lambda x: next((kw for kw in CRPR_KW if kw in str(x)), 'NON CARACTERISE')
    )

    # Pivot statut / caracterisation
    piv_prep_stat = pd.pivot_table(
        df_prep, index='Poste travail princ.', columns='Carac Prep',
        values='Ordre', aggfunc='count', fill_value=0
    ).reindex(vp, fill_value=0)
    for c in ['CARACTERISE', 'NON CARACTERISE']:
        if c not in piv_prep_stat.columns:
            piv_prep_stat[c] = 0

    # Pivot type de caracterisation
    df_carac_prep = df_prep[df_prep['Carac Prep'] == 'CARACTERISE']
    piv_prep_type = pd.pivot_table(
        df_carac_prep, index='Poste travail princ.', columns='Type Carac Prep',
        values='Ordre', aggfunc='count', fill_value=0
    ).reindex(vp, fill_value=0)

    # ── Backlog Planification ────────────────────────────────────────────
    # Base = OT LANC + Plan==0 + hors SOPL
    # Caracterise = contient ATEI/ATAL/ATAS/AGAR/ATHS
    df_plan = df_correctif[
        (df_correctif['Statut OT'] == 'LANC') &
        (df_correctif['Contient SOPL'] == 0)
    ].copy()
    df_plan['Carac Plan'] = df_plan['Statut utilisateur'].str.contains(
        pat_plan, na=False
    ).map({True: 'CARACTERISE', False: 'NON CARACTERISE'})

    # Type de caracterisation
    df_plan['Type Carac Plan'] = df_plan['Statut utilisateur'].apply(
        lambda x: next((kw for kw in ATPL_KW if kw in str(x)), 'NON CARACTERISE')
    )

    # Pivot statut / caracterisation
    piv_plan_stat = pd.pivot_table(
        df_plan, index='Poste travail princ.', columns='Carac Plan',
        values='Ordre', aggfunc='count', fill_value=0
    ).reindex(vp, fill_value=0)
    for c in ['CARACTERISE', 'NON CARACTERISE']:
        if c not in piv_plan_stat.columns:
            piv_plan_stat[c] = 0

    # Pivot type de caracterisation
    df_carac_plan = df_plan[df_plan['Carac Plan'] == 'CARACTERISE']
    piv_plan_type = pd.pivot_table(
        df_carac_plan, index='Poste travail princ.', columns='Type Carac Plan',
        values='Ordre', aggfunc='count', fill_value=0
    ).reindex(vp, fill_value=0)

    # ── Statuts OT (graphiques generaux) ─────────────────────────────────
    text_col  = get_text_col(dfp)
    oms_df    = dfp[dfp[text_col].astype(str).str.contains('OMS', case=False, na=False)] if text_col else pd.DataFrame()
    thm_df    = dfp[dfp[text_col].astype(str).str.contains('THERMO|THERMOGRAPH', case=False, na=False)] if text_col else pd.DataFrame()
    piv_oms   = build_statut_pivot(oms_df, vp)
    piv_thm   = build_statut_pivot(thm_df, vp)
    piv_all   = build_statut_pivot(dfp, vp)

    # ── RENDU ────────────────────────────────────────────────────────────

    # Section 1 : Caracterisation Backlog Preparation
    st.markdown(
        '<div class="stl c">📋 Caractérisation Backlog Préparation '
        '(OT CRÉÉ + Plan==0, carac = ATPD/ATMR/ATRS/ATMO/ATER)</div>',
        unsafe_allow_html=True
    )

    # Tableau recapitulatif
    recap_prep = []
    for poste in vp:
        carac = int(piv_prep_stat.loc[poste, 'CARACTERISE']) if poste in piv_prep_stat.index else 0
        non   = int(piv_prep_stat.loc[poste, 'NON CARACTERISE']) if poste in piv_prep_stat.index else 0
        tot   = carac + non
        taux  = round(carac / tot * 100, 1) if tot > 0 else 0.0
        recap_prep.append({
            'Poste de travail': poste,
            'Caractérisé': carac,
            'Non Caractérisé': non,
            'Total': tot,
            'Taux Carac %': f'{taux}%'
        })

    # Ligne total
    total_carac = sum(r['Caractérisé'] for r in recap_prep)
    total_non   = sum(r['Non Caractérisé'] for r in recap_prep)
    total_tot   = total_carac + total_non
    recap_prep.append({
        'Poste de travail': 'TOTAL',
        'Caractérisé': total_carac,
        'Non Caractérisé': total_non,
        'Total': total_tot,
        'Taux Carac %': f'{round(total_carac/total_tot*100,1) if total_tot>0 else 0}%'
    })

    c1, c2 = st.columns([0.5, 0.5], vertical_alignment='center')
    with c1:
        # Tableau HTML
        h = '<table class="tw omt"><thead><tr>'
        for col in ['Poste de travail','Caractérisé','Non Caractérisé','Total','Taux Carac %']:
            h += f'<th>{col}</th>'
        h += '</tr></thead><tbody>'
        for row in recap_prep:
            is_total = row['Poste de travail'] == 'TOTAL'
            style = 'font-weight:800;background:#e2e8f0' if is_total else ''
            h += f'<tr style="{style}">'
            for col in ['Poste de travail','Caractérisé','Non Caractérisé','Total','Taux Carac %']:
                v = row[col]
                cell_style = ''
                if col == 'Caractérisé':
                    cell_style = 'background:#d1fae5;color:#065f46;font-weight:600'
                elif col == 'Non Caractérisé':
                    cell_style = 'background:#fee2e2;color:#991b1b;font-weight:600'
                elif col == 'Taux Carac %':
                    try:
                        pct = float(str(v).replace('%',''))
                        if pct >= 80: cell_style = 'background:#c6efce;color:#006100;font-weight:700'
                        elif pct >= 50: cell_style = 'background:#ffeb9c;color:#9c6500;font-weight:700'
                        else: cell_style = 'background:#ffc7ce;color:#9c0006;font-weight:700'
                    except: pass
                h += f'<td style="text-align:center;{cell_style}">{v}</td>'
            h += '</tr>'
        h += '</tbody></table>'
        st.markdown(h, unsafe_allow_html=True)

    with c2:
        show_simple_pie(piv_prep_stat, 'Répartition Caractérisé / Non Caractérisé (Prep)', keep_non_carac=True)
        if not piv_prep_type.empty and piv_prep_type.sum().sum() > 0:
            show_simple_pie(piv_prep_type, 'Répartition par Type de Caractérisation (Prep)', keep_non_carac=False)

    # Types de caracterisation
    if not df_carac_prep.empty:
        st.markdown('<div class="stl s">Types de caractérisation — Préparation</div>', unsafe_allow_html=True)
        type_counts = df_carac_prep['Type Carac Prep'].value_counts()
        h = '<table class="tw omt"><thead><tr><th>Type</th><th>Description</th><th>Nb OT</th><th>%</th></tr></thead><tbody>'
        desc_map = {
            'ATPD': 'Attente PDR',
            'ATMR': 'Attente marché',
            'ATRS': 'Attente ressources',
            'ATMO': 'Attente moyens ou Outillage',
            'ATER': 'Attente équipement de rechange',
        }
        for typ, cnt in type_counts.items():
            pct = round(cnt / type_counts.sum() * 100, 1)
            desc = desc_map.get(typ, typ)
            h += f'<tr><td style="font-weight:700;color:#059669">{typ}</td><td>{desc}</td><td style="text-align:center;font-weight:600">{cnt}</td><td style="text-align:center">{pct}%</td></tr>'
        h += '</tbody></table>'
        st.markdown(h, unsafe_allow_html=True)

    st.markdown('---')

    # Section 2 : Caracterisation Backlog Planification
    st.markdown(
        '<div class="stl c">📋 Caractérisation Backlog Planification '
        '(OT LANC + Plan==0 + hors SOPL, carac = ATEI/ATAL/ATAS/AGAR/ATHS)</div>',
        unsafe_allow_html=True
    )

    recap_plan = []
    for poste in vp:
        carac = int(piv_plan_stat.loc[poste, 'CARACTERISE']) if poste in piv_plan_stat.index else 0
        non   = int(piv_plan_stat.loc[poste, 'NON CARACTERISE']) if poste in piv_plan_stat.index else 0
        tot   = carac + non
        taux  = round(carac / tot * 100, 1) if tot > 0 else 0.0
        recap_plan.append({
            'Poste de travail': poste,
            'Caractérisé': carac,
            'Non Caractérisé': non,
            'Total': tot,
            'Taux Carac %': f'{taux}%'
        })

    total_carac = sum(r['Caractérisé'] for r in recap_plan)
    total_non   = sum(r['Non Caractérisé'] for r in recap_plan)
    total_tot   = total_carac + total_non
    recap_plan.append({
        'Poste de travail': 'TOTAL',
        'Caractérisé': total_carac,
        'Non Caractérisé': total_non,
        'Total': total_tot,
        'Taux Carac %': f'{round(total_carac/total_tot*100,1) if total_tot>0 else 0}%'
    })

    c3, c4 = st.columns([0.5, 0.5], vertical_alignment='center')
    with c3:
        h = '<table class="tw omt"><thead><tr>'
        for col in ['Poste de travail','Caractérisé','Non Caractérisé','Total','Taux Carac %']:
            h += f'<th>{col}</th>'
        h += '</tr></thead><tbody>'
        for row in recap_plan:
            is_total = row['Poste de travail'] == 'TOTAL'
            style = 'font-weight:800;background:#e2e8f0' if is_total else ''
            h += f'<tr style="{style}">'
            for col in ['Poste de travail','Caractérisé','Non Caractérisé','Total','Taux Carac %']:
                v = row[col]
                cell_style = ''
                if col == 'Caractérisé':
                    cell_style = 'background:#d1fae5;color:#065f46;font-weight:600'
                elif col == 'Non Caractérisé':
                    cell_style = 'background:#fee2e2;color:#991b1b;font-weight:600'
                elif col == 'Taux Carac %':
                    try:
                        pct = float(str(v).replace('%',''))
                        if pct >= 80: cell_style = 'background:#c6efce;color:#006100;font-weight:700'
                        elif pct >= 50: cell_style = 'background:#ffeb9c;color:#9c6500;font-weight:700'
                        else: cell_style = 'background:#ffc7ce;color:#9c0006;font-weight:700'
                    except: pass
                h += f'<td style="text-align:center;{cell_style}">{v}</td>'
            h += '</tr>'
        h += '</tbody></table>'
        st.markdown(h, unsafe_allow_html=True)

    with c4:
        show_simple_pie(piv_plan_stat, 'Répartition Caractérisé / Non Caractérisé (Plan)', keep_non_carac=True)
        if not piv_plan_type.empty and piv_plan_type.sum().sum() > 0:
            show_simple_pie(piv_plan_type, 'Répartition par Type de Caractérisation (Plan)', keep_non_carac=False)

    if not df_carac_plan.empty:
        st.markdown('<div class="stl s">Types de caractérisation — Planification</div>', unsafe_allow_html=True)
        type_counts = df_carac_plan['Type Carac Plan'].value_counts()
        h = '<table class="tw omt"><thead><tr><th>Type</th><th>Description</th><th>Nb OT</th><th>%</th></tr></thead><tbody>'
        desc_map = {
            'ATEI': 'Attente arrêt équipement ou Installation',
            'ATAL': 'Attente arrêt ligne',
            'ATAS': 'Attente arrêt site',
            'AGAR': 'Attente grand arrêt de révision',
            'ATHS': 'Attente HSE',
        }
        for typ, cnt in type_counts.items():
            pct = round(cnt / type_counts.sum() * 100, 1)
            desc = desc_map.get(typ, typ)
            h += f'<tr><td style="font-weight:700;color:#2563eb">{typ}</td><td>{desc}</td><td style="text-align:center;font-weight:600">{cnt}</td><td style="text-align:center">{pct}%</td></tr>'
        h += '</tbody></table>'
        st.markdown(h, unsafe_allow_html=True)

    st.markdown('---')

    # Section 3 : Statuts OT
    st.markdown('<div class="stl p">📊 Statuts OT par Poste de Travail</div>', unsafe_allow_html=True)

    st.markdown('<div class="stl s">OT OMS par Poste et Statut OT</div>', unsafe_allow_html=True)
    c5, c6 = st.columns([0.5, 0.5], vertical_alignment='center')
    with c5:
        st.markdown(html_statut_pivot(piv_oms, 'omt'), unsafe_allow_html=True)
    with c6:
        show_pie_pair(piv_oms, 'OT OMS')

    st.markdown('<div class="stl s">OT Thermographie par Poste et Statut OT</div>', unsafe_allow_html=True)
    c7, c8 = st.columns([0.5, 0.5], vertical_alignment='center')
    with c7:
        st.markdown(html_statut_pivot(piv_thm, 'tht'), unsafe_allow_html=True)
    with c8:
        show_pie_pair(piv_thm, 'OT Thermographie')

    st.markdown('<div class="stl s">Tous les OT par Poste et Statut OT</div>', unsafe_allow_html=True)
    c9, c10 = st.columns([0.5, 0.5], vertical_alignment='center')
    with c9:
        st.markdown(html_statut_pivot(piv_all, 'pt'), unsafe_allow_html=True)
    with c10:
        show_pie_pair(piv_all, 'Tous les OT')
