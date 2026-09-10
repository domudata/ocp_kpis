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
import re

import pandas as pd
import streamlit as st
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

CHEMIN_HISTORIQUE_GITHUB = "kpis/indicateurs_kpis.xlsx"


def _nom_feuille(date_str: str) -> str:
    """Convertit une date en nom de feuille Excel valide (31 car. max)."""
    return re.sub(r'[/\\*?:\[\]]', '-', str(date_str))[:31]


def _telecharger_historique():
    """Récupère le classeur historique depuis GitHub, en mémoire.
    Retourne (workbook, message_diagnostic)."""
    try:
        from core.github_publish import download_file, is_configured
    except Exception as e:
        return None, f"Module github_publish indisponible : {e}"

    if not is_configured():
        return None, "GitHub non configuré (GITHUB_TOKEN / GITHUB_REPO absents des secrets)"

    contenu, err = download_file(CHEMIN_HISTORIQUE_GITHUB)
    if contenu:
        try:
            wb = load_workbook(io.BytesIO(contenu))
            return wb, f"Historique GitHub chargé : {len(wb.sheetnames)} date(s) — {wb.sheetnames}"
        except Exception as e:
            return None, f"Fichier GitHub illisible (corrompu ?) : {e}"
    if err:
        return None, f"Téléchargement échoué : {err}"
    return None, "Aucun historique sur GitHub (normal au premier enregistrement)"


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
    Enregistre les KPI de la date courante dans l'historique GitHub.
    Signature identique à l'ancienne version (compatible avec app.py).
    """
    diag = []
    nom = _nom_feuille(sheet_name)
    diag.append(f"Date à enregistrer : '{nom}'")

    wb, msg = _telecharger_historique()
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

    # Sérialisation en mémoire
    buf = io.BytesIO()
    wb.save(buf)
    contenu = buf.getvalue()

    # Publication immédiate sur GitHub (seule source de vérité)
    try:
        from core.github_publish import upload_file, is_configured
        if not is_configured():
            st.sidebar.error(
                "❌ GitHub non configuré : l'historique ne peut pas être conservé. "
                "Ajoutez GITHUB_TOKEN et GITHUB_REPO dans les secrets Streamlit."
            )
            _bouton_secours(contenu, nom)
            return
        ok, msg_up = upload_file(CHEMIN_HISTORIQUE_GITHUB, contenu,
                                  f"Historique KPI — {sheet_name}")
        if ok:
            diag.append("Publication GitHub : OK")
            st.sidebar.success(
                f"✅ Historique enregistré sur GitHub : date '{nom}' "
                f"({len(dates_apres)} date(s) au total)"
            )
        else:
            diag.append(f"Publication GitHub : ÉCHEC — {msg_up}")
            st.sidebar.error(f"❌ Publication de l'historique échouée : {msg_up}")
            _bouton_secours(contenu, nom)
    except Exception as e:
        diag.append(f"Publication GitHub : exception — {e}")
        st.sidebar.error(f"❌ Erreur lors de la publication de l'historique : {e}")
        _bouton_secours(contenu, nom)

    with st.sidebar.expander("🔍 Diagnostic historique", expanded=False):
        for ligne in diag:
            st.caption(ligne)


def _bouton_secours(contenu, nom):
    """Bouton de repli permettant de récupérer le classeur si la
    publication automatique échoue."""
    st.sidebar.download_button(
        "⬇️ Télécharger l'historique (publication échouée)",
        data=contenu, file_name="indicateurs_kpis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"secours_{nom}",
    )


@st.cache_data(show_spinner=False, ttl=60)
def charger_historique_depuis_github():
    """
    Lit l'historique complet directement depuis GitHub et le convertit en
    DataFrame exploitable (une ligne par Date × Poste × KPI).
    Remplace la lecture d'un fichier local, désormais inutile.
    """
    wb, msg = _telecharger_historique()
    if wb is None:
        return pd.DataFrame(), msg

    lignes = []
    for feuille in wb.sheetnames:
        if feuille == "Sheet":
            continue
        ws = wb[feuille]
        date_str = feuille.replace("-", "/")
        section = None
        entetes = None
        for row in ws.iter_rows(values_only=True):
            if row is None or all(v is None for v in row):
                continue
            premier = str(row[0]) if row[0] is not None else ""
            if premier.startswith("INDICATEURS DE PERFORMANCE"):
                section, entetes = "Performance", None
                continue
            if premier.startswith("INDICATEURS DE QUALITE"):
                section, entetes = "Qualite", None
                continue
            if premier.startswith("ANOMALIES"):
                section, entetes = None, None
                continue
            if section is None:
                continue
            if entetes is None:
                entetes = [str(v) if v is not None else "" for v in row]
                continue
            poste = row[0]
            if poste in (None, "", "CIBLE"):
                continue
            for j, kpi in enumerate(entetes[1:], start=1):
                if not kpi or kpi.startswith("Score") or j >= len(row):
                    continue
                val = row[j]
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue
                lignes.append({"Date": date_str, "Poste": poste, "KPI": kpi,
                               "Valeur": val, "Famille": section})

    df = pd.DataFrame(lignes)
    if not df.empty:
        df["Date_dt"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
        df = df.sort_values("Date_dt")
    return df, f"{len([s for s in wb.sheetnames if s != 'Sheet'])} date(s) chargée(s) depuis GitHub"


def export_btn(df: pd.DataFrame, filename: str) -> None:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    st.download_button(
        "📥 Exporter Excel", data=buf, file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
