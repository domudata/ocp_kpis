# -*- coding: utf-8 -*-
"""
Script autonome de calcul et d'extraction Excel pour les KPIs :
1. Backlog préparation caractérisé
2. Backlog planification caractérisé

Ce script ne modifie AUCUN fichier de l'application.
Il lit ot.xlsx et génère directement le classeur Excel d'audit :
extraction_BACKLOG_PREP_PLAN.xlsx
"""

import io
import os
import re
import numpy as np
import pandas as pd

CODES_PREP_EXACT = {"ATPD", "ATMR", "ATER", "ATRS", "ATMO"}
CODES_PLAN_EXACT = {"ATPL", "ATEI", "ATAL", "ATAS", "AGAR", "ATHS"}

def match_exact_token(statut, codes: set) -> bool:
    if statut is None or (isinstance(statut, float) and pd.isna(statut)):
        return False
    words = set(re.findall(r'[A-Za-z0-9]+', str(statut).upper()))
    return bool(words & codes)

def get_div(p):
    p_str = str(p).strip().upper()
    if p_str.startswith("SF1"):
        return "SF1 (Maroc Chimie)"
    elif p_str.startswith("SF2"):
        return "SF2 (FEEDS)"
    return "AUTRE"

def synthese_grp(df_grp, col_res="Résultat"):
    tot = len(df_grp)
    oui = int((df_grp[col_res] == "OUI").sum())
    non = int((df_grp[col_res] == "NON").sum())
    tx = (oui / tot * 100) if tot > 0 else 0.0
    return tot, oui, non, tx

def main():
    print("=" * 75)
    print("AUDIT SAP — BACKLOG PRÉPARATION & PLANIFICATION CARACTÉRISÉS")
    print("=" * 75)

    ot_file = "ot.xlsx"
    if not os.path.exists(ot_file):
        print(f"❌ Fichier '{ot_file}' introuvable.")
        return

    print(f"📖 Lecture de '{ot_file}'...")
    raw_ot = None
    with open(ot_file, "rb") as f:
        bytes_data = f.read()
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
        print("❌ Impossible de lire ot.xlsx.")
        return

    raw_ot.columns = [str(c).strip() for c in raw_ot.columns]

    # Exclusion 'cresseur'
    if "Poste travail princ." in raw_ot.columns:
        raw_ot = raw_ot[~raw_ot["Poste travail princ."].astype(str).str.contains("cresseur", case=False, na=False)].copy()

    # Détection statut système et type d'ordre
    statut_sys = raw_ot.get("Statut système", pd.Series("", index=raw_ot.index)).fillna("").astype(str)
    statut_usr = raw_ot.get("Statut utilisateur", pd.Series("", index=raw_ot.index)).fillna("").astype(str)
    type_ordre = raw_ot.get("Type d'ordre", pd.Series("", index=raw_ot.index)).fillna("").astype(str).str.strip().str.upper()

    first_statut = statut_sys.str.strip().str.split().str[0].replace({"CREE": "CRÉÉ"})
    raw_ot["Statut OT"] = first_statut
    raw_ot["Division"] = raw_ot["Poste travail princ."].apply(get_div)

    # ═════════════════════════════════════════════════════════════════════════
    # 1. BACKLOG PRÉPARATION CARACTÉRISÉ
    # ═════════════════════════════════════════════════════════════════════════
    # Périmètre : ZCOR ET Statut système commence par CRÉÉ / CREE
    is_prep = (type_ordre == "ZCOR") & first_statut.isin(["CRÉÉ", "CREE"])
    scope_prep = raw_ot[is_prep].copy()

    is_carac_prep = scope_prep["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PREP_EXACT))
    scope_prep["KPI"] = "Backlog préparation caractérisé"
    scope_prep["Résultat"] = np.where(is_carac_prep, "OUI", "NON")
    scope_prep["Motif_NON"] = np.where(
        is_carac_prep,
        "",
        scope_prep["Statut utilisateur"].apply(lambda s: f"Non caractérisé : motif préparation manquant (Statut: {s if str(s).strip() else 'VIDE'})")
    )

    tot_p_g, oui_p_g, non_p_g, tx_p_g = synthese_grp(scope_prep)
    sf1_p = scope_prep[scope_prep["Division"] == "SF1 (Maroc Chimie)"]
    tot_p_sf1, oui_p_sf1, non_p_sf1, tx_p_sf1 = synthese_grp(sf1_p)
    sf2_p = scope_prep[scope_prep["Division"] == "SF2 (FEEDS)"]
    tot_p_sf2, oui_p_sf2, non_p_sf2, tx_p_sf2 = synthese_grp(sf2_p)

    print("\n" + "─" * 75)
    print("1. BACKLOG PRÉPARATION CARACTÉRISÉ (Cible >= 100%)")
    print("─" * 75)
    print(f"🏭 SF1 (Maroc Chimie) : Total={tot_p_sf1} | Caractérisés(OUI)={oui_p_sf1} | Non Caractérisés(NON)={non_p_sf1} | Taux={tx_p_sf1:.2f}%")
    print(f"🏭 SF2 (FEEDS)        : Total={tot_p_sf2} | Caractérisés(OUI)={oui_p_sf2} | Non Caractérisés(NON)={non_p_sf2} | Taux={tx_p_sf2:.2f}%")
    print(f"🏢 TOTAL GÉNÉRAL     : Total={tot_p_g} | Caractérisés(OUI)={oui_p_g} | Non Caractérisés(NON)={non_p_g} | Taux={tx_p_g:.2f}%")
    if tot_p_g == oui_p_g + non_p_g:
        print(f"✅ Contrôle 1 OK : {tot_p_g} = {oui_p_g} (OUI) + {non_p_g} (NON)")

    # ═════════════════════════════════════════════════════════════════════════
    # 2. BACKLOG PLANIFICATION CARACTÉRISÉ
    # ═════════════════════════════════════════════════════════════════════════
    # Périmètre : ZCOR ET Statut système commence par LANC ET Contient SOPL == 0
    contient_sopl = statut_usr.str.contains("SOPL", na=False).astype(int)
    is_plan = (type_ordre == "ZCOR") & (first_statut == "LANC") & (contient_sopl == 0)
    scope_plan = raw_ot[is_plan].copy()

    is_carac_plan = scope_plan["Statut utilisateur"].apply(lambda x: match_exact_token(x, CODES_PLAN_EXACT))
    scope_plan["KPI"] = "Backlog planification caractérisé"
    scope_plan["Résultat"] = np.where(is_carac_plan, "OUI", "NON")
    scope_plan["Motif_NON"] = np.where(
        is_carac_plan,
        "",
        scope_plan["Statut utilisateur"].apply(lambda s: f"Non caractérisé : motif arrêt planification manquant (Statut: {s if str(s).strip() else 'VIDE'})")
    )

    tot_l_g, oui_l_g, non_l_g, tx_l_g = synthese_grp(scope_plan)
    sf1_l = scope_plan[scope_plan["Division"] == "SF1 (Maroc Chimie)"]
    tot_l_sf1, oui_l_sf1, non_l_l_sf1, tx_l_sf1 = synthese_grp(sf1_l)
    sf2_l = scope_plan[scope_plan["Division"] == "SF2 (FEEDS)"]
    tot_l_sf2, oui_l_sf2, non_l_l_sf2, tx_l_sf2 = synthese_grp(sf2_l)

    print("\n" + "─" * 75)
    print("2. BACKLOG PLANIFICATION CARACTÉRISÉ (Cible >= 100%)")
    print("─" * 75)
    print(f"🏭 SF1 (Maroc Chimie) : Total={tot_l_sf1} | Caractérisés(OUI)={oui_l_sf1} | Non Caractérisés(NON)={non_l_l_sf1} | Taux={tx_l_sf1:.2f}%")
    print(f"🏭 SF2 (FEEDS)        : Total={tot_l_sf2} | Caractérisés(OUI)={oui_l_sf2} | Non Caractérisés(NON)={non_l_l_sf2} | Taux={tx_l_sf2:.2f}%")
    print(f"🏢 TOTAL GÉNÉRAL     : Total={tot_l_g} | Caractérisés(OUI)={oui_l_g} | Non Caractérisés(NON)={non_l_g} | Taux={tx_l_g:.2f}%")
    if tot_l_g == oui_l_g + non_l_g:
        print(f"✅ Contrôle 1 OK : {tot_l_g} = {oui_l_g} (OUI) + {non_l_g} (NON)")

    # ── Détail par Poste ──
    rows_p = []
    for p, g in scope_prep.groupby("Poste travail princ."):
        t, o, n, tx = synthese_grp(g)
        rows_p.append({"Poste": p, "Division": g["Division"].iloc[0], "Total Prep": t, "OUI Prep": o, "NON Prep": n, "Taux Prep %": round(tx, 1)})
    df_p_postes = pd.DataFrame(rows_p)

    rows_l = []
    for p, g in scope_plan.groupby("Poste travail princ."):
        t, o, n, tx = synthese_grp(g)
        rows_l.append({"Poste": p, "Division": g["Division"].iloc[0], "Total Plan": t, "OUI Plan": o, "NON Plan": n, "Taux Plan %": round(tx, 1)})
    df_l_postes = pd.DataFrame(rows_l)

    # ── Export Excel ──
    out_file = "extraction_BACKLOG_PREP_PLAN.xlsx"
    cols_export = [
        "Ordre", "Poste travail princ.", "Division", "KPI", "Résultat", "Motif_NON",
        "Statut système", "Statut utilisateur", "Statut OT",
        "Date de début planifiée", "Créé le", "Total coûts budgétés", "Total coûts réels",
        "Désignation", "Poste technique", "Type d'ordre",
    ]
    cols_p_exist = [c for c in cols_export if c in scope_prep.columns]
    cols_l_exist = [c for c in cols_export if c in scope_plan.columns]

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        synth_df = pd.DataFrame([
            {"Indicateur": "Backlog préparation caractérisé", "Périmètre": "SF1 (Maroc Chimie)", "Total OT": tot_p_sf1, "OUI (Caractérisé)": oui_p_sf1, "NON (Anomalie)": non_p_sf1, "Taux %": f"{tx_p_sf1:.1f}%"},
            {"Indicateur": "Backlog préparation caractérisé", "Périmètre": "SF2 (FEEDS)", "Total OT": tot_p_sf2, "OUI (Caractérisé)": oui_p_sf2, "NON (Anomalie)": non_p_sf2, "Taux %": f"{tx_p_sf2:.1f}%"},
            {"Indicateur": "Backlog préparation caractérisé", "Périmètre": "TOTAL GÉNÉRAL", "Total OT": tot_p_g, "OUI (Caractérisé)": oui_p_g, "NON (Anomalie)": non_p_g, "Taux %": f"{tx_p_g:.1f}%"},
            {"Indicateur": "Backlog planification caractérisé", "Périmètre": "SF1 (Maroc Chimie)", "Total OT": tot_l_sf1, "OUI (Caractérisé)": oui_l_sf1, "NON (Anomalie)": non_l_l_sf1, "Taux %": f"{tx_l_sf1:.1f}%"},
            {"Indicateur": "Backlog planification caractérisé", "Périmètre": "SF2 (FEEDS)", "Total OT": tot_l_sf2, "OUI (Caractérisé)": oui_l_sf2, "NON (Anomalie)": non_l_l_sf2, "Taux %": f"{tx_l_sf2:.1f}%"},
            {"Indicateur": "Backlog planification caractérisé", "Périmètre": "TOTAL GÉNÉRAL", "Total OT": tot_l_g, "OUI (Caractérisé)": oui_l_g, "NON (Anomalie)": non_l_g, "Taux %": f"{tx_l_g:.1f}%"},
        ])
        synth_df.to_excel(writer, sheet_name="SYNTHESE_BACKLOGS", index=False)
        if not df_p_postes.empty:
            df_p_postes.to_excel(writer, sheet_name="POSTES_PREPARATION", index=False)
        if not df_l_postes.empty:
            df_l_postes.to_excel(writer, sheet_name="POSTES_PLANIFICATION", index=False)

        scope_prep[scope_prep["Résultat"] == "NON"][cols_p_exist].to_excel(writer, sheet_name="ANOMALIES_PREP_NON", index=False)
        scope_plan[scope_plan["Résultat"] == "NON"][cols_l_exist].to_excel(writer, sheet_name="ANOMALIES_PLAN_NON", index=False)
        scope_prep[cols_p_exist].to_excel(writer, sheet_name="TOUS_OT_PREP", index=False)
        scope_plan[cols_l_exist].to_excel(writer, sheet_name="TOUS_OT_PLAN", index=False)

    print(f"\n💾 Classeur Excel généré avec succès : '{out_file}'")
    print("   • Feuille 'SYNTHESE_BACKLOGS' : Résumé SF1 / SF2 / Total")
    print("   • Feuille 'POSTES_PREPARATION' : Détail par poste préparation")
    print("   • Feuille 'POSTES_PLANIFICATION' : Détail par poste planification")
    print(f"   • Feuille 'ANOMALIES_PREP_NON' : Les {non_p_g} OT préparation non caractérisés")
    print(f"   • Feuille 'ANOMALIES_PLAN_NON' : Les {non_l_g} OT planification non caractérisés")
    print(f"   • Feuille 'TOUS_OT_PREP' : Ensemble du backlog préparation ({tot_p_g} OT)")
    print(f"   • Feuille 'TOUS_OT_PLAN' : Ensemble du backlog planification ({tot_l_g} OT)")
    print("=" * 75)

if __name__ == "__main__":
    main()
