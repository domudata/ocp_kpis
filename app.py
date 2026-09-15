import pandas as pd

def calc_kpi_ot_cor_egal(df_ot, ano_map, poste_or_postes):
    """
    Calcule le Taux d'Egalité de Coût sur OT Correctifs avec Cible = 100%.
    
    Formule : [ (Total ZCOR - Non) / Total ZCOR ] * 100
    """
    postes = [poste_or_postes] if isinstance(poste_or_postes, str) else list(poste_or_postes)

    # 1. Nombre d'anomalies avec écart de coût (Non)
    kpi_key = "OT_COR_EGAL" if "OT_COR_EGAL" in ano_map else "OT Cor Egal"
    nb_non = float(ano_map[kpi_key].reindex(postes).fillna(0).sum()) if kpi_key in ano_map else 0.0

    # 2. Total des OT ZCOR (Oui + Non)
    if not df_ot.empty and "Poste travail princ." in df_ot.columns:
        df_zcor = df_ot[
            (df_ot["Poste travail princ."].isin(postes)) &
            (df_ot["Type d'ordre"].astype(str).str.contains("ZCOR", case=False, na=False))
        ]
        total_zcor = len(df_zcor)
    else:
        total_zcor = 0

    # 3. Calcul du Taux de Conformité (Oui / Total)
    if total_zcor > 0:
        nb_oui = max(0.0, total_zcor - nb_non)
        return round((nb_oui / total_zcor) * 100.0, 2)
    
    # Si 0 OT ZCOR, le score est parfait par défaut
    return 100.0
