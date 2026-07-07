# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from core.constants import QK, PK, CIBLE, LOWER_BETTER

TW_PREV = [350, 290, 300, 310, 360]
CRPR_KW = ['ATPD','ATMR','ATRS','ATMO','ATER']
ATPL_KW = ['ATEI','ATAL','ATAS','AGAR','ATHS']


def ckpi(n, d, sz=100):
    return np.where(d == 0, sz, (n / d) * 100)


def ckpi_inv(n, d, sz=100):
    """100 - (n/d*100) : pour tranches 1-3m et >3m"""
    return np.where(d == 0, sz, 100.0 - (n / d) * 100)


def cpiv(df, filt, col, posts):
    return pd.pivot_table(
        df[filt], index="Poste travail princ.", columns=col,
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)


def get_text_col(df):
    for c in ["Désignation","Designation","Désignation OT","Texte ordre",
              "Texte","Description","Libellé","Libelle"]:
        if c in df.columns: return c
    for c in df.columns:
        if df[c].dtype == 'object' and any(
            kw in str(c).lower() for kw in ['sign','text','desc','libell']
        ): return c
    return None


def build_statut_pivot(df_sub, posts):
    if df_sub.empty:
        return pd.DataFrame(
            index=posts, columns=["CRÉÉ","LANC","CLOT","TCLO","Total"]
        ).fillna(0).astype(int)
    piv = pd.pivot_table(
        df_sub, index="Poste travail princ.", columns="Statut OT",
        values="Ordre", aggfunc="count", fill_value=0
    )
    for s in ["CRÉÉ","LANC","CLOT","TCLO"]:
        if s not in piv.columns: piv[s] = 0
    piv["Total"] = piv[["CRÉÉ","LANC","CLOT","TCLO"]].sum(axis=1)
    return piv.reindex(posts, fill_value=0).fillna(0).astype(int)


def gscore(k, a, t):
    """
    Score binaire par KPI :
    - KPI normal (plus haut = mieux)      : 1 si a >= t, sinon 0
    - KPI LOWER_BETTER (plus bas = mieux) : 1 si a <= t, sinon 0

    Score global d une categorie (Performance / Qualite) :
        = somme(gscore) / nb_kpis × 100
    """
    if pd.isna(a) or pd.isna(t): return 0
    if k in LOWER_BETTER:
        return 1 if a <= t else 0
    return 1 if a >= t else 0


def is_lb(k): return k in LOWER_BETTER


def _age_kpis(df, filt, col_age, posts, prefix):
    """
    Valeurs BRUTES (taux réel d'OT dans chaque tranche) :
    - <1m  : N_inf1m / Total * 100   (maximiser, cible >= 80%)
    - 1-3m : N_1-3m  / Total * 100   (minimiser, cible <= 15%)
    - >3m  : N_sup3m / Total * 100   (minimiser, cible <= 5%)
    """
    pv = cpiv(df, filt, col_age, posts)
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        if c not in pv.columns:
            pv[c] = 0
    # Total = somme des 3 tranches SEULEMENT (hors Inconnu)
    # → garantit que <1m + 1-3m + >3m = 100% exactement
    pv["Total"] = pv[["<1 mois","1 mois < <3 mois",">3 mois"]].sum(axis=1)

    kpis = {}
    for idx in pv.index:
        tot = pv.loc[idx, "Total"]
        if tot == 0:
            # Base vide = aucun OT en retard → <1m parfait, 1-3m et >3m à 0
            kpis.setdefault(f"OT {prefix} <1 mois",       {})[idx] = 100.0
            kpis.setdefault(f"OT {prefix} 1mois< <3mois", {})[idx] = 0.0
            kpis.setdefault(f"OT {prefix} >3 mois",       {})[idx] = 0.0
        else:
            t1 = pv.loc[idx, "<1 mois"]           / tot * 100
            t2 = pv.loc[idx, "1 mois < <3 mois"]  / tot * 100
            t3 = pv.loc[idx, ">3 mois"]           / tot * 100
            kpis.setdefault(f"OT {prefix} <1 mois",       {})[idx] = round(t1, 2)
            kpis.setdefault(f"OT {prefix} 1mois< <3mois", {})[idx] = round(t2, 2)
            kpis.setdefault(f"OT {prefix} >3 mois",       {})[idx] = round(t3, 2)

    result = {}
    for k, d in kpis.items():
        default = 100.0 if "<1 mois" in k else 0.0
        result[k] = pd.Series(d).reindex(posts, fill_value=default)

    return result, pv


def calc_kpis(df_i, av_i, now_ts, posts):
    res = {}
    df  = df_i.copy()
    av  = av_i.copy()
    res['dfp'] = df

    # ── 1. TAUX REALISATION CORRECTIF ───────────────────────────────────
    filt_cor = df["is_correctif"] & (df["Contient SOPL"] == 1)
    an = cpiv(df, filt_cor, "Statut OT", posts)
    for c in ["CLOT","CRÉÉ","LANC","TCLO"]: an[c] = an.get(c, 0)
    an["OT_CLOTURES"] = an["CLOT"] + an["TCLO"]
    an["TOTAL_OT"]    = an[["CLOT","CRÉÉ","LANC","TCLO"]].sum(axis=1)
    an["TAUX_REALISATION_CORRECTIF/PT"] = np.where(
        an["TOTAL_OT"] == 0, 100.0, ckpi(an["OT_CLOTURES"], an["TOTAL_OT"])
    )

    # ── 2-4. AGE PREP ────────────────────────────────────────────────────
    # Base : CRÉÉ + Backlog prep NON CARAC
    # Age  : |now - Créé le| (dans prepare_data.py, avec abs)
    filt_prep = (
        (df["Statut OT"] == "CRÉÉ") &
        (df["Backlog preparation"] == "NON CARACTERISE")
    )
    kpis_prep, pv_prep = _age_kpis(df, filt_prep, "ap", posts, "préparation")

    # ── 5-7. AGE PLAN ────────────────────────────────────────────────────
    # Base : LANC + hors SOPL + Backlog plan NON CARAC
    # Age  : |now - Date planifiée| (dans prepare_data.py, avec abs)
    filt_plan = (
        (df["Statut OT"] == "LANC") &
        (df["Contient SOPL"] == 0) &
        (df["Backlog planification"] == "NON CARACTERISE")
    )
    kpis_plan, pv_plan = _age_kpis(df, filt_plan, "alp", posts, "planification")

    # ── 8-10. AGE EXEC ───────────────────────────────────────────────────
    # Base : LANC + SOPL (sans filtre TW preventifs — resultat SF1 1433/1171 ✅)
    # Age  : |now - Date planifiée| (dans prepare_data.py, avec abs)
    filt_exec = (
        (df["Statut OT"] == "LANC") &
        (df["Contient SOPL"] == 1)
    )
    kpis_exec, pv_exec = _age_kpis(df, filt_exec, "aex", posts, "exécution")

    # ── 11. PERFORMANCE GRAISSAGE (TW=350) ──────────────────────────────
    g_num = df[df["Statut OT"].isin(["CLOT","TCLO"]) & (df["_tw_num"]==350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_den = df[(df["Contient SOPL"]==1) & (df["_tw_num"]==350) & (df["Date de début planifiée"]<=now_ts)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_df  = pd.DataFrame({"_n":g_num,"_d":g_den}).reindex(posts, fill_value=0)
    g_df["Performance Graissage"] = np.where(
        g_df["_d"]==0, 100.0, (g_df["_n"]/g_df["_d"])*100
    )

    # ── 12. PERFORMANCE INSPECTION (TW=290/300/310) ──────────────────────
    ins_base = (
        df["_tw_num"].isin([290,300,310]) &
        df["Date de début planifiée"].notna() &
        (df["Date de début planifiée"] <= now_ts)
    )
    ins_num = df[df["Statut OT"].isin(["CLOT","TCLO"]) & ins_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    ins_den = df[(df["Contient SOPL"]==1) & ins_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    ins_df  = pd.DataFrame({"_n":ins_num,"_d":ins_den}).reindex(posts, fill_value=0)
    ins_df["Performance Inspection"] = np.where(
        ins_df["_d"]==0, 100.0, (ins_df["_n"]/ins_df["_d"])*100
    )

    # ── 13. PERFORMANCE SYSTEMATIQUES (TW=360) ───────────────────────────
    sys_base = (
        (df["_tw_num"] == 360) &
        df["Date de début planifiée"].notna() &
        (df["Date de début planifiée"] <= now_ts)
    )
    sys_num = df[df["Statut OT"].isin(["CLOT","TCLO"]) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_den = df[(df["Contient SOPL"]==1) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_df  = pd.DataFrame({"_n":sys_num,"_d":sys_den}).reindex(posts, fill_value=0)
    sys_df["Performance Systématiques"] = np.where(
        sys_df["_d"]==0, 100.0, (sys_df["_n"]/sys_df["_d"])*100
    )

    # ── 14. TAUX APPROBATION AVIS ────────────────────────────────────────
    avf = av.copy()
    res['avf'] = avf
    tca = pd.pivot_table(
        avf, index="Poste travail princ.", columns="Statut utilisateur",
        values="Avis", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    tca["APRV"] = tca.get("APRV", 0)
    # Total = tous les avis (toutes colonnes statut sauf index)
    tca["Total"] = tca.sum(axis=1)
    tca["Taux d'approbation des Avis"] = ckpi(tca["APRV"], tca["Total"])

    # ── 15. OT LANC ESTIME ───────────────────────────────────────────────
    filt_lanc = (
        df["is_correctif"] &
        (df["Statut OT"] == "LANC") &
        (df["Contient SOPL"] == 0)
    )
    la = pd.pivot_table(
        df[filt_lanc], index="Poste travail princ.", columns="OT LANC ESTIME",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI","NON"]: la[c] = la.get(c, 0)
    la["Total"] = la["OUI"] + la["NON"]
    la["OT LANC ESTIME"] = ckpi(la["OUI"], la["Total"])

    # ── 16. BACKLOG PREP CARACTERISE ─────────────────────────────────────
    # Num = CREE + CRPR + hors SOPL + contient ATPD/ATMR/ATRS/ATMO/ATER
    # ── 16. BACKLOG PREP CARACTERISE ─────────────────────────────────────
    # Base = Statut CRÉÉ + Plan d'entretien != 0 (préventif)
    # Caracterise = contient ATPD/ATMR/ATRS/ATMO/ATER
    pat_prep = '|'.join(CRPR_KW)
    df_cree  = df[
        (df["Statut OT"] == "CRÉÉ") &
        (~df["is_correctif"])   # Plan d'entretien != 0
    ].copy()
    df_cree["_carac"] = df_cree["Statut utilisateur"].str.contains(
        pat_prep, na=False
    ).map({True:"CARACTERISE",False:"NON CARACTERISE"})
    pc = pd.pivot_table(
        df_cree, index="Poste travail princ.", columns="_carac",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE","NON CARACTERISE"]: pc[c] = pc.get(c, 0)
    pc["Total"] = pc["CARACTERISE"] + pc["NON CARACTERISE"]
    pc["Backlog préparation caractérisé"] = ckpi(pc["CARACTERISE"], pc["Total"])

    # ── 17. BACKLOG PLAN CARACTERISE ─────────────────────────────────────
    # Base = Statut LANC + hors SOPL + Plan d'entretien != 0 (préventif)
    # Caracterise = contient ATEI/ATAL/ATAS/AGAR/ATHS
    pat_plan = '|'.join(ATPL_KW)
    df_lancp = df[
        (~df["is_correctif"]) &          # Plan d'entretien != 0
        (df["Statut OT"] == "LANC") &
        (df["Contient SOPL"] == 0)
    ].copy()
    df_lancp["_carac"] = df_lancp["Statut utilisateur"].str.contains(
        pat_plan, na=False
    ).map({True:"CARACTERISE",False:"NON CARACTERISE"})
    plc = pd.pivot_table(
        df_lancp, index="Poste travail princ.", columns="_carac",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE","NON CARACTERISE"]: plc[c] = plc.get(c, 0)
    plc["Total"] = plc["CARACTERISE"] + plc["NON CARACTERISE"]
    plc["Backlog planification caractérisé"] = ckpi(plc["CARACTERISE"], plc["Total"])

    # ── 18. OT CONFIME ───────────────────────────────────────────────────
    pv_conf = pd.pivot_table(
        df[df["Statut OT"].isin(["CLOT","TCLO"])],
        index="Poste travail princ.", columns="OT CONFIME",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI","NON"]: pv_conf[c] = pv_conf.get(c, 0)
    pv_conf["Total"]      = pv_conf["OUI"] + pv_conf["NON"]
    pv_conf["OT CONFIME"] = ckpi(pv_conf["OUI"], pv_conf["Total"])
    res["ot_confime"]     = pv_conf
   # ── 19. OT_COR_EGAL ──────────────────────────────────────────────────
# Base : OT correctifs clôturés (CLOT/TCLO) et confirmés (CONF)
# KPI : (Budget = Réel) / Total -> maximiser (bonne imputation des coûts)

df_clot = df[
    df["is_correctif"] &
    df["Statut OT"].isin(["CLOT", "TCLO"]) &
    df["Statut système"].str.contains("CONF", na=False)
].copy()

# Conversion des coûts en numérique
_bud_c = pd.to_numeric(df_clot["Total coûts budgétés"], errors="coerce")
_reel_c = pd.to_numeric(df_clot["Total coûts réels"], errors="coerce")

# OUI si Budget = Réel (tolérance de 0,01)
df_clot["_egal"] = np.where(
    np.isclose(_bud_c, _reel_c, atol=0.01),
    "OUI",
    "NON"
)

pv_cor = (
    pd.pivot_table(
        df_clot,
        index="Poste travail princ.",
        columns="_egal",
        values="Ordre",
        aggfunc="count",
        fill_value=0
    )
    .reindex(posts, fill_value=0)
)

for c in ["OUI", "NON"]:
    if c not in pv_cor.columns:
        pv_cor[c] = 0

pv_cor["Total"] = pv_cor["OUI"] + pv_cor["NON"]

# % des OT dont le coût budgété est égal au coût réel
pv_cor["OT_COR_EGAL"] = ckpi(pv_cor["OUI"], pv_cor["Total"])

res["ot_cor_egal"] = pv_cor

    fiab_s  = pd.Series(100.0, index=posts)
    avpan_s = pd.Series(100.0, index=posts)

    res['ckdf'] = pd.DataFrame({
        "TAUX_REALISATION_CORRECTIF/PT":     an["TAUX_REALISATION_CORRECTIF/PT"],
        # Age Prep : <1m direct, 1-3m et >3m = 100-val
        "OT préparation <1 mois":            kpis_prep["OT préparation <1 mois"],
        "OT préparation >3 mois":            kpis_prep["OT préparation >3 mois"],
        "OT préparation 1mois< <3mois":      kpis_prep["OT préparation 1mois< <3mois"],
        # Age Plan
        "OT planification <1 mois":          kpis_plan["OT planification <1 mois"],
        "OT planification >3 mois":          kpis_plan["OT planification >3 mois"],
        "OT planification 1mois< <3mois":    kpis_plan["OT planification 1mois< <3mois"],
        # Age Exec
        "OT exécution <1 mois":              kpis_exec["OT exécution <1 mois"],
        "OT exécution >3 mois":              kpis_exec["OT exécution >3 mois"],
        "OT exécution 1mois< <3mois":        kpis_exec["OT exécution 1mois< <3mois"],
        "Performance Graissage":             g_df["Performance Graissage"],
        "Performance Inspection":            ins_df["Performance Inspection"],
        "Performance Systématiques":         sys_df["Performance Systématiques"],
        "Taux d'approbation des Avis":       tca["Taux d'approbation des Avis"],
        "OT LANC ESTIME":                    la["OT LANC ESTIME"],
        "Backlog préparation caractérisé":   pc["Backlog préparation caractérisé"],
        "Backlog planification caractérisé": plc["Backlog planification caractérisé"],
        "OT CONFIME":                        res["ot_confime"]["OT CONFIME"],
        "OT_COR_EGAL":                       res["ot_cor_egal"]["OT_COR_EGAL"],
        "OT Fiabilité":                      fiab_s,
        "Total Avis de Panne":               avpan_s,
    })

    # Stocker les pivots bruts pour les graphiques backlog
    res['pv_prep'] = pv_prep
    res['pv_plan'] = pv_plan
    res['pv_exec'] = pv_exec

    return res

# ─── NOTE POUR constants.py ──────────────────────────────────────────────────
# Avec la nouvelle logique 100-val, mettre à jour dans constants.py :
#
# CIBLE = {
#     ...
#     "OT préparation <1 mois":       80,   # direct >= 80%
#     "OT préparation 1mois< <3mois": 85,   # score = 100-15 = 85%
#     "OT préparation >3 mois":       95,   # score = 100-5  = 95%
#     "OT planification <1 mois":     80,
#     "OT planification 1mois< <3mois": 85,
#     "OT planification >3 mois":     95,
#     "OT exécution <1 mois":         80,
#     "OT exécution 1mois< <3mois":   85,
#     "OT exécution >3 mois":         95,
#     ...
# }
#
# LOWER_BETTER doit être VIDE pour ces KPIs car
# la logique 100-val les rend tous "plus haut = mieux"
# ─────────────────────────────────────────────────────────────────────────────
