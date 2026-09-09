# -*- coding: utf-8 -*-
"""
Module de classification de l'adéquation de la fréquence de maintenance
préventive, à partir des données réelles SAP PM (ot.xlsx, plan_entretien.xlsx,
frequence.xlsx).
"""
import pandas as pd
import numpy as np

SEUIL_TAUX_CORRECTIF_INSUFFISANT = 0.15
SEUIL_JOURS_TROP_FREQUENT = 20

CATEGORIE_TW = {
    350: "Graissage", 290: "Inspection", 300: "Inspection", 310: "Inspection",
    360: "Systématique",
}


def categorie_type_travail(tw):
    return CATEGORIE_TW.get(tw, "Autre")


def corps_metier(poste_travail):
    poste = str(poste_travail)
    if len(poste) < 5:
        return "Autre"
    pref = poste[4:5]
    return {"M": "Mécanique", "E": "Électrique", "R": "Régulation/Instrumentation"}.get(pref, "Autre")


def charger_reference_plans_actifs(chemin_plan_entretien):
    ref = pd.read_excel(chemin_plan_entretien)
    ref_actifs = ref[ref["Statut"] == "P"]
    plans_actifs = set(zip(ref_actifs["Poste technique"], ref_actifs["Plan d'entretien"]))
    type_travail_map = dict(zip(
        zip(ref_actifs["Poste technique"], ref_actifs["Plan d'entretien"]),
        ref_actifs["Type de travail"],
    ))
    return plans_actifs, type_travail_map


def charger_reference_frequence_officielle(chemin_frequence):
    """
    NOTE : ce référentiel a été exploré pour obtenir la fréquence
    NOMINALE officielle (colonne 'Intervalle d'appels'), mais une
    incohérence non résolue a été identifiée sur les plans multi-tâches
    (voir chapitre Limites du rapport) — conservé ici pour traçabilité,
    non utilisé dans la classification finale (frequence OBSERVEE
    utilisée uniformément).
    """
    ref = pd.read_excel(chemin_frequence)
    ref_directe = ref[ref["Intervalle d'appels"].notna() & (ref["Intervalle d'appels"] > 0)]
    return dict(zip(ref_directe["Plan d'entretien"], ref_directe["Intervalle d'appels"]))


def construire_dataset_frequence(df_ot, plans_actifs=None, type_travail_map=None, freq_officielle_map=None):
    """
    Construit, pour chaque TRIPLET (poste technique, plan d'entretien,
    type de travail) ayant un historique suffisant (>= 3 visites), les
    variables nécessaires à la classification de l'adéquation de sa
    fréquence de maintenance.

    Unité d'analyse = triplet (poste, plan, type de travail), établie
    après investigation des données réelles :
      - 49% des postes techniques ont >= 2 plans d'entretien distincts ;
      - un même plan d'entretien peut lui-même regrouper plusieurs
        types de travail (Graissage/Inspection/Systématique) exécutés
        à des fréquences différentes sous un même identifiant de plan.
    """
    df = df_ot.copy()
    df["Date de début planifiée"] = pd.to_datetime(df["Date de début planifiée"], errors="coerce")
    df["Créé le"] = pd.to_datetime(df["Créé le"], errors="coerce")
    df["corps_metier"] = df["Poste travail princ."].apply(corps_metier)

    prev = df[
        df["Type d'ordre"].isin(["ZPRV", "ZEST"])
        & df["Date de début planifiée"].notna()
        & df["Plan d'entretien"].notna()
    ]
    correctifs = df[df["Type d'ordre"] == "ZCOR"]

    resultats = []
    for (pt, plan, tw), grp in prev.groupby(["Poste technique", "Plan d'entretien", "Type de travail"]):
        if plans_actifs is not None and (pt, plan) not in plans_actifs:
            continue

        dates = sorted(grp["Date de début planifiée"].dropna().unique())
        if len(dates) < 3:
            continue
        intervalles = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        freq_observee = float(np.mean(intervalles))
        freq_std = float(np.std(intervalles))

        freq_officielle = freq_officielle_map.get(plan) if freq_officielle_map else None
        freq_reference = freq_observee
        source_freq = "observée"

        corr_pt = correctifs[correctifs["Poste technique"] == pt]

        correctif_entre_visites = 0
        for i in range(len(dates) - 1):
            c = corr_pt[(corr_pt["Créé le"] >= dates[i]) & (corr_pt["Créé le"] < dates[i + 1])]
            if len(c) > 0:
                correctif_entre_visites += 1

        designation_avis = grp["Désignation"].dropna().iloc[0] if "Désignation" in grp.columns and grp["Désignation"].notna().any() else ""
        designation_poste = grp["Désignation du poste technique"].dropna().iloc[0] if "Désignation du poste technique" in grp.columns and grp["Désignation du poste technique"].notna().any() else ""

        resultats.append({
            "poste_technique": pt,
            "designation": designation_avis,
            "designation_poste_technique": designation_poste,
            "plan_entretien": plan,
            "type_travail_code": tw,
            "corps_metier": grp["corps_metier"].iloc[0],
            "categorie_travail": categorie_type_travail(tw),
            "nb_visites_preventives": len(dates),
            "frequence_observee_jours": round(freq_observee, 1),
            "frequence_officielle_jours": round(freq_officielle, 1) if freq_officielle else None,
            "source_frequence": source_freq,
            "frequence_moyenne_jours": round(freq_reference, 1),
            "frequence_std_jours": round(freq_std, 1),
            "nb_correctifs_total": len(corr_pt),
            "nb_correctifs_entre_visites": correctif_entre_visites,
            "taux_correctif_entre_visites": round(correctif_entre_visites / (len(dates) - 1), 2),
        })

    return pd.DataFrame(resultats)


def classer_frequence(row):
    if row["taux_correctif_entre_visites"] > SEUIL_TAUX_CORRECTIF_INSUFFISANT:
        return "Insuffisant"
    if row["frequence_moyenne_jours"] < SEUIL_JOURS_TROP_FREQUENT and row["taux_correctif_entre_visites"] == 0:
        return "Trop fréquent"
    return "Adéquat"


def calculer_couts_reference(df_ot):
    df = df_ot
    cout_prev = df[df["Type d'ordre"].isin(["ZPRV", "ZEST"])]["Total coûts réels"].mean()
    cout_correctif = df[df["Type d'ordre"] == "ZCOR"]["Total coûts réels"].mean()
    return float(cout_prev), float(cout_correctif)


FREQUENCES_STANDARD_JOURS = [7, 15, 30, 60, 90, 180, 365, 730]


def arrondir_frequence_standard(valeur_jours):
    """
    Arrondit une fréquence calculée à la valeur STANDARD la plus proche
    parmi celles réellement utilisées en pratique dans les plans de
    maintenance SAP (7, 15, 30, 60, 90, 180, 365, 730 jours) — une
    fréquence de « 21,4 jours » n'a pas de sens opérationnel, alors
    qu'une recommandation de « 15 jours » ou « 30 jours » est
    directement actionnable par l'équipe de planification.
    """
    return min(FREQUENCES_STANDARD_JOURS, key=lambda f: abs(f - valeur_jours))


def estimer_impact_financier(row, cout_prev, cout_correctif, horizon_jours=365):
    freq = row["frequence_moyenne_jours"]
    if freq <= 0:
        return None
    nb_visites_an = horizon_jours / freq
    cout_actuel = nb_visites_an * cout_prev + row["taux_correctif_entre_visites"] * nb_visites_an * cout_correctif

    classe = row["classe_frequence"]
    if classe == "Trop fréquent":
        freq_reco = freq * 2
    elif classe == "Insuffisant":
        freq_reco = freq * 0.7
    else:
        freq_reco = freq
    freq_reco = arrondir_frequence_standard(freq_reco)

    nb_visites_an_reco = horizon_jours / freq_reco
    taux_correctif_reco = row["taux_correctif_entre_visites"] * (0.5 if classe == "Insuffisant" else 1.0)
    cout_reco = nb_visites_an_reco * cout_prev + taux_correctif_reco * nb_visites_an_reco * cout_correctif

    return {
        "frequence_actuelle_jours": round(freq, 1),
        "frequence_recommandee_jours": round(freq_reco, 1),
        "cout_actuel_annuel_mad": round(cout_actuel, 0),
        "cout_recommande_annuel_mad": round(cout_reco, 0),
        "economie_estimee_mad": round(cout_actuel - cout_reco, 0),
    }


def entrainer_classifieur_frequence(ds, test_size=0.2, random_state=42):
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.svm import SVC
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score

    ds_enc = pd.get_dummies(ds, columns=["corps_metier", "categorie_travail"], prefix=["metier", "cat"])
    feature_cols = ["nb_visites_preventives", "frequence_moyenne_jours", "frequence_std_jours",
                     "nb_correctifs_total"] + [c for c in ds_enc.columns if c.startswith("metier_") or c.startswith("cat_")]

    X = ds_enc[feature_cols]
    y = ds_enc["classe_frequence"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=random_state, stratify=y)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    models = {
        "Régression Logistique": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=random_state),
        "SVM (RBF)": SVC(kernel="rbf", class_weight="balanced", random_state=random_state, probability=True),
        "Random Forest": RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=random_state),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=200, random_state=random_state),
        "MLP (Deep Learning)": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=500, random_state=random_state),
    }

    results = []
    fitted = {}
    for name, model in models.items():
        model.fit(X_train_s, y_train)
        y_pred = model.predict(X_test_s)
        results.append({
            "Modèle": name,
            "Accuracy": round(accuracy_score(y_test, y_pred), 3),
            "F1-macro": round(f1_score(y_test, y_pred, average="macro"), 3),
        })
        fitted[name] = (model, scaler, feature_cols)

    results_df = pd.DataFrame(results).sort_values("F1-macro", ascending=False)
    return results_df, fitted


if __name__ == "__main__":
    df_ot = pd.read_excel("/mnt/user-data/uploads/ot.xlsx")

    plans_actifs, type_travail_map = charger_reference_plans_actifs(
        "/mnt/user-data/uploads/plan_entretien.xlsx"
    )
    freq_officielle_map = charger_reference_frequence_officielle(
        "/mnt/user-data/uploads/frequence.xlsx"
    )
    print(f"Référentiel plans actifs : {len(plans_actifs)} couples")

    ds = construire_dataset_frequence(
        df_ot, plans_actifs=plans_actifs, type_travail_map=type_travail_map,
        freq_officielle_map=freq_officielle_map,
    )
    ds["classe_frequence"] = ds.apply(classer_frequence, axis=1)
    print(f"Triplets analysés : {len(ds)}")

    cout_prev, cout_correctif = calculer_couts_reference(df_ot)
    impacts = ds.apply(lambda r: estimer_impact_financier(r, cout_prev, cout_correctif), axis=1)
    impacts_df = pd.DataFrame(list(impacts))
    ds_final = pd.concat([ds.reset_index(drop=True), impacts_df], axis=1)
    ds_final.to_csv("/home/claude/frequence_maintenance_avec_impact.csv", index=False)

    print(f"Économie totale estimée : {ds_final['economie_estimee_mad'].sum():,.0f} MAD/an".replace(",", " "))
    print(ds_final["classe_frequence"].value_counts(normalize=True).round(3) * 100)

    results_df, fitted = entrainer_classifieur_frequence(ds)
    print(results_df.to_string(index=False))
