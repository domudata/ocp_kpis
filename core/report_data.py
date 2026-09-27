# -*- coding: utf-8 -*-
"""
Préparation des données des rapports PDF (par poste et par division
SF01/SF02). Module 100 % pandas, sans Streamlit ni graphique : il
calcule les structures que core/generate_report_pdf.py se contente
d'afficher.

Contenu :
  · postes_par_indicateur()   → postes ayant dégradé chaque indicateur
  · impact_postes_critiques() → postes impactants + % d'impact (divisions)
  · comparaison_semaines()    → S-1 vs S par indicateur (chart butterfly)
  · evolution_scores()        → scores Perf/Qualité sur toutes les dates
  · backlog_caract_counts()   → nb d'OT caractérisés par code (camemberts)
  · traitement_backlog()      → nb traités entre les 2 dernières extractions

Toutes les fonctions lisent l'historique produit par
core.export_excel.charger_historique_depuis_github() (colonnes
"Poste de travail", "Date_parsed", "_section", KPI...), filtré sur la
liste de postes du rapport (un seul poste, ou tous les postes d'une
division).
"""
import pandas as pd

from core.constants import QK, PK, CIBLE, LOWER_BETTER
from core.calcul_kpi import gscore

# Codes de caractérisation — mêmes listes que la page Backlog de l'app.
try:
    from components.backlog_widgets import CRPR_KW, ATPL_KW, DESC_PREP, DESC_PLAN
except Exception:  # hors Streamlit (tests) : copies identiques
    CRPR_KW = ['ATPD', 'ATMR', 'ATRS', 'ATMO', 'ATER']
    ATPL_KW = ['ATEI', 'ATAL', 'ATAS', 'AGAR', 'ATHS']
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


# ── Helpers ──────────────────────────────────────────────────────────────────
def _num(v):
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def semaine_label(ts) -> str:
    ts = pd.Timestamp(ts)
    return f"S{ts.isocalendar().week} ({ts.strftime('%d/%m')})"


def _hist_ok(hist_df) -> bool:
    return (hist_df is not None and not hist_df.empty
            and {"Poste de travail", "Date_parsed", "_section"}.issubset(hist_df.columns))


def choisir_dates_s_prec_s(dates):
    """
    S   = dernière extraction enregistrée.
    S-1 = dernière extraction d'une semaine ANTÉRIEURE à celle de S
          (si plusieurs extractions la même semaine, on compare bien à la
          semaine d'avant) ; à défaut, l'avant-dernière extraction.
    Retourne (d_prec, d_act) — d_prec peut être None.
    """
    dates = sorted({pd.Timestamp(d) for d in dates if pd.notna(d)})
    if not dates:
        return None, None
    d_act = dates[-1]
    debut_semaine = d_act.normalize() - pd.Timedelta(days=d_act.weekday())
    avant = [d for d in dates if d < debut_semaine]
    if avant:
        return avant[-1], d_act
    return (dates[-2] if len(dates) >= 2 else None), d_act


def _rows(hist_df, section, postes, date):
    sub = hist_df[(hist_df["_section"] == section)
                  & (hist_df["Date_parsed"] == date)
                  & (hist_df["Poste de travail"].isin(postes))]
    return sub.drop_duplicates(subset=["Poste de travail"], keep="last")


# ── 1) Postes ayant dégradé chaque indicateur ──────────────────────────────
def postes_par_indicateur(ano_map, ckdf, postes, kpis=None):
    """
    Pour chaque indicateur : liste des postes qui le dégradent, c.-à-d.
    ayant au moins une anomalie OU un verdict non conforme (gscore = 0).
    Chaque entrée : {"poste", "nb" (anomalies), "conforme" (bool|None),
    "valeur"}. Triée par nombre d'anomalies décroissant.
    """
    kpis = kpis or (list(QK) + list(PK))
    out = {}
    for k in kpis:
        serie = ano_map.get(k) if ano_map else None
        lst = []
        for p in postes:
            try:
                n = int(serie.get(p, 0)) if serie is not None else 0
            except (TypeError, ValueError):
                n = 0
            val = None
            if ckdf is not None and p in ckdf.index and k in ckdf.columns:
                val = _num(ckdf.loc[p].get(k))
            conforme = None if val is None else bool(gscore(k, val, CIBLE.get(k, 100)))
            if n > 0 or conforme is False:
                lst.append({"poste": p, "nb": n, "conforme": conforme, "valeur": val})
        lst.sort(key=lambda d: (-d["nb"], d["conforme"] is not False, d["poste"]))
        out[k] = lst
    return out


SEUIL_CRITIQUE, SEUIL_MODERE = 0.66, 0.33   # mêmes seuils que le chart Anomalies


def impact_postes_critiques(ano_map, postes, max_kpis=3, top=5):
    """
    Divisions (Maroc Chimie / FEEDS) : pour les indicateurs aux anomalies
    critiques (≥ 66 % du max, complétés par les modérés ≥ 33 % jusqu'à 3),
    postes de travail qui génèrent ces anomalies et % d'impact (part des
    anomalies de l'indicateur). Top 5 postes + « Autres ».
    """
    totaux = {}
    for k, serie in (ano_map or {}).items():
        try:
            totaux[k] = sum(int(serie.get(p, 0) or 0) for p in postes)
        except (TypeError, ValueError):
            continue
    if not totaux or max(totaux.values()) <= 0:
        return []
    mx = max(totaux.values())
    retenus = [(k, t) for k, t in sorted(totaux.items(), key=lambda x: -x[1])
               if t > 0 and t / mx >= SEUIL_MODERE][:max_kpis]
    panneaux = []
    for k, t in retenus:
        serie = ano_map[k]
        vals = sorted(((p, int(serie.get(p, 0) or 0)) for p in postes), key=lambda x: -x[1])
        vals = [(p, n) for p, n in vals if n > 0]
        tete, reste = vals[:top], vals[top:]
        panneaux.append({
            "kpi": k, "total": t,
            "severite": "Critique" if t / mx >= SEUIL_CRITIQUE else "Modéré",
            "postes": [{"poste": p, "nb": n, "pct": n / t * 100} for p, n in tete],
            "autres_nb": sum(n for _, n in reste),
            "autres_postes": len(reste),
            "autres_pct": sum(n for _, n in reste) / t * 100 if reste else 0.0,
        })
    return panneaux


# ── 2) Comparaison S-1 vs S ──────────────────────────────────────────────────
def _valeurs_a_date(hist_df, postes, date, mode_division):
    """
    Pour une date : valeur de chaque KPI (poste) ou taux de conformité
    (division), scores Perf/Qualité et total d'anomalies.
    """
    perf = _rows(hist_df, "perf", postes, date)
    qual = _rows(hist_df, "qual", postes, date)
    if perf.empty and qual.empty:
        return None

    kpi_vals = {}
    verdicts = {"perf": [], "qual": []}
    for sec, df_sec, kpis in (("perf", perf, QK), ("qual", qual, PK)):
        for k in kpis:
            if k not in df_sec.columns:
                continue
            vals = [_num(v) for v in df_sec[k].tolist()]
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            v_scores = [gscore(k, v, CIBLE.get(k, 100)) for v in vals]
            verdicts[sec].extend(v_scores)
            if mode_division:
                kpi_vals[k] = round(sum(v_scores) / len(v_scores) * 100, 1)
            else:
                kpi_vals[k] = round(vals[0], 1)

    def _score(sec, df_sec, col):
        if mode_division:
            v = verdicts[sec]
            return round(sum(v) / len(v) * 100, 1) if v else None
        if col in df_sec.columns and not df_sec.empty:
            return _num(df_sec[col].iloc[0])
        return None

    anomalies = 0
    for sec, kpis in (("ano_perf", QK), ("ano_qual", PK)):
        a = _rows(hist_df, sec, postes, date)
        for k in kpis:
            if k in a.columns:
                anomalies += int(pd.to_numeric(a[k], errors="coerce").fillna(0).sum())

    return {
        "kpi": kpi_vals,
        "score_perf": _score("perf", perf, "Score Performance"),
        "score_qual": _score("qual", qual, "Score Qualite"),
        "anomalies": anomalies,
    }


def comparaison_semaines(hist_df, postes, mode_division=False):
    """
    Données du chart butterfly S-1 vs S.
    Retourne None si l'historique ne contient pas 2 extractions exploitables,
    sinon :
      {"label_prec", "label_act", "date_prec", "date_act",
       "perf": [{"kpi", "prec", "act", "lower"}], "qual": [...],
       "score_perf": (prec, act), "score_qual": (prec, act),
       "anomalies": (prec, act), "mode_division": bool}
    En mode division, chaque valeur = % de postes conformes sur le KPI.
    """
    if not _hist_ok(hist_df) or not postes:
        return None
    sub = hist_df[hist_df["_section"].isin(["perf", "qual"])
                  & hist_df["Poste de travail"].isin(postes)]
    d_prec, d_act = choisir_dates_s_prec_s(sub["Date_parsed"].dropna().unique())
    if d_prec is None or d_act is None:
        return None
    v_prec = _valeurs_a_date(hist_df, postes, d_prec, mode_division)
    v_act = _valeurs_a_date(hist_df, postes, d_act, mode_division)
    if not v_prec or not v_act:
        return None

    def _liste(kpis):
        res = []
        for k in kpis:
            if k in v_prec["kpi"] or k in v_act["kpi"]:
                res.append({"kpi": k,
                            "prec": v_prec["kpi"].get(k),
                            "act": v_act["kpi"].get(k),
                            # en mode division (taux de conformité) plus haut = mieux
                            "lower": (k in LOWER_BETTER) and not mode_division})
        return res

    return {
        "label_prec": semaine_label(d_prec),
        "label_act": semaine_label(d_act),
        "date_prec": d_prec, "date_act": d_act,
        "perf": _liste(QK), "qual": _liste(PK),
        "score_perf": (v_prec["score_perf"], v_act["score_perf"]),
        "score_qual": (v_prec["score_qual"], v_act["score_qual"]),
        "anomalies": (v_prec["anomalies"], v_act["anomalies"]),
        "mode_division": mode_division,
    }


# ── 3) Évolution des scores sur toutes les dates ──────────────────────────────
def evolution_scores(hist_df, postes, mode_division=False, max_dates=8):
    """
    DataFrame [Date, Perf, Qual] sur les dernières extractions (scores du
    poste, ou scores de conformité de la division).
    """
    if not _hist_ok(hist_df) or not postes:
        return pd.DataFrame(columns=["Date", "Perf", "Qual"])
    sub = hist_df[hist_df["_section"].isin(["perf", "qual"])
                  & hist_df["Poste de travail"].isin(postes)]
    dates = sorted({pd.Timestamp(d) for d in sub["Date_parsed"].dropna().unique()})
    dates = dates[-max_dates:]
    lignes = []
    for d in dates:
        v = _valeurs_a_date(hist_df, postes, d, mode_division)
        if v:
            lignes.append({"Date": d, "Perf": v["score_perf"], "Qual": v["score_qual"]})
    return pd.DataFrame(lignes, columns=["Date", "Perf", "Qual"])


# ── 4) Backlog caractérisation : comptage par code ────────────────────────────
def _section_dates(hist_df, section, postes):
    sub = hist_df[(hist_df["_section"] == section)
                  & (hist_df["Poste de travail"].isin(postes))]
    return sorted({pd.Timestamp(d) for d in sub["Date_parsed"].dropna().unique()})


def _somme_codes(hist_df, section, postes, date, codes):
    rows = _rows(hist_df, section, postes, date)
    return {c: (int(pd.to_numeric(rows[c], errors="coerce").fillna(0).sum())
                if c in rows.columns else 0) for c in codes}


def backlog_caract_counts(hist_df, postes, df_ot=None):
    """
    Nombre d'OT caractérisés par code (dernière extraction) pour ces postes.
    Source : historique (sections BACKLOG CARACT). Si absent, calcul direct
    depuis le fichier OT (df_ot) avec la même règle que la page Backlog.
    Retourne {"prep": {code: n}, "planif": {code: n}, "date": ts|None}
    ou None.
    """
    res = {"prep": {}, "planif": {}, "date": None}
    if _hist_ok(hist_df):
        for section, codes, cle in (("backlog_carac_prep", CRPR_KW, "prep"),
                                    ("backlog_carac_planif", ATPL_KW, "planif")):
            dates = _section_dates(hist_df, section, postes)
            if dates:
                res[cle] = _somme_codes(hist_df, section, postes, dates[-1], codes)
                res["date"] = dates[-1]
    if not res["prep"] and not res["planif"] and df_ot is not None:
        try:
            from components.backlog_widgets import calc_backlog_caract_rows
            prep_rows, _, plan_rows, _, _ = calc_backlog_caract_rows(df_ot, list(postes))
            for rows, codes, cle in ((prep_rows, CRPR_KW, "prep"),
                                     (plan_rows, ATPL_KW, "planif")):
                lignes = [r for r in rows if r.get("_t") != "total"
                          and r.get("Poste de travail") in postes]
                res[cle] = {c: int(sum(_num(r.get(c)) or 0 for r in lignes)) for c in codes}
        except Exception:
            pass
    if not res["prep"] and not res["planif"]:
        return None
    return res


# ── 5) Backlog caractérisation : nombre traité ───────────────────────────────
def traitement_backlog(hist_df, postes):
    """
    Même règle que la page Backlog de l'app (core/backlog_caract_history),
    mais limitée aux postes du rapport : on compare les 2 dernières
    extractions ; traité = max(0, précédent − actuel).
    Retourne {"prep": {code: {...}}, "planif": {...}, "date_prec", "date_act",
    "total_prec", "total_act", "total_traite"} ou None si < 2 extractions.
    """
    if not _hist_ok(hist_df) or not postes:
        return None
    res = {"prep": {}, "planif": {}, "date_prec": None, "date_act": None}
    for section, codes, cle in (("backlog_carac_prep", CRPR_KW, "prep"),
                                ("backlog_carac_planif", ATPL_KW, "planif")):
        dates = _section_dates(hist_df, section, postes)
        if len(dates) < 2:
            continue
        d_prec, d_act = dates[-2], dates[-1]
        prec = _somme_codes(hist_df, section, postes, d_prec, codes)
        act = _somme_codes(hist_df, section, postes, d_act, codes)
        for c in codes:
            traite = max(0, prec[c] - act[c])
            res[cle][c] = {"precedent": prec[c], "actuel": act[c], "traite": traite,
                           "pct_traite": round(traite / prec[c] * 100, 1) if prec[c] else 0.0}
        res["date_prec"], res["date_act"] = d_prec, d_act
    if not res["prep"] and not res["planif"]:
        return None
    for cle in ("prep", "planif"):
        res[f"{cle}_total_prec"] = sum(v["precedent"] for v in res[cle].values())
        res[f"{cle}_total_traite"] = sum(v["traite"] for v in res[cle].values())
    res["total_prec"] = res["prep_total_prec"] + res["planif_total_prec"]
    res["total_traite"] = res["prep_total_traite"] + res["planif_total_traite"]
    return res


# ── 6) Synthèse d'un périmètre quelconque (export PowerPoint) ────────────────
def synthese_perimetre(ckdf, pscores, qscores, ano_map, postes):
    """
    Mêmes règles que les rapports PDF (core/publish_reports.py) :
      · 1 poste   → valeurs brutes des KPI et scores du poste ;
      · N postes  → pour chaque KPI, % de postes conformes (gscore 0/1),
                    scores = moyenne des verdicts sur toutes les cellules.
    Retourne {"mode_division", "postes", "kpi_perf", "kpi_qual", "pscore",
    "qscore", "anomalies", "total_anomalies", "plan_action"}.
    """
    from core.constants import ACT_MAP, KPI_RESP_MAP
    postes = [p for p in postes if ckdf is not None and p in ckdf.index]
    mode_division = len(postes) > 1
    kpi_perf, kpi_qual = {}, {}
    verdicts = {"perf": [], "qual": []}
    for sec, kpis, cible_dict in (("perf", QK, kpi_perf), ("qual", PK, kpi_qual)):
        for k in kpis:
            if k not in ckdf.columns:
                continue
            vals = [_num(ckdf.loc[p].get(k)) for p in postes]
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            vs = [gscore(k, v, CIBLE.get(k, 100)) for v in vals]
            verdicts[sec].extend(vs)
            cible_dict[k] = round(sum(vs) / len(vs) * 100, 1) if mode_division else round(vals[0], 1)

    if mode_division:
        ps = round(sum(verdicts["perf"]) / len(verdicts["perf"]) * 100, 1) if verdicts["perf"] else 0
        qs = round(sum(verdicts["qual"]) / len(verdicts["qual"]) * 100, 1) if verdicts["qual"] else 0
    else:
        p0 = postes[0] if postes else None
        ps = float((pscores or {}).get(p0, 0) or 0)
        qs = float((qscores or {}).get(p0, 0) or 0)

    anomalies = {}
    for k in list(QK) + list(PK):
        serie = (ano_map or {}).get(k)
        try:
            anomalies[k] = int(sum(int(serie.get(p, 0) or 0) for p in postes)) if serie is not None else 0
        except (TypeError, ValueError):
            anomalies[k] = 0

    plan = []
    for k in list(QK) + list(PK):
        nb = anomalies.get(k, 0)
        if nb <= 0:
            continue
        cible = CIBLE.get(k, 100)
        actual = kpi_perf.get(k, kpi_qual.get(k, 0)) or 0
        if mode_division:
            ecart = actual - 100
        else:
            ecart = (cible - actual) if k in LOWER_BETTER else (actual - cible)
        plan.append({"kpi": k, "actual": round(actual, 1), "target": cible,
                     "ecart": round(ecart, 1), "nb_anom": nb,
                     "responsable": KPI_RESP_MAP.get(k, "Non assigné"),
                     "action": ACT_MAP.get(k, "")})
    plan.sort(key=lambda x: -x["nb_anom"])
    return {"mode_division": mode_division, "postes": postes,
            "kpi_perf": kpi_perf, "kpi_qual": kpi_qual, "pscore": ps, "qscore": qs,
            "anomalies": anomalies, "total_anomalies": sum(anomalies.values()),
            "plan_action": plan}
