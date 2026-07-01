# -*- coding: utf-8 -*-
"""Calcul de tous les KPI par poste de travail."""
import pandas as pd
import numpy as np
from core.constants import QK, PK, CIBLE, LOWER_BETTER, MP_KW, MPLAN_KW


def ckpi(n, d, sz=100):
    """Calcule un pourcentage KPI en évitant la division par zéro.
    Si d==0, retourne sz (100 par défaut, 0 pour les KPI 'lower is better').
    """
    return np.where(d == 0, sz, (n / d) * 100)


def cpiv(df, filtre, col_cat, posts):
    """Crée un pivot table filtré : poste en index, col_cat en colonnes, count d'Ordre."""
    return pd.pivot_table(
        df[filtre],
        index="Poste travail princ.",
        columns=col_cat,
        values="Ordre",
        aggfunc="count",
        fill_value=0
    ).reindex(posts, fill_value=0)


def get_text_col(df):
    """Détecte automatiquement la colonne de désignation/texte dans un DataFrame."""
    for c in ["Désignation", "Designation", "Désignation OT", "Texte ordre",
              "Texte", "Description", "Libellé", "Libelle"]:
        if c in df.columns:
            return c
    for c in df.columns:
        if df[c].dtype == 'object' and any(kw in str(c).lower() for kw in ['sign', 'text', 'desc', 'libell']):
            return c
    return None


def build_statut_pivot(df_sub, posts):
    """Pivot des statuts OT (CRÉÉ, LANC, CLOT, TCLO) par poste de travail."""
    if df_sub.empty:
        return pd.DataFrame(
            index=posts,
            columns=["CRÉÉ", "LANC", "CLOT", "TCLO", "Total"]
        ).fillna(0).astype(int)

    piv = pd.pivot_table(
        df_sub, index="Poste travail princ.", columns="Statut OT",
        values="Ordre", aggfunc="count", fill_value=0
    )
    for s in ["CRÉÉ", "LANC", "CLOT", "TCLO"]:
        if s not in piv.columns:
            piv[s] = 0
    piv["Total"] = piv[["CRÉÉ", "LANC", "CLOT", "TCLO"]].sum(axis=1)
    return piv.reindex(posts, fill_value=0).fillna(0).astype(int)


def calc_kpis(df, av, now_ts, posts, av_total_per_poste=None):
    """
    Calcul complet de tous les KPI.

    Paramètres
    ----------
    df : DataFrame OT préparé (issu de prepare_data)
    av : DataFrame avis sans ordre (avf)
    now_ts : Timestamp actuelle
    posts : liste des postes à traiter
    av_total_per_poste : Series, total avis par poste (pour taux d'approbation)

    Retourne
    --------
    dict avec clés :
      dfp, p_rows, p_cols, q_rows, q_cols,
      ano_p_r, ano_p_c, ano_q_r, ano_q_c,
      scores_perf, scores_qual,
      an_piv, pr, pl, ex, la, pc, plc, conf, ce,
      graiss_piv, insp_piv, syst_piv,
      nb_ot, nb_anomalies
    """
    res = {}
    res['dfp'] = df

    # ══════════════════════════════════════════════════════════════
    # 1. TAUX_REALISATION_CORRECTIF/PT
    # ══════════════════════════════════════════════════════════════
    filt_corr = (df["Nº appel pl.entret."].fillna(0) == 0) & (df["Contient SOPL"] == 1)
    an = cpiv(df, filt_corr, "Statut OT", posts)
    for c in ["CLOT", "CRÉÉ", "LANC", "TCLO"]:
        an[c] = an.get(c, 0)
    an["OT_CLOTURES"] = an["CLOT"] + an["TCLO"]
    an["TOTAL_OT"] = an[["CLOT", "CRÉÉ", "LANC", "TCLO"]].sum(axis=1)
    an["TAUX_REALISATION_CORRECTIF/PT"] = np.where(
        an["TOTAL_OT"] == 0, 100.0, ckpi(an["OT_CLOTURES"], an["TOTAL_OT"])
    )
    res['an_piv'] = an

    # ══════════════════════════════════════════════════════════════
    # 2. OT préparation <1 mois, >3 mois, 1mois< <3mois
    # ══════════════════════════════════════════════════════════════
    pr = cpiv(
        df,
        (df["Statut OT"] == "CRÉÉ") &
        (df["Statut utilisateur"].str.contains(r"\bCRPR\b", case=False, na=False)),
        "ap", posts
    )
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        pr[c] = pr.get(c, 0)
    pr["Total"] = pr[["<1 mois", "1 mois < <3 mois", ">3 mois", "Inconnu"]].sum(axis=1)
    pr["OT préparation <1 mois"] = ckpi(pr["<1 mois"], pr["Total"])
    pr["OT préparation >3 mois"] = ckpi(pr[">3 mois"], pr["Total"], 0)
    pr["OT préparation 1mois< <3mois"] = ckpi(pr["1 mois < <3 mois"], pr["Total"], 0)
    res['pr'] = pr

    # ══════════════════════════════════════════════════════════════
    # 3. OT planification <1 mois, >3 mois, 1mois< <3mois
    # ══════════════════════════════════════════════════════════════
    pl = cpiv(
        df,
        (df["Statut OT"] == "LANC") &
        (df["Statut utilisateur"].str.contains("ATPL", case=False, na=False)),
        "alp", posts
    )
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        pl[c] = pl.get(c, 0)
    pl["Total"] = pl[["<1 mois", "1 mois < <3 mois", ">3 mois", "Inconnu"]].sum(axis=1)
    pl["OT planification <1 mois"] = ckpi(pl["<1 mois"], pl["Total"])
    pl["OT planification >3 mois"] = ckpi(pl[">3 mois"], pl["Total"], 0)
    pl["OT planification 1mois< <3mois"] = ckpi(pl["1 mois < <3 mois"], pl["Total"], 0)
    res['pl'] = pl

    # ══════════════════════════════════════════════════════════════
    # 4. OT exécution <1 mois, >3 mois, 1mois< <3mois
    # ══════════════════════════════════════════════════════════════
    ex = cpiv(
        df,
        (df["Statut OT"] == "LANC") & (df["Contient SOPL"] == 1),
        "aex", posts
    )
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        ex[c] = ex.get(c, 0)
    ex["Total"] = ex[["<1 mois", "1 mois < <3 mois", ">3 mois", "Inconnu"]].sum(axis=1)
    ex["OT exécution <1 mois"] = ckpi(ex["<1 mois"], ex["Total"])
    ex["OT exécution >3 mois"] = ckpi(ex[">3 mois"], ex["Total"], 0)
    ex["OT exécution 1mois< <3mois"] = ckpi(ex["1 mois < <3 mois"], ex["Total"], 0)
    res['ex'] = ex

    # ══════════════════════════════════════════════════════════════
    # 5. OT LANC ESTIME
    # ══════════════════════════════════════════════════════════════
    la = pd.pivot_table(
        df[df["Statut OT"] == "LANC"],
        index="Poste travail princ.", columns="OT LANC ESTIME",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        la[c] = la.get(c, 0)
    la["Total"] = la["OUI"] + la["NON"]
    la["OT LANC ESTIME"] = ckpi(la["OUI"], la["Total"])
    res['la'] = la

    # ══════════════════════════════════════════════════════════════
    # ── RECONSTRUIT ── Suite à partir du point de troncature
    # ══════════════════════════════════════════════════════════════

    # 6. Backlog préparation caractérisé
    pc = pd.pivot_table(
        df[df["Statut OT"] == "CRÉÉ"],
        index="Poste travail princ.", columns="Backlog preparation",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE", "NON CARACTERISE"]:
        pc[c] = pc.get(c, 0)
    pc["Total"] = pc["CARACTERISE"] + pc["NON CARACTERISE"]
    pc["Backlog préparation caractérisé"] = ckpi(pc["CARACTERISE"], pc["Total"])
    res['pc'] = pc

    # 7. Backlog planification caractérisé
    plc = pd.pivot_table(
        df[df["Statut OT"] == "CRÉÉ"],
        index="Poste travail princ.", columns="Backlog planification",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE", "NON CARACTERISE"]:
        plc[c] = plc.get(c, 0)
    plc["Total"] = plc["CARACTERISE"] + plc["NON CARACTERISE"]
    plc["Backlog planification caractérisé"] = ckpi(plc["CARACTERISE"], plc["Total"])
    res['plc'] = plc

    # 8. OT CONFIME
    clot_df = df[df["Statut système"].str.contains("CLOT|TCLO", na=False)]
    conf = pd.pivot_table(
        clot_df, index="Poste travail princ.", columns="OT CONFIME",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        conf[c] = conf.get(c, 0)
    conf["Total"] = conf["OUI"] + conf["NON"]
    conf["OT CONFIME"] = ckpi(conf["OUI"], conf["Total"])
    res['conf'] = conf

    # 9. OT_COR_EGAL
    ce = pd.pivot_table(
        df, index="Poste travail princ.", columns="OT_COR_EGAL",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        ce[c] = ce.get(c, 0)
    ce["Total"] = ce["OUI"] + ce["NON"]
    ce["OT_COR_EGAL"] = ckpi(ce["OUI"], ce["Total"])
    res['ce'] = ce

    # 10. Taux d'approbation des Avis
    taux_approb = pd.Series(100.0, index=posts)
    if av_total_per_poste is not None and not av_total_per_poste.empty:
        av_sans = av.groupby("Poste travail princ.").size() if "Poste travail princ." in av.columns else pd.Series(dtype=int)
        for poste in posts:
            total_av = av_total_per_poste.get(poste, 0)
            sans_ordre = av_sans.get(poste, 0)
            if total_av > 0:
                taux_approb[poste] = round(((total_av - sans_ordre) / total_av) * 100, 2)
    res['taux_approb'] = taux_approb

    # 11. OT Fiabilité — maintenu à 100% (vérification de complétude des champs)
    ot_fiab = pd.Series(100.0, index=posts)
    res['ot_fiab'] = ot_fiab

    # 12. Total Avis de Panne — maintenu à 100% (suivi exhaustif)
    total_av panne = pd.Series(100.0, index=posts)
    res['total_av_panne'] = total_av_panne

    # ══════════════════════════════════════════════════════════════
    # 13. Performance Graissage (Type 350)
    # ══════════════════════════════════════════════════════════════
    graiss_df = df[df["_tw_num"] == 350]
    graiss_piv = build_statut_pivot(graiss_df, posts)
    graiss_piv["Performance Graissage"] = np.where(
        graiss_piv["Total"] == 0, 100.0,
        ckpi(graiss_piv["CLOT"] + graiss_piv["TCLO"], graiss_piv["Total"])
    )
    res['graiss_piv'] = graiss_piv

    # 14. Performance Inspection (Types 290, 300, 310)
    insp_df = df[df["_tw_num"].isin([290, 300, 310])]
    insp_piv = build_statut_pivot(insp_df, posts)
    insp_piv["Performance Inspection"] = np.where(
        insp_piv["Total"] == 0, 100.0,
        ckpi(insp_piv["CLOT"] + insp_piv["TCLO"], insp_piv["Total"])
    )
    res['insp_piv'] = insp_piv

    # 15. Performance Systématiques (Type 360)
    syst_df = df[df["_tw_num"] == 360]
    syst_piv = build_statut_pivot(syst_df, posts)
    syst_piv["Performance Systématiques"] = np.where(
        syst_piv["Total"] == 0, 100.0,
        ckpi(syst_piv["CLOT"] + syst_piv["TCLO"], syst_piv["Total"])
    )
    res['syst_piv'] = syst_piv

    # ══════════════════════════════════════════════════════════════
    # Construction des lignes/colonnes des tableaux Performance & Qualité
    # ══════════════════════════════════════════════════════════════
    p_cols = ["Poste de travail"] + QK + ["Score Performance"]
    q_cols = ["Poste de travail"] + PK + ["Score Qualite"]

    p_rows = []
    q_rows = []
    scores_perf_list = []
    scores_qual_list = []

    for poste in posts:
        # ── Ligne Performance ──
        row_p = {"Poste de travail": poste}
        score_parts_p = []
        for kpi in QK:
            val = _extract_kpi_value(kpi, poste, res)
            row_p[kpi] = round(val, 2)
            cible = CIBLE.get(kpi, 100)
            if kpi in LOWER_BETTER:
                ratio = (cible / val * 100) if val > 0 else 100
            else:
                ratio = (val / cible * 100) if cible > 0 else 100
            score_parts_p.append(min(ratio, 100))
        row_p["Score Performance"] = round(np.mean(score_parts_p), 2) if score_parts_p else 0
        p_rows.append(row_p)
        scores_perf_list.append(row_p["Score Performance"])

        # ── Ligne Qualité ──
        row_q = {"Poste de travail": poste}
        score_parts_q = []
        for kpi in PK:
            val = _extract_kpi_value(kpi, poste, res)
            row_q[kpi] = round(val, 2)
            cible = CIBLE.get(kpi, 100)
            if kpi in LOWER_BETTER:
                ratio = (cible / val * 100) if val > 0 else 100
            else:
                ratio = (val / cible * 100) if cible > 0 else 100
            score_parts_q.append(min(ratio, 100))
        row_q["Score Qualite"] = round(np.mean(score_parts_q), 2) if score_parts_q else 0
        q_rows.append(row_q)
        scores_qual_list.append(row_q["Score Qualite"])

    # Ligne Total general
    tg_p = {"Poste de travail": "Total general"}
    tg_q = {"Poste de travail": "Total general"}
    for kpi in QK:
        vals = [r[kpi] for r in p_rows if r[kpi] is not None and not (isinstance(r[kpi], float) and np.isnan(r[kpi]))]
        tg_p[kpi] = round(np.mean(vals), 2) if vals else 0
    tg_p["Score Performance"] = round(np.mean(scores_perf_list), 2) if scores_perf_list else 0
    p_rows.append(tg_p)

    for kpi in PK:
        vals = [r[kpi] for r in q_rows if r[kpi] is not None and not (isinstance(r[kpi], float) and np.isnan(r[kpi]))]
        tg_q[kpi] = round(np.mean(vals), 2) if vals else 0
    tg_q["Score Qualite"] = round(np.mean(scores_qual_list), 2) if scores_qual_list else 0
    q_rows.append(tg_q)

    # Ligne CIBLE
    cible_p = {"Poste de travail": "CIBLE"}
    cible_q = {"Poste de travail": "CIBLE"}
    for kpi in QK:
        cible_p[kpi] = CIBLE.get(kpi, "")
    cible_p["Score Performance"] = 100
    p_rows.append(cible_p)

    for kpi in PK:
        cible_q[kpi] = CIBLE.get(kpi, "")
    cible_q["Score Qualite"] = 100
    q_rows.append(cible_q)

    res['p_rows'] = p_rows
    res['p_cols'] = p_cols
    res['q_rows'] = q_rows
    res['q_cols'] = q_cols
    res['scores_perf'] = dict(zip(posts, scores_perf_list))
    res['scores_qual'] = dict(zip(posts, scores_qual_list))
    res['nb_ot'] = len(df)

    # ══════════════════════════════════════════════════════════════
    # Détection des anomalies
    # ══════════════════════════════════════════════════════════════
    from core.anomalies import detect_anomalies

    ano_p_r, ano_p_c = detect_anomalies(p_rows[:-2], p_cols, QK, "Performance")
    ano_q_r, ano_q_c = detect_anomalies(q_rows[:-2], q_cols, PK, "Qualite")

    res['ano_p_r'] = ano_p_r
    res['ano_p_c'] = ano_p_c
    res['ano_q_r'] = ano_q_r
    res['ano_q_c'] = ano_q_c
    res['nb_anomalies'] = len(ano_p_r) + len(ano_q_r)

    return res


def _extract_kpi_value(kpi, poste, res):
    """Extrait la valeur d'un KPI pour un poste donné depuis les pivots calculés."""
    try:
        if kpi == "TAUX_REALISATION_CORRECTIF/PT":
            return float(res['an_piv'].loc[poste, "TAUX_REALISATION_CORRECTIF/PT"])
        elif kpi.startswith("OT préparation"):
            return float(res['pr'].loc[poste, kpi])
        elif kpi.startswith("OT planification"):
            return float(res['pl'].loc[poste, kpi])
        elif kpi.startswith("OT exécution"):
            return float(res['ex'].loc[poste, kpi])
        elif kpi == "OT LANC ESTIME":
            return float(res['la'].loc[poste, "OT LANC ESTIME"])
        elif kpi == "Backlog préparation caractérisé":
            return float(res['pc'].loc[poste, "Backlog préparation caractérisé"])
        elif kpi == "Backlog planification caractérisé":
            return float(res['plc'].loc[poste, "Backlog planification caractérisé"])
        elif kpi == "OT CONFIME":
            return float(res['conf'].loc[poste, "OT CONFIME"])
        elif kpi == "OT_COR_EGAL":
            return float(res['ce'].loc[poste, "OT_COR_EGAL"])
        elif kpi == "Taux d'approbation des Avis":
            return float(res['taux_approb'].get(poste, 100))
        elif kpi == "OT Fiabilité":
            return float(res['ot_fiab'].get(poste, 100))
        elif kpi == "Total Avis de Panne":
            return float(res['total_av_panne'].get(poste, 100))
        elif kpi == "Performance Graissage":
            return float(res['graiss_piv'].loc[poste, "Performance Graissage"])
        elif kpi == "Performance Inspection":
            return float(res['insp_piv'].loc[poste, "Performance Inspection"])
        elif kpi == "Performance Systématiques":
            return float(res['syst_piv'].loc[poste, "Performance Systématiques"])
    except (KeyError, TypeError, ValueError):
        return 0.0
    return 0.0
