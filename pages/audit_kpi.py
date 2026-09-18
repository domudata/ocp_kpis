# -*- coding: utf-8 -*-
"""
Module central de contrôle OUI / NON des KPIs SAP OCP.
SOURCE UNIQUE DE VÉRITÉ :
Pour chaque KPI, ce module évalue chaque OT / Avis éligible et détermine :
  - OUI : respecte toutes les conditions du KPI
  - NON : ne respecte pas au moins une condition
  - Motif_NON : explication détaillée du rejet
  - Les colonnes SAP d'origine ayant servi au calcul.
"""

import io
import re
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from core.constants import (
    QK, PK, ALL_KPI, CIBLE, LOWER_BETTER,
    CODES_PREP_EXACT, CODES_PLAN_EXACT, ALL_CARAC_EXACT,
)


def match_exact_token(statut, codes: set) -> bool:
    if statut is None or (isinstance(statut, float) and pd.isna(statut)):
        return False
    words = set(re.findall(r'[A-Za-z0-9]+', str(statut).upper()))
    return bool(words & codes)


def get_division(poste: str) -> str:
    p = str(poste).strip().upper()
    if p.startswith("SF1"):
        return "SF1"
    elif p.startswith("SF2"):
        return "SF2"
    return "AUTRE"


# ─────────────────────────────────────────────────────────────────────────────
# 1. ÉVALUATION DÉDIÉE : Préparation_Taux d'estimation du travail (OT lancés)
# ─────────────────────────────────────────────────────────────────────────────

def eval_ot_lanc_estime(df: pd.DataFrame) -> pd.DataFrame:
    """
    KPI : Préparation_Taux d'estimation du travail (OT lancés) / OT LANC ESTIME.
    Dénominateur : OT correctifs lancés
      - Type d'ordre == 'ZCOR'
      - Statut système contient 'LANC' ou Statut OT == 'LANC'
    Numérateur / OUI :
      - Charge estimée > 0 (Total coûts budgétés > 0)
    Condition NON :
      - Total coûts budgétés == 0 ou manquant (non estimé)
    Motif_NON :
      - 'Charge estimée non renseignée (Total coûts budgétés = 0 DH)'
    """
    if df.empty:
        return pd.DataFrame()

    statut_sys = df.get("Statut système", pd.Series("", index=df.index)).fillna("").astype(str)
    statut_ot = df.get("Statut OT", pd.Series("", index=df.index)).fillna("").astype(str)
    type_ordre = df.get("Type d'ordre", pd.Series("", index=df.index)).fillna("").astype(str).str.strip().str.upper()

    is_zcor = type_ordre == "ZCOR"
    is_lanc = statut_sys.str.contains("LANC", na=False) | (statut_ot == "LANC")
    scope = df[is_zcor & is_lanc].copy()

    if scope.empty:
        return pd.DataFrame()

    budget = pd.to_numeric(scope.get("Total coûts budgétés", 0), errors="coerce").fillna(0)
    is_estime = budget > 0

    scope["KPI"] = "OT LANC ESTIME"
    scope["Nom_KPI_Complet"] = "Préparation_Taux d'estimation du travail (OT lancés)"
    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    scope["Condition_ZCOR"] = "OUI"
    scope["Condition_LANC"] = "OUI"
    scope["Charge_estimee"] = budget
    scope["Condition_Charge_Estimee"] = np.where(is_estime, "OUI", "NON")
    scope["Résultat"] = np.where(is_estime, "OUI", "NON")
    scope["Motif_NON"] = np.where(
        is_estime,
        "",
        "Charge estimée non renseignée (Total coûts budgétés = 0 DH)"
    )
    return scope


# ─────────────────────────────────────────────────────────────────────────────
# 2. ÉVALUATION DÉDIÉE : Taux de Réalisation Correctif
# ─────────────────────────────────────────────────────────────────────────────

def eval_taux_realisation_correctif(df: pd.DataFrame) -> pd.DataFrame:
    """
    KPI : TAUX_REALISATION_CORRECTIF/PT
    Dénominateur : OT où Nº appel pl.entret. == 0 (ou vide) ET Statut utilisateur contient SOPL
    Numérateur / OUI : Statut OT in ['CLOT', 'TCLO'] (ou Statut système contient CLOT/TCLO)
    NON : OT correctif non clôturé
    """
    if df.empty:
        return pd.DataFrame()

    appel = pd.to_numeric(df.get("Nº appel pl.entret.", 0), errors="coerce").fillna(0)
    sopl = df.get("Contient SOPL", pd.Series(0, index=df.index))
    if "Contient SOPL" not in df.columns:
        sopl = df.get("Statut utilisateur", pd.Series("", index=df.index)).fillna("").astype(str).str.contains("SOPL", na=False).astype(int)

    filt_corr = (appel == 0) & (sopl == 1)
    scope = df[filt_corr].copy()
    if scope.empty:
        return pd.DataFrame()

    statut_ot = scope.get("Statut OT", pd.Series("", index=scope.index)).fillna("").astype(str)
    statut_sys = scope.get("Statut système", pd.Series("", index=scope.index)).fillna("").astype(str)
    is_clot = statut_ot.isin(["CLOT", "TCLO"]) | statut_sys.str.contains("CLOT|TCLO", na=False)

    scope["KPI"] = "TAUX_REALISATION_CORRECTIF/PT"
    scope["Nom_KPI_Complet"] = "Taux de réalisation correctif / PT"
    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    scope["Résultat"] = np.where(is_clot, "OUI", "NON")
    scope["Motif_NON"] = np.where(
        is_clot,
        "",
        scope["Statut OT"].apply(lambda s: f"OT correctif non clôturé (Statut: {s})")
    )
    return scope


# ─────────────────────────────────────────────────────────────────────────────
# 3. ÉVALUATION DÉDIÉE : Backlogs Préparation & Planification Caractérisés
# ─────────────────────────────────────────────────────────────────────────────

def eval_backlog_prep_caracterise(df_all: pd.DataFrame) -> pd.DataFrame:
    """
    KPI : Backlog préparation caractérisé
    Dénominateur : Type d'ordre == 'ZCOR' ET Statut système commence par 'CRÉÉ' / 'CREE'
    Numérateur / OUI : Statut utilisateur contient un token exact parmi ATPD, ATMR, ATER, ATRS, ATMO
    NON : Aucun code de caractérisation préparation
    """
    if df_all.empty:
        return pd.DataFrame()

    type_ordre = df_all.get("Type d'ordre", pd.Series("", index=df_all.index)).fillna("").astype(str).str.strip().str.upper()
    statut_sys = df_all.get("Statut système", pd.Series("", index=df_all.index)).fillna("").astype(str).str.strip().str.split().str[0]
    scope = df_all[(type_ordre == "ZCOR") & statut_sys.isin(["CRÉÉ", "CREE"])].copy()

    if scope.empty:
        return pd.DataFrame()

    statut_usr = scope.get("Statut utilisateur", pd.Series("", index=scope.index))
    is_carac = statut_usr.apply(lambda x: match_exact_token(x, CODES_PREP_EXACT))

    scope["KPI"] = "Backlog préparation caractérisé"
    scope["Nom_KPI_Complet"] = "Backlog préparation caractérisé"
    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    scope["Résultat"] = np.where(is_carac, "OUI", "NON")
    scope["Motif_NON"] = np.where(
        is_carac,
        "",
        scope.get("Statut utilisateur", "").fillna("").apply(
            lambda s: f"Backlog préparation non caractérisé (Statut: {s if s else 'VIDE'})"
        )
    )
    return scope


def eval_backlog_plan_caracterise(df_all: pd.DataFrame) -> pd.DataFrame:
    """
    KPI : Backlog planification caractérisé
    Dénominateur : Type d'ordre == 'ZCOR' ET Statut système commence par 'LANC' ET Contient SOPL == 0
    Numérateur / OUI : Statut utilisateur contient un token exact parmi ATEI, ATAL, ATAS, AGAR, ATHS
    NON : Aucun code de caractérisation planification
    """
    if df_all.empty:
        return pd.DataFrame()

    type_ordre = df_all.get("Type d'ordre", pd.Series("", index=df_all.index)).fillna("").astype(str).str.strip().str.upper()
    statut_sys = df_all.get("Statut système", pd.Series("", index=df_all.index)).fillna("").astype(str).str.strip().str.split().str[0]
    sopl = df_all.get("Contient SOPL", pd.Series(0, index=df_all.index))

    scope = df_all[(type_ordre == "ZCOR") & (statut_sys == "LANC") & (sopl == 0)].copy()
    if scope.empty:
        return pd.DataFrame()

    statut_usr = scope.get("Statut utilisateur", pd.Series("", index=scope.index))
    is_carac = statut_usr.apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT))

    scope["KPI"] = "Backlog planification caractérisé"
    scope["Nom_KPI_Complet"] = "Backlog planification caractérisé"
    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    scope["Résultat"] = np.where(is_carac, "OUI", "NON")
    scope["Motif_NON"] = np.where(
        is_carac,
        "",
        scope.get("Statut utilisateur", "").fillna("").apply(
            lambda s: f"Backlog planification non caractérisé (Statut: {s if s else 'VIDE'})"
        )
    )
    return scope


# ─────────────────────────────────────────────────────────────────────────────
# 4. ÉVALUATION DÉDIÉE : OT CONFIME et OT_COR_EGAL
# ─────────────────────────────────────────────────────────────────────────────

def eval_ot_confime(df: pd.DataFrame) -> pd.DataFrame:
    """
    KPI : OT CONFIME
    Dénominateur : Statut OT in ['CLOT', 'TCLO']
    Numérateur / OUI : Statut système contient 'CONF'
    NON : Heures réelles non confirmées
    """
    if df.empty:
        return pd.DataFrame()

    statut_ot = df.get("Statut OT", pd.Series("", index=df.index)).fillna("").astype(str)
    statut_sys = df.get("Statut système", pd.Series("", index=df.index)).fillna("").astype(str)
    scope = df[statut_ot.isin(["CLOT", "TCLO"]) | statut_sys.str.contains("CLOT|TCLO", na=False)].copy()

    if scope.empty:
        return pd.DataFrame()

    is_conf = scope["Statut système"].fillna("").astype(str).str.contains("CONF", na=False)
    scope["KPI"] = "OT CONFIME"
    scope["Nom_KPI_Complet"] = "OT Confirmé (Heures réelles)"
    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    scope["Résultat"] = np.where(is_conf, "OUI", "NON")
    scope["Motif_NON"] = np.where(
        is_conf,
        "",
        "Heures réelles non confirmées (statut CONF manquant dans Statut système)"
    )
    return scope


def eval_ot_cor_egal(df: pd.DataFrame) -> pd.DataFrame:
    """
    KPI : OT_COR_EGAL
    Dénominateur : Type d'ordre == 'ZCOR' ET Statut OT in ['CLOT', 'TCLO']
    Numérateur / OUI : Total coûts réels != 0 ET Total coûts réels != Total coûts budgétés
    NON : Coûts réels = 0 OU Coûts réels = Coûts budgétés
    """
    if df.empty:
        return pd.DataFrame()

    statut_ot = df.get("Statut OT", pd.Series("", index=df.index)).fillna("").astype(str)
    statut_sys = df.get("Statut système", pd.Series("", index=df.index)).fillna("").astype(str)
    type_ordre = df.get("Type d'ordre", pd.Series("", index=df.index)).fillna("").astype(str).str.strip().str.upper()

    is_clot = statut_ot.isin(["CLOT", "TCLO"]) | statut_sys.str.contains("CLOT|TCLO", na=False)
    scope = df[is_clot & (type_ordre == "ZCOR")].copy()

    if scope.empty:
        return pd.DataFrame()

    b = pd.to_numeric(scope.get("Total coûts budgétés", 0), errors="coerce").fillna(0)
    r = pd.to_numeric(scope.get("Total coûts réels", 0), errors="coerce").fillna(0)
    is_ok = (b != r) & (r != 0)

    scope["KPI"] = "OT_COR_EGAL"
    scope["Nom_KPI_Complet"] = "Cohérence Coûts Réels / Budgétés (OT_COR_EGAL)"
    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    scope["Résultat"] = np.where(is_ok, "OUI", "NON")

    motifs = []
    for bi, ri in zip(b, r):
        if ri == 0:
            motifs.append("Coûts réels non saisis (= 0 DH)")
        elif bi == ri:
            motifs.append(f"Coûts réels identiques au budget (= {ri:,.0f} DH, non ajustés)")
        else:
            motifs.append("")
    scope["Motif_NON"] = motifs
    return scope


# ─────────────────────────────────────────────────────────────────────────────
# 5. ÉVALUATION DÉDIÉE : Taux d'Approbation des Avis
# ─────────────────────────────────────────────────────────────────────────────

def eval_taux_approbation_avis(avf: pd.DataFrame) -> pd.DataFrame:
    """
    KPI : Taux d'approbation des Avis
    Dénominateur : Avis sans ordre, type ZU, Z4, ZR, ZP, non ACLO
    Numérateur / OUI : Statut utilisateur in ['APRV', 'APRV AVAU']
    NON : En attente d'approbation
    """
    if avf.empty:
        return pd.DataFrame()

    scope = avf.copy()
    _non_aclo = pd.Series(True, index=scope.index)
    if "Statut système" in scope.columns:
        _non_aclo = _non_aclo & ~scope["Statut système"].fillna("").astype(str).str.contains("ACLO", case=False, na=False)
    if "Statut utilisateur" in scope.columns:
        _non_aclo = _non_aclo & ~scope["Statut utilisateur"].fillna("").astype(str).str.contains("ACLO", case=False, na=False)
    scope = scope[_non_aclo].copy()

    if scope.empty:
        return pd.DataFrame()

    statut_usr = scope.get("Statut utilisateur", pd.Series("", index=scope.index)).fillna("").astype(str).str.strip()
    is_aprv = statut_usr.isin(["APRV", "APRV AVAU"])

    scope["KPI"] = "Taux d'approbation des Avis"
    scope["Nom_KPI_Complet"] = "Taux d'approbation des Avis"
    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    scope["Résultat"] = np.where(is_aprv, "OUI", "NON")
    scope["Motif_NON"] = np.where(
        is_aprv,
        "",
        scope["Statut utilisateur"].apply(lambda s: f"Avis en attente d'approbation (Statut: {s if s else 'NON RENSEIGNÉ'})")
    )
    return scope


# ─────────────────────────────────────────────────────────────────────────────
# 6. ÉVALUATION DÉDIÉE : KPI Préventif (Graissage, Inspection, Systématiques)
# ─────────────────────────────────────────────────────────────────────────────

def eval_performance_graissage(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    sopl = df.get("Contient SOPL", pd.Series(0, index=df.index))
    tw = pd.to_numeric(df.get("Type de travail", 0), errors="coerce").fillna(0)
    scope = df[(sopl == 1) & (tw == 350)].copy()
    if scope.empty:
        return pd.DataFrame()

    statut_ot = scope.get("Statut OT", pd.Series("", index=scope.index)).fillna("").astype(str)
    is_clot = statut_ot.isin(["CLOT", "TCLO"])
    scope["KPI"] = "Performance Graissage"
    scope["Nom_KPI_Complet"] = "Performance Graissage"
    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    scope["Résultat"] = np.where(is_clot, "OUI", "NON")
    scope["Motif_NON"] = np.where(is_clot, "", "OT de tournées de graissage non clôturé")
    return scope


def eval_performance_inspection(df: pd.DataFrame, now_ts) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    sopl = df.get("Contient SOPL", pd.Series(0, index=df.index))
    tw = pd.to_numeric(df.get("Type de travail", 0), errors="coerce").fillna(0)
    dt_plan = pd.to_datetime(df.get("Date de début planifiée"), errors="coerce")
    scope = df[(sopl == 1) & (tw.isin([290, 300, 310])) & dt_plan.notna() & (dt_plan <= now_ts)].copy()
    if scope.empty:
        return pd.DataFrame()

    statut_ot = scope.get("Statut OT", pd.Series("", index=scope.index)).fillna("").astype(str)
    is_clot = statut_ot.isin(["CLOT", "TCLO"])
    scope["KPI"] = "Performance Inspection"
    scope["Nom_KPI_Complet"] = "Performance Inspection"
    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    scope["Résultat"] = np.where(is_clot, "OUI", "NON")
    scope["Motif_NON"] = np.where(is_clot, "", "OT d'inspection échu non clôturé")
    return scope


def eval_performance_systematiques(df: pd.DataFrame, now_ts) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    sopl = df.get("Contient SOPL", pd.Series(0, index=df.index))
    tw = pd.to_numeric(df.get("Type de travail", 0), errors="coerce").fillna(0)
    dt_plan = pd.to_datetime(df.get("Date de début planifiée"), errors="coerce")
    scope = df[(sopl == 1) & (tw == 360) & dt_plan.notna() & (dt_plan <= now_ts)].copy()
    if scope.empty:
        return pd.DataFrame()

    statut_ot = scope.get("Statut OT", pd.Series("", index=scope.index)).fillna("").astype(str)
    is_clot = statut_ot.isin(["CLOT", "TCLO"])
    scope["KPI"] = "Performance Systématiques"
    scope["Nom_KPI_Complet"] = "Performance Systématiques"
    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    scope["Résultat"] = np.where(is_clot, "OUI", "NON")
    scope["Motif_NON"] = np.where(is_clot, "", "OT d'intervention systématique échu non clôturé")
    return scope


# ─────────────────────────────────────────────────────────────────────────────
# 7. ÉVALUATION DÉDIÉE : KPIs d'Âge (Préparation, Planification, Exécution)
# ─────────────────────────────────────────────────────────────────────────────

def eval_ages_kpi(df_all: pd.DataFrame, phase: str, now_ts) -> tuple:
    """
    Évalue les 3 tranches d'âge pour une phase donnée ('prep', 'plan', 'exec').
    Retourne (df_inf, df_1_3, df_sup) :
      - df_inf : Tranche < 1 mois (NON = anomalie si non caractérisé dans < 1 mois)
      - df_1_3 : Tranche 1-3 mois (NON = anomalie si non caractérisé dans 1-3 mois)
      - df_sup : Tranche > 3 mois (NON = anomalie si non caractérisé dans > 3 mois)
    """
    if df_all.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    type_ordre = df_all.get("Type d'ordre", pd.Series("", index=df_all.index)).fillna("").astype(str).str.strip().str.upper()

    if phase == "prep":
        statut_sys = df_all.get("Statut système", pd.Series("", index=df_all.index)).fillna("").astype(str).str.strip().str.split().str[0]
        scope = df_all[(type_ordre == "ZCOR") & statut_sys.isin(["CRÉÉ", "CREE"])].copy()
        is_carac = scope.get("Statut utilisateur", pd.Series("", index=scope.index)).apply(lambda x: match_exact_token(x, CODES_PREP_EXACT))
        age_col = "amp"
        cat_col = "ap"
        prefix = "OT préparation"
    elif phase == "plan":
        statut_sys = df_all.get("Statut système", pd.Series("", index=df_all.index)).fillna("").astype(str).str.strip().str.split().str[0]
        sopl = df_all.get("Contient SOPL", pd.Series(0, index=df_all.index))
        scope = df_all[(type_ordre == "ZCOR") & (statut_sys == "LANC") & (sopl == 0)].copy()
        is_carac = scope.get("Statut utilisateur", pd.Series("", index=scope.index)).apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT))
        age_col = "amlp"
        cat_col = "alp"
        prefix = "OT planification"
    elif phase == "exec":
        statut_sys = df_all.get("Statut système", pd.Series("", index=df_all.index)).fillna("").astype(str)
        statut_ot = df_all.get("Statut OT", pd.Series("", index=df_all.index)).fillna("").astype(str)
        statut_usr = df_all.get("Statut utilisateur", pd.Series("", index=df_all.index)).fillna("").astype(str)
        _statut_lanc_ex = (statut_sys.str.strip().str.split().str[0] == "LANC") | (statut_sys.str.contains("LANC", na=False) & ~statut_sys.str.contains("CLOT|TCLO", na=False))
        _non_clot_ex = ~statut_ot.isin(["CLOT", "TCLO"])
        _contient_sopl_ex = (df_all.get("Contient SOPL", pd.Series(0, index=df_all.index)) == 1) | statut_usr.str.contains("SOPL", case=False, na=False)
        scope = df_all[(type_ordre == "ZCOR") & _statut_lanc_ex & _non_clot_ex & _contient_sopl_ex].copy()
        is_carac = scope.get("Statut utilisateur", pd.Series("", index=scope.index)).apply(lambda x: match_exact_token(x, ALL_CARAC_EXACT))
        age_col = "amex"
        cat_col = "aex"
        prefix = "OT exécution"
    else:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    if scope.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    scope["Division"] = scope["Poste travail princ."].apply(get_division)
    ages = pd.to_numeric(scope.get(age_col, 0), errors="coerce").fillna(0)
    cats = scope.get(cat_col, pd.Series("<1 mois", index=scope.index)).fillna("<1 mois")

    # ── KPI <1 mois (Anomalie = non caractérisé dans < 1 mois) ──
    df_inf = scope.copy()
    kpi_inf_name = f"{prefix} <1 mois"
    df_inf["KPI"] = kpi_inf_name
    df_inf["Nom_KPI_Complet"] = kpi_inf_name
    is_ano_inf = (~is_carac) & (cats.isin(["<1 mois", "Inconnu"]) | (ages <= 30))
    df_inf["Résultat"] = np.where(is_ano_inf, "NON", "OUI")
    df_inf["Motif_NON"] = np.where(
        is_ano_inf,
        ages.apply(lambda a: f"OT {prefix.lower()} non caractérisé (< 1 mois : {int(a)} j.)"),
        ""
    )

    # ── KPI 1mois< <3mois (Anomalie = non caractérisé dans 1-3 mois) ──
    df_1_3 = scope.copy()
    kpi_1_3_name = f"{prefix} 1mois< <3mois"
    df_1_3["KPI"] = kpi_1_3_name
    df_1_3["Nom_KPI_Complet"] = kpi_1_3_name
    is_ano_1_3 = (~is_carac) & ((cats == "1 mois < <3 mois") | ((ages > 30) & (ages <= 90)))
    df_1_3["Résultat"] = np.where(is_ano_1_3, "NON", "OUI")
    df_1_3["Motif_NON"] = np.where(
        is_ano_1_3,
        ages.apply(lambda a: f"OT {prefix.lower()} non caractérisé (tranche 1 à 3 mois : {int(a)} j.)"),
        ""
    )

    # ── KPI >3 mois (Anomalie = non caractérisé dans > 3 mois) ──
    df_sup = scope.copy()
    kpi_sup_name = f"{prefix} >3 mois"
    df_sup["KPI"] = kpi_sup_name
    df_sup["Nom_KPI_Complet"] = kpi_sup_name
    is_ano_sup = (~is_carac) & ((cats == ">3 mois") | (ages > 90))
    df_sup["Résultat"] = np.where(is_ano_sup, "NON", "OUI")
    df_sup["Motif_NON"] = np.where(
        is_ano_sup,
        ages.apply(lambda a: f"OT {prefix.lower()} non caractérisé (> 3 mois : {int(a)} j.)"),
        ""
    )

    return df_inf, df_1_3, df_sup


# ─────────────────────────────────────────────────────────────────────────────
# 8. CONSOLIDATION GLOBALE : TABLE DE CONTRÔLE SOURCE UNIQUE
# ─────────────────────────────────────────────────────────────────────────────

def build_table_controle_complete(df_period: pd.DataFrame, avdf_period: pd.DataFrame,
                                  now_ts, df_full: pd.DataFrame = None) -> pd.DataFrame:
    """
    Construit la table unique de contrôle pour tous les KPIs.
    """
    df_all = df_full if df_full is not None else df_period

    evals = [
        eval_ot_lanc_estime(df_period),
        eval_taux_realisation_correctif(df_period),
        eval_backlog_prep_caracterise(df_all),
        eval_backlog_plan_caracterise(df_all),
        eval_ot_confime(df_period),
        eval_ot_cor_egal(df_period),
        eval_taux_approbation_avis(avdf_period),
        eval_performance_graissage(df_period),
        eval_performance_inspection(df_period, now_ts),
        eval_performance_systematiques(df_period, now_ts),
    ]

    for phase in ["prep", "plan", "exec"]:
        d_inf, d_1_3, d_sup = eval_ages_kpi(df_all, phase, now_ts)
        evals.extend([d_inf, d_1_3, d_sup])

    valides = [d for d in evals if not d.empty]
    if not valides:
        return pd.DataFrame()

    cols_standard = [
        "Ordre", "Avis", "Poste travail princ.", "Division", "KPI",
        "Résultat", "Motif_NON", "Statut système", "Statut utilisateur", "Statut OT",
        "Créé le", "Date de début planifiée", "Total coûts budgétés", "Total coûts réels",
        "Désignation", "Poste technique", "Type d'ordre", "Type de travail",
    ]

    chunks = []
    for sub in valides:
        c_sub = pd.DataFrame(index=sub.index)
        for c in cols_standard:
            c_sub[c] = sub[c] if c in sub.columns else ""
        if "Age" in sub.columns:
            c_sub["Age"] = sub["Age"]
        elif "amp" in sub.columns and "préparation" in str(sub["KPI"].iloc[0]):
            c_sub["Age"] = sub["amp"]
        elif "amlp" in sub.columns and "planification" in str(sub["KPI"].iloc[0]):
            c_sub["Age"] = sub["amlp"]
        elif "amex" in sub.columns and "exécution" in str(sub["KPI"].iloc[0]):
            c_sub["Age"] = sub["amex"]
        else:
            c_sub["Age"] = np.nan
        chunks.append(c_sub)

    table = pd.concat(chunks, ignore_index=True)
    return table


# ─────────────────────────────────────────────────────────────────────────────
# 9. CALCUL DE SYNTHÈSE PAR DIVISION ET POSTE
# ─────────────────────────────────────────────────────────────────────────────

def get_kpi_summary(table_controle: pd.DataFrame, kpi_name: str) -> dict:
    """
    Calcule le résumé Total, OUI, NON, KPI % pour un KPI donné :
    par Poste, pour SF1, pour SF2, et Total Général.
    """
    if table_controle.empty:
        return {"postes": pd.DataFrame(), "divisions": pd.DataFrame(), "total": {}}

    sub = table_controle[table_controle["KPI"] == kpi_name].copy()
    if sub.empty:
        return {"postes": pd.DataFrame(), "divisions": pd.DataFrame(), "total": {}}

    def _calc_grp(grp):
        tot = len(grp)
        oui = int((grp["Résultat"] == "OUI").sum())
        non = int((grp["Résultat"] == "NON").sum())
        if kpi_name in LOWER_BETTER:
            tx = round((non / tot * 100), 2) if tot > 0 else 0.0
        else:
            tx = round((oui / tot * 100), 2) if tot > 0 else 100.0
        return pd.Series({"Total": tot, "OUI": oui, "NON": non, "KPI %": tx})

    p_summary = sub.groupby("Poste travail princ.").apply(_calc_grp).reset_index()
    d_summary = sub.groupby("Division").apply(_calc_grp).reset_index()

    tot = len(sub)
    oui = int((sub["Résultat"] == "OUI").sum())
    non = int((sub["Résultat"] == "NON").sum())
    if kpi_name in LOWER_BETTER:
        tx = round((non / tot * 100), 2) if tot > 0 else 0.0
    else:
        tx = round((oui / tot * 100), 2) if tot > 0 else 100.0
    tot_summary = {"Total": tot, "OUI": oui, "NON": non, "KPI %": tx}

    return {"postes": p_summary, "divisions": d_summary, "total": tot_summary}


# ─────────────────────────────────────────────────────────────────────────────
# 10. GÉNÉRATION DU FICHIER EXCEL MULTI-FEUILLES (NON_DETAIL, PAR POSTE, SYNTHÈSE)
# ─────────────────────────────────────────────────────────────────────────────

def build_anomalies_excel_unified(table_controle: pd.DataFrame, kpi_filter=None) -> bytes:
    """
    Génère le fichier Excel d'audit et anomalies conforme aux exigences :
      - Feuille 1 : NON_DETAIL (toutes les lignes NON)
      - Feuille 2 : ANOMALIES_KPI_POSTE (Poste de travail | KPI | Nombre NON)
      - Feuille 3 : SYNTHESE_KPI (KPI | Total | OUI | NON | KPI %)
    """
    tbl = table_controle.copy()
    if kpi_filter:
        tbl = tbl[tbl["KPI"] == kpi_filter]

    wb = Workbook()
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    hf = Font(bold=True, color="FFFFFF", size=10)
    hfl = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    tb = Border(left=Side(style="thin", color="CBD5E1"), right=Side(style="thin", color="CBD5E1"),
                top=Side(style="thin", color="CBD5E1"), bottom=Side(style="thin", color="CBD5E1"))

    # ── Feuille 1 : NON_DETAIL ──
    ws1 = wb.create_sheet("NON_DETAIL")
    non_df = tbl[tbl["Résultat"] == "NON"].copy()

    cols_non = [
        "Ordre", "Avis", "Poste travail princ.", "Division", "KPI",
        "Résultat", "Motif_NON", "Age", "Statut OT", "Statut système", "Statut utilisateur",
        "Total coûts budgétés", "Total coûts réels", "Date de début planifiée", "Créé le",
        "Désignation", "Poste technique",
    ]
    cols_exist = [c for c in cols_non if c in non_df.columns]

    for j, c in enumerate(cols_exist, 1):
        cell = ws1.cell(row=1, column=j, value=c)
        cell.font, cell.fill, cell.border = hf, hfl, tb
        cell.alignment = Alignment(horizontal="center")

    for i, row in enumerate(non_df[cols_exist].itertuples(index=False), 2):
        for j, val in enumerate(row, 1):
            cell = ws1.cell(row=i, column=j, value="" if pd.isna(val) else str(val))
            cell.border = tb
            if j in (1, 2, 4, 5, 6, 8):
                cell.alignment = Alignment(horizontal="center")

    # ── Feuille 2 : ANOMALIES_KPI_POSTE ──
    ws2 = wb.create_sheet("ANOMALIES_KPI_POSTE")
    if not non_df.empty:
        piv = non_df.groupby(["Poste travail princ.", "KPI"]).size().reset_index(name="Nombre NON")
    else:
        piv = pd.DataFrame(columns=["Poste de travail", "KPI", "Nombre NON"])

    cols_piv = ["Poste de travail", "KPI", "Nombre NON"]
    for j, c in enumerate(cols_piv, 1):
        cell = ws2.cell(row=1, column=j, value=c)
        cell.font, cell.fill, cell.border = hf, hfl, tb
        cell.alignment = Alignment(horizontal="center")

    for i, row in enumerate(piv.itertuples(index=False), 2):
        for j, val in enumerate(row, 1):
            cell = ws2.cell(row=i, column=j, value=val)
            cell.border = tb
            cell.alignment = Alignment(horizontal="center" if j == 3 else "left")

    # ── Feuille 3 : SYNTHESE_KPI ──
    ws3 = wb.create_sheet("SYNTHESE_KPI")
    synth_rows = []
    for k in tbl["KPI"].unique():
        sub_k = tbl[tbl["KPI"] == k]
        tot = len(sub_k)
        oui = int((sub_k["Résultat"] == "OUI").sum())
        non = int((sub_k["Résultat"] == "NON").sum())
        if k in LOWER_BETTER:
            tx = round((non / tot * 100), 2) if tot > 0 else 0.0
        else:
            tx = round((oui / tot * 100), 2) if tot > 0 else 100.0
        synth_rows.append({"KPI": k, "Total": tot, "OUI": oui, "NON": non, "KPI %": f"{tx:.1f} %"})

    synth_df = pd.DataFrame(synth_rows)
    cols_synth = ["KPI", "Total", "OUI", "NON", "KPI %"]
    for j, c in enumerate(cols_synth, 1):
        cell = ws3.cell(row=1, column=j, value=c)
        cell.font, cell.fill, cell.border = hf, hfl, tb
        cell.alignment = Alignment(horizontal="center")

    for i, row in enumerate(synth_df.itertuples(index=False), 2):
        for j, val in enumerate(row, 1):
            cell = ws3.cell(row=i, column=j, value=val)
            cell.border = tb
            cell.alignment = Alignment(horizontal="center" if j > 1 else "left")

    # Ajustement largeur des colonnes
    for ws in [ws1, ws2, ws3]:
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = min(40, max(12, max_len + 3))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
