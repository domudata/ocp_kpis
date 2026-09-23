# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from core.constants import MP_KW, MPLAN_KW, QK, PK, CIBLE, LOWER_BETTER

# ──────────────────────────────────────────────
# Utilitaires de calcul
# ──────────────────────────────────────────────

def ckpi(n, d, sz=100):
    return np.where(d == 0, sz, (n / d) * 100)


def cpiv(df: pd.DataFrame, f, c: str, p: list) -> pd.DataFrame:
    return (
        pd.pivot_table(
            df[f], index="Poste travail princ.", columns=c,
            values="Ordre", aggfunc="count", fill_value=0
        ).reindex(p, fill_value=0)
    )


def get_text_col(df: pd.DataFrame):
    for c in ["Désignation", "Designation", "Désignation OT", "Texte ordre",
              "Texte", "Description", "Libellé", "Libelle"]:
        if c in df.columns:
            return c
    for c in df.columns:
        if df[c].dtype == 'object' and any(
            kw in str(c).lower() for kw in ['sign', 'text', 'desc', 'libell']
        ):
            return c
    return None


def build_statut_pivot(df_sub: pd.DataFrame, posts: list) -> pd.DataFrame:
    if df_sub.empty:
        return (
            pd.DataFrame(index=posts, columns=["CRÉÉ", "LANC", "CLOT", "TCLO", "Total"])
            .fillna(0).astype(int)
        )
    piv = pd.pivot_table(
        df_sub, index="Poste travail princ.", columns="Statut OT",
        values="Ordre", aggfunc="count", fill_value=0
    )
    for s in ["CRÉÉ", "LANC", "CLOT", "TCLO"]:
        if s not in piv.columns:
            piv[s] = 0
    piv["Total"] = piv[["CRÉÉ", "LANC", "CLOT", "TCLO"]].sum(axis=1)
    return piv.reindex(posts, fill_value=0).fillna(0).astype(int)


def gscore(k: str, a, t) -> int:
    if pd.isna(a) or pd.isna(t):
        return 0
    try:
        val = float(a)
        target = float(t)
    except Exception:
        return 0

    if is_lb(k):
        # Plus bas = mieux (1-3 mois cible 15, >3 mois cible 5)
        # Vert <= target, Jaune <= target + 5, Rouge > target + 5
        # Règle utilisateur : si rouge compte 0, sinon (vert ou jaune) compte 1
        return 1 if val <= target + 5 else 0
    elif k == "OT_COR_EGAL":
        # Plus bas = mieux (taux de non-concordance cible <= 5)
        return 1 if val <= 5 else 0
    else:
        # Plus haut = mieux
        # Vert >= target, Jaune >= target - 5, Rouge < target - 5
        # Règle utilisateur : si rouge compte 0, sinon (vert ou jaune) compte 1
        return 1 if val >= target - 5 else 0


def is_lb(k: str) -> bool:
    return k in LOWER_BETTER


# ──────────────────────────────────────────────
# Correspondance EXACTE pour Backlog préparation/planification
# (AJOUTÉ — logique convenue explicitement) :
#   CARACTERISE = Statut utilisateur ÉGAL STRICTEMENT (après suppression
#   des espaces superflus) à l'un des codes ci-dessous — aucune addition
#   avant ou après n'est tolérée (ex. "CRPR ATPD" NE compte PAS, seul
#   "ATPD" seul compte). Périmètre : OT de type ZCOR uniquement.
# ──────────────────────────────────────────────

CODES_PREP_EXACT = {"ATPD", "ATMR", "ATER", "ATRS", "ATMO"}
CODES_PLAN_EXACT = {"ATEI", "ATAL", "ATAS", "AGAR", "ATHS"}


def match_exact_token(statut, codes: set) -> bool:
    """RÉVISÉ (spécification officielle reçue — sections 5, 6, 7) :
    un OT est CARACTERISE dès que l'un des codes apparaît N'IMPORTE OÙ
    dans le champ "Statut utilisateur" — quelle que soit sa position
    (début, milieu, fin, entouré d'autre texte, combiné à d'autres codes).
    Logique "contains" explicitement exigée ; "==" et "startswith" sont
    explicitement exclus par la spécification.
    Exemples devant tous être CARACTERISE pour le code "ATPD" :
    "ATPD", "OT ATPD", "Préparation - ATPD - OK", "ATMR / ATPD / ATMO".
    (Le nom de la fonction est conservé pour ne pas casser les imports
    existants ailleurs dans le code.)"""
    if statut is None or (isinstance(statut, float) and pd.isna(statut)):
        return False
    t = str(statut).upper()
    return any(code in t for code in codes)


# ──────────────────────────────────────────────
# Calcul principal des KPI
# ──────────────────────────────────────────────

def calc_kpis(df_i: pd.DataFrame, av_i: pd.DataFrame, now_ts, posts: list,
              df_toutes_dates: pd.DataFrame = None,
              av_approve_i: pd.DataFrame = None) -> dict:
    """
    df_toutes_dates : DataFrame OT identique à df_i mais SANS le filtre de
    période de la barre latérale (mêmes colonnes). Utilisé UNIQUEMENT pour
    les indicateurs Backlog préparation/planification caractérisé (et les
    OT préparation/planification par âge qui en découlent désormais),
    dont le calcul doit porter sur l'historique complet quelle que soit la
    période sélectionnée par l'utilisateur (demande explicite). Si non
    fourni, df_i est réutilisé (comportement inchangé, rétrocompatible).
    av_approve_i : DataFrame des avis pour le KPI « AVIS APPROUVE » /
    « Taux d'approbation des Avis », filtré selon la spec §20 :
    - Statut système ne contient PAS « ACLO » (insensible à la casse)
    - Type d'avis n'est pas ZU, Z4, ZR, ZP
    Si non fourni, av_i est réutilisé (rétrocompatibilité).
    """
    res = {}
    df = df_i.copy()
    av = av_i.copy()
    res['dfp'] = df
    df_all = df_toutes_dates.copy() if df_toutes_dates is not None else df
    # avf_approve : population pour « Taux d'approbation des Avis » / AVIS APPROUVE
    # (spec §20 : exclut ACLO + exclut types ZU/Z4/ZR/ZP). Rétrocompatible si
    # av_approve_i non fourni.
    avf_approve = av_approve_i.copy() if av_approve_i is not None else av.copy()

    # ── Taux réalisation correctif ──
    filt_corr = (df["Nº appel pl.entret."].fillna(0) == 0) & (df["Contient SOPL"] == 1)
    an = cpiv(df, filt_corr, "Statut OT", posts)
    for c in ["CLOT", "CRÉÉ", "LANC", "TCLO"]:
        an[c] = an.get(c, 0)
    an["OT_CLOTURES"] = an["CLOT"] + an["TCLO"]
    an["TOTAL_OT"] = an[["CLOT", "CRÉÉ", "LANC", "TCLO"]].sum(axis=1)
    an["TAUX_REALISATION_CORRECTIF/PT"] = np.where(
        an["TOTAL_OT"] == 0, 100.0, ckpi(an["OT_CLOTURES"], an["TOTAL_OT"])
    )

    # ── Exécution — FILTRE : Statut OT == "LANC" ET Contient SOPL == 1 ──
    # Dénominateur : somme des 3 tranches d'âge (hors "Inconnu") pour que
    # <1 mois + 1-3 mois + >3 mois = 100%. Ex : 2+3+2 = 7 → 2/7 3/7 2/7.
    # Règle : si Dénominateur = 0 → KPI = 100% (sz=100).
    ex = cpiv(
        df,
        (df["Statut OT"] == "LANC") & (df["Contient SOPL"] == 1),
        "aex", posts
    )
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        ex[c] = ex.get(c, 0)
    ex["Total"] = ex[["<1 mois", "1 mois < <3 mois", ">3 mois"]].sum(axis=1)
    ex["OT exécution <1 mois"] = ckpi(ex["<1 mois"], ex["Total"], sz=100)
    ex["OT exécution >3 mois"] = ckpi(ex[">3 mois"], ex["Total"], sz=0)
    ex["OT exécution 1mois< <3mois"] = ckpi(ex["1 mois < <3 mois"], ex["Total"], sz=0)

    # ── OT lancé estimé (inchangé) ──
    # ── OT LANC ESTIME — AJOUT SOPL + ZCOR (demande explicite) ──
    la = pd.pivot_table(
        df[(df["Statut OT"] == "LANC") & (df["Contient SOPL"] == 1) & (df["Type d'ordre"] == "ZCOR")],
        index="Poste travail princ.",
        columns="OT LANC ESTIME", values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        la[c] = la.get(c, 0)
    la["Total"] = la["OUI"] + la["NON"]
    la["OT LANC ESTIME"] = ckpi(la["OUI"], la["Total"])

    # ── Backlog préparation caractérisé — spec §3 ──
    # Périmètre : ZCOR + Statut système == CRÉÉ + Date planifiée ≤ NOW_TS.
    # Population SÉPARÉE de celle utilisée pour les KPI d'âge (voir ci-dessous).
    _zcor_all = df_all[df_all["Type d'ordre"] == "ZCOR"].copy()
    _cree_base = _zcor_all[
        _zcor_all["Statut système"].fillna("").astype(str).str.strip().str.split().str[0].isin(["CRÉÉ", "CREE"])
    ]
    # _zcor_cree_backlog : filtre date planifiée ≤ NOW_TS — dénominateur du Backlog carac.
    _zcor_cree_backlog = _cree_base[
        _cree_base["Date de début planifiée"] <= now_ts
    ].copy()
    # _zcor_cree_age : SANS filtre date planifiée — population pour les KPI d'âge.
    # (L'âge "ap" est calculé depuis "Créé le", pas depuis "Date planifiée".
    #  Beaucoup d'OT CRÉÉ n'ont pas encore de date planifiée → le filtre vide la
    #  population et force tous les KPI à 100%, ce qui est incorrect.)
    _zcor_cree_age = _cree_base.copy()

    _zcor_cree_backlog["_prep_carac"] = np.where(
        _zcor_cree_backlog["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PREP_EXACT)),
        "CARACTERISE", "NON CARACTERISE",
    )
    pc = pd.pivot_table(
        _zcor_cree_backlog, index="Poste travail princ.", columns="_prep_carac",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE", "NON CARACTERISE"]:
        pc[c] = pc.get(c, 0)
    pc["Total"] = pc["CARACTERISE"] + pc["NON CARACTERISE"]
    pc["Backlog préparation caractérisé"] = ckpi(pc["CARACTERISE"], pc["Total"])

    # ── Backlog planification caractérisé — spec §4 ──
    # Périmètre : ZCOR + LANC + SOPL==0 + Date planifiée ≤ NOW_TS.
    # Population SÉPARÉE de celle des KPI d'âge planification.
    _lanc_base = _zcor_all[
        (_zcor_all["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "LANC")
        & (_zcor_all["Contient SOPL"] == 0)
    ]
    # _zcor_lanc_backlog : filtre date planifiée ≤ NOW_TS — dénominateur du Backlog carac.
    _zcor_lanc_backlog = _lanc_base[
        _lanc_base["Date de début planifiée"] <= now_ts
    ].copy()
    # _zcor_lanc_age : population pour les KPI d'âge planification (ZCOR + LANC + SOPL==0)
    # sans filtre date planifiée (comme pour la préparation), afin que les OT planifiés
    # soient répartis sur les tranches d'âge alp.
    _zcor_lanc_age = _lanc_base.copy()

    _zcor_lanc_backlog["_plan_carac"] = np.where(
        _zcor_lanc_backlog["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT)),
        "CARACTERISE", "NON CARACTERISE",
    )
    plc = pd.pivot_table(
        _zcor_lanc_backlog, index="Poste travail princ.", columns="_plan_carac",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE", "NON CARACTERISE"]:
        plc[c] = plc.get(c, 0)
    plc["Total"] = plc["CARACTERISE"] + plc["NON CARACTERISE"]
    plc["Backlog planification caractérisé"] = ckpi(plc["CARACTERISE"], plc["Total"])

    # ── OT préparation <1/1-3/>3 mois ──
    # Base = ZCOR + CRÉÉ (SANS filtre date planifiée — "ap" est calculé depuis
    # "Créé le" et est disponible même sans date planifiée).
    # Dénominateur = somme des 3 tranches seulement (hors "Inconnu")
    # → garantit que la somme des 3 tranches = 100%.
    # Si Total == 0 → <1m = 100%, 1-3m = 0%, >3m = 0% (somme = 100%).
    pr = cpiv(_zcor_cree_age, pd.Series(True, index=_zcor_cree_age.index), "ap", posts)
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        pr[c] = pr.get(c, 0)
    pr["Total"] = pr[["<1 mois", "1 mois < <3 mois", ">3 mois"]].sum(axis=1)
    pr["OT préparation <1 mois"] = ckpi(pr["<1 mois"], pr["Total"], sz=100)
    pr["OT préparation >3 mois"] = ckpi(pr[">3 mois"], pr["Total"], sz=0)
    pr["OT préparation 1mois< <3mois"] = ckpi(pr["1 mois < <3 mois"], pr["Total"], sz=0)

    # ── OT planification <1/1-3/>3 mois ──
    # Base = ZCOR + LANC + SOPL==0.
    # Dénominateur = somme des 3 tranches (hors "Inconnu")
    # → garantit que la somme des 3 tranches = 100%.
    # Si Total == 0 → <1m = 100%, 1-3m = 0%, >3m = 0% (somme = 100%).
    pl = cpiv(_zcor_lanc_age, pd.Series(True, index=_zcor_lanc_age.index), "alp", posts)
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        pl[c] = pl.get(c, 0)
    pl["Total"] = pl[["<1 mois", "1 mois < <3 mois", ">3 mois"]].sum(axis=1)
    pl["OT planification <1 mois"] = ckpi(pl["<1 mois"], pl["Total"], sz=100)
    pl["OT planification >3 mois"] = ckpi(pl[">3 mois"], pl["Total"], sz=0)
    pl["OT planification 1mois< <3mois"] = ckpi(pl["1 mois < <3 mois"], pl["Total"], sz=0)

    # ── OT confirmé / coûts égaux (inchangé) ──
    # ── OT CONFIME — CORRIGÉ (bug de colonne) ──
    # L'ancienne boucle calculait OT CONFIME et OT_COR_EGAL à partir de la
    # MÊME colonne "OT_COR_EGAL", ce qui faisait afficher pour OT CONFIME
    # exactement la même valeur que OT_COR_EGAL au lieu de sa propre
    # logique (Statut système contient CLOT/TCLO ET CONF). Périmètre
    # confirmé : Statut OT ∈ {CLOT, TCLO}.
    pv_conf = pd.pivot_table(
        df[df["Statut OT"].isin(["CLOT", "TCLO"])],
        index="Poste travail princ.", columns="OT CONFIME",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        pv_conf[c] = pv_conf.get(c, 0)
    pv_conf["Total"] = pv_conf["OUI"] + pv_conf["NON"]
    pv_conf["OT CONFIME"] = ckpi(pv_conf["OUI"], pv_conf["Total"])
    res["ot_confime"] = pv_conf

    # ── OT_COR_EGAL — AJOUT du périmètre ZCOR (demande explicite) ──
    # ── OT_COR_EGAL — RECALCULÉ DIRECTEMENT (demande explicite) ──
    # Ne dépend plus de la colonne "OT_COR_EGAL" pré-calculée dans
    # prepare_data.py : la comparaison budget/réel est refaite ici, sur
    # les colonnes sources brutes, pour éliminer toute dépendance à un
    # calcul amont potentiellement en cause.
    _scope_cor = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & (df["Type d'ordre"] == "ZCOR")].copy()
    _budget = pd.to_numeric(_scope_cor["Total coûts budgétés"], errors="coerce").fillna(0)
    _reel = pd.to_numeric(_scope_cor["Total coûts réels"], errors="coerce").fillna(0)
    _scope_cor["_cor_egal_recalcule"] = np.where(_budget == _reel, "OUI", "NON")

    pv_cor = pd.pivot_table(
        _scope_cor,
        index="Poste travail princ.", columns="_cor_egal_recalcule",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        pv_cor[c] = pv_cor.get(c, 0)
    pv_cor["Total"] = pv_cor["OUI"] + pv_cor["NON"]
    # INVERSÉ (demande explicite) : le KPI représente désormais le TAUX DE
    # NON-CONCORDANCE (NON/Total), et non plus le taux de concordance
    # (OUI/Total). Plus cette valeur est BASSE, meilleur est le résultat
    # (voir LOWER_BETTER et gscore() dans constants.py / calcul_kpi.py).
    pv_cor["OT_COR_EGAL"] = ckpi(pv_cor["NON"], pv_cor["Total"])
    res["ot_cor_egal"] = pv_cor

    # ── AVIS APPROUVE / Taux d'approbation des Avis — spec §20 ──
    # Population : avf_approve (filtré en amont : exclut ACLO dans Statut
    # système + exclut types ZU/Z4/ZR/ZP — voir prepare_data.py).
    # Numérateur : Statut utilisateur == "APRV" OU "REJET" (spec §20).
    # Anomalie  : Statut utilisateur == "APRQ" (spec §20 - gérée dans anomalies.py).
    # Dénominateur total via groupby direct (évite l'exclusion silencieuse
    # des NaN par pivot_table).
    res['avf'] = av.copy()                 # conservé pour compatibilité
    res['avf_approve'] = avf_approve       # nouvelle population approb.
    tca = pd.pivot_table(
        avf_approve, index="Poste travail princ.", columns="Statut utilisateur",
        values="Avis", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["APRQ", "APRV", "REJET"]:
        tca[c] = tca.get(c, 0)
    total_reel = avf_approve.groupby("Poste travail princ.")["Avis"].count().reindex(posts, fill_value=0)
    tca["Total"] = total_reel
    tca["_num_approve"] = tca["APRV"] + tca["REJET"]
    tca["Taux d'approbation des Avis"] = ckpi(tca["_num_approve"], tca["Total"])

    # ── Performance Graissage — CORRIGÉ (2 bugs détectés lors de l'audit) ──
    # Bug 1 : le numérateur (Statut CLOT/TCLO) n'était pas contraint à
    # Contient SOPL==1 comme le dénominateur — un numérateur pouvait donc
    # dépasser son dénominateur (valeurs >100% constatées : SF1-MPP1,
    # SF1-MPP2). Corrigé en ajoutant Contient SOPL==1 au numérateur aussi,
    # garantissant numérateur ⊆ dénominateur.
    # Bug 2 : la fusion de deux Series indexées différemment (un poste
    # présent dans l'une mais pas l'autre) produisait un NaN non couvert
    # par le reindex(fill_value=0) qui ne s'applique qu'aux postes
    # totalement absents — corrigé par un .fillna(0) explicite après fusion
    # (NaN constatés : SF1-GCMC, SF2-GCFD).
    g_num = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & (df["Contient SOPL"] == 1) & (df["_tw_num"] == 350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_den = df[(df["Contient SOPL"] == 1) & (df["_tw_num"] == 350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_df = pd.DataFrame({"_n": g_num, "_d": g_den}).reindex(posts, fill_value=0).fillna(0)
    g_df["Performance Graissage"] = np.where(
        g_df["_d"] == 0, 100.0, (g_df["_n"] / g_df["_d"]) * 100
    )

    # ── Performance Inspection — MÊME CORRECTIF ──
    ins_types = [290, 300, 310]
    ins_base = (
        (df["_tw_num"].isin(ins_types))
        & (df["Date de début planifiée"].notna())
        & (df["Date de début planifiée"] <= now_ts)
    )
    ins_num = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & (df["Contient SOPL"] == 1) & ins_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    ins_den = df[(df["Contient SOPL"] == 1) & ins_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    ins_df = pd.DataFrame({"_n": ins_num, "_d": ins_den}).reindex(posts, fill_value=0).fillna(0)
    ins_df["Performance Inspection"] = np.where(
        ins_df["_d"] == 0, 100.0, (ins_df["_n"] / ins_df["_d"]) * 100
    )

    # ── Performance Systématiques — MÊME CORRECTIF ──
    sys_base = (
        (df["_tw_num"] == 360)
        & (df["Date de début planifiée"].notna())
        & (df["Date de début planifiée"] <= now_ts)
    )
    sys_num = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & (df["Contient SOPL"] == 1) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_den = df[(df["Contient SOPL"] == 1) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_df = pd.DataFrame({"_n": sys_num, "_d": sys_den}).reindex(posts, fill_value=0).fillna(0)
    sys_df["Performance Systématiques"] = np.where(
        sys_df["_d"] == 0, 100.0, (sys_df["_n"] / sys_df["_d"]) * 100
    )

    fiab_s = pd.Series(100.0, index=posts)
    avpan_s = pd.Series(100.0, index=posts)

    res['ckdf'] = pd.DataFrame({
        "TAUX_REALISATION_CORRECTIF/PT": an["TAUX_REALISATION_CORRECTIF/PT"],
        "OT préparation <1 mois": pr["OT préparation <1 mois"],
        "OT préparation >3 mois": pr["OT préparation >3 mois"],
        "OT préparation 1mois< <3mois": pr["OT préparation 1mois< <3mois"],
        "OT planification <1 mois": pl["OT planification <1 mois"],
        "OT planification >3 mois": pl["OT planification >3 mois"],
        "OT planification 1mois< <3mois": pl["OT planification 1mois< <3mois"],
        "OT exécution <1 mois": ex["OT exécution <1 mois"],
        "OT exécution >3 mois": ex["OT exécution >3 mois"],
        "OT exécution 1mois< <3mois": ex["OT exécution 1mois< <3mois"],
        "Performance Graissage": g_df["Performance Graissage"],
        "Performance Inspection": ins_df["Performance Inspection"],
        "Performance Systématiques": sys_df["Performance Systématiques"],
        "Taux d'approbation des Avis": tca["Taux d'approbation des Avis"],
        "OT LANC ESTIME": la["OT LANC ESTIME"],
        "Backlog préparation caractérisé": pc["Backlog préparation caractérisé"],
        "Backlog planification caractérisé": plc["Backlog planification caractérisé"],
        "OT CONFIME": res['ot_confime']["OT CONFIME"],
        "OT_COR_EGAL": res['ot_cor_egal']["OT_COR_EGAL"],
        "OT Fiabilité": fiab_s,
        "Total Avis de Panne": avpan_s,
    })

    # ── Dictionnaire numérateur/dénominateur (AJOUTÉ, additif uniquement) ──
    # N'existait pas dans le fichier de production ; ajouté sans rien
    # retirer, pour permettre les totaux consolidés (business case,
    # comparaisons). N'affecte aucun calcul existant.
    res['nd'] = {
        "TAUX_REALISATION_CORRECTIF/PT": (an["OT_CLOTURES"], an["TOTAL_OT"]),
        "OT préparation <1 mois": (pr["<1 mois"], pr["Total"]),
        "OT préparation 1mois< <3mois": (pr["1 mois < <3 mois"], pr["Total"]),
        "OT préparation >3 mois": (pr[">3 mois"], pr["Total"]),
        "OT planification <1 mois": (pl["<1 mois"], pl["Total"]),
        "OT planification 1mois< <3mois": (pl["1 mois < <3 mois"], pl["Total"]),
        "OT planification >3 mois": (pl[">3 mois"], pl["Total"]),
        "OT exécution <1 mois": (ex["<1 mois"], ex["Total"]),
        "OT exécution 1mois< <3mois": (ex["1 mois < <3 mois"], ex["Total"]),
        "OT exécution >3 mois": (ex[">3 mois"], ex["Total"]),
        "Performance Graissage": (g_df["_n"], g_df["_d"]),
        "Performance Inspection": (ins_df["_n"], ins_df["_d"]),
        "Performance Systématiques": (sys_df["_n"], sys_df["_d"]),
        "Taux d'approbation des Avis": (tca["_num_approve"], tca["Total"]),
        "OT LANC ESTIME": (la["OUI"], la["Total"]),
        "Backlog préparation caractérisé": (pc["CARACTERISE"], pc["Total"]),
        "Backlog planification caractérisé": (plc["CARACTERISE"], plc["Total"]),
        "OT CONFIME": (res['ot_confime']["OUI"], res['ot_confime']["Total"]),
        "OT_COR_EGAL": (res['ot_cor_egal']["NON"], res['ot_cor_egal']["Total"]),
        "OT Fiabilité": (fiab_s, fiab_s),
        "Total Avis de Panne": (avpan_s, avpan_s),
    }

    return res
