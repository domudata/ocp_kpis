# -*- coding: utf-8 -*-
import re
import streamlit as st
import pandas as pd
import numpy as np

from components.charts import show_pie_pair, show_simple_pie
from components.tables import html_generic_pivot, html_statut_pivot
from core.calcul_kpi import build_statut_pivot, get_text_col
CODES_PREP_EXACT = {'ATPD', 'ATMR', 'ATER', 'ATRS', 'ATMO'}
CODES_PLAN_EXACT = {'ATPL', 'ATEI', 'ATAL', 'ATAS', 'AGAR', 'ATHS'}
ALL_CARAC_EXACT = CODES_PREP_EXACT | CODES_PLAN_EXACT


def match_exact_token(statut, codes: set) -> bool:
    if statut is None or (isinstance(statut, float) and pd.isna(statut)):
        return False
    words = set(re.findall(r'[A-Za-z0-9]+', str(statut).upper()))
    return bool(words & codes)

# Mots cles caracterisation d apres PDF OCP
CRPR_KW = ['ATPD', 'ATMR', 'ATRS', 'ATMO', 'ATER']
ATPL_KW = ['ATPL', 'ATEI', 'ATAL', 'ATAS', 'AGAR', 'ATHS']
TW_PREV = [350, 290, 300, 310, 360]



def html_age_dispatch_table(rows, include_exec=False):
    cols = [
        ("Poste de travail", "left", "Poste de travail"),
        ("AGE PREP <1M", "center", "AGE PREP <1M"), ("NB <1M", "center", "BASE_P_INF"),
        ("AGE PREP 1-3M", "center", "AGE PREP 1-3M"), ("NB 1-3M", "center", "BASE_P_1_3"),
        ("AGE PREP >3M", "center", "AGE PREP >3M"), ("NB >3M", "center", "BASE_P_SUP"),
        ("AGE PLANIF <1M", "center", "AGE PLANIF <1M"), ("NB <1M", "center", "BASE_L_INF"),
        ("AGE PLANIF 1-3M", "center", "AGE PLANIF 1-3M"), ("NB 1-3M", "center", "BASE_L_1_3"),
        ("AGE PLANIF >3M", "center", "AGE PLANIF >3M"), ("NB >3M", "center", "BASE_L_SUP"),
    ]
    if include_exec:
        cols.extend([
            ("AGE EXEC <1M", "center", "AGE EXEC <1M"), ("NB <1M", "center", "BASE_E_INF"),
            ("AGE EXEC 1-3M", "center", "AGE EXEC 1-3M"), ("NB 1-3M", "center", "BASE_E_1_3"),
            ("AGE EXEC >3M", "center", "AGE EXEC >3M"), ("NB >3M", "center", "BASE_E_SUP"),
        ])
    h = '<table class="tw omt"><thead><tr>'
    for c, align, _ in cols:
        h += f'<th style="text-align:{align};font-size:11px">{c}</th>'
    h += '</tr></thead><tbody>'

    for r in rows:
        is_cible = r.get("_t") == "cible"
        is_total = r.get("_t") == "total"
        row_style = ""
        if is_cible:
            row_style = "font-weight:700;background:#1e3a5f;color:#ffffff"
        elif is_total:
            row_style = "font-weight:800;background:#e2e8f0"
        h += f'<tr style="{row_style}">'

        for _, align, key in cols:
            val = r.get(key, "")
            cell_style = f"text-align:{align};font-size:12px;"
            if not is_cible and not is_total:
                if "%" in str(val):
                    try:
                        num = float(str(val).replace("%", "").strip())
                        if key in ["AGE PREP <1M", "AGE PLANIF <1M", "AGE EXEC <1M"]:
                            cell_style += "background:#c6efce;color:#006100;font-weight:700" if num >= 80 else ("background:#ffeb9c;color:#9c6500;font-weight:700" if num >= 75 else "background:#ffc7ce;color:#9c0006;font-weight:700")
                        elif key in ["AGE PREP 1-3M", "AGE PLANIF 1-3M", "AGE EXEC 1-3M"]:
                            cell_style += "background:#c6efce;color:#006100;font-weight:700" if num <= 15 else ("background:#ffeb9c;color:#9c6500;font-weight:700" if num <= 20 else "background:#ffc7ce;color:#9c0006;font-weight:700")
                        elif key in ["AGE PREP >3M", "AGE PLANIF >3M", "AGE EXEC >3M"]:
                            cell_style += "background:#c6efce;color:#006100;font-weight:700" if num <= 5 else ("background:#ffeb9c;color:#9c6500;font-weight:700" if num <= 10 else "background:#ffc7ce;color:#9c0006;font-weight:700")
                    except Exception:
                        pass
                elif "BASE_" in key and val not in ("", 0, "0"):
                    cell_style += "font-weight:600"
            h += f'<td style="{cell_style}">{val}</td>'
        h += '</tr>'
    h += '</tbody></table>'
    return h


def build_age_table_rows(postes, df_prep, df_plan, df_exec=None, label_total="TOTAL"):
    include_exec = df_exec is not None and not df_exec.empty
    rows = []
    cible_row = {
        "Poste de travail": "CIBLE",
        "AGE PREP <1M": "80 %", "BASE_P_INF": "",
        "AGE PREP 1-3M": "15 %", "BASE_P_1_3": "",
        "AGE PREP >3M": "5 %", "BASE_P_SUP": "",
        "AGE PLANIF <1M": "80 %", "BASE_L_INF": "",
        "AGE PLANIF 1-3M": "15 %", "BASE_L_1_3": "",
        "AGE PLANIF >3M": "5 %", "BASE_L_SUP": "",
        "_t": "cible",
    }
    if include_exec:
        cible_row.update({
            "AGE EXEC <1M": "80 %", "BASE_E_INF": "",
            "AGE EXEC 1-3M": "15 %", "BASE_E_1_3": "",
            "AGE EXEC >3M": "5 %", "BASE_E_SUP": "",
        })
    rows.append(cible_row)

    t_p_tot = t_p_inf = t_p_1_3 = t_p_sup = 0
    t_l_tot = t_l_inf = t_l_1_3 = t_l_sup = 0
    t_e_tot = t_e_inf = t_e_1_3 = t_e_sup = 0

    for p in postes:
        cp = df_prep[df_prep["Poste travail princ."] == p] if df_prep is not None and not df_prep.empty else pd.DataFrame()
        lp = df_plan[df_plan["Poste travail princ."] == p] if df_plan is not None and not df_plan.empty else pd.DataFrame()
        ep = df_exec[df_exec["Poste travail princ."] == p] if df_exec is not None and not df_exec.empty else pd.DataFrame()

        nb_p = len(cp)
        cp_non = cp[cp["Carac Prep"] == "NON CARACTERISE"] if "Carac Prep" in cp.columns else cp[~cp["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PREP_EXACT))] if "Statut utilisateur" in cp.columns else cp
        p_inf = int((cp_non["ap"].isin(["<1 mois", "Inconnu"])).sum()) if "ap" in cp_non.columns else 0
        p_1_3 = int((cp_non["ap"] == "1 mois < <3 mois").sum()) if "ap" in cp_non.columns else 0
        p_sup = int((cp_non["ap"] == ">3 mois").sum()) if "ap" in cp_non.columns else 0

        nb_l = len(lp)
        lp_non = lp[lp["Carac Plan"] == "NON CARACTERISE"] if "Carac Plan" in lp.columns else lp[~lp["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT))] if "Statut utilisateur" in lp.columns else lp
        l_inf = int((lp_non["alp"].isin(["<1 mois", "Inconnu"])).sum()) if "alp" in lp_non.columns else 0
        l_1_3 = int((lp_non["alp"] == "1 mois < <3 mois").sum()) if "alp" in lp_non.columns else 0
        l_sup = int((lp_non["alp"] == ">3 mois").sum()) if "alp" in lp_non.columns else 0

        nb_e = len(ep)
        ep_non = ep[ep["Carac Exec"] == "NON CARACTERISE"] if "Carac Exec" in ep.columns else ep[~ep["Statut utilisateur"].apply(lambda x: match_exact_token(x, ALL_CARAC_EXACT))] if "Statut utilisateur" in ep.columns else ep
        e_inf = int((ep_non["aex"].isin(["<1 mois", "Inconnu"])).sum()) if "aex" in ep_non.columns else 0
        e_1_3 = int((ep_non["aex"] == "1 mois < <3 mois").sum()) if "aex" in ep_non.columns else 0
        e_sup = int((ep_non["aex"] == ">3 mois").sum()) if "aex" in ep_non.columns else 0

        t_p_tot += nb_p; t_p_inf += p_inf; t_p_1_3 += p_1_3; t_p_sup += p_sup
        t_l_tot += nb_l; t_l_inf += l_inf; t_l_1_3 += l_1_3; t_l_sup += l_sup
        t_e_tot += nb_e; t_e_inf += e_inf; t_e_1_3 += e_1_3; t_e_sup += e_sup

        r = {
            "Poste de travail": p,
            "AGE PREP <1M": f"{round(p_inf / nb_p * 100)} %" if nb_p else "0 %",
            "BASE_P_INF": p_inf,
            "AGE PREP 1-3M": f"{round(p_1_3 / nb_p * 100)} %" if nb_p else "0 %",
            "BASE_P_1_3": p_1_3,
            "AGE PREP >3M": f"{round(p_sup / nb_p * 100)} %" if nb_p else "0 %",
            "BASE_P_SUP": p_sup,
            "AGE PLANIF <1M": f"{round(l_inf / nb_l * 100)} %" if nb_l else "0 %",
            "BASE_L_INF": l_inf,
            "AGE PLANIF 1-3M": f"{round(l_1_3 / nb_l * 100)} %" if nb_l else "0 %",
            "BASE_L_1_3": l_1_3,
            "AGE PLANIF >3M": f"{round(l_sup / nb_l * 100)} %" if nb_l else "0 %",
            "BASE_L_SUP": l_sup,
        }
        if include_exec:
            r.update({
                "AGE EXEC <1M": f"{round(e_inf / nb_e * 100)} %" if nb_e else "0 %",
                "BASE_E_INF": e_inf,
                "AGE EXEC 1-3M": f"{round(e_1_3 / nb_e * 100)} %" if nb_e else "0 %",
                "BASE_E_1_3": e_1_3,
                "AGE EXEC >3M": f"{round(e_sup / nb_e * 100)} %" if nb_e else "0 %",
                "BASE_E_SUP": e_sup,
            })
        rows.append(r)

    tot_r = {
        "Poste de travail": label_total,
        "AGE PREP <1M": f"{round(t_p_inf / t_p_tot * 100)} %" if t_p_tot else "0 %",
        "BASE_P_INF": t_p_inf,
        "AGE PREP 1-3M": f"{round(t_p_1_3 / t_p_tot * 100)} %" if t_p_tot else "0 %",
        "BASE_P_1_3": t_p_1_3,
        "AGE PREP >3M": f"{round(t_p_sup / t_p_tot * 100)} %" if t_p_tot else "0 %",
        "BASE_P_SUP": t_p_sup,
        "AGE PLANIF <1M": f"{round(t_l_inf / t_l_tot * 100)} %" if t_l_tot else "0 %",
        "BASE_L_INF": t_l_inf,
        "AGE PLANIF 1-3M": f"{round(t_l_1_3 / t_l_tot * 100)} %" if t_l_tot else "0 %",
        "BASE_L_1_3": t_l_1_3,
        "AGE PLANIF >3M": f"{round(t_l_sup / t_l_tot * 100)} %" if t_l_tot else "0 %",
        "BASE_L_SUP": t_l_sup,
        "_t": "total",
    }
    if include_exec:
        tot_r.update({
            "AGE EXEC <1M": f"{round(t_e_inf / t_e_tot * 100)} %" if t_e_tot else "0 %",
            "BASE_E_INF": t_e_inf,
            "AGE EXEC 1-3M": f"{round(t_e_1_3 / t_e_tot * 100)} %" if t_e_tot else "0 %",
            "BASE_E_1_3": t_e_1_3,
            "AGE EXEC >3M": f"{round(t_e_sup / t_e_tot * 100)} %" if t_e_tot else "0 %",
            "BASE_E_SUP": t_e_sup,
        })
    rows.append(tot_r)
    return rows


def render_backlog_tab(dfp: pd.DataFrame, vp: list, df_toutes_dates: pd.DataFrame = None) -> None:
    """Rendu complet de l'onglet Backlog."""

    # ── Filtres de base ──────────────────────────────────────────────────
    df_all = df_toutes_dates.copy() if df_toutes_dates is not None else dfp.copy()
    _zcor = df_all[df_all["Type d'ordre"] == "ZCOR"].copy()

    # ── Backlog Preparation ──────────────────────────────────────────────
    # Filtre : ZCOR ET Statut système == CRÉÉ
    df_prep = _zcor[
        _zcor["Statut système"].fillna("").astype(str).str.strip().str.split().str[0].isin(["CRÉÉ", "CREE"])
    ].copy()
    df_prep['Carac Prep'] = np.where(
        df_prep['Statut utilisateur'].apply(lambda x: match_exact_token(x, CODES_PREP_EXACT)),
        'CARACTERISE', 'NON CARACTERISE'
    )

    def _extract_kw(statut, kw_list):
        if statut is None or (isinstance(statut, float) and pd.isna(statut)):
            return 'NON CARACTERISE'
        words = set(re.findall(r'[A-Za-z0-9]+', str(statut).upper()))
        for kw in kw_list:
            if kw in words:
                return kw
        return 'NON CARACTERISE'

    # Type de caracterisation
    df_prep['Type Carac Prep'] = df_prep['Statut utilisateur'].apply(
        lambda x: _extract_kw(x, CRPR_KW)
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
    # Filtre : ZCOR ET Statut système == LANC + Contient SOPL == 0
    df_plan = _zcor[
        (_zcor["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "LANC")
        & (_zcor["Contient SOPL"] == 0)
    ].copy()
    df_plan['Carac Plan'] = np.where(
        df_plan['Statut utilisateur'].apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT)),
        'CARACTERISE', 'NON CARACTERISE'
    )

    # Type de caracterisation
    df_plan['Type Carac Plan'] = df_plan['Statut utilisateur'].apply(
        lambda x: _extract_kw(x, ATPL_KW)
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

    # ── Backlog Exécution ────────────────────────────────────────────────
    _statut_lanc_ex = (
        (_zcor["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "LANC")
        | (_zcor["Statut système"].fillna("").astype(str).str.contains("LANC", na=False)
           & ~_zcor["Statut système"].fillna("").astype(str).str.contains("CLOT|TCLO", na=False))
    )
    _non_clot_ex = ~_zcor["Statut OT"].isin(["CLOT", "TCLO"]) if "Statut OT" in _zcor.columns else True
    _contient_sopl_ex = (
        (_zcor["Contient SOPL"] == 1) if "Contient SOPL" in _zcor.columns
        else _zcor["Statut utilisateur"].fillna("").astype(str).str.contains("SOPL", case=False, na=False)
    )
    df_exec = _zcor[_statut_lanc_ex & _non_clot_ex & _contient_sopl_ex].copy()
    df_exec["Carac Exec"] = np.where(
        df_exec["Statut utilisateur"].apply(lambda x: match_exact_token(x, ALL_CARAC_EXACT)),
        "CARACTERISE", "NON CARACTERISE"
    )

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
        '<div class="stl c">📋 Caractérisation Backlog Préparation</div>',
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
            'Non Caractérisé (Anomalies)': non,
            'Total': tot,
            'Taux Carac %': f'{taux}%'
        })

    # Ligne total
    total_carac = sum(r['Caractérisé'] for r in recap_prep)
    total_non   = sum(r['Non Caractérisé (Anomalies)'] for r in recap_prep)
    total_tot   = total_carac + total_non
    recap_prep.append({
        'Poste de travail': 'TOTAL',
        'Caractérisé': total_carac,
        'Non Caractérisé (Anomalies)': total_non,
        'Total': total_tot,
        'Taux Carac %': f'{round(total_carac/total_tot*100,1) if total_tot>0 else 0}%'
    })

    c1, c2 = st.columns([0.5, 0.5], vertical_alignment='top')
    with c1:
        # Tableau HTML
        h = '<table class="tw omt"><thead><tr>'
        for col in ['Poste de travail','Caractérisé','Non Caractérisé (Anomalies)','Total','Taux Carac %']:
            h += f'<th>{col}</th>'
        h += '</tr></thead><tbody>'
        for row in recap_prep:
            is_total = row['Poste de travail'] == 'TOTAL'
            style = 'font-weight:800;background:#e2e8f0' if is_total else ''
            h += f'<tr style="{style}">'
            for col in ['Poste de travail','Caractérisé','Non Caractérisé (Anomalies)','Total','Taux Carac %']:
                v = row[col]
                cell_style = ''
                if col == 'Caractérisé':
                    cell_style = 'background:#d1fae5;color:#065f46;font-weight:600'
                elif col == 'Non Caractérisé (Anomalies)':
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
        '<div class="stl c">📋 Caractérisation Backlog Planification</div>',
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
            'Non Caractérisé (Anomalies)': non,
            'Total': tot,
            'Taux Carac %': f'{taux}%'
        })

    total_carac = sum(r['Caractérisé'] for r in recap_plan)
    total_non   = sum(r['Non Caractérisé (Anomalies)'] for r in recap_plan)
    total_tot   = total_carac + total_non
    recap_plan.append({
        'Poste de travail': 'TOTAL',
        'Caractérisé': total_carac,
        'Non Caractérisé (Anomalies)': total_non,
        'Total': total_tot,
        'Taux Carac %': f'{round(total_carac/total_tot*100,1) if total_tot>0 else 0}%'
    })

    c3, c4 = st.columns([0.5, 0.5], vertical_alignment='top')
    with c3:
        h = '<table class="tw omt"><thead><tr>'
        for col in ['Poste de travail','Caractérisé','Non Caractérisé (Anomalies)','Total','Taux Carac %']:
            h += f'<th>{col}</th>'
        h += '</tr></thead><tbody>'
        for row in recap_plan:
            is_total = row['Poste de travail'] == 'TOTAL'
            style = 'font-weight:800;background:#e2e8f0' if is_total else ''
            h += f'<tr style="{style}">'
            for col in ['Poste de travail','Caractérisé','Non Caractérisé (Anomalies)','Total','Taux Carac %']:
                v = row[col]
                cell_style = ''
                if col == 'Caractérisé':
                    cell_style = 'background:#d1fae5;color:#065f46;font-weight:600'
                elif col == 'Non Caractérisé (Anomalies)':
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
            'ATPL': 'Attente planification',
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

    # Section : Répartition de l'Âge des Backlogs (Préparation, Planification & Exécution)
    st.markdown(
        '<div class="stl c">⏱️ Répartition de l\'Âge des Backlogs (Préparation, Planification & Exécution)</div>',
        unsafe_allow_html=True
    )
    st.caption("Base : répartition par âge du Backlog Préparation, Planification et Exécution (conforme aux indicateurs consolidés).")

    sf1_p = [p for p in vp if str(p).startswith("SF1")]
    sf2_p = [p for p in vp if str(p).startswith("SF2")]

    tab_tous, tab_sf1, tab_sf2 = st.tabs(["🌐 Tous les postes sélectionnés", "🏭 Division SF1", "🏭 Division SF2"])
    with tab_tous:
        rows_all = build_age_table_rows(vp, df_prep, df_plan, df_exec=df_exec, label_total="TOTAL GÉNÉRAL")
        st.markdown(html_age_dispatch_table(rows_all, include_exec=True), unsafe_allow_html=True)
    with tab_sf1:
        if sf1_p:
            rows_sf1 = build_age_table_rows(sf1_p, df_prep, df_plan, df_exec=df_exec, label_total="TOTAL SF1")
            st.markdown(html_age_dispatch_table(rows_sf1, include_exec=True), unsafe_allow_html=True)
        else:
            st.info("Aucun poste SF1 dans la sélection courante.")
    with tab_sf2:
        if sf2_p:
            rows_sf2 = build_age_table_rows(sf2_p, df_prep, df_plan, df_exec=df_exec, label_total="TOTAL SF2")
            st.markdown(html_age_dispatch_table(rows_sf2, include_exec=True), unsafe_allow_html=True)
        else:
            st.info("Aucun poste SF2 dans la sélection courante.")

    st.markdown('---')

    # Section 3 : Statuts OT
    st.markdown('<div class="stl p">📊 Statuts OT par Poste de Travail</div>', unsafe_allow_html=True)

    st.markdown('<div class="stl s">OT OMS par Poste et Statut OT</div>', unsafe_allow_html=True)
    c5, c6 = st.columns([0.5, 0.5], vertical_alignment='top')
    with c5:
        st.markdown(html_statut_pivot(piv_oms, 'omt'), unsafe_allow_html=True)
    with c6:
        show_pie_pair(piv_oms, 'OT OMS')

    st.markdown('<div class="stl s">OT Thermographie par Poste et Statut OT</div>', unsafe_allow_html=True)
    c7, c8 = st.columns([0.5, 0.5], vertical_alignment='top')
    with c7:
        st.markdown(html_statut_pivot(piv_thm, 'tht'), unsafe_allow_html=True)
    with c8:
        show_pie_pair(piv_thm, 'OT Thermographie')

    st.markdown('<div class="stl s">Tous les OT par Poste et Statut OT</div>', unsafe_allow_html=True)
    c9, c10 = st.columns([0.5, 0.5], vertical_alignment='top')
    with c9:
        st.markdown(html_statut_pivot(piv_all, 'pt'), unsafe_allow_html=True)
    with c10:
        show_pie_pair(piv_all, 'Tous les OT')
