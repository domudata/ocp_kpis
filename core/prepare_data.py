# -*- coding: utf-8 -*-
import io
import os
import numpy as np
import pandas as pd
import streamlit as st

from core.constants import MP_KW, MPLAN_KW

# ──────────────────────────────────────────────
# Utilitaires basiques
# ──────────────────────────────────────────────

def get_date_from_file() -> str:
    if os.path.exists("date.txt"):
        try:
            with open("date.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return pd.Timestamp.today().strftime("%d/%m/%Y")

def contient_mot(t, lm) -> bool:
    """CORRIGÉ (bug majeur) : l'ancienne version vérifiait TOUS les mots de
    chaque entrée de lm, y compris le préfixe générique "CRPR"/"ATPL" des
    entrées composées ("CRPR ATPD".split() -> ["CRPR","ATPD"]). Résultat :
    un Statut utilisateur = "CRPR" SEUL (sans aucun code de
    caractérisation) déclenchait quand même CARACTERISE, simplement parce
    que "CRPR" matchait le premier mot d'une entrée composée. Sur données
    réelles : 176 OT avec CRPR, dont seulement 59 (33,5%) ont un vrai code
    (ATPD/ATMR/ATER/ATRS/ATMO) -> les 117 autres ("CRPR" seul) étaient
    quand même comptés CARACTERISE à tort (100% au lieu de ~34%).
    Fix : ne vérifier que le CODE SPÉCIFIQUE (dernier mot de chaque
    entrée), jamais le préfixe générique seul."""
    t = str(t).upper()
    return any(l.split()[-1].upper() in t for l in lm)

def cat_age(a) -> str:
    """Catégorise l'âge d'un OT selon la règle officielle SAP PM (en JOURS,
    cf. classeur "Définition KPIs SAP PM") :
      - < 30 jours              -> "<1 mois"
      - > 30j et < 90j          -> "1 mois < <3 mois"
      - > 90j                   -> ">3 mois"

    ATTENTION : `a` doit être un nombre de JOURS (pas de mois calendaires).
    L'ancienne version comparait une différence de mois calendaires
    ((année_now-année_date)*12 + (mois_now-mois_date)), ce qui provoque des
    erreurs de classement autour des changements de mois (ex : un OT créé
    la veille, le dernier jour du mois précédent, était compté comme
    "1 mois < <3 mois" au lieu de "<1 mois"). Corrigé : calcul en jours.
    """
    if pd.isna(a):
        return "Inconnu"
    if a < 30:
        return "<1 mois"
    if a > 90:
        return ">3 mois"
    return "1 mois < <3 mois"

def excr(df: pd.DataFrame) -> pd.DataFrame:
    if "Poste travail princ." in df.columns:
        return df[
            ~df["Poste travail princ."].astype(str).str.contains(
                "cresseur", case=False, na=False
            )
        ].copy()
    return df

# ──────────────────────────────────────────────
# Lecture Excel robuste
# ──────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def read_excel_safe(bytes_data: bytes) -> pd.DataFrame:
    """Lit un fichier Excel en détectant automatiquement le vrai format."""
    bio = io.BytesIO(bytes_data)
    header = bytes_data[:8]

    if header[:4] in (b'PK\x03\x04', b'PK\x05\x06'):
        for engine in ['openpyxl', 'calamine']:
            try:
                return pd.read_excel(bio, engine=engine)
            except Exception:
                bio.seek(0)
                continue

    if header == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        for engine in ['xlrd', 'calamine']:
            try:
                return pd.read_excel(bio, engine=engine)
            except Exception:
                bio.seek(0)
                continue

    for engine in ['openpyxl', 'xlrd', 'calamine']:
        try:
            bio.seek(0)
            return pd.read_excel(bio, engine=engine)
        except Exception:
            continue

    raise ValueError(
        "Format de fichier non reconnu. Le fichier n'est ni un .xlsx ni un .xls valide.\n"
        "Vérifiez que le fichier n'est pas corrompu ou protégé par mot de passe."
    )

# ──────────────────────────────────────────────
# Préparation des données
# ──────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def prepare_data(ot_bytes: bytes, av_bytes: bytes, date_str: str):
    raw_ot = read_excel_safe(ot_bytes)
    raw_av = read_excel_safe(av_bytes)
    raw_ot = excr(raw_ot)
    raw_av = excr(raw_av)

    for c in ["Créé le", "Date de début planifiée", "Date de clôture", "Début réel", "Fin réelle"]:
        if c in raw_ot.columns:
            raw_ot[c] = pd.to_datetime(raw_ot[c], errors="coerce")
    for c in ["Créé le", "Début souhaité", "Date de la clôture"]:
        if c in raw_av.columns:
            raw_av[c] = pd.to_datetime(raw_av[c], errors="coerce")

    now_ts = pd.Timestamp.today()
    df = raw_ot.copy()

    df["Backlog preparation"] = np.where(
        df["Statut utilisateur"].apply(lambda x: contient_mot(x, MP_KW)),
        "CARACTERISE", "NON CARACTERISE"
    )
    df["Backlog planification"] = np.where(
        df["Statut utilisateur"].apply(lambda x: contient_mot(x, MPLAN_KW)),
        "CARACTERISE", "NON CARACTERISE"
    )
    # CORRIGÉ : kw.split()[0] renvoyait le préfixe générique ("CRPR" ou
    # "ATPL") pour les entrées composées de MP_KW/MPLAN_KW (ex: "CRPR ATPD"
    # -> "CRPR"), pas le code de caractérisation utile. Le code specifique
    # (ATPD/ATMR/ATER/ATRS/ATMO ou ATEI/ATAL/ATAS/AGAR/ATHS) est le DERNIER
    # mot de l'entrée. kw.split()[-1] fonctionne aussi bien pour les
    # entrées composées ("CRPR ATPD" -> "ATPD") que pour les entrées à un
    # seul mot ("ATPD" -> "ATPD"), sans risque d'IndexError.
    # CORRIGÉ (TypeError) : l'étape intermédiaire "_su_upper = ...astype(str)
    # .str.upper()" plantait car avec le dtype Arrow/string de pandas
    # récent, une valeur vide (NaN) reste un objet NA (pas une vraie chaîne
    # Python) même après .astype(str) -> "kw.upper() in x" levait un
    # TypeError sur ces valeurs. Fix : str(x).upper() directement dans le
    # lambda (comme contient_mot() ci-dessus), qui convertit TOUJOURS en
    # chaîne Python native quel que soit le type d'entrée (NaN, NA, etc.).
    df["Type Carac Prep"] = df["Statut utilisateur"].apply(
        lambda x: next((kw.split()[-1] for kw in MP_KW if kw.upper() in str(x).upper()), "NON CARACTERISE")
    )
    df["Type Carac Plan"] = df["Statut utilisateur"].apply(
        lambda x: next((kw.split()[-1] for kw in MPLAN_KW if kw.upper() in str(x).upper()), "NON CARACTERISE")
    )

    # ── Âge des OT (Préparation / Planification / Exécution) ──
    # Règle officielle (classeur "Définition KPIs SAP PM") :
    #   Préparation   : référence = "Créé le"                → < 30j / 30-90j / > 90j
    #   Planification : référence = "Date de début planifiée" → < 30j / 30-90j / > 90j
    #   Exécution     : référence = "Date de début planifiée" → < 30j / 30-90j / > 90j
    # CORRIGÉ : âge calculé en JOURS (now_ts - date).dt.days, plus en
    # différence de mois calendaires (qui décalait le classement des OT
    # autour des changements de mois).
    for dc, am, ac in [
        ('Créé le', "amp", "ap"),
        ('Date de début planifiée', "amlp", "alp"),
        ('Date de début planifiée', "amex", "aex"),
    ]:
        if dc in df.columns:
            df[am] = (now_ts - df[dc]).dt.days
            df[ac] = df[am].apply(cat_age)
        else:
            df[am] = np.nan
            df[ac] = "Inconnu"

    df["OT CONFIME"] = np.where(
        df["Statut système"].str.contains("CLOT|TCLO", na=False)
        & df["Statut système"].str.contains("CONF", na=False),
        "OUI", "NON"
    )

    df["Contient SOPL"] = (
        df["Statut utilisateur"].str.contains("SOPL", na=False).map({True: 1, False: 0})
    )
    df["OT LANC ESTIME"] = np.where(df["Total coûts budgétés"].fillna(0) == 0, "NON", "OUI")
    df["OT_COR_EGAL"] = np.where(
        (df["Total coûts budgétés"].fillna(0) - df["Total coûts réels"].fillna(0)) == 0,
        "OUI", "NON"
    )
    df["_tw_num"] = pd.to_numeric(
        df.get("Type de travail", pd.Series(dtype=float)), errors="coerce"
    )

    if "Statut système" in df.columns:
        df["Statut OT"] = (
            df["Statut système"].fillna("").astype(str).str.strip().str.split().str[0]
        )

    # CORRIGÉ (formule officielle SAP PM) : "Taux d'approbation des Avis" =
    # avis approuvés (APRV) / TOTAL DES AVIS CRÉÉS — sans aucun filtre sur
    # Ordre ni Type d'avis. L'ancien filtre (Ordre vide + Type d'avis dans
    # une liste restreinte) éliminait ~93% des avis réels (23 114 sur
    # 24 716 pour un périmètre test), ce qui faussait complètement le taux.
    avf = raw_av.copy()

    apm = sorted(
        df[
            df["Poste travail princ."].astype(str).str.startswith(("SF1", "SF2"), na=False)
        ]["Poste travail princ."].dropna().unique().tolist()
    )

    return df, avf, apm, now_ts
