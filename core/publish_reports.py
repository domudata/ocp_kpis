# -*- coding: utf-8 -*-
"""
Orchestration : pour un poste de travail donné, génère le rapport KPI
(PPTX ET PDF, tous deux en Python pur), génère le fichier Excel des
anomalies OT+Avis, puis publie les fichiers sur GitHub dans
presentation/<poste>/.

CORRIGÉ : le PDF n'est plus obtenu par conversion du PPTX via
LibreOffice (subprocess "soffice"), ce mécanisme s'étant révélé fragile
sur Streamlit Cloud (dépendance système absente après suppression de
packages.txt, elle-même nécessaire pour contourner un échec de dépôt
Debian côté plateforme). Le PDF est désormais généré DIRECTEMENT et
indépendamment via reportlab (core/generate_report_pdf.py), sans
aucune dépendance système. Le PPTX continue d'être généré et publié
séparément, pour ceux qui préfèrent l'éditer.
"""
import io
import pandas as pd
import streamlit as st

# CORRIGÉ : plus aucune dépendance à core/generate_report.py ni au PPTX.
# La génération PowerPoint a été abandonnée au profit du PDF direct
# (reportlab), et l'import de build_poste_report_pptx faisait échouer
# tout le module quand cette fonction n'existait plus. SHORT_LABELS,
# seule autre chose qui en venait, est défini ici.
SHORT_LABELS = {
    "TAUX_REALISATION_CORRECTIF/PT": "Réalisation correctif",
    "OT préparation <1 mois": "Prépa <1m",
    "OT préparation 1mois< <3mois": "Prépa 1-3m",
    "OT préparation >3 mois": "Prépa >3m",
    "OT planification <1 mois": "Planif <1m",
    "OT planification 1mois< <3mois": "Planif 1-3m",
    "OT planification >3 mois": "Planif >3m",
    "OT exécution <1 mois": "Exéc <1m",
    "OT exécution 1mois< <3mois": "Exéc 1-3m",
    "OT exécution >3 mois": "Exéc >3m",
    "Performance Graissage": "Graissage",
    "Performance Inspection": "Inspection",
    "Performance Systématiques": "Systématiques",
    "Taux d'approbation des Avis": "Approbation avis",
    "OT LANC ESTIME": "OT estimés",
    "Backlog préparation caractérisé": "Backlog prépa",
    "Backlog planification caractérisé": "Backlog planif",
    "OT CONFIME": "OT confirmés",
    "OT_COR_EGAL": "Coûts égaux",
    "OT Fiabilité": "Fiabilité",
    "Total Avis de Panne": "Avis panne",
}
from core.generate_report_pdf import build_poste_report_pdf
from core.anomalies import build_anomaly_dfs
from core.export_anomalies import build_anomalies_workbook
from core.github_publish import upload_file, is_configured
from core.constants import QK, PK, CIBLE, ACT_MAP, KPI_RESP_MAP


def _sanitize_poste_name(poste: str) -> str:
    """Nettoie le nom du poste pour en faire un nom de dossier valide."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(poste))


def generate_and_publish_poste_report(
    poste: str, ckdf_row: pd.Series, pscore: float, qscore: float,
    ano_map: dict, dfp: pd.DataFrame, avf: pd.DataFrame, now_ts,
    date_str: str, dry_run: bool = False,
):
    """
    Génère et publie (si dry_run=False) les fichiers pour UN poste.
    Retourne un dict de statut : {"poste":, "pdf": bool,
    "xlsx": bool, "messages": [...]}.
    """
    status = {"poste": poste, "pdf": False, "xlsx": False, "messages": []}
    folder = _sanitize_poste_name(poste)

    # ── 1) Données KPI + anomalies + plan d'action pour ce poste ──
    kpi_perf = {k: round(float(ckdf_row[k]), 1) for k in QK if k in ckdf_row.index and pd.notna(ckdf_row[k])}
    kpi_qual = {k: round(float(ckdf_row[k]), 1) for k in PK if k in ckdf_row.index and pd.notna(ckdf_row[k])}

    anomalies = {}
    total_anomalies = 0
    for k in list(QK) + list(PK):
        n = int(ano_map.get(k, pd.Series()).get(poste, 0))
        anomalies[k] = n
        total_anomalies += n

    plan_action = []
    for kpi in list(QK) + list(PK):
        nb_anom = anomalies.get(kpi, 0)
        if nb_anom <= 0:
            continue
        actual = float(ckdf_row.get(kpi, 100))
        target = CIBLE.get(kpi, 100)
        from core.calcul_kpi import is_lb
        lower = is_lb(kpi)
        ecart = (target - actual) if lower else (actual - target)
        plan_action.append({
            "kpi": kpi, "actual": round(actual, 1), "target": target,
            "ecart": round(ecart, 1), "nb_anom": nb_anom,
            "responsable": KPI_RESP_MAP.get(kpi, "Non assigné"),
            "action": ACT_MAP.get(kpi, ""),
        })

    # ── 3) Génération PDF — DIRECTEMENT via reportlab, sans LibreOffice ──
    try:
        pdf_bytes = build_poste_report_pdf(
            poste=poste, pscore=pscore, qscore=qscore,
            kpi_perf=kpi_perf, kpi_qual=kpi_qual, cibles=CIBLE,
            anomalies=anomalies, total_anomalies=total_anomalies,
            plan_action=plan_action, date_str=date_str,
            short_labels=SHORT_LABELS,
        )
        status["pdf"] = True
    except Exception as e:
        status["messages"].append(f"Échec génération PDF : {e}")
        pdf_bytes = None

    # ── 4) Fichier Excel des anomalies (OT + Avis), filtré sur ce poste ──
    try:
        dfp_poste = dfp[dfp["Poste travail princ."] == poste].copy()
        avf_poste = avf[avf["Poste travail princ."] == poste].copy() if "Poste travail princ." in avf.columns else avf.iloc[0:0]
        anomaly_dfs = build_anomaly_dfs(dfp_poste, avf_poste, now_ts)
        xlsx_bytes = build_anomalies_workbook(anomaly_dfs, KPI_RESP_MAP, ACT_MAP)
        status["xlsx"] = True
    except Exception as e:
        status["messages"].append(f"Échec génération Excel anomalies : {e}")
        xlsx_bytes = None

    if dry_run:
        status["messages"].append("Mode test (dry_run) : fichiers générés mais NON publiés sur GitHub.")
        status["_pdf_bytes"] = pdf_bytes
        status["_xlsx_bytes"] = xlsx_bytes
        return status

    # ── 5) Publication sur GitHub (PDF + Excel) ──
    if not is_configured():
        status["messages"].append("GITHUB_TOKEN / GITHUB_REPO non configurés — fichiers générés mais non publiés.")
        return status

    if pdf_bytes:
        ok, msg = upload_file(f"presentation/{folder}/rapport.pdf", pdf_bytes, f"Rapport KPI {poste} (PDF) — {date_str}")
        status["messages"].append(f"PDF → GitHub : {'OK' if ok else msg}")
        status["pdf_published"] = ok

    if xlsx_bytes:
        ok, msg = upload_file(f"presentation/{folder}/anomalies.xlsx", xlsx_bytes, f"Anomalies {poste} — {date_str}")
        status["messages"].append(f"Excel → GitHub : {'OK' if ok else msg}")
        status["xlsx_published"] = ok

    return status


def generate_and_publish_division_report(
    division: str, postes_division: list, ckdf: pd.DataFrame,
    pscores: dict, qscores: dict, ano_map: dict, date_str: str,
    dry_run: bool = False,
):
    """
    Génère et publie UN rapport consolidé pour une division entière
    (SF01 ou SF02), agrégeant l'ensemble de ses postes.

    Différence assumée avec les rapports par poste : ce rapport de
    synthèse ne s'accompagne PAS d'un fichier Excel d'anomalies. Le
    détail ligne à ligne reste disponible dans les rapports par poste ;
    ici l'objectif est une vue d'ensemble destinée au pilotage, pas à
    l'exploitation opérationnelle.

    Méthode d'agrégation des KPI : pour chaque indicateur, on applique
    gscore() à la valeur de CHAQUE poste (verdict 0/1), puis on rapporte
    la somme au nombre de postes évalués — soit le taux de conformité de
    la division sur cet indicateur. C'est la même logique 0/1 que celle
    utilisée pour les scores de l'application.
    """
    from core.calcul_kpi import gscore

    status = {"poste": division, "pdf": False, "xlsx": None,
              "messages": [], "est_division": True}
    folder = _sanitize_poste_name(division)

    postes_valides = [p for p in postes_division if p in ckdf.index]
    if not postes_valides:
        status["messages"].append("Aucun poste de cette division dans les données.")
        return status

    def _taux_conformite(kpi):
        """% de postes de la division conformes sur ce KPI."""
        total = valides = 0
        for p in postes_valides:
            val = ckdf.loc[p].get(kpi)
            if val is None or pd.isna(val):
                continue
            total += gscore(kpi, float(val), CIBLE.get(kpi, 100))
            valides += 1
        return (total / valides * 100) if valides else None

    kpi_perf, kpi_qual = {}, {}
    for k in QK:
        t = _taux_conformite(k)
        if t is not None:
            kpi_perf[k] = round(t, 1)
    for k in PK:
        t = _taux_conformite(k)
        if t is not None:
            kpi_qual[k] = round(t, 1)

    # Score global de la division = moyenne des verdicts 0/1 sur toutes
    # les cellules (poste × KPI), cohérent avec les cartes de l'application
    def _score_global(liste_kpi):
        total = valides = 0
        for p in postes_valides:
            for k in liste_kpi:
                val = ckdf.loc[p].get(k)
                if val is None or pd.isna(val):
                    continue
                total += gscore(k, float(val), CIBLE.get(k, 100))
                valides += 1
        return round(total / valides * 100, 1) if valides else 0

    pscore_div = _score_global(QK)
    qscore_div = _score_global(PK)

    # Anomalies cumulées sur toute la division
    anomalies, total_anomalies = {}, 0
    for k in list(QK) + list(PK):
        serie = ano_map.get(k, pd.Series(dtype=float))
        n = sum(int(serie.get(p, 0)) for p in postes_valides)
        anomalies[k] = n
        total_anomalies += n

    # Plan d'action de la division, trié par volume d'anomalies
    plan_action = []
    for kpi in list(QK) + list(PK):
        nb_anom = anomalies.get(kpi, 0)
        if nb_anom <= 0:
            continue
        from core.calcul_kpi import is_lb
        target = CIBLE.get(kpi, 100)
        taux = kpi_perf.get(kpi, kpi_qual.get(kpi, 0))
        # L'écart porte ici sur le taux de conformité de la division
        ecart = taux - 100
        plan_action.append({
            "kpi": kpi, "actual": round(taux, 1), "target": target,
            "ecart": round(ecart, 1), "nb_anom": nb_anom,
            "responsable": KPI_RESP_MAP.get(kpi, "Non assigné"),
            "action": ACT_MAP.get(kpi, ""),
        })
    plan_action.sort(key=lambda x: -x["nb_anom"])

    titre = f"{division} — Synthèse division ({len(postes_valides)} postes)"
    try:
        pdf_bytes = build_poste_report_pdf(
            poste=titre, pscore=pscore_div, qscore=qscore_div,
            kpi_perf=kpi_perf, kpi_qual=kpi_qual, cibles=CIBLE,
            anomalies=anomalies, total_anomalies=total_anomalies,
            plan_action=plan_action, date_str=date_str,
            short_labels=SHORT_LABELS, mode_conformite=True,
        )
        status["pdf"] = True
    except Exception as e:
        status["messages"].append(f"Échec génération PDF division : {e}")
        return status

    if dry_run:
        status["messages"].append("Mode test (dry_run) : rapport généré mais NON publié.")
        status["_pdf_bytes"] = pdf_bytes
        return status

    if not is_configured():
        status["messages"].append("GitHub non configuré — rapport généré mais non publié.")
        return status

    ok, msg = upload_file(f"presentation/{folder}/rapport.pdf", pdf_bytes,
                           f"Rapport de division {division} — {date_str}")
    status["messages"].append(f"PDF division → GitHub : {'OK' if ok else msg}")
    status["pdf_published"] = ok
    return status


def generate_and_publish_all_postes(
    ckdf: pd.DataFrame, pscores: dict, qscores: dict, ano_map: dict,
    dfp: pd.DataFrame, avf: pd.DataFrame, now_ts, date_str: str,
    postes: list = None, dry_run: bool = False, progress_callback=None,
):
    """
    Boucle sur tous les postes (ou la liste fournie) et publie leur
    rapport, PUIS génère deux rapports de synthèse supplémentaires —
    un par division (SF01 et SF02) — sans fichier Excel associé.
    progress_callback(i, n, poste) est appelé avant chaque poste.
    Retourne la liste des status.
    """
    postes = postes if postes is not None else list(ckdf.index)
    results = []

    # ── Rapports par poste (inchangés : PDF + Excel d'anomalies) ──
    for i, poste in enumerate(postes):
        if progress_callback:
            progress_callback(i, len(postes), poste)
        if poste not in ckdf.index:
            results.append({"poste": poste, "messages": ["Poste absent de ckdf, ignoré."]})
            continue
        res = generate_and_publish_poste_report(
            poste=poste, ckdf_row=ckdf.loc[poste],
            pscore=pscores.get(poste, 0), qscore=qscores.get(poste, 0),
            ano_map=ano_map, dfp=dfp, avf=avf, now_ts=now_ts,
            date_str=date_str, dry_run=dry_run,
        )
        results.append(res)

    # ── Deux rapports de synthèse par division, SANS Excel ──
    for division, prefixe in [("SF01", "SF1"), ("SF02", "SF2")]:
        postes_div = [p for p in postes if str(p).startswith(prefixe)]
        if not postes_div:
            continue
        if progress_callback:
            progress_callback(len(postes), len(postes) + 2, f"Synthèse {division}")
        res = generate_and_publish_division_report(
            division=division, postes_division=postes_div, ckdf=ckdf,
            pscores=pscores, qscores=qscores, ano_map=ano_map,
            date_str=date_str, dry_run=dry_run,
        )
        results.append(res)

    return results
