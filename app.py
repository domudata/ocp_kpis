def calc_score_division(postes, liste_kpi, ano_map, ckdf):
    """
    Calcule le score global d'une division (SF1 ou SF2) basé sur les volumes
    totaux d'anomalies / réalisations cumulés sur l'ensemble des postes.
    """
    total_gscores = 0
    nb_kpis_valides = 0

    for kpi in liste_kpi:
        # Récupération des données d'anomalies cumulées sur les postes de la division
        if kpi in ano_map:
            s_anom = ano_map[kpi].reindex(postes).fillna(0)
            nb_non = s_anom.sum()
        else:
            nb_non = 0

        # KPI d'âge du backlog : conservation de la logique de moyenne pondérée/précédente
        if "préparation" in kpi or "planification" in kpi or "exécution" in kpi:
            vals = [ckdf.loc[p, kpi] for p in postes if p in ckdf.index and kpi in ckdf.columns and pd.notna(ckdf.loc[p, kpi])]
            if vals:
                valeur_globale = sum(vals) / len(vals)
                total_gscores += gscore(kpi, valeur_globale, CIBLE[kpi])
                nb_kpis_valides += 1
            continue

        # Extraction des valeurs mesurées sur les postes pour estimer les volumes
        vals_kpi = [ckdf.loc[p, kpi] for p in postes if p in ckdf.index and kpi in ckdf.columns and pd.notna(ckdf.loc[p, kpi])]
        if not vals_kpi:
            continue

        avg_val = sum(vals_kpi) / len(vals_kpi)

        # Règle spécifique pour OT Correctif : Non / (Oui + Non)
        if kpi == "OT Correctif":
            # Estimation du volume total à partir du taux moyen et des anomalies
            tot_vol = (nb_non / (avg_val / 100)) if avg_val > 0 else nb_non
            valeur_globale = (nb_non / tot_vol * 100) if tot_vol > 0 else 0.0
        else:
            # Règle standard : Oui / (Oui + Non)
            # Taux = 100 - %Anomalies (ou calcul direct selon le KPI)
            if is_lb(kpi):
                valeur_globale = avg_val
            else:
                tot_vol = (nb_non / ((100 - avg_val) / 100)) if (100 - avg_val) > 0 else nb_non
                nb_oui = max(0, tot_vol - nb_non)
                valeur_globale = (nb_oui / tot_vol * 100) if tot_vol > 0 else 100.0

        # Évaluation par rapport à la cible
        total_gscores += gscore(kpi, valeur_globale, CIBLE[kpi])
        nb_kpis_valides += 1

    return round((total_gscores / nb_kpis_valides) * 100, 2) if nb_kpis_valides > 0 else 0

# ── Calcul des cartes SF1 et SF2 mis à jour ─────────────────────────────────
sf1_p = int(calc_score_division(sf1_posts, QK, ano_map, ckdf))
sf1_q = int(calc_score_division(sf1_posts, PK, ano_map, ckdf))

sf2_p = int(calc_score_division(sf2_posts, QK, ano_map, ckdf))
sf2_q = int(calc_score_division(sf2_posts, PK, ano_map, ckdf))
