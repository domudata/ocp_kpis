# -*- coding: utf-8 -*-
import io
import os
import numpy as np
import pandas as pd
import streamlit as st

from core.constants import MP_KW, MPLAN_KW

# Mots cles caracterisation (d apres PDF OCP)
CRPR_KW  = ['ATPD','ATMR','ATRS','ATMO','ATER']  # Prep caracterisee
ATPL_KW  = ['ATEI','ATAL','ATAS','AGAR','ATHS']  # Plan caracterisee
TW_PREV  = [350, 290, 300, 310, 360]              # TW preventifs


def get_date_from_file() -> str:
    if os.path.exists("date.txt"):
        try:
            with open("date.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return pd.Timestamp.today().strftime("%d/%m/%Y")


def contient_mot(t, lm) -> bool:
    t = str(t)
    return any(m in t for l in lm for m in l.split())


def cat_age_jours(days) -> str:
    """Age en jours -> tranche"""
    if pd.isna(days): return "Inconnu"
    if days < 30:     return "<1 mois"
    elif days > 90:   return ">3 mois"
    return "1 mois < <3 mois"


def excr(df: pd.DataFrame) -> pd.DataFrame:
    if "Poste travail princ." in df.columns:
        return df[
            ~df["Poste travail princ."].astype(str).str.contains(
                "cresseur", case=False, na=False)
        ].copy()
    return df


@st.cache_data(show_spinner=False)
def read_excel_safe(bytes_data: bytes) -> pd.DataFrame:
    bio = io.BytesIO(bytes_data)
    header = bytes_data[:8]
    if header[:4] in (b'PK\x03\x04', b'PK\x05\x06'):
        for engine in ['openpyxl', 'calamine']:
            try:    return pd.read_excel(bio, engine=engine)
            except: bio.seek(0)
    if header == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        for engine in ['xlrd', 'calamine']:
            try:    return pd.read_excel(bio, engine=engine)
            except: bio.seek(0)
    for engine in ['openpyxl', 'xlrd', 'calamine']:
        try:
            bio.seek(0)
            return pd.read_excel(bio, engine=engine)
        except: continue
    raise ValueError("Format de fichier non reconnu.")


@st.cache_data(show_spinner=False)
def prepare_data(ot_bytes: bytes, av_bytes: bytes, date_str: str):
    raw_ot = read_excel_safe(ot_bytes)
    raw_av = read_excel_safe(av_bytes)
    raw_ot = excr(raw_ot)
    raw_av = excr(raw_av)

    # Dates OT
    for c in ["Créé le","Date de début planifiée","Date de clôture","Début réel","Fin réelle"]:
        if c in raw_ot.columns:
            raw_ot[c] = pd.to_datetime(raw_ot[c], errors="coerce")
    # Dates Avis
    for c in ["Créé le","Début souhaité","Date de la clôture"]:
        if c in raw_av.columns:
            raw_av[c] = pd.to_datetime(raw_av[c], errors="coerce")

    now_ts = pd.Timestamp.today()
    df = raw_ot.copy()

    # ── OT correctif = Plan d entretien == 0 ────────────────────────────
    df["is_correctif"] = df["Plan d'entretien"].fillna(0) == 0

    # ── Statut OT (1er mot du statut systeme) ───────────────────────────
    if "Statut système" in df.columns:
        df["Statut OT"] = (
            df["Statut système"].fillna("").astype(str).str.strip().str.split().str[0]
        )

    # ── SOPL ─────────────────────────────────────────────────────────────
    df["Contient SOPL"] = (
        df["Statut utilisateur"].str.contains("SOPL", na=False).map({True:1, False:0})
    )

    # ── Type de travail numerique ────────────────────────────────────────
    df["_tw_num"] = pd.to_numeric(
        df.get("Type de travail", pd.Series(dtype=float)), errors="coerce"
    )

    # ── Age PREP : date de creation (en jours) ──────────────────────────
    if "Créé le" in df.columns:
        df["days_prep"] = (now_ts - df["Créé le"]).dt.days
        df["ap"] = df["days_prep"].apply(cat_age_jours)
    else:
        df["days_prep"] = np.nan
        df["ap"] = "Inconnu"

    # ── Age PLAN et EXEC : date planifiee (en jours) ─────────────────────
    if "Date de début planifiée" in df.columns:
        df["days_planif"] = (now_ts - df["Date de début planifiée"]).dt.days
        df["alp"] = df["days_planif"].apply(cat_age_jours)
        df["aex"] = df["days_planif"].apply(cat_age_jours)
    else:
        df["days_planif"] = np.nan
        df["alp"] = "Inconnu"
        df["aex"] = "Inconnu"

    # ── OT CONFIME ───────────────────────────────────────────────────────
    df["OT CONFIME"] = np.where(
        df["Statut système"].str.contains("CLOT|TCLO", na=False) &
        df["Statut système"].str.contains("CONF", na=False),
        "OUI", "NON"
    )

    # ── OT LANC ESTIME : charge estimee > 0 ─────────────────────────────
    df["OT LANC ESTIME"] = np.where(
        df["Total coûts budgétés"].fillna(0) > 0, "OUI", "NON"
    )

    # ── OT_COR_EGAL ──────────────────────────────────────────────────────
    # EGAL = budget == reel  → anomalie (KPI baisse)
    # DIFF = budget != reel  → conforme (KPI monte)
    df["OT_COR_EGAL"] = np.where(
        df["Total coûts budgétés"].fillna(0) == df["Total coûts réels"].fillna(0),
        "EGAL", "DIFF"
    )

    # ── Backlog preparation (pour graphiques) ───────────────────────────
    pat_prep = '|'.join(CRPR_KW)
    df["Backlog preparation"] = np.where(
        df["Statut utilisateur"].str.contains(pat_prep, na=False),
        "CARACTERISE", "NON CARACTERISE"
    )
    df["Type Carac Prep"] = df["Statut utilisateur"].apply(
        lambda x: next((kw for kw in CRPR_KW if kw in str(x)), "NON CARACTERISE")
    )

    # ── Backlog planification (pour graphiques) ──────────────────────────
    pat_plan = '|'.join(ATPL_KW)
    df["Backlog planification"] = np.where(
        df["Statut utilisateur"].str.contains(pat_plan, na=False),
        "CARACTERISE", "NON CARACTERISE"
    )
    df["Type Carac Plan"] = df["Statut utilisateur"].apply(
        lambda x: next((kw for kw in ATPL_KW if kw in str(x)), "NON CARACTERISE")
    )

    # ── Avis : hors types ZU/Z4/ZR/ZP (d apres PDF page 11) ─────────────
    avf = raw_av[
        ~raw_av["Type d'avis"].isin(["ZU","Z4","ZR","ZP"])
    ].copy()

    # ── Postes de travail SF1/SF2 ────────────────────────────────────────
    apm = sorted(
        df[
            df["Poste travail princ."].astype(str).str.startswith(("SF1","SF2"), na=False)
        ]["Poste travail princ."].dropna().unique().tolist()
    )

    return df, avf, apm, now_ts
