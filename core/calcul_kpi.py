
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
    if k in ["OT préparation <1 mois", "OT planification <1 mois", "OT exécution <1 mois"]:
        return 1 if a >= 75 else 0
    if k in ["OT préparation 1mois< <3mois", "OT planification 1mois< <3mois", "OT exécution 1mois< <3mois"]:
        return 1 if a <= 15 else 0
    if k in ["OT préparation >3 mois", "OT planification >3 mois", "OT exécution >3 mois"]:
        return 1 if a <= 5 else 0
    if k == "TAUX_REALISATION_CORRECTIF/PT":
        return 1 if a >= 80 else 0
    if k == "Taux d'approbation des Avis":
        return 1 if a >= 90 else 0
    if k in ["OT LANC ESTIME", "Backlog préparation caractérisé",
             "Backlog planification caractérisé", "OT CONFIME"]:
        return 1 if a >= 95 else 0
    if k == "OT_COR_EGAL":
        # INVERSÉ (demande explicite) : ce KPI représente désormais le taux
        # de NON-concordance (NON/Total) — plus bas est meilleur.
        return 1 if a <= 5 else 0
    if k in ["Performance Graissage", "Performance Inspection", "Performance Systématiques"]:
        return 1 if a >= 95 else 0
    if k in ["OT Fiabilité", "Total Avis de Panne"]:
        return 1 if a >= 100 else 0
    return 0


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
# Fonctions de population centralisées
# Réutilisées par anomalies.py pour garantir la cohérence KPI / anomalies.
# ──────────────────────────────────────────────

def build_avis_zc_population(avdf: pd.DataFrame) -> pd.DataFrame:
    """Population commune pour le KPI « Taux d'approbation des Avis ».

    Règles :
      - exclusion des types d'Avis ZU, Z4, ZR et ZP ;
      - les autres types sont conservés ;
      - la population APRV sert au numérateur ;
      - le dénominateur du KPI est le total des OT CRÉÉ et non le total des Avis.

    La fonction accepte les colonnes préparées par prepare_data.py :
      _type_avis / _avis_type_exclu.
    Elle reste rétrocompatible si ces colonnes n'existent pas.
    """
    av = avdf.copy()

    if "_avis_type_exclu" in av.columns:
        return av[~av["_avis_type_exclu"].fillna(False)].copy()

    if "_type_avis" in av.columns:
        types_exclus = {"ZU", "Z4", "ZR", "ZP"}
        types = av["_type_avis"].fillna("").astype(str).str.strip().str.upper()
        return av[~types.isin(types_exclus)].copy()

    # Si la préparation n'a pas encore ajouté le type, on conserve la population
    # afin de ne pas casser l'application.
    return av.copy()


def build_execution_population(df: pd.DataFrame, now_ts=None) -> pd.DataFrame:
    """Population d'exécution : LANC (contient) + Contient SOPL==1.
    Filtre Type d'ordre (ZCOR) et Type de travail SUPPRIMÉ (demande explicite).
    Tous les OT lancés contenant SOPL sont distribués sur les 3 tranches
    d'âge d'exécution (<1 mois / 1-3 mois / >3 mois).

    Population commune pour les KPI âge d'exécution et les anomalies
    correspondantes dans anomalies.py.
    """
    mask = (
        (
            (df["Statut OT"].fillna("").astype(str).str.upper().str.strip() == "LANC")
            | df["Statut système"].fillna("").astype(str).str.contains("LANC", na=False)
        )
        & (pd.to_numeric(df["Contient SOPL"], errors="coerce").fillna(0) == 1)
    )
    return df[mask].copy()


def build_avis_anomalies_population(avdf: pd.DataFrame) -> pd.DataFrame:
    """Population commune des anomalies Avis.

    Une anomalie Avis est définie par :
      - Statut système = AOUV
      - Statut utilisateur = APRQ
      - exclusion des types ZU, Z4, ZR et ZP
    """
    av = build_avis_zc_population(avdf)

    statut_sys = (
        av.get("Statut système", pd.Series("", index=av.index))
        .fillna("").astype(str).str.upper().str.strip()
    )
    statut_usr = (
        av.get("Statut utilisateur", pd.Series("", index=av.index))
        .fillna("").astype(str).str.upper().str.strip()
    )

    mask = (
        statut_sys.str.contains(r"\bAOUV\b", regex=True, na=False)
        & statut_usr.str.contains(r"\bAPRQ\b", regex=True, na=False)
    )
    return av[mask].copy()


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

    # ── Exécution — NOUVELLE POPULATION : LANC + SOPL==1 (sans filtre ZCOR/type travail) ──
    df_exec = build_execution_population(df_all, now_ts)
    ex = cpiv(df_exec, pd.Series(True, index=df_exec.index), "aex", posts)
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois"]:
        ex[c] = ex.get(c, 0)
    # Total = somme des 3 tranches réelles seulement (pas d'"Inconnu").
    ex["Total"] = ex[["<1 mois", "1 mois < <3 mois", ">3 mois"]].sum(axis=1)
    # Pourcentages directs — si Total == 0 : résultat = 0 % (ckpi sz=0).
    ex["OT exécution <1 mois"] = ckpi(ex["<1 mois"], ex["Total"])
    ex["OT exécution >3 mois"] = ckpi(ex[">3 mois"], ex["Total"], 0)
    ex["OT exécution 1mois< <3mois"] = ckpi(ex["1 mois < <3 mois"], ex["Total"], 0)

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

    # ── Backlog préparation caractérisé — NOUVELLE LOGIQUE (convenue) ──
    # Périmètre : Type d'ordre == "ZCOR", sur df_all (toutes dates).
    # Statut système contient "CRÉÉ" (pas restreint au 1er mot).
    # Caractérisé = Statut utilisateur égal STRICTEMENT à ATPD/ATMR/ATER/ATRS/ATMO.
    _zcor_all = df_all[df_all["Type d'ordre"] == "ZCOR"].copy()

    _zcor_cree_all = _zcor_all[
        (
            (_zcor_all["Statut OT"] == "CRÉÉ")
            | _zcor_all["Statut système"].fillna("").astype(str).str.contains("CRÉÉ|CREE|CRÉE", regex=True, na=False)
        )
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

    # ── Backlog planification caractérisé — NOUVELLE LOGIQUE (convenue) ──
    # Périmètre : ZCOR ET Statut système contient "LANC" ET Contient SOPL == 0, sur df_all.
    # Caractérisé = Statut utilisateur égal STRICTEMENT à ATEI/ATAL/ATAS/AGAR/ATHS.
    _zcor_lanc_all = _zcor_all[
        (
            (_zcor_all["Statut OT"] == "LANC")
            | _zcor_all["Statut système"].fillna("").astype(str).str.contains("LANC", na=False)
        )
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

    # ── OT préparation <1/1-3/>3 mois ──
    # Base = POPULATION COMPLÈTE du Backlog préparation (ZCOR + CRÉÉ),
    # CARACTERISE ET NON CARACTERISE confondus, répartie intégralement sur
    # les 3 tranches d'âge.
    pr = cpiv(_zcor_cree_all, pd.Series(True, index=_zcor_cree_all.index), "ap", posts)
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois"]:
        pr[c] = pr.get(c, 0)
    pr["Total"] = pr[["<1 mois", "1 mois < <3 mois", ">3 mois"]].sum(axis=1)
    pr["OT préparation <1 mois"] = ckpi(pr["<1 mois"], pr["Total"])
    pr["OT préparation >3 mois"] = ckpi(pr[">3 mois"], pr["Total"], 0)
    pr["OT préparation 1mois< <3mois"] = ckpi(pr["1 mois < <3 mois"], pr["Total"], 0)

    # ── OT planification <1/1-3/>3 mois — NOUVELLE BASE : ANOMALIES NON CARACTÉRISÉES (demande explicite) ──
    # Base = Population des OT lancés NON CARACTÉRISÉS en planification (ZCOR + LANC + SOPL==0 + non carac),
    # répartie sur les 3 tranches d'âge. Le total correspond au total des anomalies de planification.
    _zcor_lanc_non_carac = _zcor_lanc_all[_zcor_lanc_all["_plan_carac"] == "NON CARACTERISE"].copy()
    pl = cpiv(_zcor_lanc_non_carac, pd.Series(True, index=_zcor_lanc_non_carac.index), "alp", posts)
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois"]:
        pl[c] = pl.get(c, 0)
    pl["Total"] = pl[["<1 mois", "1 mois < <3 mois", ">3 mois"]].sum(axis=1)
    pl["OT planification <1 mois"] = ckpi(pl["<1 mois"], pl["Total"])
    pl["OT planification >3 mois"] = ckpi(pl[">3 mois"], pl["Total"], 0)
    pl["OT planification 1mois< <3mois"] = ckpi(pl["1 mois < <3 mois"], pl["Total"], 0)

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

    # ── Taux d'approbation des Avis — NOUVELLE LOGIQUE ──
    # Numérateur : Avis APRV (hors ZU/Z4/ZR/ZP).
    # Dénominateur : TOTAL OT CRÉÉ, et NON le nombre total d'Avis.
    # Le calcul reste par Poste de travail afin de conserver la granularité
    # du dashboard.
    avf_zc = build_avis_zc_population(av)
    res['avf'] = avf_zc

    # Avis APRV par poste. On accepte APRV et APRV AVAU comme auparavant,
    # mais uniquement après exclusion des types ZU/Z4/ZR/ZP.
    if not avf_zc.empty and "Poste travail princ." in avf_zc.columns:
        _avis_statut = (
            avf_zc.get("Statut utilisateur", pd.Series("", index=avf_zc.index))
            .fillna("").astype(str).str.upper().str.strip()
        )
        _avis_aprv_mask = _avis_statut.str.contains(r"\bAPRV\b", regex=True, na=False)
        aprv_par_poste = (
            avf_zc.loc[_avis_aprv_mask]
            .groupby("Poste travail princ.")["Avis"]
            .count()
            .reindex(posts, fill_value=0)
        )
    else:
        aprv_par_poste = pd.Series(0, index=posts, dtype=float)

    # Total OT CRÉÉ par Poste de travail. Compatibilité CRÉÉ/CREE.
    _statut_ot_calc = (
        df["Statut OT"].fillna("").astype(str).str.upper().str.strip()
    )
    _ot_cree_mask = _statut_ot_calc.isin(["CRÉÉ", "CREE"])
    ot_cree_par_poste = (
        df.loc[_ot_cree_mask]
        .groupby("Poste travail princ.")["Ordre"]
        .count()
        .reindex(posts, fill_value=0)
    )

    tca = pd.DataFrame(index=posts)
    tca["APRV"] = aprv_par_poste.astype(float)
    tca["Total OT CRÉÉ"] = ot_cree_par_poste.astype(float)
    tca["Total"] = tca["Total OT CRÉÉ"]
    tca["Taux d'approbation des Avis"] = np.where(
        tca["Total OT CRÉÉ"] == 0,
        0.0,
        ckpi(tca["APRV"], tca["Total OT CRÉÉ"])
    )
    # Pour conserver les colonnes historiques éventuellement utilisées par
    # l'interface ou les exports.
    tca["APRQ"] = 0
    tca["APRV AVAU"] = 0
    tca["REJT"] = 0

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
        "Taux d'approbation des Avis": (tca["APRV"], tca["Total OT CRÉÉ"]),
        "OT LANC ESTIME": (la["OUI"], la["Total"]),
        "Backlog préparation caractérisé": (pc["CARACTERISE"], pc["Total"]),
        "Backlog planification caractérisé": (plc["CARACTERISE"], plc["Total"]),
        "OT CONFIME": (res['ot_confime']["OUI"], res['ot_confime']["Total"]),
        "OT_COR_EGAL": (res['ot_cor_egal']["NON"], res['ot_cor_egal']["Total"]),
        "OT Fiabilité": (fiab_s, fiab_s),
        "Total Avis de Panne": (avpan_s, avpan_s),
    }

    return res
