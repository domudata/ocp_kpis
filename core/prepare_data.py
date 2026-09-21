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

@st.cache_data(show_spinner=False, ttl=300)
def _lire_date_github():
    """Lit date.txt directement depuis le dépôt GitHub configuré.

    PROTECTION ANTI-GEL (seul ajout de ce fichier) : si le jeton GitHub
    est invalide/expiré, un appel réseau sans protection peut bloquer
    l'application (tourne indéfiniment, sans message d'erreur visible)
    car Streamlit relance ce code à chaque interaction. Trois garde-fous :
      1. cache 300 s : au plus un appel réseau toutes les 5 minutes ;
      2. drapeau de session : après un premier échec, plus aucune
         tentative n'est faite pendant la session en cours ;
      3. try/except large : aucune exception ne remonte à l'interface.
    """
    if st.session_state.get("_github_date_indisponible"):
        return None, "GitHub désactivé pour cette session (échec précédent)"
    try:
        from core.github_publish import download_file, is_configured
        if not is_configured():
            st.session_state["_github_date_indisponible"] = True
            return None, "GitHub non configuré"
        contenu, err = download_file("date.txt")
        if contenu:
            valeur = contenu.decode("utf-8").strip()
            if valeur:
                return valeur, "GitHub"
        st.session_state["_github_date_indisponible"] = True
        return None, err or "date.txt absent du dépôt"
    except Exception as e:
        st.session_state["_github_date_indisponible"] = True
        return None, f"lecture GitHub impossible : {e}"


def get_date_from_file() -> str:
    """Date de l'extraction courante. Tente d'abord GitHub (protégé par
    _lire_date_github ci-dessus), puis le disque local, puis la date du
    jour — comportement de secours identique à l'original."""
    date_gh, _source = _lire_date_github()
    if date_gh:
        return date_gh
    if os.path.exists("date.txt"):
        try:
            with open("date.txt", "r", encoding="utf-8") as f:
                valeur = f.read().strip()
                if valeur:
                    return valeur
        except Exception:
            pass
    return pd.Timestamp.today().strftime("%d/%m/%Y")


def contient_mot(t, lm) -> bool:
    t = str(t)
    return any(m in t for l in lm for m in l.split())


def cat_age(a) -> str:
    if pd.isna(a):
        return ">3 mois"
    if a <= 1:
        return "<1 mois"
    elif a >= 3:
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

    # CORRIGÉ (bug identifié) : now_ts utilisait pd.Timestamp.today() et
    # ignorait TOTALEMENT date_str, quel que soit son contenu. Corrigé
    # pour utiliser réellement date_str, avec un format jj/mm/aaaa
    # EXPLICITE (dayfirst) — sans cela, pandas peut interpréter une date
    # ambiguë comme "05/09/2026" en mois/jour (5 septembre lu comme
    # "9 mai"), faussant tous les calculs d'âge en aval.
    try:
        now_ts = pd.to_datetime(date_str, format="%d/%m/%Y")
    except Exception:
        try:
            now_ts = pd.to_datetime(date_str, dayfirst=True)
        except Exception:
            now_ts = pd.Timestamp.today()
    # NOTE : pas de copie "df_toutes_dates" ici — inutile. La valeur "df"
    # retournée par cette fonction EST déjà la version complète, sans
    # aucun filtre de date (le filtre de période est appliqué plus tard,
    # dans app.py, uniquement sur la copie destinée aux autres KPI).
    # app.py réutilise directement ce "df" (sous le nom df_full) comme
    # df_toutes_dates lors de l'appel à calc_kpis().
    df = raw_ot.copy()

    df["Backlog preparation"] = np.where(
        df["Statut utilisateur"].apply(lambda x: contient_mot(x, MP_KW)),
        "CARACTERISE", "NON CARACTERISE"
    )
    df["Backlog planification"] = np.where(
        df["Statut utilisateur"].apply(lambda x: contient_mot(x, MPLAN_KW)),
        "CARACTERISE", "NON CARACTERISE"
    )
    df["Type Carac Prep"] = df["Statut utilisateur"].apply(
        lambda x: next((kw.split()[0] for kw in MP_KW if kw in str(x)), "NON CARACTERISE")
    )
    df["Type Carac Plan"] = df["Statut utilisateur"].apply(
        lambda x: next((kw.split()[0] for kw in MPLAN_KW if kw in str(x)), "NON CARACTERISE")
    )

    for dc, am, ac in [
        ('Créé le', "amp", "ap"),
        ('Date de début planifiée', "amlp", "alp"),
        ('Date de début planifiée', "amex", "aex"),
    ]:
        if dc in df.columns:
            df[am] = (
                (now_ts.year - df[dc].dt.year) * 12
                + (now_ts.month - df[dc].dt.month)
            ).round(2)
            df[ac] = df[am].apply(cat_age)
        else:
            df[am] = np.nan
            df[ac] = ">3 mois"

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

    # MODIFIÉ : population Avis restreinte au type ZC uniquement (demande
    # explicite). L'ancienne restriction ZU/Z4/ZR/ZP est remplacée par ZC.
    # Le filtre "Ordre vide" est conservé (avis non rattachés à un OT).
    # build_avis_zc_population() dans calcul_kpi.py applique la même règle
    # en double sécurité, garantissant la cohérence KPI / anomalies.
    avf = raw_av[
        (raw_av["Ordre"].isna() | (raw_av["Ordre"].astype(str).str.strip() == ""))
        & raw_av["Type d'avis"].astype(str).str.strip().str.upper().eq("ZC")
    ].copy()

    apm = sorted(
        df[
            df["Poste travail princ."].astype(str).str.startswith(("SF1", "SF2"), na=False)
        ]["Poste travail princ."].dropna().unique().tolist()
    )

    # AJOUTÉ : avis complet (non restreint aux types ZU/Z4/ZR/ZP), destiné
    # aux usages autres que le Taux d'approbation des Avis — notamment le
    # suivi HSE, qui a besoin des types ZI (Inspection) et ZH (HSE),
    # structurellement absents de "avf" ci-dessus.
    avis_complet = raw_av.copy()

    return df, avf, apm, now_ts, avis_complet
