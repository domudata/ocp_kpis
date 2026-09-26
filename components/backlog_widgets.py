# -*- coding: utf-8 -*-
import re
import io
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from components.charts import show_pie_pair, show_simple_pie, PLOTLY_CONFIG
from components.tables import html_generic_pivot, html_statut_pivot
from core.calcul_kpi import build_statut_pivot, get_text_col

# Codes officiels (alignés sur core/calcul_kpi.py — source unique de
# vérité) : ATPL a été retiré de la liste Planif, elle n'a jamais fait
# partie de la spécification officielle.
CODES_PREP_EXACT = {'ATPD', 'ATMR', 'ATER', 'ATRS', 'ATMO'}
CODES_PLAN_EXACT = {'ATEI', 'ATAL', 'ATAS', 'AGAR', 'ATHS'}
ALL_CARAC_EXACT = CODES_PREP_EXACT | CODES_PLAN_EXACT


def match_exact_token(statut, codes: set) -> bool:
    """
    Un OT correspond dès que l'un des codes apparaît N'IMPORTE OÙ dans le
    champ (contains pur, insensible à la casse) — pas de découpage par mot,
    pas de contrainte de position (début/milieu/fin).
    """
    if statut is None or (isinstance(statut, float) and pd.isna(statut)):
        return False
    t = str(statut).upper()
    return any(code in t for code in codes)


def _position_premier_code(texte, codes) -> int:
    """
    Renvoie la position (index) du premier caractère du code trouvé le plus
    tôt dans le texte, parmi 'codes' — ou None si aucun de ces codes n'est
    présent. Sert à départager un OT qui contient à la fois un code Prep et
    un code Planif (demande explicite : compté une seule fois, dans la
    catégorie dont le code apparaît en premier dans le texte).
    """
    if texte is None or (isinstance(texte, float) and pd.isna(texte)):
        return None
    s = str(texte).upper()
    positions = [s.find(c) for c in codes if c in s]
    return min(positions) if positions else None


def _categorie_caract(texte) -> str:
    """
    Classe l'OT en 'PREP' ou 'PLANIF' selon la présence (n'importe où dans
    le texte, "contains" pur — pas obligatoirement au début) de l'un des
    codes ATPD/ATMR/ATER/ATRS/ATMO (Prep) ou ATEI/ATAL/ATAS/AGAR/ATHS
    (Planif). Si le champ contient à la fois un code Prep ET un code
    Planif, l'OT n'est compté qu'UNE SEULE FOIS : dans la catégorie dont le
    code apparaît en premier (position la plus petite) dans le texte.
    Renvoie None si aucun des deux types de code n'est présent.
    """
    pos_prep = _position_premier_code(texte, CODES_PREP_EXACT)
    pos_plan = _position_premier_code(texte, CODES_PLAN_EXACT)
    if pos_prep is None and pos_plan is None:
        return None
    if pos_plan is None:
        return 'PREP'
    if pos_prep is None:
        return 'PLANIF'
    return 'PREP' if pos_prep <= pos_plan else 'PLANIF'


CRPR_KW = ['ATPD', 'ATMR', 'ATRS', 'ATMO', 'ATER']
ATPL_KW = ['ATEI', 'ATAL', 'ATAS', 'AGAR', 'ATHS']
TW_PREV = [350, 290, 300, 310, 360]

DESC_PREP = {
    'ATPD': 'Attente PDR',
    'ATMR': 'Attente marché',
    'ATRS': 'Attente ressources',
    'ATMO': 'Attente moyens ou Outillage',
    'ATER': 'Attente équipement de rechange',
}
DESC_PLAN = {
    'ATEI': 'Attente arrêt équipement ou Installation',
    'ATAL': 'Attente arrêt ligne',
    'ATAS': 'Attente arrêt site',
    'AGAR': 'Attente grand arrêt de révision',
    'ATHS': 'Attente HSE',
}


def _legende_codes(codes: list, desc_map: dict) -> str:
    """
    NOUVEAU (26/09) — légende compacte "CODE = signification" affichée
    sous les graphiques qui n'utilisent que les codes bruts (ATPD, ATMR,
    ...) sur leurs axes, pour que le poste/technicien qui lit le graphique
    sache ce que chaque code représente sans devoir chercher ailleurs.
    """
    items = " · ".join(
        f"<b>{c}</b> = {desc_map.get(c, c)}" for c in codes
    )
    return (
        f'<div style="font-size:12px;color:#64748b;padding:4px 0 10px 0;line-height:1.6;">{items}</div>'
    )


def html_age_dispatch_table(rows, include_exec=False):
    cols = [
        ("Poste de travail", "left", "Poste de travail"),
        ("AGE PREP <1M", "center", "AGE PREP <1M"),
        ("NB <1M", "center", "BASE_P_INF"),
        ("AGE PREP 1-3M", "center", "AGE PREP 1-3M"),
        ("NB 1-3M", "center", "BASE_P_1_3"),
        ("AGE PREP >3M", "center", "AGE PREP >3M"),
        ("NB >3M", "center", "BASE_P_SUP"),
        ("AGE PLANIF <1M", "center", "AGE PLANIF <1M"),
        ("NB <1M", "center", "BASE_L_INF"),
        ("AGE PLANIF 1-3M", "center", "AGE PLANIF 1-3M"),
        ("NB 1-3M", "center", "BASE_L_1_3"),
        ("AGE PLANIF >3M", "center", "AGE PLANIF >3M"),
        ("NB >3M", "center", "BASE_L_SUP"),
    ]
    if include_exec:
        cols.extend([
            ("AGE EXEC <1M", "center", "AGE EXEC <1M"),
            ("NB <1M", "center", "BASE_E_INF"),
            ("AGE EXEC 1-3M", "center", "AGE EXEC 1-3M"),
            ("NB 1-3M", "center", "BASE_E_1_3"),
            ("AGE EXEC >3M", "center", "AGE EXEC >3M"),
            ("NB >3M", "center", "BASE_E_SUP"),
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
        "AGE PREP <1M": "80 %",
        "BASE_P_INF": "",
        "AGE PREP 1-3M": "15 %",
        "BASE_P_1_3": "",
        "AGE PREP >3M": "5 %",
        "BASE_P_SUP": "",
        "AGE PLANIF <1M": "80 %",
        "BASE_L_INF": "",
        "AGE PLANIF 1-3M": "15 %",
        "BASE_L_1_3": "",
        "AGE PLANIF >3M": "5 %",
        "BASE_L_SUP": "",
        "_t": "cible",
    }
    if include_exec:
        cible_row.update({
            "AGE EXEC <1M": "80 %",
            "BASE_E_INF": "",
            "AGE EXEC 1-3M": "15 %",
            "BASE_E_1_3": "",
            "AGE EXEC >3M": "5 %",
            "BASE_E_SUP": "",
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

        t_p_tot += nb_p
        t_p_inf += p_inf
        t_p_1_3 += p_1_3
        t_p_sup += p_sup
        t_l_tot += nb_l
        t_l_inf += l_inf
        t_l_1_3 += l_1_3
        t_l_sup += l_sup
        t_e_tot += nb_e
        t_e_inf += e_inf
        t_e_1_3 += e_1_3
        t_e_sup += e_sup

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


def calc_backlog_caract_rows(df_all: pd.DataFrame, vp: list):
    """
    NOUVEAU (26/09) — remplace l'ancienne comparaison Caractérisé / Non
    Caractérisé. Calcule directement le nombre d'OT par poste et par CODE
    (pas de colonne Non Caractérisé) pour le Backlog Caractérisation
    Préparation et Planification.

    Population (identique pour les 2, indépendante du filtre Période) :
    tout OT non CLOT/TCLO, quel que soit son type ou sa date. Un OT
    contenant à la fois un code Prep et un code Planif n'est compté
    qu'une seule fois, dans la catégorie dont le code apparaît en premier
    dans "Statut utilisateur" (voir _categorie_caract).

    Retourne (prep_rows, prep_cols, plan_rows, plan_cols, df_univers) :
      - prep_cols = ['Poste de travail', 'Total', 'ATPD', 'ATMR', 'ATRS', 'ATMO', 'ATER']
      - plan_cols = ['Poste de travail', 'Total', 'ATEI', 'ATAL', 'ATAS', 'AGAR', 'ATHS']
      - prep_rows / plan_rows : liste de dicts, un par poste de vp + une
        ligne finale de synthèse avec 'Poste de travail' == 'Total' (et
        non 'TOTAL' — libellé choisi pour rester cohérent avec le filtre
        d'exclusion utilisé par core.export_excel.charger_historique_
        depuis_github lors de la relecture de l'historique, qui exclut
        les lignes "Cible" / "Total general" / "Total").
      - df_univers : DataFrame de la population complète (avec la colonne
        'Categorie Caract'), réutilisable pour l'affichage.
    """
    if "Statut OT" in df_all.columns:
        df_univers = df_all[~df_all["Statut OT"].isin(["CLOT", "TCLO"])].copy()
    else:
        _premier_mot_sys = df_all["Statut système"].fillna("").astype(str).str.strip().str.split().str[0]
        df_univers = df_all[~_premier_mot_sys.isin(["CLOT", "TCLO"])].copy()

    df_univers['Categorie Caract'] = df_univers['Statut utilisateur'].apply(_categorie_caract)

    def _extract_kw(statut, kw_list):
        if statut is None or (isinstance(statut, float) and pd.isna(statut)):
            return None
        s = str(statut).upper()
        for kw in kw_list:
            if kw in s:
                return kw
        return None

    prep_codes = list(CRPR_KW)   # ATPD, ATMR, ATRS, ATMO, ATER
    plan_codes = list(ATPL_KW)   # ATEI, ATAL, ATAS, AGAR, ATHS

    df_prep_c = df_univers[df_univers['Categorie Caract'] == 'PREP'].copy()
    df_prep_c['Code'] = df_prep_c['Statut utilisateur'].apply(lambda x: _extract_kw(x, prep_codes))

    df_plan_c = df_univers[df_univers['Categorie Caract'] == 'PLANIF'].copy()
    df_plan_c['Code'] = df_plan_c['Statut utilisateur'].apply(lambda x: _extract_kw(x, plan_codes))

    piv_prep = pd.pivot_table(
        df_prep_c, index='Poste travail princ.', columns='Code',
        values='Ordre', aggfunc='count', fill_value=0
    ).reindex(vp, fill_value=0)
    for c in prep_codes:
        if c not in piv_prep.columns:
            piv_prep[c] = 0

    piv_plan = pd.pivot_table(
        df_plan_c, index='Poste travail princ.', columns='Code',
        values='Ordre', aggfunc='count', fill_value=0
    ).reindex(vp, fill_value=0)
    for c in plan_codes:
        if c not in piv_plan.columns:
            piv_plan[c] = 0

    prep_cols = ['Poste de travail', 'Total'] + prep_codes
    plan_cols = ['Poste de travail', 'Total'] + plan_codes

    prep_rows = []
    for poste in vp:
        row = {'Poste de travail': poste}
        tot = 0
        for c in prep_codes:
            v = int(piv_prep.loc[poste, c]) if poste in piv_prep.index else 0
            row[c] = v
            tot += v
        row['Total'] = tot
        prep_rows.append(row)
    tot_row = {'Poste de travail': 'Total', '_t': 'total'}
    tot_all = 0
    for c in prep_codes:
        s = sum(r[c] for r in prep_rows)
        tot_row[c] = s
        tot_all += s
    tot_row['Total'] = tot_all
    prep_rows.append(tot_row)

    plan_rows = []
    for poste in vp:
        row = {'Poste de travail': poste}
        tot = 0
        for c in plan_codes:
            v = int(piv_plan.loc[poste, c]) if poste in piv_plan.index else 0
            row[c] = v
            tot += v
        row['Total'] = tot
        plan_rows.append(row)
    tot_row2 = {'Poste de travail': 'Total', '_t': 'total'}
    tot_all2 = 0
    for c in plan_codes:
        s = sum(r[c] for r in plan_rows)
        tot_row2[c] = s
        tot_all2 += s
    tot_row2['Total'] = tot_all2
    plan_rows.append(tot_row2)

    return prep_rows, prep_cols, plan_rows, plan_cols, df_univers


def _html_backlog_caract_table(rows, cols, desc_map, accent_color):
    """Rendu HTML du nouveau tableau Poste de travail | Total | <codes>."""
    h = '<table class="tw omt"><thead><tr>'
    for col in cols:
        h += f'<th>{col}</th>'
    h += '</tr></thead><tbody>'
    for row in rows:
        is_total = row.get('_t') == 'total'
        style = 'font-weight:800;background:#e2e8f0' if is_total else ''
        h += f'<tr style="{style}">'
        for col in cols:
            v = row.get(col, 0)
            cell_style = ''
            if col == 'Total':
                cell_style = f'background:#e0f2fe;color:{accent_color};font-weight:700'
            elif col != 'Poste de travail' and not is_total and v not in (0, "0"):
                cell_style = 'font-weight:600'
            h += f'<td style="text-align:center;{cell_style}">{v}</td>'
        h += '</tr>'
    h += '</tbody></table>'
    return h


def _bar_traitement_par_code(res_cat: dict, codes: list, titre: str, key: str) -> None:
    """
    NOUVEAU (26/09) — bar chart horizontal 2 couleurs (vert = Traité,
    orange = Restant) montrant le % de traitement du Backlog Caract, par
    code, entre l'avant-dernière et la dernière extraction enregistrée
    dans l'historique GitHub.

    res_cat : dict {code: {"precedent": int|None, "actuel": int,
                            "traite": int, "pct_traite": float}}
    (sous-dict "prep" ou "planif" du retour de
    calculate_traitement_backlog_caract).
    """
    codes_dispo = [c for c in codes if c in res_cat]
    if not codes_dispo:
        st.markdown('<div style="padding:12px;color:#94a3b8;">Données insuffisantes pour ce graphique.</div>',
                    unsafe_allow_html=True)
        return

    actuel = [res_cat[c]["actuel"] for c in codes_dispo]
    traite = [res_cat[c]["traite"] for c in codes_dispo]
    precedent = [res_cat[c]["precedent"] if res_cat[c]["precedent"] is not None else res_cat[c]["actuel"] for c in codes_dispo]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=codes_dispo, x=traite, orientation='h', name="Traité",
        marker=dict(color="#10b981", line=dict(color='white', width=1)),
        text=[str(v) if v > 0 else "" for v in traite], textposition='inside',
        textfont=dict(color='white', size=12),
    ))
    fig.add_trace(go.Bar(
        y=codes_dispo, x=actuel, orientation='h', name="Restant",
        marker=dict(color="#f97316", line=dict(color='white', width=1)),
        text=[str(v) for v in actuel], textposition='inside',
        textfont=dict(color='white', size=12),
    ))
    for c, p, a, t in zip(codes_dispo, precedent, actuel, traite):
        pct = res_cat[c]["pct_traite"]
        base = p if p else a
        fig.add_annotation(x=base + max(base, 1) * 0.02, y=c, text=f"  {pct}% traité",
                            showarrow=False, xanchor='left', font=dict(size=12, color='black'))

    fig.update_layout(
        barmode='stack', title=titre, height=max(260, 46 * len(codes_dispo) + 90),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12, family='Inter'),
                   fixedrange=True, automargin=True),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", fixedrange=True, title="Nombre d'OT"),
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, x=0.5, xanchor="center"),
        margin=dict(t=40, b=60, l=20, r=110),
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=key)


def _counts_lanc_cree_par_code(df_univers: pd.DataFrame, categorie: str, kw_list: list) -> dict:
    """
    NOUVEAU (26/09) — pour chaque code (Prep ou Planif), compte combien
    d'OT caractérisés avec ce code sont au statut LANC et combien sont au
    statut CRÉÉ (les deux seuls statuts possibles ici puisque df_univers
    exclut déjà CLOT/TCLO). Sert au nouveau graphique demandé montrant la
    répartition LANC/CRÉÉ par type de code.
    """
    resultat = {}
    if df_univers is None or df_univers.empty:
        return {c: {"LANC": 0, "CREE": 0} for c in kw_list}

    sub = df_univers[df_univers['Categorie Caract'] == categorie].copy()
    if sub.empty:
        return {c: {"LANC": 0, "CREE": 0} for c in kw_list}

    sub['Code'] = sub['Statut utilisateur'].apply(
        lambda x: next((k for k in kw_list if k in str(x).upper()), None)
    )

    if 'Statut OT' in sub.columns:
        statut_simple = sub['Statut OT'].fillna('').astype(str).str.strip().str.upper()
    else:
        statut_simple = sub['Statut système'].fillna('').astype(str).str.strip().str.split().str[0].str.upper()

    for code in kw_list:
        mask = sub['Code'] == code
        resultat[code] = {
            "LANC": int((mask & (statut_simple == 'LANC')).sum()),
            "CREE": int((mask & (statut_simple == 'CRÉÉ')).sum()),
        }
    return resultat


def _bar_lanc_cree_par_code(counts: dict, codes: list, titre: str, key: str) -> None:
    """
    NOUVEAU (26/09) — bar chart horizontal empilé montrant, pour chaque
    code, combien d'OT sont au statut LANC (bleu) et combien sont au
    statut CRÉÉ (violet).
    """
    codes_dispo = [c for c in codes if c in counts]
    if not codes_dispo or all((counts[c]["LANC"] + counts[c]["CREE"]) == 0 for c in codes_dispo):
        st.markdown('<div style="padding:12px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)
        return

    lanc = [counts[c]["LANC"] for c in codes_dispo]
    cree = [counts[c]["CREE"] for c in codes_dispo]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=codes_dispo, x=lanc, orientation='h', name="LANC",
        marker=dict(color="#3b82f6", line=dict(color='white', width=1)),
        text=[str(v) if v > 0 else "" for v in lanc], textposition='inside',
        textfont=dict(color='white', size=12),
    ))
    fig.add_trace(go.Bar(
        y=codes_dispo, x=cree, orientation='h', name="CRÉÉ",
        marker=dict(color="#8b5cf6", line=dict(color='white', width=1)),
        text=[str(v) if v > 0 else "" for v in cree], textposition='inside',
        textfont=dict(color='white', size=12),
    ))
    for c, l, r in zip(codes_dispo, lanc, cree):
        tot = l + r
        fig.add_annotation(x=tot + max(tot, 1) * 0.02, y=c, text=f"  {tot} OT",
                            showarrow=False, xanchor='left', font=dict(size=12, color='black'))

    fig.update_layout(
        barmode='stack', title=titre, height=max(260, 46 * len(codes_dispo) + 90),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12, family='Inter'),
                   fixedrange=True, automargin=True),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", fixedrange=True, title="Nombre d'OT"),
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, x=0.5, xanchor="center"),
        margin=dict(t=40, b=60, l=20, r=110),
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=key)


def _build_backlog_download(prep_rows: list, prep_cols: list, plan_rows: list, plan_cols: list) -> bytes:
    """
    Construit un classeur Excel (2 feuilles) pour le téléchargement du
    backlog Caractérisation Préparation / Planification — indépendant du
    filtre période, nouveau format Total + par code (demande explicite).
    """
    buf = io.BytesIO()
    df_prep_export = pd.DataFrame(prep_rows)[prep_cols]
    df_plan_export = pd.DataFrame(plan_rows)[plan_cols]
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_prep_export.to_excel(writer, sheet_name="Backlog Preparation", index=False)
        df_plan_export.to_excel(writer, sheet_name="Backlog Planification", index=False)
    buf.seek(0)
    return buf.getvalue()


def render_backlog_tab(dfp: pd.DataFrame, vp: list, df_toutes_dates: pd.DataFrame = None,
                        hist_df: pd.DataFrame = None) -> None:
    """Rendu complet de l'onglet Backlog."""

    df_all = df_toutes_dates.copy() if df_toutes_dates is not None else dfp.copy()
    _zcor = df_all[df_all["Type d'ordre"] == "ZCOR"].copy()

    # ── Backlog Caractérisation Préparation / Planification ────────────
    # REDÉFINI (demande explicite du 26/09) — supprime toute comparaison
    # Caractérisé / Non Caractérisé. Nouveau format de tableau :
    #   Poste de travail | Total | <une colonne par code>
    # Population : indépendante du filtre Période (calculée sur
    # df_toutes_dates) — tout OT non CLOT/TCLO, quel que soit son type ou
    # sa date. Voir calc_backlog_caract_rows pour le détail des règles.
    prep_rows, prep_cols, plan_rows, plan_cols, df_univers = calc_backlog_caract_rows(df_all, vp)

    def _piv_type(categorie, kw_list):
        sub = df_univers[df_univers['Categorie Caract'] == categorie].copy() if not df_univers.empty else pd.DataFrame()
        if sub.empty:
            return pd.DataFrame()
        sub['Code'] = sub['Statut utilisateur'].apply(
            lambda x: next((k for k in kw_list if k in str(x).upper()), None)
        )
        piv = pd.pivot_table(sub, index='Poste travail princ.', columns='Code',
                              values='Ordre', aggfunc='count', fill_value=0)
        return piv.reindex(vp, fill_value=0)

    piv_prep_type = _piv_type('PREP', CRPR_KW)
    piv_plan_type = _piv_type('PLANIF', ATPL_KW)

    # ── % de traitement (26/09) — comparé à l'avant-dernière extraction ──
    try:
        from core.backlog_caract_history import calculate_traitement_backlog_caract
        res_traitement = calculate_traitement_backlog_caract(
            hist_df, list(CRPR_KW), list(ATPL_KW)
        )
    except Exception:
        res_traitement = {"prep": {}, "planif": {}, "date_prec": None, "date_act": None}

    counts_lanc_cree_prep = _counts_lanc_cree_par_code(df_univers, 'PREP', CRPR_KW)
    counts_lanc_cree_plan = _counts_lanc_cree_par_code(df_univers, 'PLANIF', ATPL_KW)

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

    text_col = get_text_col(dfp)
    oms_df = dfp[dfp[text_col].astype(str).str.contains('OMS', case=False, na=False)] if text_col else pd.DataFrame()
    thm_df = dfp[dfp[text_col].astype(str).str.contains('THERMO|THERMOGRAPH', case=False, na=False)] if text_col else pd.DataFrame()
    piv_oms = build_statut_pivot(oms_df, vp)
    piv_thm = build_statut_pivot(thm_df, vp)
    piv_all = build_statut_pivot(dfp, vp)

    # ═══ Backlog Caractérisation Préparation ═══
    st.markdown(
        '<div class="stl c">📋 Caractérisation Backlog Préparation</div>',
        unsafe_allow_html=True
    )
    st.caption(
        "🔓 Indépendant du filtre Période (calculé sur toutes les dates, tous types d'OT) — "
        "Population = tout OT non CLOT/TCLO · Caractérisé = « Statut utilisateur » contient "
        "ATPD/ATMR/ATER/ATRS/ATMO (n'importe où) · un OT contenant aussi un code Planif n'est "
        "compté ici que si le code Prep apparaît en premier."
    )

    c1, c2 = st.columns([0.5, 0.5], vertical_alignment='top')
    with c1:
        st.markdown(_html_backlog_caract_table(prep_rows, prep_cols, DESC_PREP, "#065f46"), unsafe_allow_html=True)
    with c2:
        if not piv_prep_type.empty and piv_prep_type.sum().sum() > 0:
            show_simple_pie(piv_prep_type, 'Répartition par Type de Caractérisation (Prep)', keep_non_carac=False)
        else:
            st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)

        # NOUVEAU (26/09) — placé directement sous le pie de cette catégorie,
        # chaque graphique séparé visuellement avec son propre titre
        st.markdown('<hr style="margin:14px 0;border-color:#e2e8f0;">', unsafe_allow_html=True)
        st.markdown('<div class="stl s">📈 Taux de traitement — Préparation</div>', unsafe_allow_html=True)
        _bar_traitement_par_code(res_traitement.get("prep", {}), CRPR_KW,
                                  "Taux de traitement — Préparation", key="bar_traite_prep")
        st.markdown(_legende_codes(CRPR_KW, DESC_PREP), unsafe_allow_html=True)

        st.markdown('<hr style="margin:14px 0;border-color:#e2e8f0;">', unsafe_allow_html=True)
        st.markdown('<div class="stl s">🔵 Répartition LANC / CRÉÉ — Préparation</div>', unsafe_allow_html=True)
        _bar_lanc_cree_par_code(counts_lanc_cree_prep, CRPR_KW,
                                 "LANC / CRÉÉ par code — Préparation", key="bar_lanc_cree_prep")
        st.markdown(_legende_codes(CRPR_KW, DESC_PREP), unsafe_allow_html=True)

        # DÉPLACÉ (26/09) — mis à la place du graphique LANC/CRÉÉ, dans la
        # même colonne, au lieu d'un bloc pleine largeur séparé
        st.markdown('<hr style="margin:14px 0;border-color:#e2e8f0;">', unsafe_allow_html=True)
        st.markdown('<div class="stl s">Types de caractérisation — Préparation</div>', unsafe_allow_html=True)
        h = '<table class="tw omt"><thead><tr><th>Type</th><th>Description</th><th>Nb OT</th><th>%</th></tr></thead><tbody>'
        total_prep_codes = sum(prep_rows[-1][c] for c in CRPR_KW)
        for typ in CRPR_KW:
            cnt = prep_rows[-1][typ]
            pct = round(cnt / total_prep_codes * 100, 1) if total_prep_codes else 0.0
            desc = DESC_PREP.get(typ, typ)
            h += f'<tr><td style="font-weight:700;color:#059669">{typ}</td><td>{desc}</td><td style="text-align:center;font-weight:600">{cnt}</td><td style="text-align:center">{pct}%</td></tr>'
        h += '</tbody></table>'
        st.markdown(h, unsafe_allow_html=True)

    st.markdown('---')

    # ═══ Backlog Caractérisation Planification ═══
    st.markdown(
        '<div class="stl c">📋 Caractérisation Backlog Planification</div>',
        unsafe_allow_html=True
    )
    st.caption(
        "🔓 Indépendant du filtre Période (calculé sur toutes les dates, tous types d'OT) — "
        "Population = tout OT non CLOT/TCLO · Caractérisé = « Statut utilisateur » contient "
        "ATEI/ATAL/ATAS/AGAR/ATHS (n'importe où) · un OT contenant aussi un code Prep n'est "
        "compté ici que si le code Planif apparaît en premier."
    )

    c3, c4 = st.columns([0.5, 0.5], vertical_alignment='top')
    with c3:
        st.markdown(_html_backlog_caract_table(plan_rows, plan_cols, DESC_PLAN, "#1e40af"), unsafe_allow_html=True)
    with c4:
        if not piv_plan_type.empty and piv_plan_type.sum().sum() > 0:
            show_simple_pie(piv_plan_type, 'Répartition par Type de Caractérisation (Plan)', keep_non_carac=False)
        else:
            st.markdown('<div style="padding:20px;color:#94a3b8;">Aucune donnée</div>', unsafe_allow_html=True)

        # NOUVEAU (26/09) — placé directement sous le pie de cette catégorie,
        # chaque graphique séparé visuellement avec son propre titre
        st.markdown('<hr style="margin:14px 0;border-color:#e2e8f0;">', unsafe_allow_html=True)
        st.markdown('<div class="stl s">📈 Taux de traitement — Planification</div>', unsafe_allow_html=True)
        _bar_traitement_par_code(res_traitement.get("planif", {}), ATPL_KW,
                                  "Taux de traitement — Planification", key="bar_traite_planif")
        st.markdown(_legende_codes(ATPL_KW, DESC_PLAN), unsafe_allow_html=True)

        st.markdown('<hr style="margin:14px 0;border-color:#e2e8f0;">', unsafe_allow_html=True)
        st.markdown('<div class="stl s">🔵 Répartition LANC / CRÉÉ — Planification</div>', unsafe_allow_html=True)
        _bar_lanc_cree_par_code(counts_lanc_cree_plan, ATPL_KW,
                                 "LANC / CRÉÉ par code — Planification", key="bar_lanc_cree_planif")
        st.markdown(_legende_codes(ATPL_KW, DESC_PLAN), unsafe_allow_html=True)

        # DÉPLACÉ (26/09) — mis à la place du graphique LANC/CRÉÉ, dans la
        # même colonne, au lieu d'un bloc pleine largeur séparé
        st.markdown('<hr style="margin:14px 0;border-color:#e2e8f0;">', unsafe_allow_html=True)
        st.markdown('<div class="stl s">Types de caractérisation — Planification</div>', unsafe_allow_html=True)
        h = '<table class="tw omt"><thead><tr><th>Type</th><th>Description</th><th>Nb OT</th><th>%</th></tr></thead><tbody>'
        total_plan_codes = sum(plan_rows[-1][c] for c in ATPL_KW)
        for typ in ATPL_KW:
            cnt = plan_rows[-1][typ]
            pct = round(cnt / total_plan_codes * 100, 1) if total_plan_codes else 0.0
            desc = DESC_PLAN.get(typ, typ)
            h += f'<tr><td style="font-weight:700;color:#2563eb">{typ}</td><td>{desc}</td><td style="text-align:center;font-weight:600">{cnt}</td><td style="text-align:center">{pct}%</td></tr>'
        h += '</tbody></table>'
        st.markdown(h, unsafe_allow_html=True)

    # ── Téléchargement du backlog Caractérisation (Prep + Planif) ──────
    st.markdown("")
    try:
        xlsx_bytes = _build_backlog_download(prep_rows, prep_cols, plan_rows, plan_cols)
        st.download_button(
            label="⬇️ Télécharger ce backlog (Excel)",
            data=xlsx_bytes,
            file_name="backlog_caracterisation_prep_planif.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_backlog_carac",
        )
    except Exception as e:
        st.caption(f"⚠️ Téléchargement indisponible ({e}).")

    st.markdown('---')

    st.markdown('<div class="stl p">📊 Statuts OT par Poste de Travail</div>', unsafe_allow_html=True)

    st.markdown('<div class="stl s">OT OMS par Poste et Statut OT</div>', unsafe_allow_html=True)
    c7, c8 = st.columns([0.5, 0.5], vertical_alignment='top')
    with c7:
        st.markdown(html_statut_pivot(piv_oms, 'omt'), unsafe_allow_html=True)
    with c8:
        show_pie_pair(piv_oms, 'OT OMS')

    st.markdown('<div class="stl s">OT Thermographie par Poste et Statut OT</div>', unsafe_allow_html=True)
    c9, c10 = st.columns([0.5, 0.5], vertical_alignment='top')
    with c9:
        st.markdown(html_statut_pivot(piv_thm, 'tht'), unsafe_allow_html=True)
    with c10:
        show_pie_pair(piv_thm, 'OT Thermographie')

    st.markdown('<div class="stl s">Tous les OT par Poste et Statut OT</div>', unsafe_allow_html=True)
    c11, c12 = st.columns([0.5, 0.5], vertical_alignment='top')
    with c11:
        st.markdown(html_statut_pivot(piv_all, 'pt'), unsafe_allow_html=True)
    with c12:
        show_pie_pair(piv_all, 'Tous les OT')
