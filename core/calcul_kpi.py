# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from core.constants import MP_KW, MPLAN_KW, QK, PK, ALL_KPI, CIBLE, LOWER_BETTER

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

# ──────────────────────────────────────────────
# Score binaire : ROUGE = 0, sinon (orange/vert) = 1
# Seuils STRICTEMENT alignés sur ks() / get_bar_color()
# de components/tables.py.
# Score = somme des 1 / nombre de KPIs (fait dans app.py)
# ──────────────────────────────────────────────

def gscore(k: str, a, t) -> int:
    """Retourne 0 si la cellule est ROUGE, 1 sinon (orange ou vert).

    Les seuils "rouge" ci-dessous sont identiques a ceux de la
    fonction ks() dans components/tables.py :
      - <1 mois            : rouge si < 75   (orange 75-80, vert >= 80)
      - 1mois< <3mois      : rouge si > 15   (vert <= 15)
      - >3 mois            : rouge si > 5    (vert <= 5)
      - TAUX_REALISATION   : rouge si < 80   (orange 80-85, vert >= 85)
      - Taux approbation   : rouge si < 90   (orange 90-95, vert >= 95)
      - LANC ESTIME & co   : rouge si < 95   (orange 95-100, vert >= 100)
      - Perf Graissage/Insp/Syst : rouge si <= 90 (orange 90-95, vert >= 95)
      - OT Fiabilité / Avis de Panne : jamais rouge (vert >= 100, sinon orange)
    """
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
        # Performance Systématiques utilise le MÊME seuil que le Taux de
        # réalisation correctif (rouge<80, sinon 1) — confirmé par le
        # fichier système SAP (KPI_PERFORMANCE_QUALITE) : une entité à
        # 87% en Performance Systématiques y est comptée conforme pour un
        # score global de 100%, ce qui n'est mathématiquement possible
        # qu'avec un seuil ~80-85%, pas 90-95% (groupe Graissage/Inspection).
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
    # Défaut aligné sur get_bar_color : rouge si < 80
    return 0 if a < 80 else 1

def is_lb(k: str) -> bool:
    return k in LOWER_BETTER

# ──────────────────────────────────────────────
# Total pondéré (VRAI total, pas une moyenne)
# Le "Total general" par KPI doit refléter le volume réel de chaque
# poste (un poste avec 2000 OT ne pèse pas comme un poste avec 5 OT).
# Une simple moyenne des % par poste pondère chaque poste également,
# ce qui fausse le résultat. Ici : somme(numérateurs) / somme(dénominateurs).
# ──────────────────────────────────────────────

def weighted_total(num, den, default: float = 100.0) -> float:
    """Total pondéré = somme(num) / somme(den) × 100 (100 si somme(den)=0).
    num/den : Series ou array-like indexés par poste (mêmes KPI que ckdf)."""
    try:
        ns = float(pd.Series(num).sum())
        ds = float(pd.Series(den).sum())
    except Exception:
        return default
    return default if ds == 0 else (ns / ds) * 100.0

# ──────────────────────────────────────────────
# Score Global (Points 6 & 7)
# Reutilise STRICTEMENT gscore() -> memes seuils que ks() / get_bar_color().
#   Rouge  = 0
#   Orange = 1
#   Vert   = 1
# Score Global (%) = (somme des gscore) / (nb de KPI evalues) * 100
# ──────────────────────────────────────────────

def score_global(values, kpi_list: list = None) -> float:
    """Calcule le Score Global (%) a partir d'un jeu de valeurs de KPI.

    values    : dict ou pd.Series {nom_kpi: valeur}
                Peut etre soit la ligne d'un poste (ckdf.loc[poste],
                valeurs brutes du KPI), soit la ligne "Total general"
                (valeurs deja agregees en %, memes unites 0-100 donc
                comparables aux memes seuils gscore/ks/get_bar_color).
    kpi_list  : liste des KPI a inclure (defaut = ALL_KPI = QK + PK).

    Utilisation :
      - Par poste       : score_global(ckdf.loc[poste])
      - Total General   : score_global(tot_general_dict)  # cf. app.py
    """
    if kpi_list is None:
        kpi_list = ALL_KPI

    pts = 0
    tc = 0
    for k in kpi_list:
        if k not in values:
            continue
        v = values[k]
        if v is None:
            continue
        try:
            if pd.isna(v):
                continue
        except (TypeError, ValueError):
            pass
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        pts += gscore(k, v, CIBLE.get(k, 100))
        tc += 1

    return round((pts / tc) * 100, 2) if tc > 0 else 0.0

# ──────────────────────────────────────────────
# Calcul principal des KPI
# ──────────────────────────────────────────────

def calc_kpis(df_i: pd.DataFrame, av_i: pd.DataFrame, now_ts, posts: list) -> dict:
    res = {}
    df = df_i.copy()
    av = av_i.copy()
    res['dfp'] = df

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

    # ── Préparation ──
    pr = cpiv(
        df,
        (df["Statut OT"] == "CRÉÉ")
        & (df["Statut utilisateur"].str.contains(r"\bCRPR\b", case=False, na=False)),
        "ap", posts
    )
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        pr[c] = pr.get(c, 0)
    pr["Total"] = pr[["<1 mois", "1 mois < <3 mois", ">3 mois", "Inconnu"]].sum(axis=1)
    pr["OT préparation <1 mois"]     = ckpi(pr["<1 mois"], pr["Total"])
    pr["OT préparation >3 mois"]     = ckpi(pr[">3 mois"], pr["Total"], 0)
    pr["OT préparation 1mois< <3mois"] = ckpi(pr["1 mois < <3 mois"], pr["Total"], 0)

    # ── Planification ──
    pl = cpiv(
        df,
        (df["Statut OT"] == "LANC")
        & (df["Statut utilisateur"].str.contains("ATPL", case=False, na=False)),
        "alp", posts
    )
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        pl[c] = pl.get(c, 0)
    pl["Total"] = pl[["<1 mois", "1 mois < <3 mois", ">3 mois", "Inconnu"]].sum(axis=1)
    pl["OT planification <1 mois"]     = ckpi(pl["<1 mois"], pl["Total"])
    pl["OT planification >3 mois"]     = ckpi(pl[">3 mois"], pl["Total"], 0)
    pl["OT planification 1mois< <3mois"] = ckpi(pl["1 mois < <3 mois"], pl["Total"], 0)

    # ── Exécution ──
    ex = cpiv(
        df,
        (df["Statut OT"] == "LANC") & (df["Contient SOPL"] == 1),
        "aex", posts
    )
    for c in ["<1 mois", ">3 mois", "1 mois < <3 mois", "Inconnu"]:
        ex[c] = ex.get(c, 0)
    ex["Total"] = ex[["<1 mois", "1 mois < <3 mois", ">3 mois", "Inconnu"]].sum(axis=1)
    ex["OT exécution <1 mois"]     = ckpi(ex["<1 mois"], ex["Total"])
    ex["OT exécution >3 mois"]     = ckpi(ex[">3 mois"], ex["Total"], 0)
    ex["OT exécution 1mois< <3mois"] = ckpi(ex["1 mois < <3 mois"], ex["Total"], 0)

    # ── OT lancé estimé ──
    la = pd.pivot_table(
        df[df["Statut OT"] == "LANC"], index="Poste travail princ.",
        columns="OT LANC ESTIME", values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        la[c] = la.get(c, 0)
    la["Total"] = la["OUI"] + la["NON"]
    la["OT LANC ESTIME"] = ckpi(la["OUI"], la["Total"])

    # ── Backlog préparation ──
    # Filtre : Statut OT = CRÉÉ ET Statut utilisateur contient CRPR
    pc = pd.pivot_table(
        df[(df["Statut OT"] == "CRÉÉ")
           & (df["Statut utilisateur"].str.contains("CRPR", case=False, na=False))],
        index="Poste travail princ.",
        columns="Backlog preparation", values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE", "NON CARACTERISE"]:
        pc[c] = pc.get(c, 0)
    pc["Total"] = pc["CARACTERISE"] + pc["NON CARACTERISE"]
    pc["Backlog préparation caractérisé"] = ckpi(pc["CARACTERISE"], pc["Total"])

    # ── Backlog planification ──
    # Filtre : Statut OT = LANC ET Contient SOPL == 0 (pas encore en exécution).
    # Vérifié numériquement face au fichier système SAP : LANC+SOPL==0 donne
    # un dénominateur (532) très proche de NB_OT_BCKLG_PLANIF (590, écart
    # probablement dû au décalage d'instant de mesure) ; LANC+ATPL (essayé
    # précédemment) donnait un dénominateur bien trop grand (1966).
    plc = pd.pivot_table(
        df[(df["Statut OT"] == "LANC") & (df["Contient SOPL"] == 0)],
        index="Poste travail princ.", columns="Backlog planification",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["CARACTERISE", "NON CARACTERISE"]:
        plc[c] = plc.get(c, 0)
    plc["Total"] = plc["CARACTERISE"] + plc["NON CARACTERISE"]
    plc["Backlog planification caractérisé"] = ckpi(plc["CARACTERISE"], plc["Total"])

    # ── OT CONFIME (pivot dédié, colonne "OT CONFIME" uniquement) ──
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

    # ── OT_COR_EGAL (pivot dédié, colonne "OT_COR_EGAL" uniquement) ──
    # Formule (corrigée) : NON / (OUI+NON) × 100.
    # OUI = écart de coût détecté (anomalie, cf. anomalies.py), donc c'est
    # NON qui doit être récompensé dans le score — cohérent avec la
    # définition de l'anomalie (OUI compté comme anomalie).
    pv_cor = pd.pivot_table(
        df[df["Statut OT"].isin(["CLOT", "TCLO"])],
        index="Poste travail princ.", columns="OT_COR_EGAL",
        values="Ordre", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    for c in ["OUI", "NON"]:
        pv_cor[c] = pv_cor.get(c, 0)
    pv_cor["Total"] = pv_cor["OUI"] + pv_cor["NON"]
    pv_cor["OT_COR_EGAL"] = ckpi(pv_cor["NON"], pv_cor["Total"])
    res["ot_cor_egal"] = pv_cor

    # ── Taux approbation avis ──
    avf = av.copy()
    res['avf'] = avf
    tca = pd.pivot_table(
        avf, index="Poste travail princ.", columns="Statut utilisateur",
        values="Avis", aggfunc="count", fill_value=0
    ).reindex(posts, fill_value=0)
    # Total = somme des avis avec un Statut utilisateur pertinent
    # (APRQ/APRV/APRV AVAU/REJT) — PAS toutes les lignes brutes de avf, qui
    # contient énormément d'avis avec Statut utilisateur vide (déjà transformés
    # en OT ou dans un autre workflow, hors périmètre du taux d'approbation).
    for c in ["APRQ", "APRV", "APRV AVAU", "REJT"]:
        tca[c] = tca.get(c, 0)
    tca["Total"] = tca[["APRQ", "APRV", "APRV AVAU", "REJT"]].sum(axis=1)
    # CORRIGÉ (formule officielle) : numérateur = APRV SEUL, pas APRV+APRV AVAU.
    # La doc SAP PM dit explicitement "(statut utilisateur \"APRV\")", sans mention
    # de APRV AVAU.
    tca["Taux d'approbation des Avis"] = ckpi(tca["APRV"], tca["Total"])

    # ── Performance Graissage ──
    # Vérifié (Point 5) : dénominateur = OT type 350 avec Contient SOPL == 1
    # (origine préventive/planifiée). Cette règle est strictement identique à
    # celle utilisée pour Performance Inspection et Performance Systématiques
    # ci-dessous (même filtre Contient SOPL == 1) : cohérence confirmée dans
    # les 3 KPI de préventif. Aucune correction appliquée.
    g_num = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & (df["_tw_num"] == 350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    g_den = df[(df["Contient SOPL"] == 1) & (df["_tw_num"] == 350)].groupby(
        "Poste travail princ.")["Ordre"].count()
    # CORRIGÉ : .reindex(fill_value=0) ne comble que les postes ABSENTS de
    # l'index, pas les NaN internes à une ligne déjà présente. Si un poste
    # a des OT au numérateur mais aucun au dénominateur (ou l'inverse),
    # pd.DataFrame({"_n":.., "_d":..}) aligne par index et laisse un NaN
    # côté manquant -> Performance Graissage = NaN au lieu de 0%/100%.
    # .fillna(0) après reindex corrige ce cas.
    g_df = pd.DataFrame({"_n": g_num, "_d": g_den}).reindex(posts, fill_value=0).fillna(0)
    g_df["Performance Graissage"] = np.where(
        g_df["_d"] == 0, 100.0, (g_df["_n"] / g_df["_d"]) * 100
    )

    # ── Performance Inspection ──
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
    # CORRIGÉ : même problème que g_df ci-dessus (voir commentaire).
    ins_df = pd.DataFrame({"_n": ins_num, "_d": ins_den}).reindex(posts, fill_value=0).fillna(0)
    ins_df["Performance Inspection"] = np.where(
        ins_df["_d"] == 0, 100.0, (ins_df["_n"] / ins_df["_d"]) * 100
    )

    # ── Performance Systématiques ──
    sys_base = (
        (df["_tw_num"] == 360)
        & (df["Date de début planifiée"].notna())
        & (df["Date de début planifiée"] <= now_ts)
    )
    sys_num = df[(df["Statut OT"].isin(["CLOT", "TCLO"])) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    sys_den = df[(df["Contient SOPL"] == 1) & sys_base].groupby(
        "Poste travail princ.")["Ordre"].count()
    # CORRIGÉ : même problème que g_df ci-dessus (voir commentaire).
    sys_df = pd.DataFrame({"_n": sys_num, "_d": sys_den}).reindex(posts, fill_value=0).fillna(0)
    sys_df["Performance Systématiques"] = np.where(
        sys_df["_d"] == 0, 100.0, (sys_df["_n"] / sys_df["_d"]) * 100
    )

    fiab_s = pd.Series(100.0, index=posts)
    avpan_s = pd.Series(100.0, index=posts)

    # ── Numérateurs/dénominateurs bruts par KPI (pour le total pondéré) ──
    # Utilisé par app.py pour calculer le "Total general" comme
    # somme(num)/somme(den)×100 sur TOUS les postes, au lieu d'une
    # moyenne simple des % (qui pondère chaque poste également peu
    # importe son volume réel).
    res['nd'] = {
        "TAUX_REALISATION_CORRECTIF/PT":      (an["OT_CLOTURES"], an["TOTAL_OT"]),
        "OT préparation <1 mois":             (pr["<1 mois"], pr["Total"]),
        "OT préparation 1mois< <3mois":       (pr["1 mois < <3 mois"], pr["Total"]),
        "OT préparation >3 mois":             (pr[">3 mois"], pr["Total"]),
        "OT planification <1 mois":           (pl["<1 mois"], pl["Total"]),
        "OT planification 1mois< <3mois":     (pl["1 mois < <3 mois"], pl["Total"]),
        "OT planification >3 mois":           (pl[">3 mois"], pl["Total"]),
        "OT exécution <1 mois":               (ex["<1 mois"], ex["Total"]),
        "OT exécution 1mois< <3mois":         (ex["1 mois < <3 mois"], ex["Total"]),
        "OT exécution >3 mois":               (ex[">3 mois"], ex["Total"]),
        "Performance Graissage":              (g_df["_n"], g_df["_d"]),
        "Performance Inspection":              (ins_df["_n"], ins_df["_d"]),
        "Performance Systématiques":           (sys_df["_n"], sys_df["_d"]),
        "Taux d'approbation des Avis":         (tca["APRV"], tca["Total"]),
        "OT LANC ESTIME":                     (la["OUI"], la["Total"]),
        "Backlog préparation caractérisé":    (pc["CARACTERISE"], pc["Total"]),
        "Backlog planification caractérisé":  (plc["CARACTERISE"], plc["Total"]),
        "OT CONFIME":                         (pv_conf["OUI"], pv_conf["Total"]),
        "OT_COR_EGAL":                        (pv_cor["NON"], pv_cor["Total"]),
        "OT Fiabilité":                       (fiab_s, fiab_s),
        "Total Avis de Panne":                (avpan_s, avpan_s),
    }

    res['ckdf'] = pd.DataFrame({
        "TAUX_REALISATION_CORRECTIF/PT":      an["TAUX_REALISATION_CORRECTIF/PT"],
        "OT préparation <1 mois":             pr["OT préparation <1 mois"],
        "OT préparation >3 mois":             pr["OT préparation >3 mois"],
        "OT préparation 1mois< <3mois":       pr["OT préparation 1mois< <3mois"],
        "OT planification <1 mois":           pl["OT planification <1 mois"],
        "OT planification >3 mois":           pl["OT planification >3 mois"],
        "OT planification 1mois< <3mois":     pl["OT planification 1mois< <3mois"],
        "OT exécution <1 mois":               ex["OT exécution <1 mois"],
        "OT exécution >3 mois":               ex["OT exécution >3 mois"],
        "OT exécution 1mois< <3mois":         ex["OT exécution 1mois< <3mois"],
        "Performance Graissage":              g_df["Performance Graissage"],
        "Performance Inspection":             ins_df["Performance Inspection"],
        "Performance Systématiques":          sys_df["Performance Systématiques"],
        "Taux d'approbation des Avis":        tca["Taux d'approbation des Avis"],
        "OT LANC ESTIME":                     la["OT LANC ESTIME"],
        "Backlog préparation caractérisé":    pc["Backlog préparation caractérisé"],
        "Backlog planification caractérisé":  plc["Backlog planification caractérisé"],
        "OT CONFIME":                         res['ot_confime']["OT CONFIME"],
        "OT_COR_EGAL":                        res['ot_cor_egal']["OT_COR_EGAL"],
        "OT Fiabilité":                       fiab_s,
        "Total Avis de Panne":                avpan_s,
    })

    return res
