# -*- coding: utf-8 -*-
"""
Documents joints des ordres de travail (fichier « fichiers originaux »).

Le fichier « Ordres de travail.xlsx » (racine de l'application) liste des
OT — colonne « Ordre » au format « désignation (4135259) » — et une colonne
« Fichiers originaux » (nombre de fichiers joints). Toute valeur différente de 0 compte pour 1 : l'OT a
au moins un document joint. Un OT absent du fichier n'en a pas.

Sources, dans l'ordre :
  1. secret Streamlit DOCS_JOINTS_URL (lien de partage OneDrive) ;
  2. un fichier à la racine de l'application, parmi NOMS_FICHIERS.
"""
import io
import os
import re
import pandas as pd
import streamlit as st

NOMS_FICHIERS = [
    "Ordres de travail.xlsx", "ordres de travail.xlsx", "Ordres_de_travail.xlsx",
    "fichiers_originaux.xlsx", "fichier_originaux.xlsx", "fichiers_origine.xlsx",
    "fichier_origine.xlsx", "documents_joints_ot.xlsx", "documents_joints.xlsx",
]


def _norm_num(v):
    """Numéro d'OT normalisé en texte sans décimale ('4001060961')."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    m = re.search(r"\((\d+)\)\s*$", s)          # « désignation (4135259) »
    if m:
        s = m.group(1)
    s = re.sub(r"\.0+$", "", s)
    return s.lstrip("0") or None


def _code_poste(v):
    """« Section Mécanique Engrais REX (SF1-MREX) » → « SF1-MREX »."""
    s = str(v or "").strip()
    m = re.search(r"\(([^()]+)\)\s*$", s)
    return m.group(1).strip() if m else s


def _colonne(cols, tests):
    for t in tests:
        for c in cols:
            if t(str(c).strip().lower()):
                return c
    return None


def lire_documents(contenu: bytes):
    """Renvoie (DataFrame [ot, poste] des OT avec document joint, message d'erreur)."""
    vide = pd.DataFrame(columns=["ot", "poste"])
    try:
        if contenu[:2] in (b"PK", b"\xd0\xcf"):
            df = pd.read_excel(io.BytesIO(contenu))
        else:
            df = pd.read_csv(io.BytesIO(contenu), sep=None, engine="python")
    except Exception as e:
        return vide, f"lecture impossible ({e})"
    cols = list(df.columns)
    c_ot = _colonne(cols, [lambda c: c == "ordre", lambda c: c in ("ot", "n° ot", "n°ot", "numéro ot"),
                           lambda c: "ordre" in c and "type" not in c])
    c_doc = _colonne(cols, [lambda c: "fichier" in c and "orig" in c, lambda c: "fichier" in c,
                            lambda c: "document" in c or "pièce" in c or "piece" in c])
    c_poste = _colonne(cols, [lambda c: "poste" in c and "trav" in c and "division" not in c])
    if c_ot is None:
        return vide, f"colonne des numéros d'OT introuvable (colonnes : {', '.join(map(str, cols))})"
    d = df.copy()
    if c_doc is not None:
        val = d[c_doc]
        num = pd.to_numeric(val, errors="coerce")
        # nombre ≠ 0 → document joint (compte pour 1) ; texte non vide → document joint
        a_doc = num.fillna(0).ne(0) | (num.isna() & val.notna() & val.astype(str).str.strip().ne(""))
        d = d[a_doc]
    out = pd.DataFrame({"ot": d[c_ot].map(_norm_num),
                        "poste": d[c_poste].map(_code_poste) if c_poste is not None else None})
    out = out.dropna(subset=["ot"]).drop_duplicates("ot")
    return out, None


@st.cache_data(ttl=900, show_spinner=False)
def _charger(url, chemin, mtime):
    if url:
        from core.onedrive_loader import fetch_bytes
        contenu, err = fetch_bytes(url)
        if contenu is None:
            return set(), f"OneDrive : {err}", "OneDrive"
        tab, err = lire_documents(contenu)
        return tab, err, "OneDrive"
    with open(chemin, "rb") as f:
        tab, err = lire_documents(f.read())
    return tab, err, os.path.basename(chemin)


def charger_table_documents():
    """(DataFrame [ot, poste], source, erreur) ; source None si aucun fichier trouvé."""
    url = None
    try:
        url = st.secrets.get("DOCS_JOINTS_URL")
    except Exception:
        pass
    if url:
        tab, err, src = _charger(url, None, 0)
        return tab, src, err
    for nom in NOMS_FICHIERS:
        if os.path.exists(nom):
            tab, err, src = _charger(None, nom, os.path.getmtime(nom))
            if not err or nom != "documents_joints.xlsx":
                return tab, src, err
    return pd.DataFrame(columns=["ot", "poste"]), None, None


def charger_ot_avec_document():
    """(ensemble d'OT avec document joint, source, erreur)."""
    tab, src, err = charger_table_documents()
    return set(tab["ot"]), src, err


def total_par_poste(postes=None):
    """Nombre d'OT avec document joint par poste de travail (tous types d'OT)."""
    tab, src, err = charger_table_documents()
    if src is None or err or tab.empty:
        return None, src, err
    t = tab.groupby("poste").size().rename("Nombre documents joints")
    if postes:
        t = t.reindex([str(p) for p in postes], fill_value=0)
    t = t.sort_index().reset_index().rename(columns={"poste": "Poste de travail", "index": "Poste de travail"})
    t["Nombre documents joints"] = t["Nombre documents joints"].astype(int)
    return t, src, None


def marquer(df, ots_avec_doc):
    """Ajoute la colonne « Document joint » (Oui / Non) à un DataFrame d'OT."""
    d = df.copy()
    num = d["Ordre"].map(_norm_num) if "Ordre" in d.columns else pd.Series(None, index=d.index)
    d["Document joint"] = num.isin(ots_avec_doc).map({True: "Oui", False: "Non"})
    return d


def synthese_par_poste(df_marque, col_poste="Poste travail princ."):
    """Tableau par poste : Total OT, Avec document, Sans document, % documentés."""
    if df_marque.empty or col_poste not in df_marque.columns:
        return pd.DataFrame(columns=["Poste de travail", "Total OT", "Avec document", "Sans document", "% avec document"])
    g = df_marque.groupby(col_poste)["Document joint"]
    t = pd.DataFrame({"Total OT": g.size(), "Avec document": g.apply(lambda s: int((s == "Oui").sum()))})
    t = t[t["Total OT"] > 0]
    t["Sans document"] = t["Total OT"] - t["Avec document"]
    t["% avec document"] = (t["Avec document"] / t["Total OT"] * 100).round(1)
    t = t.sort_values(["Total OT", "Avec document"], ascending=False).reset_index().rename(columns={col_poste: "Poste de travail"})
    tot = {"Poste de travail": "TOTAL", "Total OT": int(t["Total OT"].sum()),
           "Avec document": int(t["Avec document"].sum())}
    tot["Sans document"] = tot["Total OT"] - tot["Avec document"]
    tot["% avec document"] = round(tot["Avec document"] / tot["Total OT"] * 100, 1) if tot["Total OT"] else 0.0
    return pd.concat([t, pd.DataFrame([tot])], ignore_index=True)
