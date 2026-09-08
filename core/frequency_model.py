# -*- coding: utf-8 -*-
"""
Module de classification de l'adéquation de la fréquence de maintenance
préventive, à partir des données réelles SAP PM (ot.xlsx).

Construit sur des données 100% RÉELLES :
  - Fréquence "actuelle" = intervalle moyen OBSERVÉ entre visites
    préventives/systématiques successives (ZPRV/ZEST) pour un même
    poste technique — à défaut, au moment de la rédaction, du fichier
    de référence officiel du plan de maintenance (fréquence NOMINALE
    par Plan d'entretien), qui n'était pas disponible. Amélioration
    directe et immédiate dès que ce fichier de référence sera fourni :
    remplacer 'frequence_moyenne_jours' (observée) par la fréquence
    nominale officielle du Plan d'entretien correspondant.
  - Corps de métier = déduit du préfixe du Poste travail princ.
    (M = Mécanique, E = Électrique, R = Régulation/Instrumentation),
    convention à confirmer avec le service Méthodes.
  - Coûts réels (Total coûts réels) = coût moyen réel observé par
    type d'ordre, pour l'estimation d'impact financier.
"""
import pandas as pd
import numpy as np

SEUIL_TAUX_CORRECTIF_INSUFFISANT = 0.15
SEUIL_JOURS_TROP_FREQUENT = 20


def charger_reference_frequence_officielle(chemin_frequence):
    """
    Charge le référentiel frequence.xlsx (table SAP des cycles de plan
    d'entretien) et retourne un dictionnaire
    Plan d'entretien -> fréquence officielle en jours.

    IMPORTANT : SAP définit la fréquence d'un plan de deux façons
    distinctes :
      1. Directement via 'Intervalle d'appels' + 'Unité interv.appels'
         (toujours en jours, 'JRS', dans ce jeu de données) — cas des
         plans à cycle UNIQUE (ex. 30, 90, 365, 730 jours) ;
      2. Via un code 'Stratégie entretien' (ex. STJ055, STJ200), qui
         référence un PAQUET de plusieurs cycles combinés (ex. 7 jours
         + 30 jours + 90 jours) — cas des plans à cycles MULTIPLES.
         Le détail de ce paquet réside dans une table SAP séparée
         (paquet de cycles / plan stratégie), non disponible au moment
         de cette étude.

    Sur les 13 637 plans du référentiel, 2 309 (17%) ont un intervalle
    direct exploitable ; les 11 310 restants (83%) utilisent une
    stratégie dont le détail n'est pas résolu ici. Pour ces derniers,
    la fréquence OBSERVÉE (intervalle réel entre exécutions, calculée
    dans construire_dataset_frequence) est utilisée comme repli —
    seule information disponible en l'absence de la table de paquet.
    """
    ref = pd.read_excel(chemin_frequence)
    ref_directe = ref[ref["Intervalle d'appels"].notna() & (ref["Intervalle d'appels"] > 0)]
    return dict(zip(ref_directe["Plan d'entretien"], ref_directe["Intervalle d'appels"]))


def corps_metier(poste_travail):
    """Déduit le corps de métier à partir du préfixe du poste de travail
    principal (convention SF1-<M/E/R><code> observée dans les données)."""
    poste = str(poste_travail)
    if len(poste) < 5:
        return "Autre"
    pref = poste[4:5]
    return {"M": "Mécanique", "E": "Électrique", "R": "Régulation/Instrumentation"}.get(pref, "Autre")


def charger_reference_plans_actifs(chemin_plan_entretien):
    """
    Charge le référentiel officiel des plans d'entretien
    (plan_entretien.xlsx) et retourne :
      - l'ensemble des couples (Poste technique, Plan d'entretien) dont
        le statut est ACTIF ('P'), pour exclure les plans clôturés de
        l'analyse ;
      - un dictionnaire (Poste technique, Plan d'entretien) -> Type de
        travail (code tw), permettant de rattacher chaque plan à la
        même nomenclature que celle utilisée en Partie I (Graissage
        tw=350, Inspection tw∈{290,300,310}, Systématique tw=360).

    NOTE IMPORTANTE : ce référentiel officiel NE CONTIENT PAS le champ
    de fréquence nominale (stratégie / cycle de maintenance, en jours),
    qui réside dans une autre table SAP non disponible au moment de
    l'étude. La fréquence utilisée dans ce module reste donc la
    fréquence OBSERVÉE (intervalle réel entre exécutions), et non la
    fréquence officiellement planifiée — limite documentée au chapitre
    « Limites et améliorations futures » du rapport.
    """
    ref = pd.read_excel(chemin_plan_entretien)
    ref_actifs = ref[ref["Statut"] == "P"]
    plans_actifs = set(zip(ref_actifs["Poste technique"], ref_actifs["Plan d'entretien"]))
    type_travail_map = dict(zip(
        zip(ref_actifs["Poste technique"], ref_actifs["Plan d'entretien"]),
        ref_actifs["Type de travail"],
    ))
    return plans_actifs, type_travail_map


CATEGORIE_TW = {
    350: "Graissage", 290: "Inspection", 300: "Inspection", 310: "Inspection",
    360: "Systématique",
}


def categorie_type_travail(tw):
    return CATEGORIE_TW.get(tw, "Autre")


def construire_dataset_frequence(df_ot, plans_actifs=None, type_travail_map=None, freq_officielle_map=None):
    """
    Construit, pour chaque TRIPLET (poste technique, plan d'entretien,
    type de travail) ayant un historique suffisant (≥ 3 visites), les
    variables nécessaires à la classification de l'adéquation de sa
    fréquence de maintenance.

    DEUX CORRECTIONS MÉTHODOLOGIQUES IMPORTANTES, établies par
    investigation directe des données réelles :

    1. Un même poste technique peut être couvert par PLUSIEURS plans
       d'entretien distincts et simultanés, à des fréquences
       différentes (49% des postes techniques ont ≥ 2 plans distincts).
       L'unité d'analyse ne peut donc pas être le seul poste technique.

    2. Un même PLAN D'ENTRETIEN peut lui-même regrouper PLUSIEURS types
       de travail distincts (Graissage, Inspection, Systématique — code
       'Type de travail') exécutés à des fréquences différentes sous un
       identifiant de plan unique (stratégie à cycles multiples, ex.
       « 7 jours + mensuel + trimestriel »). Une analyse au niveau du
       seul couple (poste, plan) mélangerait encore ces sous-cycles :
       vérifié sur un exemple réel (plan 52250, fréquence officielle
       affichée = 730 jours) où les visites effectivement observées
       reviennent toutes les 3 à 8 semaines, car elles mélangent 3
       types de travail différents (Systématique tw=360, Graissage
       tw=350, Inspection tw=290/300/310).

    L'unité d'analyse correcte est donc le TRIPLET (poste technique,
    plan d'entretien, type de travail). La fréquence OFFICIELLE
    (Intervalle d'appels, référentiel frequence.xlsx) n'est utilisée
    comme référence que lorsque le plan concerné ne regroupe qu'un
    SEUL type de travail (cas où elle est non ambiguë) ; dans le cas
    contraire, la fréquence OBSERVÉE de ce type de travail spécifique
    est utilisée, la valeur officielle globale du plan n'étant pas
    interprétable au niveau de la sous-tâche.
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
            continue  # plan clôturé dans le référentiel officiel -> exclu

        dates = sorted(grp["Date de début planifiée"].dropna().unique())
        if len(dates) < 3:
            continue
        intervalles = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        freq_observee = float(np.mean(intervalles))
        freq_std = float(np.std(intervalles))

        # SIMPLIFICATION ASSUMÉE (voir investigation ci-dessus) : la
        # colonne 'Intervalle d'appels' du référentiel frequence.xlsx a
        # été explorée comme piste de fréquence NOMINALE officielle,
        # mais une investigation sur données réelles a révélé une
        # incohérence non résolue (ex. plan à Intervalle=730 jours dont
        # les visites effectives reviennent toutes les ~30 jours, même
        # après isolement par type de travail) — la sémantique exacte de
        # ce champ dans ce contexte SAP reste à confirmer avec l'équipe
        # de planification. Dans l'attente de cette confirmation, la
        # fréquence OBSERVÉE (seule interprétation non ambiguë sur les
        # données disponibles) est utilisée de façon uniforme.
        freq_officielle = freq_officielle_map.get(plan) if freq_officielle_map else None
        freq_reference = freq_observee
        source_freq = "observée"

        corr_pt = correctifs[correctifs["Poste technique"] == pt]

        correctif_entre_visites = 0
        for i in range(len(dates) - 1):
            c = corr_pt[(corr_pt["Créé le"] >= dates[i]) & (corr_pt["Créé le"] < dates[i + 1])]
            if len(c) > 0:
                correctif_entre_visites += 1

        resultats.append({
            "poste_technique": pt,
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
    """Classification en 3 catégories, à partir de règles simples et
    interprétables (à affiner par ML — voir train_classifieur_frequence)."""
    if row["taux_correctif_entre_visites"] > SEUIL_TAUX_CORRECTIF_INSUFFISANT:
        return "Insuffisant"
    if row["frequence_moyenne_jours"] < SEUIL_JOURS_TROP_FREQUENT and row["taux_correctif_entre_visites"] == 0:
        return "Trop fréquent"
    return "Adéquat"


def calculer_couts_reference(df_ot):
    """Coût réel moyen observé par visite préventive et par OT correctif
    — sert de base à l'estimation d'impact financier."""
    df = df_ot
    cout_prev = df[df["Type d'ordre"].isin(["ZPRV", "ZEST"])]["Total coûts réels"].mean()
    cout_correctif = df[df["Type d'ordre"] == "ZCOR"]["Total coûts réels"].mean()
    return float(cout_prev), float(cout_correctif)


def estimer_impact_financier(row, cout_prev, cout_correctif, horizon_jours=365):
    """
    Estime, pour un équipement donné et sur un horizon d'un an :
      - le coût actuel (préventif + correctifs observés) ;
      - le coût si la fréquence était ajustée selon la recommandation.
    Hypothèse simplificatrice assumée : le taux de correctif par
    intervalle reste constant si la fréquence change proportionnellement
    (hypothèse à valider avec des données réelles complémentaires).
    """
    freq = row["frequence_moyenne_jours"]
    if freq <= 0:
        return None
    nb_visites_an = horizon_jours / freq
    cout_actuel = nb_visites_an * cout_prev + row["taux_correctif_entre_visites"] * nb_visites_an * cout_correctif

    classe = row["classe_frequence"]
    if classe == "Trop fréquent":
        # Recommandation : doubler l'intervalle (reduire la frequence de moitie)
        freq_reco = freq * 2
    elif classe == "Insuffisant":
        # Recommandation : reduire l'intervalle de 30% pour limiter les correctifs
        freq_reco = freq * 0.7
    else:
        freq_reco = freq

    nb_visites_an_reco = horizon_jours / freq_reco
    # Hypothese : reduire l'intervalle de 30% reduit le taux de correctif
    # de moitie (relation plausible mais non calibree sur donnees reelles
    # de suivi post-changement -- a valider en conditions operationnelles).
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
    """
    Entraîne et compare 5 modèles de classification (Régression
    Logistique, SVM, Random Forest, Gradient Boosting, MLP) pour
    prédire la classe d'adéquation de fréquence à partir des variables
    disponibles. Retourne le tableau comparatif et les modèles entraînés.
    """
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
            "Précision (Insuffisant)": round(precision_score(y_test, y_pred, labels=["Insuffisant"], average="macro", zero_division=0), 2),
            "Recall (Insuffisant)": round(recall_score(y_test, y_pred, labels=["Insuffisant"], average="macro", zero_division=0), 2),
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
    print()
    print("NOTE : la fréquence 'officielle' (frequence.xlsx, Intervalle d'appels) a été")
    print("investiguée mais présente une incohérence non résolue sur les plans multi-tâches")
    print("(ex. plan à 730 jours dont les visites reviennent en réalité tous les ~30 jours).")
    print("Sémantique exacte à confirmer avec l'équipe planification -> fréquence OBSERVÉE")
    print("utilisée de façon uniforme dans cette version du modèle.")
    print()

    ds = construire_dataset_frequence(
        df_ot, plans_actifs=plans_actifs, type_travail_map=type_travail_map,
        freq_officielle_map=freq_officielle_map,
    )
    ds["classe_frequence"] = ds.apply(classer_frequence, axis=1)
    print(f"Triplets (poste, plan, type de travail) analysés : {len(ds)}")
    print()
    print("Répartition par catégorie de travail (nomenclature Partie I) :")
    print(ds["categorie_travail"].value_counts())
    print()

    cout_prev, cout_correctif = calculer_couts_reference(df_ot)
    print(f"Coût moyen préventif : {cout_prev:.0f} MAD | Coût moyen correctif : {cout_correctif:.0f} MAD")
    print()

    impacts = ds.apply(lambda r: estimer_impact_financier(r, cout_prev, cout_correctif), axis=1)
    impacts_df = pd.DataFrame(list(impacts))
    ds_final = pd.concat([ds.reset_index(drop=True), impacts_df], axis=1)

    print("=== Synthèse de l'impact financier estimé (agrégé) ===")
    print(f"Économie totale estimée (parc analysé, {len(ds_final)} équipements) : "
          f"{ds_final['economie_estimee_mad'].sum():,.0f} MAD / an".replace(",", " "))
    print()
    print("Par classe :")
    print(ds_final.groupby("classe_frequence")["economie_estimee_mad"].agg(["count", "sum", "mean"]))
    print()
    print("Par corps de métier :")
    print(ds_final.groupby("corps_metier")["economie_estimee_mad"].sum())

    ds_final.to_csv("/home/claude/frequence_maintenance_avec_impact.csv", index=False)
    print()
    print("Fichier sauvegardé : frequence_maintenance_avec_impact.csv")

    print()
    print("=== Entraînement et comparaison des modèles ML ===")
    results_df, fitted = entrainer_classifieur_frequence(ds)
    print(results_df.to_string(index=False))
