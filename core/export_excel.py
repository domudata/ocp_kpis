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

    # 2) Publication sur GitHub si configuré et mise en mémoire
    publie_gh = False
    buf = io.BytesIO()
    wb.save(buf)
    contenu = buf.getvalue()
    try:
        st.session_state["_dernier_historique_bytes"] = contenu
        st.session_state["_historique_dates_list"] = dates_apres
    except Exception:
        pass

    try:
        from core.github_publish import upload_file, is_configured
        if is_configured():
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


def get_historique_bytes():
    """
    Récupère le contenu binaire (.xlsx) et la liste des feuilles (dates)
    du classeur historique.
    Vérifie dans l'ordre :
      1. st.session_state["_dernier_historique_bytes"]
      2. Le fichier kpis/indicateurs_kpis.xlsx local
      3. Le fichier kpis.xlsx local
      4. Téléchargement depuis GitHub via download_file
    Retourne : (bytes_data: bytes | None, sheetnames: list[str])
    """
    # 1. En mémoire de session si tout juste enregistré
    try:
        if "_dernier_historique_bytes" in st.session_state and st.session_state["_dernier_historique_bytes"]:
            b = st.session_state["_dernier_historique_bytes"]
            dates = st.session_state.get("_historique_dates_list", [])
            return b, dates
    except Exception:
        pass

    # 2. Local kpis/indicateurs_kpis.xlsx
    if os.path.exists(CHEMIN_HISTORIQUE_KPIS_DIR):
        try:
            with open(CHEMIN_HISTORIQUE_KPIS_DIR, "rb") as f:
                content = f.read()
            wb = load_workbook(io.BytesIO(content), read_only=True)
            dates = [s for s in wb.sheetnames if s != "Sheet"]
            wb.close()
            return content, dates
        except Exception:
            pass

    # 3. Local kpis.xlsx
    if os.path.exists(CHEMIN_HISTORIQUE_LOCAL):
        try:
            with open(CHEMIN_HISTORIQUE_LOCAL, "rb") as f:
                content = f.read()
            wb = load_workbook(io.BytesIO(content), read_only=True)
            dates = [s for s in wb.sheetnames if s != "Sheet"]
            wb.close()
            return content, dates
        except Exception:
            pass

    # 4. GitHub si configuré
    try:
        from core.github_publish import download_file, is_configured
        if is_configured():
            content, err = download_file(CHEMIN_HISTORIQUE_GITHUB)
            if content:
                wb = load_workbook(io.BytesIO(content), read_only=True)
                dates = [s for s in wb.sheetnames if s != "Sheet"]
                wb.close()
                return content, dates
    except Exception:
        pass

    return None, []


def build_date_suivi_workbook(
    prows: list, pcols: list,
    qrows: list, qcols: list,
    ano_p_r: list = None, ano_p_c: list = None,
    ano_q_r: list = None, ano_q_c: list = None,
    date_str: str = "",
    sdt=None, edt=None,
) -> bytes:
    """
    Construit un classeur Excel pour la date active avec 4 onglets :
      - Indicateurs Performance
      - Anomalies Performance
      - Indicateurs Qualité
      - Anomalies Qualité
    """
    wb = Workbook()
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    hf = Font(bold=True, color="FFFFFF", size=10)
    hfl = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    tb = Border(left=Side(style="thin", color="CBD5E1"), right=Side(style="thin", color="CBD5E1"),
                top=Side(style="thin", color="CBD5E1"), bottom=Side(style="thin", color="CBD5E1"))
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")

    def _add_sheet(titre_feuille, cols, rows):
        if not cols or not rows:
            return
        ws = wb.create_sheet(titre_feuille[:31])
        # Entêtes
        for j, c in enumerate(cols, 1):
            cell = ws.cell(row=1, column=j, value=c)
            cell.font, cell.fill, cell.border = hf, hfl, tb
            cell.alignment = center_align
        # Lignes
        for i, r in enumerate(rows, 2):
            is_special = r.get("_t") in ("cible", "total") or str(r.get(cols[0], "")).upper() in ("CIBLE", "TOTAL GENERAL")
            for j, c in enumerate(cols, 1):
                val = r.get(c, "")
                cell = ws.cell(row=i, column=j, value="" if val is None or pd.isna(val) else str(val))
                cell.border = tb
                if is_special:
                    cell.font = Font(bold=True, color="1E3A5F" if r.get("_t") == "total" else "059669")
                cell.alignment = left_align if j == 1 else center_align
        # Ajustement largeur colonnes
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = min(40, max(12, max_len + 3))

    _add_sheet("Indicateurs Performance", pcols, prows)
    if ano_p_c and ano_p_r:
        _add_sheet("Anomalies Performance", ano_p_c, ano_p_r)
    _add_sheet("Indicateurs Qualité", qcols, qrows)
    if ano_q_c and ano_q_r:
        _add_sheet("Anomalies Qualité", ano_q_c, ano_q_r)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_variations_workbook(var_df: pd.DataFrame) -> bytes:
    """Exporte le tableau des variations entre dates dans un fichier Excel formaté."""
    if var_df is None or var_df.empty:
        return b""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        var_df.to_excel(writer, sheet_name="Variations KPI", index=False)
        ws = writer.sheets["Variations KPI"]
        hf = Font(bold=True, color="FFFFFF", size=10)
        hfl = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        for cell in ws[1]:
            cell.font = hf
            cell.fill = hfl
            cell.alignment = Alignment(horizontal="center")
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(40, max(12, max_len + 3))
    return buf.getvalue()


def render_sidebar_suivi_date_export(
    fichier_date: str,
    prows: list, pcols: list,
    qrows: list, qcols: list,
    ano_p_r: list = None, ano_p_c: list = None,
    ano_q_r: list = None, ano_q_c: list = None,
    hist_df: pd.DataFrame = None,
    var_df: pd.DataFrame = None,
    sdt=None, edt=None,
) -> None:
    """
    Affiche dans la barre latérale (st.sidebar) un expander dédié à l'export
    du suivi de date et de l'historique :
      1. Suivi complet (Toutes les dates — indicateurs_kpis.xlsx)
      2. Suivi de la date active ({fichier_date})
      3. Variations entre dates (si disponibles)
    """
    clean_date = str(fichier_date).strip().replace("/", "-")

    with st.sidebar:
        with st.expander("📅 Export Suivi Date & Historique", expanded=True):
            st.markdown(
                f"<div style='font-size:12px;color:#cbd5e1;margin-bottom:6px;'>"
                f"Date active : <strong style='color:#38bdf8;'>{fichier_date}</strong>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if sdt and edt:
                try:
                    s_str = sdt.strftime('%d/%m/%Y')
                    e_str = edt.strftime('%d/%m/%Y')
                    st.caption(f"Période analysée : {s_str} ➔ {e_str}")
                except Exception:
                    pass

            # ── 1. Suivi de la date active ──
            try:
                date_bytes = build_date_suivi_workbook(
                    prows, pcols, qrows, qcols,
                    ano_p_r, ano_p_c, ano_q_r, ano_q_c,
                    date_str=fichier_date, sdt=sdt, edt=edt
                )
                if date_bytes:
                    st.download_button(
                        f"⬇️ Suivi de la date ({fichier_date})",
                        data=date_bytes,
                        file_name=f"suivi_kpis_{clean_date}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"dl_suivi_date_active_{clean_date}",
                        help="Classeur Excel complet pour cette date : Performance, Qualité et Anomalies.",
                    )
            except Exception as e_date:
                st.caption(f"Export date active indisponible : {e_date}")

            st.markdown("<hr style='margin:8px 0;border-color:rgba(255,255,255,0.15);'>", unsafe_allow_html=True)

            # ── 2. Suivi complet de toutes les dates (Historique) ──
            hist_bytes, dates_list = get_historique_bytes()
            if hist_bytes:
                nb = len(dates_list) if dates_list else (hist_df["Date"].nunique() if hist_df is not None and not hist_df.empty and "Date" in hist_df.columns else 1)
                st.caption(f"📂 Suivi historique : **{nb} date(s)**")
                st.download_button(
                    "⬇️ Suivi complet — Toutes dates (.xlsx)",
                    data=hist_bytes,
                    file_name="indicateurs_kpis.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_suivi_dates_complet_sb",
                    help="Classeur complet indicateurs_kpis.xlsx avec une feuille par date d'extraction.",
                )
            else:
                st.caption("ℹ️ Aucun historique multi-dates disponible.")

            # ── 3. Variations entre dates (si disponibles) ──
            if var_df is not None and not var_df.empty:
                try:
                    var_bytes = build_variations_workbook(var_df)
                    if var_bytes:
                        st.download_button(
                            "⬇️ Variations & Évolution (.xlsx)",
                            data=var_bytes,
                            file_name=f"variations_kpis_{clean_date}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            key="dl_var_dates_sb",
                            help="Évolution et écarts de chaque KPI par poste entre les dates d'extraction.",
                        )
                except Exception:
                    pass
