# -*- coding: utf-8 -*-
"""
Orchestration : pour un poste de travail donné, génère le rapport KPI
(PPTX), le convertit en PDF (via LibreOffice), génère le fichier Excel
des anomalies OT+Avis, puis publie les 3 fichiers sur GitHub dans
presentation/<poste>/.

⚠️ PRÉREQUIS IMPORTANT : la conversion PDF nécessite LibreOffice
installé sur la machine qui exécute l'app. Sur Streamlit Cloud, ça
nécessite d'ajouter un fichier `packages.txt` à la racine du dépôt
contenant la ligne `libreoffice`, sinon la conversion PDF échouera
(le PPTX sera quand même généré et publié normalement).
"""
import io
import os
import subprocess
import tempfile

import pandas as pd
import streamlit as st

from core.generate_report import build_poste_report_pptx
from core.anomalies import build_anomaly_dfs
from core.export_anomalies import build_anomalies_workbook
from core.github_publish import upload_file, is_configured
from core.constants import QK, PK, CIBLE, ACT_MAP, KPI_RESP_MAP


def _sanitize_poste_name(poste: str) -> str:
    """Nettoie le nom du poste pour en faire un nom de dossier valide."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(poste))


def pptx_bytes_to_pdf_bytes(pptx_bytes: bytes):
    """
    Convertit des bytes PPTX en bytes PDF via LibreOffice (soffice).
    Retourne (pdf_bytes, error_message). error_message est None si OK.
    """
    with tempfile.TemporaryDirectory() as tmp:
        pptx_path = os.path.join(tmp, "rapport.pptx")
        with open(pptx_path, "wb") as f:
            f.write(pptx_bytes)
        try:
            result = subprocess.run(
                ["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, pptx_path],
                capture_output=True, text=True, timeout=60,
            )
        except FileNotFoundError:
            return None, "LibreOffice ('soffice') introuvable sur ce serveur — ajoutez 'libreoffice' dans packages.txt."
        except subprocess.TimeoutExpired:
            return None, "Conversion PDF trop longue (timeout 60s)."

        pdf_path = os.path.join(tmp, "rapport.pdf")
        if not os.path.exists(pdf_path):
            return None, f"Conversion PDF échouée : {result.stderr[:300]}"
        with open(pdf_path, "rb") as f:
            return f.read(), None


def generate_and_publish_poste_report(
    poste: str, ckdf_row: pd.Series, pscore: float, qscore: float,
    ano_map: dict, dfp: pd.DataFrame, avf: pd.DataFrame, now_ts,
    date_str: str, dry_run: bool = False,
):
    """
    Génère et publie (si dry_run=False) les 3 fichiers pour UN poste.
    Retourne un dict de statut : {"poste":, "pptx": bool, "pdf": bool,
    "xlsx": bool, "messages": [...]}.
    """
    status = {"poste": poste, "pptx": False, "pdf": False, "xlsx": False, "messages": []}
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

    # ── 2) Génération PPTX ──
    try:
        prs = build_poste_report_pptx(
            poste=poste, pscore=pscore, qscore=qscore,
            kpi_perf=kpi_perf, kpi_qual=kpi_qual, cibles=CIBLE,
            anomalies=anomalies, total_anomalies=total_anomalies,
            plan_action=plan_action, date_str=date_str,
        )
        buf = io.BytesIO()
        prs.save(buf)
        pptx_bytes = buf.getvalue()
        status["pptx"] = True
    except Exception as e:
        status["messages"].append(f"Échec génération PPTX : {e}")
        return status

    # ── 3) Conversion PDF ──
    pdf_bytes, pdf_err = pptx_bytes_to_pdf_bytes(pptx_bytes)
    if pdf_err:
        status["messages"].append(f"PDF non généré : {pdf_err}")
    else:
        status["pdf"] = True

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
        status["_pptx_bytes"] = pptx_bytes
        status["_pdf_bytes"] = pdf_bytes
        status["_xlsx_bytes"] = xlsx_bytes
        return status

    # ── 5) Publication sur GitHub ──
    # CORRIGÉ (sur demande) : le PPTX n'est plus publié — seuls le PDF et
    # l'Excel des anomalies sont envoyés sur GitHub. Le PPTX reste généré
    # en interne (étape 2) car nécessaire pour produire le PDF, mais son
    # contenu n'est jamais poussé vers presentation/<poste>/.
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


def generate_and_publish_all_postes(
    ckdf: pd.DataFrame, pscores: dict, qscores: dict, ano_map: dict,
    dfp: pd.DataFrame, avf: pd.DataFrame, now_ts, date_str: str,
    postes: list = None, dry_run: bool = False, progress_callback=None,
):
    """
    Boucle sur tous les postes (ou la liste fournie) et publie leur
    rapport. progress_callback(i, n, poste) est appelé avant chaque
    poste, si fourni (utile pour une barre de progression Streamlit).
    Retourne la liste des status par poste.
    """
    postes = postes if postes is not None else list(ckdf.index)
    results = []
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
    return results
