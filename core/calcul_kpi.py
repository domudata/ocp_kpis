# -*- coding: utf-8 -*-
import re
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


def is_cell_red(k: str, a) -> bool:
    """Détermine si une cellule est rouge (non-conforme au-delà de la tolérance de 5 points).
    Règle universelle : tolérance de 5 points pour TOUS les indicateurs par rapport à leur cible.
    - Si plus grand est meilleur : rouge si valeur < cible - 5 (la zone [cible-5, cible[ est en tolérance orange/jaune).
    - Si plus petit est meilleur (LOWER_BETTER) : rouge si valeur > cible + 5 (la zone ]cible, cible+5] est en tolérance orange/jaune).
    - 'OT Fiabilité' et 'Total Avis de Panne' restent non-rouges.
    """
    try:
        val = float(a)
    except Exception:
        return True
    if pd.isna(val):
        return True
    if k in ["OT Fiabilité", "Total Avis de Panne"]:
        return False
    tgt = CIBLE.get(k, 100)
    if k in LOWER_BETTER:
        return val > (tgt + 5)
    return val < (tgt - 5)


def gscore(k: str, a, t=None) -> int:
    """Renvoie 0 si cellule rouge, sinon 1 (vert ou jaune)."""
    return 0 if is_cell_red(k, a) else 1


def is_lb(k: str) -> bool:
    return k in LOWER_BETTER


# ──────────────────────────────────────────────
# Caractérisation Backlog préparation/planification
# Périmètre : OT de type ZCOR uniquement.
# Logique : "pas contient exacte mais il existe le mot"
# ──────────────────────────────────────────────

CODES_PREP_EXACT = {"ATPD", "ATMR", "ATER", "ATRS", "ATMO"}
CODES_PLAN_EXACT = {"ATEI", "ATAL", "ATAS", "AGAR", "ATHS"}
ALL_CARAC_EXACT = CODES_PREP_EXACT | CODES_PLAN_EXACT


def match_exact_token(statut, codes: set) -> bool:
    """True si au moins un des codes existe comme mot dans le statut utilisateur SAP
    ('pas contient exacte mais il existe le mot', gère 'CRPR ATPD', 'ATPL ATAL', 'CRPR/ATPD', 'ATPD', etc.)."""
    if statut is None or (isinstance(statut, float) and pd.isna(statut)):
        return False
    words = set(re.findall(r'[A-Za-z0-9]+', str(statut).upper()))
    return bool(words & codes)


# ──────────────────────────────────────────────
# Calcul principal des KPI
# ──────────────────────────────────────────────

def calc_kpis(df_i: pd.DataFrame, av_i: pd.DataFrame, now_ts, posts: list,
              df_toutes_dates: pd.DataFrame = None) -> dict:
    """
    df_toutes_dates : DataFrame OT identique à df_i mais SANS le filtre de
    période de la barre latérale (mêmes colonnes). Utilisé UNIQUEMENT pour
    les indicateurs Backlog préparation/planification caractérisé (et les
    OT préparation/planification par âge qui en découlent désormais),
    dont le calcul doit porter sur l'historique complet quelle que soit la
    période sélectionnée par l'utilisateur (demande explicite). Si non
    fourni, df_i est réutilisé (comportement inchangé, rétrocompatible).
    """
    res = {}
    df = df_i.copy()
    av = av_i.copy()
    res['dfp'] = df
    df_all = df_toutes_dates.copy() if df_toutes_dates is not None else df

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

    # ── Exécution (demande explicite : OT lancé, type ZCOR, non caractérisé planif ou prépar) ──
    # Âge (jours) = Date de l'extraction (now_ts) - Date de début planifiée (colonne 'aex')
    _statut_lanc_ex = (
        (df_all["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "LANC")
        | (df_all["Statut système"].fillna("").astype(str).str.contains("LANC", na=False)
           & ~df_all["Statut système"].fillna("").astype(str).str.contains("CLOT|TCLO", na=False))
    )
    _non_clot_ex = ~df_all["Statut OT"].isin(["CLOT", "TCLO"]) if "Statut OT" in df_all.columns else True
    _zcor_ex = (df_all["Type d'ordre"] == "ZCOR") & _statut_lanc_ex & _non_clot_ex
    _pas_carac_ex = ~df_all["Statut utilisateur"].apply(lambda x: match_exact_token(x, ALL_CARAC_EXACT))
    _zcor_exec_all = df_all[_zcor_ex & _pas_carac_ex].copy()

    ex = cpiv(
        _zcor_exec_all,
        pd.Series(True, index=_zcor_exec_all.index),
        "aex", posts
    )
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        ex[c] = ex.get(c, 0)
    ex["<1 mois"] = ex["<1 mois"] + ex["Inconnu"]
    ex["Total"] = ex[["<1 mois", "1 mois < <3 mois", ">3 mois"]].sum(axis=1)
    ex["OT exécution <1 mois"] = ckpi(ex["<1 mois"], ex["Total"])
    ex["OT exécution 1mois< <3mois"] = ckpi(ex["1 mois < <3 mois"], ex["Total"], 0)
    ex["OT exécution >3 mois"] = ckpi(ex[">3 mois"], ex["Total"], 0)

    # ── OT LANC ESTIME — CONTIENT LANC ET TYPE ZCOR (demande explicite : statut contient LANC, type ZCOR, budget=0 anomalie) ──
    _statut_lanc = df["Statut système"].fillna("").astype(str).str.contains("LANC", na=False) | (df["Statut OT"] == "LANC")
    _lanc_scope = df[_statut_lanc & (df["Type d'ordre"] == "ZCOR")]
    la = pd.pivot_table(
        _lanc_scope,
        index="Poste travail princ.",
        columns="OT LANC ESTIME", values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        la[c] = la.get(c, 0)
    la["Total"] = la["OUI"] + la["NON"]
    la["OT LANC ESTIME"] = ckpi(la["OUI"], la["Total"])

    # ── Backlog préparation caractérisé — NOUVELLE LOGIQUE (convenue) ──
    # Périmètre : Type d'ordre == "ZCOR", sur df_all (toutes dates).
    # Caractérisé = Statut utilisateur égal STRICTEMENT à ATPD/ATMR/ATER/ATRS/ATMO.
    _zcor_all = df_all[df_all["Type d'ordre"] == "ZCOR"].copy()

    # AJOUTÉ (demande explicite) : le périmètre de la Préparation doit
    # être ZCOR ET Statut système == CRÉÉ (symétrique à Planification,
    # qui exige déjà ZCOR ET Statut système == LANC ci-dessous). Cette
    # restriction est appliquée à une COPIE dédiée (_zcor_cree_all) pour
    # ne pas restreindre _zcor_all, dont dérive aussi la population
    # Planification (ZCOR seul, puis filtrée sur LANC séparément).
    _zcor_cree_all = _zcor_all[
        _zcor_all["Statut système"].fillna("").astype(str).str.strip().str.split().str[0].isin(["CRÉÉ", "CREE"])
    ].copy()
    _zcor_cree_all["_prep_carac"] = np.where(
        _zcor_cree_all["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PREP_EXACT)),
        "CARACTERISE", "NON CARACTERISE",
    )
    pc = pd.pivot_table(
        _zcor_cree_all, index="Poste travail princ.", columns="_prep_carac",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE", "NON CARACTERISE"]:
        pc[c] = pc.get(c, 0)
    pc["Total"] = pc["CARACTERISE"] + pc["NON CARACTERISE"]
    pc["Backlog préparation caractérisé"] = ckpi(pc["CARACTERISE"], pc["Total"])

    # ── Backlog planification caractérisé — SYNCHRONISÉ ──
    # Périmètre : ZCOR ET Statut système == LANC ET Contient SOPL == 0, sur df_all.
    # Caractérisé = Statut utilisateur contient ATPL ou un motif ATEI/ATAL/ATAS/AGAR/ATHS.
    _zcor_lanc_all = _zcor_all[
        (_zcor_all["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "LANC")
        & (_zcor_all["Contient SOPL"] == 0)
    ].copy()
    _zcor_lanc_all["_plan_carac"] = np.where(
        _zcor_lanc_all["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT)),
        "CARACTERISE", "NON CARACTERISE",
    )
    plc = pd.pivot_table(
        _zcor_lanc_all, index="Poste travail princ.", columns="_plan_carac",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE", "NON CARACTERISE"]:
        plc[c] = plc.get(c, 0)
    plc["Total"] = plc["CARACTERISE"] + plc["NON CARACTERISE"]
    plc["Backlog planification caractérisé"] = ckpi(plc["CARACTERISE"], plc["Total"])

    # ── OT préparation <1/1-3/>3 mois — SUR LE BACKLOG COMPLET PRÉPARATION (_zcor_cree_all) ──
    pr = cpiv(_zcor_cree_all, pd.Series(True, index=_zcor_cree_all.index), "ap", posts)
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        pr[c] = pr.get(c, 0)
    pr["<1 mois"] = pr["<1 mois"] + pr["Inconnu"]
    pr["Total"] = pr["<1 mois"] + pr["1 mois < <3 mois"] + pr[">3 mois"]
    pr["OT préparation <1 mois"] = ckpi(pr["<1 mois"], pr["Total"])
    pr["OT préparation 1mois< <3mois"] = ckpi(pr["1 mois < <3 mois"], pr["Total"], 0)
    pr["OT préparation >3 mois"] = ckpi(pr[">3 mois"], pr["Total"], 0)

    # ── OT planification <1/1-3/>3 mois — SUR LE BACKLOG COMPLET PLANIFICATION (_zcor_lanc_all) ──
    pl = cpiv(_zcor_lanc_all, pd.Series(True, index=_zcor_lanc_all.index), "alp", posts)
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        pl[c] = pl.get(c, 0)
    pl["<1 mois"] = pl["<1 mois"] + pl["Inconnu"]
    pl["Total"] = pl["<1 mois"] + pl["1 mois < <3 mois"] + pl[">3 mois"]
    pl["OT planification <1 mois"] = ckpi(pl["<1 mois"], pl["Total"])
    pl["OT planification 1mois< <3mois"] = ckpi(pl["1 mois < <3 mois"], pl["Total"], 0)
    pl["OT planification >3 mois"] = ckpi(pl[">3 mois"], pl["Total"], 0)

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

    # ── OT_COR_EGAL — (Périmètre ZCOR + CLOT/TCLO, conforme si budget != réel ET réel != 0) ──
    _statut_clot_tclo = df["Statut OT"].isin(["CLOT", "TCLO"]) | df["Statut système"].str.contains("CLOT|TCLO", na=False)
    _scope_cor = df[_statut_clot_tclo & (df["Type d'ordre"] == "ZCOR")].copy()
    _budget = pd.to_numeric(_scope_cor["Total coûts budgétés"], errors="coerce").fillna(0)
    _reel = pd.to_numeric(_scope_cor["Total coûts réels"], errors="coerce").fillna(0)
    _scope_cor["_is_conforme"] = np.where((_budget != _reel) & (_reel != 0), "OUI", "NON")

    pv_cor = pd.pivot_table(
        _scope_cor,
        index="Poste travail princ.", columns="_is_conforme",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        pv_cor[c] = pv_cor.get(c, 0)
    pv_cor["Total"] = pv_cor["OUI"] + pv_cor["NON"]
    pv_cor["OT_COR_EGAL"] = ckpi(pv_cor["OUI"], pv_cor["Total"])
    res["ot_cor_egal"] = pv_cor

    # NOTE : le filtre d'exclusion ZU/Z4/ZR/ZP a été retiré ici. avf, tel
    # que construit par prepare_data.py, est DÉJÀ restreint à ces mêmes
    # types (avec Ordre vide) — un filtre d'exclusion supplémentaire ici
    # viderait la population presque entièrement (107 → 0 lignes constaté
    # sur données réelles). Voir prepare_data.py pour la définition d'avf.
    avf = av.copy()
    res['avf'] = avf
    # Total avis sans ordre et hors ZU/Z4/ZR/ZP par poste (population avf)
    avf_tot = avf.groupby("Poste travail princ.")["Avis"].count().reindex(posts, fill_value=0)
    # Anomalie : Statut système contient AOUV (Avis Ouvert sans OT)
    _is_aouv = avf["Statut système"].fillna("").astype(str).str.contains("AOUV", case=False, na=False)
    avf_aouv = avf[_is_aouv].groupby("Poste travail princ.")["Avis"].count().reindex(posts, fill_value=0)
    # Conformes : avis traités/approuvés (ne contenant pas AOUV)
    avf_conf = avf_tot - avf_aouv
    tca = pd.DataFrame({
        "CONFORME": avf_conf,
        "AOUV": avf_aouv,
        "Total": avf_tot,
        "Taux d'approbation des Avis": np.where(avf_tot == 0, 100.0, (avf_conf / avf_tot) * 100.0)
    }, index=posts)

    # ── Performance Graissage (inchangé) ──
    g_num = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & (df["_tw_num"] == 350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_den = df[(df["Contient SOPL"] == 1) & (df["_tw_num"] == 350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_df = pd.DataFrame({"_n": g_num, "_d": g_den}).reindex(posts, fill_value=0)
    g_df["Performance Graissage"] = np.where(
        g_df["_d"] == 0, 100.0, (g_df["_n"] / g_df["_d"]) * 100
    )

    # ── Performance Inspection (inchangé) ──
    ins_types = [290, 300, 310]
    ins_base = (
        (df["_tw_num"].isin(ins_types))
        & (df["Date de début planifiée"].notna())
        & (df["Date de début planifiée"] <= now_ts)
    )
    ins_num = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & ins_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    ins_den = df[(df["Contient SOPL"] == 1) & ins_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    ins_df = pd.DataFrame({"_n": ins_num, "_d": ins_den}).reindex(posts, fill_value=0)
    ins_df["Performance Inspection"] = np.where(
        ins_df["_d"] == 0, 100.0, (ins_df["_n"] / ins_df["_d"]) * 100
    )

    # ── Performance Systématiques (inchangé) ──
    sys_base = (
        (df["_tw_num"] == 360)
        & (df["Date de début planifiée"].notna())
        & (df["Date de début planifiée"] <= now_ts)
    )
    sys_num = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_den = df[(df["Contient SOPL"] == 1) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_df = pd.DataFrame({"_n": sys_num, "_d": sys_den}).reindex(posts, fill_value=0)
    sys_df["Performance Systématiques"] = np.where(
        sys_df["_d"] == 0, 100.0, (sys_df["_n"] / sys_df["_d"]) * 100
    )

    fiab_s = pd.Series(100.0, index=posts)
    avpan_s = pd.Series(100.0, index=posts)

    res['ckdf'] = pd.DataFrame({
        "TAUX_REALISATION_CORRECTIF/PT": an["TAUX_REALISATION_CORRECTIF/PT"],
        "OT préparation <1 mois": pr["OT préparation <1 mois"],
        "OT préparation 1mois< <3mois": pr["OT préparation 1mois< <3mois"],
        "OT préparation >3 mois": pr["OT préparation >3 mois"],
        "OT planification <1 mois": pl["OT planification <1 mois"],
        "OT planification 1mois< <3mois": pl["OT planification 1mois< <3mois"],
        "OT planification >3 mois": pl["OT planification >3 mois"],
        "OT exécution <1 mois": ex["OT exécution <1 mois"],
        "OT exécution 1mois< <3mois": ex["OT exécution 1mois< <3mois"],
        "OT exécution >3 mois": ex["OT exécution >3 mois"],
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
        "Taux d'approbation des Avis": (tca["CONFORME"], tca["Total"]),
        "OT LANC ESTIME": (la["OUI"], la["Total"]),
        "Backlog préparation caractérisé": (pc["CARACTERISE"], pc["Total"]),
        "Backlog planification caractérisé": (plc["CARACTERISE"], plc["Total"]),
        "OT CONFIME": (res['ot_confime']["OUI"], res['ot_confime']["Total"]),
        "OT_COR_EGAL": (res['ot_cor_egal']["OUI"], res['ot_cor_egal']["Total"]),
        "OT Fiabilité": (fiab_s, fiab_s),
        "Total Avis de Panne": (avpan_s, avpan_s),
    }

    return res
