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
    if pd.isna(a) or pd.isna(t): return 0
    if k in ["OT préparation <1 mois","OT planification <1 mois","OT exécution <1 mois"]:
        return 1 if a >= 75 else 0
    if k in ["OT préparation 1mois< <3mois","OT planification 1mois< <3mois","OT exécution 1mois< <3mois"]:
        return 1 if a >= 85 else 0   # score = 100-15 = 85
    if k in ["OT préparation >3 mois","OT planification >3 mois","OT exécution >3 mois"]:
        return 1 if a >= 95 else 0   # score = 100-5 = 95
    if k == "TAUX_REALISATION_CORRECTIF/PT": return 1 if a >= 80 else 0
    if k == "Taux d'approbation des Avis":   return 1 if a >= 90 else 0
    if k in ["OT LANC ESTIME","Backlog préparation caractérisé",
             "Backlog planification caractérisé","OT CONFIME","OT_COR_EGAL"]:
        return 1 if a >= 95 else 0
    if k in ["Performance Graissage","Performance Inspection","Performance Systématiques"]:
        return 1 if a >= 95 else 0
    if k in ["OT Fiabilité","Total Avis de Panne"]: return 1 if a >= 100 else 0
    return 0


def is_lb(k): return k in LOWER_BETTER


def _age_kpis(df, filt, col_age, posts, prefix):
    """
    Calcule les 3 KPIs age pour un backlog donné.

    Logique officielle OCP :
    - <1m  : N_inf1m / Total                  → valeur directe  (maximiser, cible 80%)
    - 1-3m : 100 - (N_1-3m  / Total * 100)   → complément       (cible ≥ 85% = max 15% dans tranche)
    - >3m  : 100 - (N_sup3m / Total * 100)   → complément       (cible ≥ 95% = max 5% dans tranche)

    Tous les scores sont dans [0,100] : plus la valeur est haute, mieux c est.
    La somme des 3 taux BRUTS = 100% (répartition totale).
    """
    pv = cpiv(df, filt, col_age, posts)
    for c in ["<1 mois",">3 mois","1 mois < <3 mois","Inconnu"]:
        pv[c] = pv.get(c, 0)
    pv["Total"] = pv[["<1 mois","1 mois < <3 mois",">3 mois","Inconnu"]].sum(axis=1)

    # Taux bruts (pour affichage dans tableau détaillé)
    pv["taux_inf1m"]  = np.where(pv["Total"]==0, 100.0, pv["<1 mois"]          / pv["Total"] * 100)
    pv["taux_1-3m"]   = np.where(pv["Total"]==0,   0.0, pv["1 mois < <3 mois"] / pv["Total"] * 100)
    pv["taux_sup3m"]  = np.where(pv["Total"]==0,   0.0, pv[">3 mois"]          / pv["Total"] * 100)

    kpis = {}
    # KPI <1m  : taux brut direct (plus c est grand mieux c est)
    kpis[f"OT {prefix} <1 mois"]       = pv["taux_inf1m"]
    # KPI 1-3m : 100 - taux_brut (plus il y a d OT dans cette tranche, moins bon)
    kpis[f"OT {prefix} 1mois< <3mois"] = 100.0 - pv["taux_1-3m"]
    # KPI >3m  : 100 - taux_brut (plus il y a d OT dans cette tranche, moins bon)
    kpis[f"OT {prefix} >3 mois"]       = 100.0 - pv["taux_sup3m"]

    return kpis, pv


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
    # Plan==0 + CREE + CRPR, age = date_création
    # <1m = direct | 1-3m = 100-val | >3m = 100-val
    filt_prep = (
        df["is_correctif"] &
        (df["Statut OT"] == "CRÉÉ") &
        df["Statut utilisateur"].str.contains(r"\bCRPR\b", case=False, na=False)
    )
    kpis_prep, pv_prep = _age_kpis(df, filt_prep, "ap", posts, "préparation")

    # ── 5-7. AGE PLAN ────────────────────────────────────────────────────
    # Plan==0 + LANC + ATPL, age = date_planif
    filt_plan = (
        df["is_correctif"] &
        (df["Statut OT"] == "LANC") &
        df["Statut utilisateur"].str.contains("ATPL", case=False, na=False)
    )
    kpis_plan, pv_plan = _age_kpis(df, filt_plan, "alp", posts, "planification")

    # ── 8-10. AGE EXEC ───────────────────────────────────────────────────
    # Plan==0 + LANC + SOPL + hors TW preventifs, age = date_planif
    filt_exec = (
        df["is_correctif"] &
        (df["Statut OT"] == "LANC") &
        (df["Contient SOPL"] == 1) &
        (~df["_tw_num"].isin(TW_PREV))
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
    pat_prep = '|'.join(CRPR_KW)
    df_cree  = df[df["is_correctif"] & (df["Statut OT"]=="CRÉÉ")].copy()
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
    pat_plan = '|'.join(ATPL_KW)
    df_lancp = df[df["is_correctif"] & (df["Statut OT"]=="LANC") & (df["Contient SOPL"]==0)].copy()
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
    df_clot = df[df["is_correctif"] & df["Statut OT"].isin(["CLOT","TCLO"])].copy()
    df_clot["_egal"] = df_clot["OT_COR_EGAL"].map({"EGAL":"OUI","DIFF":"NON"})
    pv_cor = pd.pivot_table(
        df_clot, index="Poste travail princ.", columns="_egal",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI","NON"]: pv_cor[c] = pv_cor.get(c, 0)
    pv_cor["Total"]       = pv_cor["OUI"] + pv_cor["NON"]
    pv_cor["OT_COR_EGAL"] = ckpi(pv_cor["OUI"], pv_cor["Total"])
    res["ot_cor_egal"]    = pv_cor

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
