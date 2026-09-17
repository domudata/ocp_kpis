# -*- coding: utf-8 -*-
"""
Historisation des KPI — architecture 100% GitHub, sans disque local.

PROBLÈME RÉSOLU : la version précédente utilisait le disque local comme
intermédiaire (téléchargement GitHub → fusion locale → sauvegarde locale
→ publication GitHub séparée, pilotée par app.py). Sur Streamlit Cloud,
le système de fichiers est ÉPHÉMÈRE : il est réinitialisé à chaque
redémarrage de l'application. Toute date écrite localement mais non
republiée immédiatement était donc perdue, et le fichier local repartait
systématiquement de zéro — d'où l'historique bloqué à une seule date.

NOUVELLE ARCHITECTURE : tout se passe en mémoire, et GitHub est la
SEULE source de vérité.
    1. Télécharger le classeur historique depuis GitHub (en mémoire)
    2. Y ajouter / mettre à jour la feuille de la date courante
    3. Republier immédiatement le classeur complet sur GitHub
    4. Lire l'historique directement depuis GitHub pour l'affichage
Aucune écriture disque n'intervient : le redémarrage de l'application
n'a plus aucun effet sur l'historique.

L'enregistrement est déclenché par la date lue dans date.txt : une
nouvelle date crée une nouvelle feuille, une date déjà présente met à
jour la feuille existante.
"""
import io
import os
import re

import pandas as pd
import streamlit as st
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

CHEMIN_HISTORIQUE_GITHUB = "kpis/indicateurs_kpis.xlsx"
CHEMIN_HISTORIQUE_LOCAL = "kpis.xlsx"
CHEMIN_HISTORIQUE_KPIS_DIR = os.path.join("kpis", "indicateurs_kpis.xlsx")


def _nom_feuille(date_str: str) -> str:
    """Convertit une date en nom de feuille Excel valide (31 car. max)."""
    return re.sub(r'[/\\*?:\[\]]', '-', str(date_str))[:31]


def _charger_historique_classeur():
    """Récupère le classeur historique en priorité depuis :
      1. GitHub si configuré
      2. Le fichier kpis.xlsx local (racine)
      3. Le fichier kpis/indicateurs_kpis.xlsx local
    Retourne (workbook, message_diagnostic)."""
    # 1. GitHub si configuré
    try:
        from core.github_publish import download_file, is_configured
        if is_configured():
            contenu, err = download_file(CHEMIN_HISTORIQUE_GITHUB)
            if contenu:
                try:
                    wb = load_workbook(io.BytesIO(contenu))
                    sheets = [s for s in wb.sheetnames if s != "Sheet"]
                    return wb, f"Historique GitHub chargé ({len(sheets)} date(s) : {sheets})"
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Local kpis.xlsx (racine)
    if os.path.exists(CHEMIN_HISTORIQUE_LOCAL):
        try:
            wb = load_workbook(CHEMIN_HISTORIQUE_LOCAL)
            sheets = [s for s in wb.sheetnames if s != "Sheet"]
            if sheets:
                return wb, f"Fichier kpis.xlsx local chargé ({len(sheets)} date(s) : {sheets})"
        except Exception:
            pass

    # 3. Local kpis/indicateurs_kpis.xlsx
    if os.path.exists(CHEMIN_HISTORIQUE_KPIS_DIR):
        try:
            wb = load_workbook(CHEMIN_HISTORIQUE_KPIS_DIR)
            sheets = [s for s in wb.sheetnames if s != "Sheet"]
            if sheets:
                return wb, f"Fichier kpis/indicateurs_kpis.xlsx local chargé ({len(sheets)} date(s) : {sheets})"
        except Exception:
            pass

    return None, "Aucun historique existant (nouveau classeur initialisé)"


def _telecharger_historique():
    """Alias rétro-compatible."""
    return _charger_historique_classeur()


def _ecrire_feuille(wb, nom, prows, pcols, qrows, qcols, ano_p_r, ano_p_c, ano_q_r, ano_q_c):
    """Écrit (ou réécrit) la feuille d'une date dans le classeur."""
    hf = Font(bold=True, color="FFFFFF", size=10)
    hfl = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    tf = Font(bold=True, size=12, color="1E3A5F")
    tb = Border(left=Side(style="thin"), right=Side(style="thin"),
                top=Side(style="thin"), bottom=Side(style="thin"))

    if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
        del wb["Sheet"]
    if nom in wb.sheetnames:
        del wb[nom]
    ws = wb.create_sheet(nom)

    def section(titre, cols, rows, ligne):
        ws.cell(row=ligne, column=1, value=titre).font = tf
        ligne += 1
        for j, c in enumerate(cols, 1):
            cl = ws.cell(row=ligne, column=j, value=c)
            cl.font, cl.fill, cl.border = hf, hfl, tb
            cl.alignment = Alignment(horizontal="center")
        ligne += 1
        for r in rows:
            for j, c in enumerate(cols, 1):
                cl = ws.cell(row=ligne, column=j, value=r.get(c, ""))
                cl.border = tb
                cl.alignment = Alignment(horizontal="center")
            ligne += 1
        return ligne + 1

    n = 1
    n = section("INDICATEURS DE PERFORMANCE", pcols, prows, n)
    if ano_p_c and ano_p_r:
        n = section("ANOMALIES PERFORMANCE", ano_p_c, ano_p_r, n)
    n = section("INDICATEURS DE QUALITE", qcols, qrows, n)
    if ano_q_c and ano_q_r:
        n = section("ANOMALIES QUALITE", ano_q_c, ano_q_r, n)

    if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
        del wb["Sheet"]
    return wb


def save_kpis_to_excel(prows, pcols, qrows, qcols,
                        ano_p_r, ano_p_c, ano_q_r, ano_q_c,
                        sheet_name: str) -> None:
    """
    Enregistre les KPI de la date courante dans l'historique :
      - Sauvegarde en local dans kpis.xlsx (racine) ET kpis/indicateurs_kpis.xlsx
      - Si GitHub est configuré, publie également sur GitHub
    """
    diag = []
    nom = _nom_feuille(sheet_name)
    diag.append(f"Date à enregistrer : '{nom}'")

    wb, msg = _charger_historique_classeur()
    diag.append(msg)
    if wb is None:
        wb = Workbook()
        diag.append("→ Nouveau classeur créé en mémoire")

    dates_avant = [s for s in wb.sheetnames if s != "Sheet"]
    deja_presente = nom in dates_avant

    wb = _ecrire_feuille(wb, nom, prows, pcols, qrows, qcols,
                          ano_p_r, ano_p_c, ano_q_r, ano_q_c)
    dates_apres = [s for s in wb.sheetnames if s != "Sheet"]
    diag.append(f"{'Mise à jour' if deja_presente else 'Ajout'} de la date → "
                f"{len(dates_apres)} date(s) au total : {dates_apres}")

    # 1) Sauvegarde locale systématique dans kpis.xlsx et kpis/indicateurs_kpis.xlsx
    try:
        wb.save(CHEMIN_HISTORIQUE_LOCAL)
        diag.append(f"Sauvegarde locale {CHEMIN_HISTORIQUE_LOCAL} : OK")
    except Exception as e:
        diag.append(f"Erreur sauvegarde {CHEMIN_HISTORIQUE_LOCAL} : {e}")

    try:
        os.makedirs("kpis", exist_ok=True)
        wb.save(CHEMIN_HISTORIQUE_KPIS_DIR)
        diag.append(f"Sauvegarde locale {CHEMIN_HISTORIQUE_KPIS_DIR} : OK")
    except Exception as e:
        diag.append(f"Erreur sauvegarde {CHEMIN_HISTORIQUE_KPIS_DIR} : {e}")

    # Mise à jour synchronisée de date.txt
    try:
        if os.path.exists("date.txt"):
            with open("date.txt", "r", encoding="utf-8") as f:
                d_cur = f.read().strip()
        else:
            d_cur = ""
        if d_cur != sheet_name:
            with open("date.txt", "w", encoding="utf-8") as f:
                f.write(sheet_name)
            diag.append(f"date.txt mis à jour : {sheet_name}")
    except Exception as e:
        diag.append(f"Erreur mise à jour date.txt : {e}")

    # 2) Publication sur GitHub si configuré
    publie_gh = False
    try:
        from core.github_publish import upload_file, is_configured
        if is_configured():
            buf = io.BytesIO()
            wb.save(buf)
            contenu = buf.getvalue()
            ok, msg_up = upload_file(CHEMIN_HISTORIQUE_GITHUB, contenu,
                                      f"Historique KPI — {sheet_name}")
            publie_gh = ok
            diag.append(f"Publication GitHub : {'OK' if ok else msg_up}")
    except Exception as e:
        diag.append(f"Publication GitHub : exception — {e}")

    msg_succes = (
        f"✅ Historique enregistré dans `kpis.xlsx` : date '{nom}' "
        f"({len(dates_apres)} date(s) au total : {', '.join(dates_apres)})"
    )
    if publie_gh:
        msg_succes += " + synchronisé sur GitHub ☁️"
    st.sidebar.success(msg_succes)

    with st.sidebar.expander("🔍 Diagnostic historique", expanded=False):
        for ligne in diag:
            st.caption(ligne)


def _bouton_secours(contenu, nom):
    """Bouton de repli permettant de récupérer le classeur si la
    publication automatique échoue."""
    st.sidebar.download_button(
        "⬇️ Télécharger l'historique",
        data=contenu, file_name="kpis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"secours_{nom}",
    )


@st.cache_data(show_spinner=False, ttl=60)
def charger_historique_depuis_github():
    """
    Lit l'historique complet (depuis GitHub si configuré, ou depuis
    kpis.xlsx / kpis/indicateurs_kpis.xlsx en local) et le convertit en
    DataFrame standard exploitable (avec Date, Poste de travail, _section, KPIs...).
    """
    wb, msg = _charger_historique_classeur()
    if wb is None:
        return pd.DataFrame(), msg

    records = []
    for sheet_name in wb.sheetnames:
        if sheet_name == "Sheet":
            continue
        try:
            ws = wb[sheet_name]
            rows_data = list(ws.iter_rows(values_only=True))
            section = None
            headers = None
            for row in rows_data:
                if not row or not any(v is not None for v in row):
                    continue
                cell0 = str(row[0]).strip() if row[0] is not None else ""
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
                    headers = [str(c).strip() if c is not None else "" for c in row]; continue
                if section and headers and cell0 and cell0 not in ("Cible", "Total general", "Total", ""):
                    entry = {"Date": sheet_name.replace("-", "/")}
                    for j, h in enumerate(headers):
                        if j < len(row) and h:
                            entry[h] = row[j]
                    entry["_section"] = section
                    records.append(entry)
        except Exception:
            continue

    if not records:
        return pd.DataFrame(), msg

    df = pd.DataFrame(records)
    if "Date" in df.columns:
        df["Date_parsed"] = pd.to_datetime(
            df["Date"].str.replace("-", "/"), format="%d/%m/%Y", errors="coerce"
        )

    _non_numeric_cols = {"Date", "Poste de travail", "_section", "Date_parsed"}
    for col in df.columns:
        if col not in _non_numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "Date_parsed" in df.columns:
        df = df.sort_values("Date_parsed").reset_index(drop=True)

    nb_dates = len([s for s in wb.sheetnames if s != "Sheet"])
    return df, f"{nb_dates} date(s) chargée(s) ({msg})"



def export_btn(df: pd.DataFrame, filename: str) -> None:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    st.download_button(
        "📥 Exporter Excel", data=buf, file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
