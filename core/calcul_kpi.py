# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from core.constants import QK, PK, CIBLE, LOWER_BETTER


def ckpi(n, d, sz=100):
    return np.where(d == 0, sz, (n / d) * 100)


def cpiv(df, f, c, p):
    return pd.pivot_table(
        df[f], index="Poste travail princ.", columns=c,
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(p, fill_value=0)


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
        return 1 if a <= 15 else 0
    if k in ["OT préparation >3 mois","OT planification >3 mois","OT exécution >3 mois"]:
        return 1 if a <= 5 else 0
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


def calc_kpis(df_i, av_i, now_ts, posts):
    res = {}
    df  = df_i.copy()
    av  = av_i.copy()
    res['dfp'] = df

    # ── 1. TAUX REALISATION CORRECTIF ──────────────────────────────────
    # OT correctifs clôturés (TCLO/CLOT) / Total OT correctifs planifiés
    # Correctifs = sans appel PM + SOPL
    filt_corr = (df["Nº appel pl.entret."].fillna(0) == 0) & (df["Contient SOPL"] == 1)
    an = cpiv(df, filt_corr, "Statut OT", posts)
    for c in ["CLOT","CRÉÉ","LANC","TCLO"]: an[c] = an.get(c, 0)
    an["OT_CLOTURES"] = an["CLOT"] + an["TCLO"]
    an["TOTAL_OT"]    = an[["CLOT","CRÉÉ","LANC","TCLO"]].sum(axis=1)
    an["TAUX_REALISATION_CORRECTIF/PT"] = np.where(
        an["TOTAL_OT"] == 0, 100.0, ckpi(an["OT_CLOTURES"], an["TOTAL_OT"])
    )

    # ── 2. AGE PREP : CREE + CRPR + Plan entretien == 0, age = date création ──
    filt_prep = (
        (df["Statut OT"] == "CRÉÉ") &
        df["Statut utilisateur"].str.contains(r"\bCRPR\b", case=False, na=False) &
        (df["Plan d'entretien"].fillna(0) == 0)
    )
    pr = cpiv(df, filt_prep, "ap", posts)
    for c in ["<1 mois",">3 mois","1 mois < <3 mois","Inconnu"]:
        pr[c] = pr.get(c, 0)
    pr["Total"] = pr[["<1 mois","1 mois < <3 mois",">3 mois","Inconnu"]].sum(axis=1)
    pr["OT préparation <1 mois"]       = ckpi(pr["<1 mois"],           pr["Total"])
    pr["OT préparation >3 mois"]       = ckpi(pr[">3 mois"],           pr["Total"], 0)
    pr["OT préparation 1mois< <3mois"] = ckpi(pr["1 mois < <3 mois"],  pr["Total"], 0)

    # ── 3. AGE PLAN : LANC + ATPL + Plan entretien == 0, age = date planif ──
    filt_plan = (
        (df["Statut OT"] == "LANC") &
        df["Statut utilisateur"].str.contains("ATPL", case=False, na=False) &
        (df["Plan d'entretien"].fillna(0) == 0)
    )
    pl = cpiv(df, filt_plan, "alp", posts)
    for c in ["<1 mois",">3 mois","1 mois < <3 mois","Inconnu"]:
        pl[c] = pl.get(c, 0)
    pl["Total"] = pl[["<1 mois","1 mois < <3 mois",">3 mois","Inconnu"]].sum(axis=1)
    pl["OT planification <1 mois"]       = ckpi(pl["<1 mois"],           pl["Total"])
    pl["OT planification >3 mois"]       = ckpi(pl[">3 mois"],           pl["Total"], 0)
    pl["OT planification 1mois< <3mois"] = ckpi(pl["1 mois < <3 mois"],  pl["Total"], 0)

    # ── 4. AGE EXEC : LANC + SOPL + Plan entretien == 0, age = date planif ──
    filt_exec = (
        (df["Statut OT"] == "LANC") &
        (df["Contient SOPL"] == 1) &
        (df["Plan d'entretien"].fillna(0) == 0)
    )
    ex = cpiv(df, filt_exec, "aex", posts)
    for c in ["<1 mois",">3 mois","1 mois < <3 mois","Inconnu"]:
        ex[c] = ex.get(c, 0)
    ex["Total"] = ex[["<1 mois","1 mois < <3 mois",">3 mois","Inconnu"]].sum(axis=1)
    ex["OT exécution <1 mois"]       = ckpi(ex["<1 mois"],           ex["Total"])
    ex["OT exécution >3 mois"]       = ckpi(ex[">3 mois"],           ex["Total"], 0)
    ex["OT exécution 1mois< <3mois"] = ckpi(ex["1 mois < <3 mois"],  ex["Total"], 0)

    # ── 5. OT LANC ESTIME : charge estimée > 0 / Total LANC + plan==0 ──
    filt_lanc = (df["Statut OT"] == "LANC") & (df["Plan d'entretien"].fillna(0) == 0)
    la = pd.pivot_table(
        df[filt_lanc], index="Poste travail princ.", columns="OT LANC ESTIME",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI","NON"]: la[c] = la.get(c, 0)
    la["Total"] = la["OUI"] + la["NON"]
    la["OT LANC ESTIME"] = ckpi(la["OUI"], la["Total"])

    # ── 6. BACKLOG PREP CARACTERISE : CREE + CRPR + plan==0 ──
    filt_bp = (
        (df["Statut OT"] == "CRÉÉ") &
        df["Statut utilisateur"].str.contains(r"\bCRPR\b", case=False, na=False) &
        (df["Plan d'entretien"].fillna(0) == 0)
    )
    pc = pd.pivot_table(
        df[filt_bp], index="Poste travail princ.", columns="Backlog preparation",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE","NON CARACTERISE"]: pc[c] = pc.get(c, 0)
    pc["Total"] = pc["CARACTERISE"] + pc["NON CARACTERISE"]
    pc["Backlog préparation caractérisé"] = ckpi(pc["CARACTERISE"], pc["Total"])

    # ── 7. BACKLOG PLAN CARACTERISE : LANC + hors SOPL + plan==0 ──
    filt_bpl = (
        (df["Statut OT"] == "LANC") &
        (df["Contient SOPL"] == 0) &
        (df["Plan d'entretien"].fillna(0) == 0)
    )
    plc = pd.pivot_table(
        df[filt_bpl], index="Poste travail princ.", columns="Backlog planification",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE","NON CARACTERISE"]: plc[c] = plc.get(c, 0)
    plc["Total"] = plc["CARACTERISE"] + plc["NON CARACTERISE"]
    plc["Backlog planification caractérisé"] = ckpi(plc["CARACTERISE"], plc["Total"])

    # ── 8. OT CONFIME : CONF / Total CLOT+TCLO ──
    pv_conf = pd.pivot_table(
        df[df["Statut OT"].isin(["CLOT","TCLO"])],
        index="Poste travail princ.", columns="OT CONFIME",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI","NON"]: pv_conf[c] = pv_conf.get(c, 0)
    pv_conf["Total"]     = pv_conf["OUI"] + pv_conf["NON"]
    pv_conf["OT CONFIME"] = ckpi(pv_conf["OUI"], pv_conf["Total"])
    res["ot_confime"]    = pv_conf

    # ── 9. OT_COR_EGAL : ZCOR + TCLO, budget == réel (approche logique) ──
    # KPI = OT où budget EGAL réel / Total ZCOR TCLO
    # Anomalie = budget DIFFERENT de réel
    filt_cor = (
        (df["Type d'ordre"] == "ZCOR") &
        (df["Statut OT"] == "TCLO")
    )
    df_cor = df[filt_cor].copy()
    df_cor["_egal"] = (
        df_cor["Total coûts budgétés"].fillna(0) == df_cor["Total coûts réels"].fillna(0)
    ).map({True: "OUI", False: "NON"})
    pv_cor = pd.pivot_table(
        df_cor, index="Poste travail princ.", columns="_egal",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI","NON"]: pv_cor[c] = pv_cor.get(c, 0)
    pv_cor["Total"]      = pv_cor["OUI"] + pv_cor["NON"]
    pv_cor["OT_COR_EGAL"] = ckpi(pv_cor["OUI"], pv_cor["Total"])
    res["ot_cor_egal"]   = pv_cor

    # ── 10. TAUX APPROBATION AVIS : APRV / Total (hors ZU/Z4/ZR/ZP) ──
    # Note : le filtre hors ZU/Z4/ZR/ZP est appliqué dans prepare_data.py
    avf = av.copy()
    res['avf'] = avf
    tca = pd.pivot_table(
        avf, index="Poste travail princ.", columns="Statut utilisateur",
        values="Avis", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["APRV","APRQ","REJT"]: tca[c] = tca.get(c, 0)
    tca["Total"] = tca[["APRV","APRQ","REJT"]].sum(axis=1)
    tca["Taux d'approbation des Avis"] = ckpi(tca["APRV"], tca["Total"])

    # ── 11. PERFORMANCE GRAISSAGE (TW=350) ──
    g_num = df[df["Statut OT"].isin(["CLOT","TCLO"]) & (df["_tw_num"]==350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_den = df[(df["Contient SOPL"]==1) & (df["_tw_num"]==350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_df = pd.DataFrame({"_n":g_num,"_d":g_den}).reindex(posts, fill_value=0)
    g_df["Performance Graissage"] = np.where(
        g_df["_d"]==0, 100.0, (g_df["_n"]/g_df["_d"])*100
    )

    # ── 12. PERFORMANCE INSPECTION (TW=290/300/310) ──
    ins_base = (
        df["_tw_num"].isin([290,300,310]) &
        df["Date de début planifiée"].notna() &
        (df["Date de début planifiée"] <= now_ts)
    )
    ins_num = df[df["Statut OT"].isin(["CLOT","TCLO"]) & ins_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    ins_den = df[(df["Contient SOPL"]==1) & ins_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    ins_df = pd.DataFrame({"_n":ins_num,"_d":ins_den}).reindex(posts, fill_value=0)
    ins_df["Performance Inspection"] = np.where(
        ins_df["_d"]==0, 100.0, (ins_df["_n"]/ins_df["_d"])*100
    )

    # ── 13. PERFORMANCE SYSTEMATIQUES (TW=360) ──
    sys_base = (
        (df["_tw_num"]==360) &
        df["Date de début planifiée"].notna() &
        (df["Date de début planifiée"] <= now_ts)
    )
    sys_num = df[df["Statut OT"].isin(["CLOT","TCLO"]) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_den = df[(df["Contient SOPL"]==1) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_df = pd.DataFrame({"_n":sys_num,"_d":sys_den}).reindex(posts, fill_value=0)
    sys_df["Performance Systématiques"] = np.where(
        sys_df["_d"]==0, 100.0, (sys_df["_n"]/sys_df["_d"])*100
    )

    fiab_s  = pd.Series(100.0, index=posts)
    avpan_s = pd.Series(100.0, index=posts)

    res['ckdf'] = pd.DataFrame({
        "TAUX_REALISATION_CORRECTIF/PT":     an["TAUX_REALISATION_CORRECTIF/PT"],
        "OT préparation <1 mois":            pr["OT préparation <1 mois"],
        "OT préparation >3 mois":            pr["OT préparation >3 mois"],
        "OT préparation 1mois< <3mois":      pr["OT préparation 1mois< <3mois"],
        "OT planification <1 mois":          pl["OT planification <1 mois"],
        "OT planification >3 mois":          pl["OT planification >3 mois"],
        "OT planification 1mois< <3mois":    pl["OT planification 1mois< <3mois"],
        "OT exécution <1 mois":              ex["OT exécution <1 mois"],
        "OT exécution >3 mois":              ex["OT exécution >3 mois"],
        "OT exécution 1mois< <3mois":        ex["OT exécution 1mois< <3mois"],
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

    return res
