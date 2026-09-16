# -*- coding: utf-8 -*-
"""
Script d'audit conforme aux 11 définitions officielles OCP :
1. Préparation_Taux de caractérisation Backlog préparation
2. Planification _Taux de caractérisation Backlog Planification
3. Age du Backlog des OT (Préparation)_<1mois
4. Age du Backlog des OT (Préparation)_1mois<..<3mois
5. Age du Backlog des OT (Préparation)_>3mois
6. Age du Backlog des OT (Planification)_<1mois (LANC + ATPL)
7. Age du Backlog des OT (Planification)_1mois<..<3mois (LANC + ATPL)
8. Age du Backlog des OT (Planification)_>3mois (LANC + ATPL)
9. Age du Backlog des OT (Exécution)_<1mois (LANC + SOPL)
10. Age du Backlog des OT (Exécution)_1mois<..<3mois (LANC + SOPL)
11. Age du Backlog des OT (Exécution)_>3mois (LANC + SOPL)

Intègre le filtre de période de la barre latérale (Date de début planifiée).
Génère le classeur Excel complet : audit_officiel_backlogs_et_ages.xlsx
"""

import io
import os
import re
from datetime import datetime
import numpy as np
import pandas as pd

CODES_PREP = {"ATPD", "ATMR", "ATER", "ATRS", "ATMO"}
CODES_PLAN = {"ATPL", "ATEI", "ATAL", "ATAS", "AGAR", "ATHS"}

def match_token(statut, codes: set) -> bool:
    if statut is None or (isinstance(statut, float) and pd.isna(statut)):
        return False
    words = set(re.findall(r'[A-Za-z0-9]+', str(statut).upper()))
    return bool(words & codes)

def get_division(poste: str) -> str:
    p = str(poste).strip().upper()
    if p.startswith("SF1"):
        return "SF1 (Maroc Chimie)"
    elif p.startswith("SF2"):
        return "SF2 (FEEDS)"
    return "AUTRE"

def cat_age_jours(j):
    if pd.isna(j):
        return "<1mois"
    if j <= 30:
        return "<1mois"
    elif j <= 90:
        return "1mois<..<3mois"
    return ">3mois"

def main():
    print("=" * 80)
    print("AUDIT OFFICIEL OCP — BACKLOGS & ÂGES (PRÉPARATION, PLANIFICATION, EXÉCUTION)")
    print("=" * 80)

    ot_file = "ot.xlsx"
    if not os.path.exists(ot_file):
        print(f"❌ Fichier '{ot_file}' introuvable.")
        return

    # Date de référence
    ref_date_str = "16/09/2026"
    if os.path.exists("date.txt"):
        try:
            with open("date.txt", "r", encoding="utf-8") as f:
                d = f.read().strip()
                if d: ref_date_str = d
        except Exception:
            pass
    now_ts = pd.to_datetime(ref_date_str, format="%d/%m/%Y", errors="coerce")
    if pd.isna(now_ts):
        now_ts = pd.Timestamp.today().normalize()
    print(f"📅 Date de référence extraction : {now_ts.strftime('%d/%m/%Y')}")

    # Lecture ot.xlsx
    with open(ot_file, "rb") as f:
        bytes_data = f.read()
    raw_ot = None
    try:
        from core.prepare_data import read_excel_safe
        raw_ot = read_excel_safe(bytes_data)
    except Exception:
        for eng in ["openpyxl", "calamine", "xlrd", None]:
            try:
                raw_ot = pd.read_excel(io.BytesIO(bytes_data), engine=eng) if eng else pd.read_excel(io.BytesIO(bytes_data))
                break
            except Exception:
                continue

    if raw_ot is None:
        print("❌ Lecture impossible.")
        return

    raw_ot.columns = [str(c).strip() for c in raw_ot.columns]
    print(f"📖 Lignes chargées dans ot.xlsx : {len(raw_ot):,}")

    # Exclusion 'cresseur'
    if "Poste travail princ." in raw_ot.columns:
        raw_ot = raw_ot[~raw_ot["Poste travail princ."].astype(str).str.contains("cresseur", case=False, na=False)].copy()

    # Parsing dates
    for c in ["Créé le", "Date de début planifiée", "Date de clôture"]:
        if c in raw_ot.columns:
            raw_ot[c] = pd.to_datetime(raw_ot[c], errors="coerce", dayfirst=True)

    # Statut système et Statut OT
    statut_sys = raw_ot.get("Statut système", pd.Series("", index=raw_ot.index)).fillna("").astype(str)
    statut_usr = raw_ot.get("Statut utilisateur", pd.Series("", index=raw_ot.index)).fillna("").astype(str)
    type_ordre = raw_ot.get("Type d'ordre", pd.Series("", index=raw_ot.index)).fillna("").astype(str).str.strip().str.upper()

    first_statut = statut_sys.str.strip().str.split().str[0].replace({"CREE": "CRÉÉ"})
    raw_ot["Statut OT"] = first_statut
    raw_ot["Division"] = raw_ot["Poste travail princ."].apply(get_division)

    # ═════════════════════════════════════════════════════════════════════════
    # A. APPLICATION DU FILTRE DE PÉRIODE SIDEBAR
    # ═════════════════════════════════════════════════════════════════════════
    # Valeurs par défaut du sidebar : du 01/01/2025 à aujourd'hui
    sdt = pd.to_datetime(datetime(2025, 1, 1))
    edt = pd.to_datetime(datetime.today())
    
    # df_period : filtré selon la Date de début planifiée dans la période
    has_date_plan = raw_ot["Date de début planifiée"].notna()
    df_period = raw_ot[has_date_plan & raw_ot["Date de début planifiée"].between(sdt, edt)].copy()
    print(f"🔍 Période sidebar appliquée : {sdt.strftime('%d/%m/%Y')} au {edt.strftime('%d/%m/%Y')}")
    print(f"   • Lignes sur la période : {len(df_period):,} (sur {len(raw_ot):,} total)")

    df_eval = df_period.copy()

    # ═════════════════════════════════════════════════════════════════════════
    # 1. PRÉPARATION : CARACTÉRISATION & ÂGES
    # ═════════════════════════════════════════════════════════════════════════
    # Périmètre Préparation : Type d'ordre == 'ZCOR' & Statut système commence par 'CRÉÉ' / 'CREE'
    is_prep = (df_eval["Type d'ordre"].astype(str).str.upper() == "ZCOR") & df_eval["Statut OT"].isin(["CRÉÉ", "CREE"])
    scope_prep = df_eval[is_prep].copy()

    # Âge Préparation : Date de création (Créé le)
    dt_cree_prep = scope_prep["Créé le"].fillna(scope_prep["Date de début planifiée"])
    scope_prep["Age_Jours"] = (now_ts - dt_cree_prep.dt.normalize()).dt.days
    scope_prep["Cat_Age"] = scope_prep["Age_Jours"].apply(cat_age_jours)

    # Caractérisation Préparation
    is_carac_prep = scope_prep["Statut utilisateur"].apply(lambda s: match_token(s, CODES_PREP))
    scope_prep["Carac_Prep"] = np.where(is_carac_prep, "OUI", "NON")

    # ═════════════════════════════════════════════════════════════════════════
    # 2. PLANIFICATION : CARACTÉRISATION & ÂGES (LANC + ATPL)
    # ═════════════════════════════════════════════════════════════════════════
    # Périmètre Planification officiel : Statut système commence par 'LANC' ET Statut utilisateur contient 'ATPL'
    is_lanc = df_eval["Statut OT"] == "LANC"
    contient_atpl = df_eval["Statut utilisateur"].fillna("").astype(str).str.contains("ATPL", case=False, na=False)
    is_plan = (df_eval["Type d'ordre"].astype(str).str.upper() == "ZCOR") & is_lanc & contient_atpl
    scope_plan = df_eval[is_plan].copy()

    dt_plan = scope_plan["Date de début planifiée"]
    scope_plan["Age_Jours"] = (now_ts - dt_plan.dt.normalize()).dt.days
    scope_plan["Cat_Age"] = scope_plan["Age_Jours"].apply(cat_age_jours)

    is_carac_plan = scope_plan["Statut utilisateur"].apply(lambda s: match_token(s, CODES_PLAN))
    scope_plan["Carac_Plan"] = np.where(is_carac_plan, "OUI", "NON")

    # ═════════════════════════════════════════════════════════════════════════
    # 3. EXÉCUTION : ÂGES (LANC + SOPL)
    # ═════════════════════════════════════════════════════════════════════════
    # Périmètre Exécution officiel : Statut système commence par 'LANC' ET Statut utilisateur contient 'SOPL'
    contient_sopl = df_eval["Statut utilisateur"].fillna("").astype(str).str.contains("SOPL", case=False, na=False)
    is_exec = (df_eval["Type d'ordre"].astype(str).str.upper() == "ZCOR") & is_lanc & contient_sopl
    scope_exec = df_eval[is_exec].copy()

    dt_exec = scope_exec["Date de début planifiée"]
    scope_exec["Age_Jours"] = (now_ts - dt_exec.dt.normalize()).dt.days
    scope_exec["Cat_Age"] = scope_exec["Age_Jours"].apply(cat_age_jours)

    # ═════════════════════════════════════════════════════════════════════════
    # SYNTHÈSE DES 11 KPIS PAR DIVISION (SF1, SF2 ET TOTAL)
    # ═════════════════════════════════════════════════════════════════════════
    def compute_kpis_for_scope(sc_prep, sc_plan, sc_exec, label):
        records = []

        # 1. Caractérisation Préparation
        t_p = len(sc_prep)
        o_p = int((sc_prep["Carac_Prep"] == "OUI").sum())
        n_p = t_p - o_p
        tx_p = (o_p / t_p * 100) if t_p > 0 else 100.0
        records.append({"Périmètre": label, "KPI": "Préparation_Taux de caractérisation Backlog préparation", "Total": t_p, "OUI": o_p, "NON (Anomalies)": n_p, "Taux %": f"{tx_p:.1f}%", "Cible": "≥100%"})

        # 2. Caractérisation Planification
        t_l = len(sc_plan)
        o_l = int((sc_plan["Carac_Plan"] == "OUI").sum())
        n_l = t_l - o_l
        tx_l = (o_l / t_l * 100) if t_l > 0 else 100.0
        records.append({"Périmètre": label, "KPI": "Planification_Taux de caractérisation Backlog Planification", "Total": t_l, "OUI": o_l, "NON (Anomalies)": n_l, "Taux %": f"{tx_l:.1f}%", "Cible": "≥100%"})

        # 3, 4, 5. Âges Préparation
        c_inf = int((sc_prep["Cat_Age"] == "<1mois").sum())
        c_1_3 = int((sc_prep["Cat_Age"] == "1mois<..<3mois").sum())
        c_sup = int((sc_prep["Cat_Age"] == ">3mois").sum())
        records.append({"Périmètre": label, "KPI": "Age du Backlog des OT (Préparation)_<1mois", "Total": t_p, "OUI": c_inf, "NON (Anomalies)": t_p - c_inf, "Taux %": f"{(c_inf/t_p*100) if t_p else 0:.1f}%", "Cible": "≥80%"})
        records.append({"Périmètre": label, "KPI": "Age du Backlog des OT (Préparation)_1mois<..<3mois", "Total": t_p, "OUI": c_1_3, "NON (Anomalies)": t_p - c_1_3, "Taux %": f"{(c_1_3/t_p*100) if t_p else 0:.1f}%", "Cible": "≤15%"})
        records.append({"Périmètre": label, "KPI": "Age du Backlog des OT (Préparation)_>3mois", "Total": t_p, "OUI": c_sup, "NON (Anomalies)": t_p - c_sup, "Taux %": f"{(c_sup/t_p*100) if t_p else 0:.1f}%", "Cible": "≤5%"})

        # 6, 7, 8. Âges Planification (LANC + ATPL)
        pl_inf = int((sc_plan["Cat_Age"] == "<1mois").sum())
        pl_1_3 = int((sc_plan["Cat_Age"] == "1mois<..<3mois").sum())
        pl_sup = int((sc_plan["Cat_Age"] == ">3mois").sum())
        records.append({"Périmètre": label, "KPI": "Age du Backlog des OT (Planification)_<1mois", "Total": t_l, "OUI": pl_inf, "NON (Anomalies)": t_l - pl_inf, "Taux %": f"{(pl_inf/t_l*100) if t_l else 0:.1f}%", "Cible": "≥80%"})
        records.append({"Périmètre": label, "KPI": "Age du Backlog des OT (Planification)_1mois<..<3mois", "Total": t_l, "OUI": pl_1_3, "NON (Anomalies)": t_l - pl_1_3, "Taux %": f"{(pl_1_3/t_l*100) if t_l else 0:.1f}%", "Cible": "≤15%"})
        records.append({"Périmètre": label, "KPI": "Age du Backlog des OT (Planification)_>3mois", "Total": t_l, "OUI": pl_sup, "NON (Anomalies)": t_l - pl_sup, "Taux %": f"{(pl_sup/t_l*100) if t_l else 0:.1f}%", "Cible": "≤5%"})

        # 9, 10, 11. Âges Exécution (LANC + SOPL)
        t_e = len(sc_exec)
        ex_inf = int((sc_exec["Cat_Age"] == "<1mois").sum())
        ex_1_3 = int((sc_exec["Cat_Age"] == "1mois<..<3mois").sum())
        ex_sup = int((sc_exec["Cat_Age"] == ">3mois").sum())
        records.append({"Périmètre": label, "KPI": "Age du Backlog des OT (Exécution)_<1mois", "Total": t_e, "OUI": ex_inf, "NON (Anomalies)": t_e - ex_inf, "Taux %": f"{(ex_inf/t_e*100) if t_e else 0:.1f}%", "Cible": "≥80%"})
        records.append({"Périmètre": label, "KPI": "Age du Backlog des OT (Exécution)_1mois<..<3mois", "Total": t_e, "OUI": ex_1_3, "NON (Anomalies)": t_e - ex_1_3, "Taux %": f"{(ex_1_3/t_e*100) if t_e else 0:.1f}%", "Cible": "≤15%"})
        records.append({"Périmètre": label, "KPI": "Age du Backlog des OT (Exécution)_>3mois", "Total": t_e, "OUI": ex_sup, "NON (Anomalies)": t_e - ex_sup, "Taux %": f"{(ex_sup/t_e*100) if t_e else 0:.1f}%", "Cible": "≤5%"})

        return records

    rec_sf1 = compute_kpis_for_scope(
        scope_prep[scope_prep["Division"] == "SF1 (Maroc Chimie)"],
        scope_plan[scope_plan["Division"] == "SF1 (Maroc Chimie)"],
        scope_exec[scope_exec["Division"] == "SF1 (Maroc Chimie)"],
        "SF1 (Maroc Chimie)",
    )
    rec_sf2 = compute_kpis_for_scope(
        scope_prep[scope_prep["Division"] == "SF2 (FEEDS)"],
        scope_plan[scope_plan["Division"] == "SF2 (FEEDS)"],
        scope_exec[scope_exec["Division"] == "SF2 (FEEDS)"],
        "SF2 (FEEDS)",
    )
    rec_tot = compute_kpis_for_scope(scope_prep, scope_plan, scope_exec, "TOTAL GÉNÉRAL")

    df_synth_all = pd.DataFrame(rec_sf1 + rec_sf2 + rec_tot)
    print("\n" + "─" * 80)
    print("TABLEAU DE SYNTHÈSE DES 11 KPIS OFFICIELS :")
    print("─" * 80)
    print(df_synth_all[["Périmètre", "KPI", "Total", "OUI", "NON (Anomalies)", "Taux %", "Cible"]].to_string(index=False))

    # ── Export Excel complet ──
    out_file = "audit_officiel_backlogs_et_ages.xlsx"
    cols_base = [
        "Ordre", "Poste travail princ.", "Division", "Statut système", "Statut utilisateur",
        "Statut OT", "Date de début planifiée", "Créé le", "Age_Jours", "Cat_Age",
        "Désignation", "Poste technique",
    ]
    cols_p = [c for c in cols_base + ["Carac_Prep"] if c in scope_prep.columns]
    cols_l = [c for c in cols_base + ["Carac_Plan"] if c in scope_plan.columns]
    cols_e = [c for c in cols_base if c in scope_exec.columns]

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df_synth_all.to_excel(writer, sheet_name="SYNTHESE_11_KPIS", index=False)
        scope_prep[cols_p].to_excel(writer, sheet_name="STOCK_PREPARATION", index=False)
        scope_plan[cols_l].to_excel(writer, sheet_name="STOCK_PLANIFICATION_ATPL", index=False)
        scope_exec[cols_e].to_excel(writer, sheet_name="STOCK_EXECUTION_SOPL", index=False)

    print(f"\n💾 Classeur généré : '{out_file}'")
    print("   • Feuille 'SYNTHESE_11_KPIS' : Synthèse SF1, SF2 et Total pour les 11 indicateurs")
    print(f"   • Feuille 'STOCK_PREPARATION' : {len(scope_prep)} OT (CRÉÉ)")
    print(f"   • Feuille 'STOCK_PLANIFICATION_ATPL' : {len(scope_plan)} OT (LANC + ATPL)")
    print(f"   • Feuille 'STOCK_EXECUTION_SOPL' : {len(scope_exec)} OT (LANC + SOPL)")
    print("=" * 80)

if __name__ == "__main__":
    main()
