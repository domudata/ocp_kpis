# -*- coding: utf-8 -*-
import io
import os
import numpy as np
import pandas as pd
import streamlit as st

from core.constants import MP_KW, MPLAN_KW


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


def cat_age(a) -> str:
    if pd.isna(a): return "Inconnu"
    if a <= 1:     return "<1 mois"
    elif a >= 3:   return ">3 mois"
    return "1 mois < <3 mois"


def excr(df: pd.DataFrame) -> pd.DataFrame:
    if "Poste travail princ." in df.columns:
        return df[
            ~df["Poste travail princ."].astype(str).str.contains(
                "cresseur", case=False, na=False
            )
        ].copy()
    return df


@st.cache_data(show_spinner=False)
def read_excel_safe(bytes_data: bytes) -> pd.DataFrame:
    bio = io.BytesIO(bytes_data)
    header = bytes_data[:8]
    if header[:4] in (b'PK\x03\x04', b'PK\x05\x06'):
        for engine in ['openpyxl', 'calamine']:
            try:
                return pd.read_excel(bio, engine=engine)
            except Exception:
                bio.seek(0)
    if header == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        for engine in ['xlrd', 'calamine']:
            try:
                return pd.read_excel(bio, engine=engine)
            except Exception:
                bio.seek(0)
    for engine in ['openpyxl', 'xlrd', 'calamine']:
        try:
            bio.seek(0)
            return pd.read_excel(bio, engine=engine)
        except Exception:
            continue
    raise ValueError("Format de fichier non reconnu.")


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
    df["Type Carac Prep"] = df["Statut utilisateur"].apply(
        lambda x: next((kw.split()[0] for kw in MP_KW if kw in str(x)), "NON CARACTERISE")
    )
    df["Type Carac Plan"] = df["Statut utilisateur"].apply(
        lambda x: next((kw.split()[0] for kw in MPLAN_KW if kw in str(x)), "NON CARACTERISE")
    )

    # Age PREP : date création (pas date planif)
    if "Créé le" in df.columns:
        df["amp"] = ((now_ts.year - df["Créé le"].dt.year) * 12
                     + (now_ts.month - df["Créé le"].dt.month)).round(2)
        df["ap"] = df["amp"].apply(cat_age)
    else:
        df["amp"] = np.nan; df["ap"] = "Inconnu"

    # Age PLAN et EXEC : date planif
    for am, ac in [("amlp", "alp"), ("amex", "aex")]:
        if "Date de début planifiée" in df.columns:
            df[am] = ((now_ts.year - df["Date de début planifiée"].dt.year) * 12
                      + (now_ts.month - df["Date de début planifiée"].dt.month)).round(2)
            df[ac] = df[am].apply(cat_age)
        else:
            df[am] = np.nan; df[ac] = "Inconnu"

    df["OT CONFIME"] = np.where(
        df["Statut système"].str.contains("CLOT|TCLO", na=False) &
        df["Statut système"].str.contains("CONF", na=False),
        "OUI", "NON"
    )

    df["Contient SOPL"] = (
        df["Statut utilisateur"].str.contains("SOPL", na=False).map({True: 1, False: 0})
    )

    # OT LANC ESTIME : charge estimée > 0
    df["OT LANC ESTIME"] = np.where(
        df["Total coûts budgétés"].fillna(0) > 0, "OUI", "NON"
    )

    # OT_COR_EGAL : budget == réel (anomalie = égaux, KPI = différents)
    # Approche logique en attendant validation SAP
    df["OT_COR_EGAL"] = np.where(
        df["Total coûts budgétés"].fillna(0) == df["Total coûts réels"].fillna(0),
        "EGAL", "DIFF"
    )

    df["_tw_num"] = pd.to_numeric(
        df.get("Type de travail", pd.Series(dtype=float)), errors="coerce"
    )

    if "Statut système" in df.columns:
        df["Statut OT"] = (
            df["Statut système"].fillna("").astype(str).str.strip().str.split().str[0]
        )

    # Avis : hors types ZU, Z4, ZR, ZP (d'après PDF page 11)
    avf = raw_av[
        ~raw_av["Type d'avis"].isin(["ZU", "Z4", "ZR", "ZP"])
    ].copy()

    apm = sorted(
        df[
            df["Poste travail princ."].astype(str).str.startswith(("SF1", "SF2"), na=False)
        ]["Poste travail princ."].dropna().unique().tolist()
    )

    return df, avf, apm, now_ts
