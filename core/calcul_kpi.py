# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from core.constants import MP_KW, MPLAN_KW, QK, PK, ALL_KPI, CIBLE, LOWER_BETTER


def ckpi(n, d, sz=100):
    return np.where(d == 0, sz, (n / d) * 100)


def cpiv(df: pd.DataFrame, f, c: str, p: list) -> pd.DataFrame:
    return (
        pd.pivot_table(
            df[f], index="Poste travail princ.", columns=c,
            values="Ordre", aggfunc="count", fill_value=0
        ).reindex(p, fill_value=0)
    )


def gscore(k: str, a, t) -> int:
    if pd.isna(a):
        return 0
    try:
        a = float(a)
    except Exception:
        return 0

    if k in ["OT préparation <1 mois", "OT planification <1 mois", "OT exécution <1 mois"]:
        return 0 if a < 75 else 1
    if k in ["OT préparation 1mois< <3mois", "OT planification 1mois< <3mois", "OT exécution 1mois< <3mois"]:
        return 0 if a > 15 else 1
    if k in ["OT préparation >3 mois", "OT planification >3 mois", "OT exécution >3 mois"]:
        return 0 if a > 5 else 1
    if k in ["TAUX_REALISATION_CORRECTIF/PT", "Performance Systématiques"]:
        return 0 if a < 80 else 1
    if k == "Taux d'approbation des Avis":
        return 0 if a < 90 else 1
    if k in ["OT LANC ESTIME", "Backlog préparation caractérisé",
             "Backlog planification caractérisé", "OT CONFIME", "OT_COR_EGAL"]:
        return 0 if a < 95 else 1
    if k in ["Performance Graissage", "Performance Inspection"]:
        return 0 if a <= 90 else 1
    if k in ["OT Fiabilité", "Total Avis de Panne"]:
        return 1
    return 0 if a < 80 else 1


def is_lb(k: str) -> bool:
    return k in LOWER_BETTER


def match_exact_token(statut, codes: set) -> bool:
    """Retourne True si Statut utilisateur, une fois débarrassé des
    espaces superflus, est ÉGAL STRICTEMENT à l'un des CODES — aucune
    addition avant ou après n'est tolérée.

    CORRIGÉ (précision explicite, deuxième itération) : la version
    précédente acceptait les formes composées ("CRPR ATPD", "ATPL ATEI")
    dès lors que l'un des mots correspondait à un code. Sur demande
    explicite, ce comportement est resserré : une valeur composée comme
    "CRPR ATPD" est désormais NON CARACTERISE, seule la valeur "ATPD"
    seule (sans aucun préfixe/suffixe) est CARACTERISE.
    """
    if statut is None or (isinstance(statut, float) and pd.isna(statut)):
        return False
    return str(statut).strip().upper() in codes


CODES_PREP_EXACT = {"ATPD", "ATMR", "ATER", "ATRS", "ATMO"}
CODES_PLAN_EXACT = {"ATEI", "ATAL", "ATAS", "AGAR", "ATHS"}


def calc_kpis(df_i: pd.DataFrame, av_i: pd.DataFrame, now_ts, posts: list,
               df_toutes_dates: pd.DataFrame = None) -> dict:
    """
    df_toutes_dates : DataFrame OT SANS le filtre de période de la barre
    latérale (mêmes colonnes que df_i). Utilisé UNIQUEMENT pour les deux
    indicateurs Backlog préparation/planification caractérisé, dont le
    calcul doit porter sur l'historique complet des OT ZCOR quelle que
    soit la période sélectionnée par l'utilisateur (demande explicite).
    Si non fourni, df_i est réutilisé (comportement inchangé).
    """
    res = {}
    df = df_i.copy()
    av = av_i.copy()
    res['dfp'] = df
    df_all = df_toutes_dates.copy() if df_toutes_dates is not None else df

    filt_corr = (df["Nº appel pl.entret."].fillna(0) == 0) & (df["Contient SOPL"] == 1)
    an = cpiv(df, filt_corr, "Statut OT", posts)
    for c in ["CLOT", "CRÉÉ", "LANC", "TCLO"]:
        an[c] = an.get(c, 0)
    an["OT_CLOTURES"] = an["CLOT"] + an["TCLO"]
    an["TOTAL_OT"] = an[["CLOT", "CRÉÉ", "LANC", "TCLO"]].sum(axis=1)
    an["TAUX_REALISATION_CORRECTIF/PT"] = np.where(
        an["TOTAL_OT"] == 0, 100.0, ckpi(an["OT_CLOTURES"], an["TOTAL_OT"])
    )

    # (pr et pl — OT préparation/planification par âge — sont désormais
    # calculés plus bas, juste après pc/plc, car ils réutilisent la même
    # population NON CARACTERISE issue de _zcor_all / _zcor_lanc_all.)



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

    la = pd.pivot_table(
        df[(df["Statut OT"] == "LANC") & (df["Type d'ordre"] == "ZCOR") & (df["Contient SOPL"] == 1)],
        index="Poste travail princ.",
        columns="OT LANC ESTIME", values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        la[c] = la.get(c, 0)
    la["Total"] = la["OUI"] + la["NON"]
    la["OT LANC ESTIME"] = ckpi(la["OUI"], la["Total"])

    # ── Backlog préparation caractérisé — NOUVELLE LOGIQUE (demande explicite) ──
    # Périmètre : OT de type ZCOR (correctifs) uniquement, sur TOUTES les
    # dates (df_all, indépendant du filtre de période de la barre latérale).
    # Caractérisé = Statut utilisateur contient, en token exact, l'un des
    # codes ATPD / ATMR / ATER / ATRS / ATMO.
    _zcor_all = df_all[df_all["Type d'ordre"] == "ZCOR"].copy()
    _zcor_all["_prep_carac"] = np.where(
        _zcor_all["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PREP_EXACT)),
        "CARACTERISE", "NON CARACTERISE",
    )
    pc = pd.pivot_table(
        _zcor_all, index="Poste travail princ.", columns="_prep_carac",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE", "NON CARACTERISE"]:
        pc[c] = pc.get(c, 0)
    pc["Total"] = pc["CARACTERISE"] + pc["NON CARACTERISE"]
    pc["Backlog préparation caractérisé"] = ckpi(pc["CARACTERISE"], pc["Total"])

    # ── Backlog planification caractérisé — NOUVELLE LOGIQUE (demande explicite) ──
    # Périmètre : OT ZCOR ET Statut système = LANC, sur TOUTES les dates.
    # Caractérisé = Statut utilisateur contient, en token exact, l'un des
    # codes ATEI / ATAL / ATAS / AGAR / ATHS.
    _zcor_lanc_all = _zcor_all[
        _zcor_all["Statut système"].fillna("").astype(str).str.strip().str.split().str[0] == "LANC"
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

    # ── OT préparation <1/1-3/>3 mois — NOUVELLE LOGIQUE (demande explicite) ──
    # Base = OT NON CARACTERISE du Backlog préparation (même population
    # que ci-dessus), répartis selon leur âge ("ap" = jours depuis "Créé le").
    _non_prep_age = _zcor_all[_zcor_all["_prep_carac"] == "NON CARACTERISE"]
    pr = cpiv(_non_prep_age, pd.Series(True, index=_non_prep_age.index), "ap", posts)
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        pr[c] = pr.get(c, 0)
    pr["Total"] = pr[["<1 mois", "1 mois < <3 mois", ">3 mois", "Inconnu"]].sum(axis=1)
    pr["OT préparation <1 mois"] = ckpi(pr["<1 mois"], pr["Total"])
    pr["OT préparation >3 mois"] = ckpi(pr[">3 mois"], pr["Total"], 0)
    pr["OT préparation 1mois< <3mois"] = ckpi(pr["1 mois < <3 mois"], pr["Total"], 0)

    # ── OT planification <1/1-3/>3 mois — même logique, sur "alp" ──
    _non_plan_age = _zcor_lanc_all[_zcor_lanc_all["_plan_carac"] == "NON CARACTERISE"]
    pl = cpiv(_non_plan_age, pd.Series(True, index=_non_plan_age.index), "alp", posts)
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        pl[c] = pl.get(c, 0)
    pl["Total"] = pl[["<1 mois", "1 mois < <3 mois", ">3 mois", "Inconnu"]].sum(axis=1)
    pl["OT planification <1 mois"] = ckpi(pl["<1 mois"], pl["Total"])
    pl["OT planification >3 mois"] = ckpi(pl[">3 mois"], pl["Total"], 0)
    pl["OT planification 1mois< <3mois"] = ckpi(pl["1 mois < <3 mois"], pl["Total"], 0)

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

    pv_cor = pd.pivot_table(
        df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & (df["Type d'ordre"] == "ZCOR")],
        index="Poste travail princ.", columns="OT_COR_EGAL",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        pv_cor[c] = pv_cor.get(c, 0)
    pv_cor["Total"] = pv_cor["OUI"] + pv_cor["NON"]
    pv_cor["OT_COR_EGAL"] = ckpi(pv_cor["NON"], pv_cor["Total"])
    res["ot_cor_egal"] = pv_cor

    avf = av.copy()
    res['avf'] = avf
    # CORRIGÉ (ré-ajouté sur demande) : le document officiel SAP PM précise
    # "hors les avis types : ZU, Z4, ZR, ZP" pour le Taux d'approbation des
    # Avis. Ce filtre avait disparu du code ; il est réintégré ici. Impact
    # mesuré sur données réelles : marginal sur ce KPI (population -1,1%,
    # taux +0,3 point), car ZP/ZR concernent surtout des avis hors du
    # périmètre Statut utilisateur (APRQ/APRV/APRV AVAU) déjà retenu.
    avf_filtre = avf[~avf["Type d'avis"].isin(["ZU", "Z4", "ZR", "ZP"])] if "Type d'avis" in avf.columns else avf
    tca = pd.pivot_table(
        avf_filtre, index="Poste travail princ.", columns="Statut utilisateur",
        values="Avis", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["APRQ", "APRV", "APRV AVAU", "REJT"]:
        tca[c] = tca.get(c, 0)
    tca["Total"] = tca[["APRQ", "APRV", "APRV AVAU"]].sum(axis=1)
    tca["Taux d'approbation des Avis"] = ckpi(tca["APRV"], tca["Total"])

    g_num = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & (df["_tw_num"] == 350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_den = df[(df["Contient SOPL"] == 1) & (df["_tw_num"] == 350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_df = pd.DataFrame({"_n": g_num, "_d": g_den}).reindex(posts, fill_value=0).fillna(0)
    g_df["Performance Graissage"] = np.where(
        g_df["_d"] == 0, 100.0, (g_df["_n"] / g_df["_d"]) * 100
    )

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
    ins_df = pd.DataFrame({"_n": ins_num, "_d": ins_den}).reindex(posts, fill_value=0).fillna(0)
    ins_df["Performance Inspection"] = np.where(
        ins_df["_d"] == 0, 100.0, (ins_df["_n"] / ins_df["_d"]) * 100
    )

    sys_base = (
        (df["_tw_num"] == 360)
        & (df["Date de début planifiée"].notna())
        & (df["Date de début planifiée"] <= now_ts)
    )
    sys_num = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_den = df[(df["Contient SOPL"] == 1) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_df = pd.DataFrame({"_n": sys_num, "_d": sys_den}).reindex(posts, fill_value=0).fillna(0)
    sys_df["Performance Systématiques"] = np.where(
        sys_df["_d"] == 0, 100.0, (sys_df["_n"] / sys_df["_d"]) * 100
    )

    fiab_s = pd.Series(100.0, index=posts)
    avpan_s = pd.Series(100.0, index=posts)

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
        "Taux d'approbation des Avis": (tca["APRV"], tca["Total"]),
        "OT LANC ESTIME": (la["OUI"], la["Total"]),
        "Backlog préparation caractérisé": (pc["CARACTERISE"], pc["Total"]),
        "Backlog planification caractérisé": (plc["CARACTERISE"], plc["Total"]),
        "OT CONFIME": (pv_conf["OUI"], pv_conf["Total"]),
        "OT_COR_EGAL": (pv_cor["NON"], pv_cor["Total"]),
        "OT Fiabilité": (fiab_s, fiab_s),
        "Total Avis de Panne": (avpan_s, avpan_s),
    }

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

    return res
