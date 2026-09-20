# -*- coding: utf-8 -*-
import os
import pandas as pd
from openpyxl import load_workbook

from core.constants import LOWER_BETTER

def load_historical_kpis(filepath: str = None) -> pd.DataFrame:
    """Charge TOUT l'historique enregistré (une feuille par date dans le
    classeur)."""
    target = filepath
    if not target or not os.path.exists(target):
        if os.path.exists("kpis.xlsx"):
            target = "kpis.xlsx"
        elif os.path.exists(os.path.join("kpis", "indicateurs_kpis.xlsx")):
            target = os.path.join("kpis", "indicateurs_kpis.xlsx")
        else:
            return pd.DataFrame()
    try:
        wb = load_workbook(target, data_only=True)
    except Exception:
        return pd.DataFrame()

    records = []
    for sheet_name in wb.sheetnames:
        try:
            ws = wb[sheet_name]
            rows_data = list(ws.iter_rows(values_only=True))
            section = None
            headers = None
            for row in rows_data:
                cell0 = str(row[0]).strip() if row[0] else ""
                up = cell0.upper()
                if "ANOMALIES PERFORMANCE" in up:
                    section = "ano_perf"; headers = None; continue
                elif "ANOMALIES QUALITE" in up:
                    section = "ano_qual"; headers = None; continue
                elif "INDICATEURS DE PERFORMANCE" in up:
                    section = "perf"; headers = None; continue
                elif "INDICATEURS DE QUALITE" in up:
                    section = "qual"; headers = None; continue
                if section and headers is None and cell0:
                    headers = [str(c).strip() if c else "" for c in row]; continue
                if section and headers and cell0 and cell0 not in ("Cible", "Total general", "Total", ""):
                    entry = {"Date": sheet_name}
                    for j, h in enumerate(headers):
                        if j < len(row):
                            entry[h] = row[j]
                    entry["_section"] = section
                    records.append(entry)
        except Exception:
            continue

    wb.close()
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["Date_parsed"] = pd.to_datetime(
        df["Date"].str.replace("-", "/"), format="%d/%m/%Y", errors="coerce"
    )

    # CORRIGÉ : les valeurs de KPI sont enregistrées dans le fichier Excel
    # comme du TEXTE formaté (ex: "96.3", pas le nombre 96.3 — cf.
    # `"%.1f" % r[k]` dans app.py). Sans conversion, toute comparaison
    # numérique en aval (sparklines, gscore, évaluation de tendance)
    # plante avec "'>=' not supported between instances of 'str' and
    # 'int'". On convertit ici, une seule fois, toutes les colonnes sauf
    # les colonnes texte connues (identité de la ligne).
    _non_numeric_cols = {"Date", "Poste de travail", "_section", "Date_parsed"}
    for col in df.columns:
        if col not in _non_numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.sort_values("Date_parsed").reset_index(drop=True)

def calculate_variations(hist_df: pd.DataFrame) -> pd.DataFrame:
    if hist_df.empty or "Date" not in hist_df.columns:
        return pd.DataFrame()

    dates = sorted(hist_df["Date"].unique())
    if len(dates) < 2:
        return pd.DataFrame()

    perf_df = hist_df[hist_df["_section"] == "perf"].copy()
    qual_df = hist_df[hist_df["_section"] == "qual"].copy()
    variations = []

    from core.constants import QK, PK

    for i in range(1, len(dates)):
        prev_date, curr_date = dates[i - 1], dates[i]

        prev_perf = perf_df[perf_df["Date"] == prev_date].set_index("Poste de travail") if "Poste de travail" in perf_df.columns else pd.DataFrame()
        curr_perf = perf_df[perf_df["Date"] == curr_date].set_index("Poste de travail") if "Poste de travail" in perf_df.columns else pd.DataFrame()
        prev_qual = qual_df[qual_df["Date"] == prev_date].set_index("Poste de travail") if "Poste de travail" in qual_df.columns else pd.DataFrame()
        curr_qual = qual_df[qual_df["Date"] == curr_date].set_index("Poste de travail") if "Poste de travail" in qual_df.columns else pd.DataFrame()

        for sec_name, prev_d, curr_d, kpi_list in [
            ("Performance", prev_perf, curr_perf, QK + ["Score Performance"]),
            ("Qualite", prev_qual, curr_qual, PK + ["Score Qualite"]),
        ]:
            for poste in set(prev_d.index) & set(curr_d.index):
                for kpi in kpi_list:
                    if kpi not in prev_d.columns or kpi not in curr_d.columns:
                        continue
                    try:
                        pv = float(prev_d.loc[poste, kpi])
                    except Exception:
                        continue
                    try:
                        cv = float(curr_d.loc[poste, kpi])
                    except Exception:
                        continue

                    diff = cv - pv
                    pct = (diff / pv * 100) if pv != 0 else (100 if cv != 0 else 0)

                    if abs(diff) <= 0.5:
                        trend = "stabilite"
                    elif diff > 0.5:
                        trend = "hausse"
                    else:
                        trend = "baisse"

                    if trend == "stabilite":
                        sens = "Stable"
                    elif (trend == "hausse" and kpi not in LOWER_BETTER) or \
                         (trend == "baisse" and kpi in LOWER_BETTER):
                        sens = "Amelioration"
                    else:
                        sens = "Degradation"

                    variations.append({
                        "Date precedente": prev_date, "Date actuelle": curr_date,
                        "Poste": poste, "Type": sec_name, "KPI": kpi,
                        "Valeur precedente": round(pv, 2), "Valeur actuelle": round(cv, 2),
                        "Ecart": round(diff, 2), "Ecart %": round(pct, 2),
                        "Tendance": trend, "Sens": sens,
                    })

    return pd.DataFrame(variations)

def generate_journal(var_df: pd.DataFrame) -> pd.DataFrame:
    if var_df.empty:
        return pd.DataFrame()
    j = var_df.copy()
    j["Significatif"] = j["Ecart %"].abs() >= 5
    j = j[j["Significatif"]].copy()
    return j.sort_values(["Date actuelle", "Ecart %"], ascending=[True, False])

def calculate_rankings(var_df: pd.DataFrame):
    if var_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    scores = {}
    for poste in var_df["Poste"].unique():
        pv = var_df[var_df["Poste"] == poste].copy()
        scores[poste] = sum(
            (-r["Ecart %"] if r["KPI"] in LOWER_BETTER else r["Ecart %"])
            for _, r in pv.iterrows()
        )
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return (
        pd.DataFrame(ranked[:5], columns=["Poste", "Score variation"]),
        pd.DataFrame(ranked[-5:][::-1], columns=["Poste", "Score variation"]),
    )

# ──────────────────────────────────────────────
# NOUVEAU : évaluation sur les N dernières valeurs enregistrées
# (pas seulement la comparaison entre les 2 dernières périodes)
# ──────────────────────────────────────────────

def get_recent_window(hist_df: pd.DataFrame, section: str, kpi: str, n: int = 5) -> pd.DataFrame:
    """Pivot Poste x Date restreint aux n dernières dates enregistrées,
    pour un KPI et une section donnés (section : "perf"/"qual"/"ano_perf"/"ano_qual")."""
    if hist_df.empty or kpi not in hist_df.columns:
        return pd.DataFrame()
    sub = hist_df[hist_df["_section"] == section].copy()
    if sub.empty or "Poste de travail" not in sub.columns:
        return pd.DataFrame()
    sub["Date_str"] = sub["Date_parsed"].dt.strftime("%d/%m/%Y")
    pv = sub.pivot_table(index="Poste de travail", columns="Date_str", values=kpi, aggfunc="first")
    ordered_cols = sorted(pv.columns, key=lambda c: pd.to_datetime(c, format="%d/%m/%Y", errors="coerce"))
    pv = pv[ordered_cols]
    return pv.iloc[:, -n:] if n else pv

def evaluate_trend_last_n(hist_df: pd.DataFrame, section: str, kpi_list: list, n: int = 5) -> pd.DataFrame:
    """Pour chaque poste et chaque KPI (ou KPI d'anomalies), évalue la
    tendance sur les n DERNIÈRES valeurs enregistrées — pas seulement les
    2 dernières comme calculate_variations(). Compare la première valeur
    de la fenêtre à la dernière.
    section : "perf"/"qual" pour les KPI, "ano_perf"/"ano_qual" pour les
    anomalies (dans ce cas, toujours "plus bas = mieux", cible implicite 0).
    """
    is_anomalie = section in ("ano_perf", "ano_qual")
    rows = []
    for kpi in kpi_list:
        pv = get_recent_window(hist_df, section, kpi, n)
        if pv.empty:
            continue
        for poste in pv.index:
            vals = pv.loc[poste].dropna().tolist()
            if len(vals) < 2:
                continue
            first, last = vals[0], vals[-1]
            diff = last - first
            pct = (diff / first * 100) if first else (100 if last else 0)
            lower = True if is_anomalie else (kpi in LOWER_BETTER)
            if abs(diff) < (0.5 if is_anomalie else 0) and abs(pct) < 2:
                tendance = "Stable"
            elif (diff > 0 and not lower) or (diff < 0 and lower):
                tendance = "Amélioration"
            elif diff == 0:
                tendance = "Stable"
            else:
                tendance = "Dégradation"
            rows.append({
                "Poste": poste, "KPI": kpi, "Nb valeurs": len(vals),
                "Valeurs": vals, "Première": round(first, 1), "Dernière": round(last, 1),
                "Écart": round(diff, 1), "Écart %": round(pct, 1), "Tendance": tendance,
            })
    return pd.DataFrame(rows)

# ──────────────────────────────────────────────────────────────────
# NOUVEAU : Système de suivi hebdomadaire du taux de traitement des
# anomalies (demande explicite). Repose sur les sections déjà
# enregistrées "ano_perf" / "ano_qual" (comptes d'anomalies par poste
# et par KPI, une feuille par date d'extraction) — aucune nouvelle
# source de données requise.
#
# Semaine = LUNDI à DIMANCHE (demande explicite précédente, réutilisée
# ici pour la cohérence). "Semaine précédente" = les 7 jours juste
# avant la semaine actuelle.
# ──────────────────────────────────────────────────────────────────


def get_bornes_semaines(now_ts: pd.Timestamp):
    """Retourne (lundi_actuel, dimanche_actuel, lundi_precedent,
    dimanche_precedent, numero_semaine_actuelle, numero_semaine_precedente)
    pour la semaine calendaire ISO (lundi->dimanche) contenant now_ts,
    et la semaine juste avant. Le numéro de semaine est le numéro ISO
    (ex : « Semaine 38 »)."""
    _now = pd.Timestamp(now_ts).normalize()
    lundi_actuel = _now - pd.Timedelta(days=_now.weekday())
    dimanche_actuel = lundi_actuel + pd.Timedelta(days=6)
    lundi_precedent = lundi_actuel - pd.Timedelta(days=7)
    dimanche_precedent = lundi_actuel - pd.Timedelta(days=1)
    num_actuelle = int(lundi_actuel.isocalendar().week)
    num_precedente = int(lundi_precedent.isocalendar().week)
    return (lundi_actuel, dimanche_actuel, lundi_precedent, dimanche_precedent,
            num_actuelle, num_precedente)


def _derniere_date_dans(hist_df: pd.DataFrame, section: str, debut, fin):
    """Dernière date d'extraction (Date_parsed) de la section donnée
    tombant dans [debut, fin] ; None si aucune."""
    sub = hist_df[hist_df["_section"] == section]
    dates = sub["Date_parsed"].dropna()
    dates = dates[(dates >= debut) & (dates <= fin)]
    return dates.max() if not dates.empty else None


def calculate_suivi_anomalies_semaine(hist_df: pd.DataFrame, now_ts: pd.Timestamp,
                                       kpi_list_perf: list, kpi_list_qual: list) -> dict:
    """
    NOUVEAU système de suivi hebdomadaire des anomalies (remplace l'ancien
    "taux de traitement" — demande explicite de recalibrage complet).

    Principe : chaque poste a un nombre d'anomalies « cette semaine »
    (semaine ISO en cours, ex. Semaine 38). Quand une nouvelle extraction
    arrive dans une semaine ultérieure, on regarde combien de ces
    anomalies ont été RÉSORBÉES (traitées) par rapport à la semaine
    précédente. La semaine en cours reste affichée jusqu'à ce que la
    semaine suivante démarre (nouvelle extraction dans la semaine
    suivante), moment où le cycle recommence.

    Retourne :
      {
        "num_semaine_actuelle": int, "num_semaine_precedente": int,
        "date_act": Timestamp|None, "date_prec": Timestamp|None,
        "par_poste": DataFrame [Poste, Anomalies semaine, Anomalies traitees],
        "detail_par_poste": {poste: DataFrame [KPI, Type, Anomalies semaine, Anomalies traitees]},
      }
    "Anomalies traitees" = max(0, anomalies_semaine_precedente - anomalies_semaine_actuelle)
    — un nombre, jamais un pourcentage, jamais négatif (une dégradation
    donne 0 traité, pas un nombre négatif, conformément à la demande).
    Si la semaine précédente n'a aucune extraction, "Anomalies traitees"
    n'est pas calculable : on retourne alors le compte actuel seul, avec
    Anomalies traitees = 0 (rien à comparer pour l'instant).
    """
    (lundi_act, dim_act, lundi_prec, dim_prec,
     num_act, num_prec) = get_bornes_semaines(now_ts)

    resultat_vide = {
        "num_semaine_actuelle": num_act, "num_semaine_precedente": num_prec,
        "date_act": None, "date_prec": None,
        "par_poste": pd.DataFrame(columns=["Poste", "Anomalies semaine", "Anomalies traitees"]),
        "detail_par_poste": {},
    }
    if hist_df is None or hist_df.empty or "_section" not in hist_df.columns:
        return resultat_vide

    date_act = max(
        (_derniere_date_dans(hist_df, "ano_perf", lundi_act, dim_act),
         _derniere_date_dans(hist_df, "ano_qual", lundi_act, dim_act)),
        default=None, key=lambda d: (d is not None, d),
    )
    if date_act is None:
        return resultat_vide
    date_prec = max(
        (_derniere_date_dans(hist_df, "ano_perf", lundi_prec, dim_prec),
         _derniere_date_dans(hist_df, "ano_qual", lundi_prec, dim_prec)),
        default=None, key=lambda d: (d is not None, d),
    )

    lignes_detail = []
    for type_nom, section, kpi_list in [("Performance", "ano_perf", kpi_list_perf),
                                          ("Qualite", "ano_qual", kpi_list_qual)]:
        sub = hist_df[hist_df["_section"] == section]
        if sub.empty or "Poste de travail" not in sub.columns:
            continue
        row_act = sub[sub["Date_parsed"] == date_act].set_index("Poste de travail")
        row_prec = (sub[sub["Date_parsed"] == date_prec].set_index("Poste de travail")
                    if date_prec is not None else pd.DataFrame())
        for poste in row_act.index:
            for kpi in kpi_list:
                if kpi not in row_act.columns:
                    continue
                try:
                    a_act = float(row_act.loc[poste, kpi])
                except Exception:
                    continue
                if pd.isna(a_act):
                    continue
                a_prec = None
                if not row_prec.empty and poste in row_prec.index and kpi in row_prec.columns:
                    try:
                        a_prec = float(row_prec.loc[poste, kpi])
                    except Exception:
                        a_prec = None
                traite = max(0, int(a_prec) - int(a_act)) if a_prec is not None and not pd.isna(a_prec) else 0
                lignes_detail.append({
                    "Poste": poste, "Type": type_nom, "KPI": kpi,
                    "Anomalies semaine": int(a_act), "Anomalies traitees": traite,
                })

    detail_df = pd.DataFrame(lignes_detail)
    if detail_df.empty:
        return resultat_vide

    par_poste = (
        detail_df.groupby("Poste")[["Anomalies semaine", "Anomalies traitees"]]
        .sum().reset_index().sort_values("Anomalies semaine", ascending=False)
    )
    detail_par_poste = {
        poste: grp[["Type", "KPI", "Anomalies semaine", "Anomalies traitees"]]
                .sort_values("Anomalies semaine", ascending=False).reset_index(drop=True)
        for poste, grp in detail_df.groupby("Poste")
    }

    return {
        "num_semaine_actuelle": num_act, "num_semaine_precedente": num_prec,
        "date_act": date_act, "date_prec": date_prec,
        "par_poste": par_poste, "detail_par_poste": detail_par_poste,
    }


def calculate_suivi_semaine_intra(hist_df: pd.DataFrame, annee: int, numero_semaine: int,
                                   kpi_list_perf: list, kpi_list_qual: list) -> dict:
    """
    NOUVEAU (demande explicite, page Suivi Évolution — corrige la
    logique précédente qui comparait à la semaine PRÉCÉDENTE) :

    Pour la semaine ISO donnée (année, numéro), compare la PREMIÈRE
    extraction enregistrée CETTE semaine-là (référence/baseline, début
    de semaine) à la DERNIÈRE extraction enregistrée cette même semaine
    (état actuel — se met à jour automatiquement à chaque nouvelle
    extraction reçue durant la semaine, sans attendre la semaine
    suivante). "Anomalies traitées" = combien ont été résorbées DEPUIS
    LE DÉBUT DE CETTE SEMAINE, jusqu'à sa dernière extraction connue.

    Si une seule extraction existe pour la semaine, traité = 0 (rien à
    comparer pour l'instant, la première extraction sert de référence).

    Retourne le même format que calculate_suivi_anomalies_semaine :
      {"num_semaine_actuelle", "num_semaine_precedente" (=même numéro
      ici, gardé pour compatibilité d'affichage), "date_act", "date_prec"
      (= date de début de semaine), "par_poste", "detail_par_poste"}.
    """
    resultat_vide = {
        "num_semaine_actuelle": numero_semaine, "num_semaine_precedente": numero_semaine,
        "date_act": None, "date_prec": None,
        "par_poste": pd.DataFrame(columns=["Poste", "Anomalies semaine", "Anomalies traitees"]),
        "detail_par_poste": {},
    }
    if hist_df is None or hist_df.empty or "_section" not in hist_df.columns:
        return resultat_vide

    sub_toutes = hist_df[hist_df["_section"].isin(["ano_perf", "ano_qual"])]
    dates_semaine = sub_toutes["Date_parsed"].dropna()
    dates_semaine = dates_semaine[
        dates_semaine.apply(lambda d: d.isocalendar().year == annee and d.isocalendar().week == numero_semaine)
    ].sort_values().unique()

    if len(dates_semaine) == 0:
        return resultat_vide

    date_debut = pd.Timestamp(dates_semaine[0])   # référence (baseline)
    date_fin = pd.Timestamp(dates_semaine[-1])    # dernière extraction connue

    lignes_detail = []
    for type_nom, section, kpi_list in [("Performance", "ano_perf", kpi_list_perf),
                                          ("Qualite", "ano_qual", kpi_list_qual)]:
        sub = hist_df[hist_df["_section"] == section]
        if sub.empty or "Poste de travail" not in sub.columns:
            continue
        row_fin = sub[sub["Date_parsed"] == date_fin].set_index("Poste de travail")
        row_fin = row_fin[~row_fin.index.duplicated(keep="last")]
        row_debut = sub[sub["Date_parsed"] == date_debut].set_index("Poste de travail")
        row_debut = row_debut[~row_debut.index.duplicated(keep="last")]

        for poste in row_fin.index:
            for kpi in kpi_list:
                if kpi not in row_fin.columns:
                    continue
                try:
                    a_fin = float(row_fin.loc[poste, kpi])
                except Exception:
                    continue
                if pd.isna(a_fin):
                    continue
                a_debut = None
                if poste in row_debut.index and kpi in row_debut.columns:
                    try:
                        a_debut = float(row_debut.loc[poste, kpi])
                    except Exception:
                        a_debut = None
                traite = max(0, int(a_debut) - int(a_fin)) if a_debut is not None and not pd.isna(a_debut) else 0
                lignes_detail.append({
                    "Poste": poste, "Type": type_nom, "KPI": kpi,
                    "Anomalies semaine": int(a_fin), "Anomalies traitees": traite,
                })

    detail_df = pd.DataFrame(lignes_detail)
    if detail_df.empty:
        return resultat_vide

    par_poste = (
        detail_df.groupby("Poste")[["Anomalies semaine", "Anomalies traitees"]]
        .sum().reset_index().sort_values("Anomalies semaine", ascending=False)
    )
    detail_par_poste = {
        poste: grp[["Type", "KPI", "Anomalies semaine", "Anomalies traitees"]]
                .sort_values("Anomalies semaine", ascending=False).reset_index(drop=True)
        for poste, grp in detail_df.groupby("Poste")
    }

    return {
        "num_semaine_actuelle": numero_semaine, "num_semaine_precedente": numero_semaine,
        "date_act": date_fin, "date_prec": date_debut if date_debut != date_fin else None,
        "par_poste": par_poste, "detail_par_poste": detail_par_poste,
    }
