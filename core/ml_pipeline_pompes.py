# -*- coding: utf-8 -*-
"""
Pipeline de Machine Learning / Deep Learning — Détection d'anomalies
sur les pompes d'eau de mer (IP01, IP02, IP04).

Reproduit le protocole décrit au Chapitre 5 du rapport PFE :
- Split temporel 80/20 (pas de mélange aléatoire, pour éviter toute
  fuite d'information du futur vers le passé)
- Standardisation des variables (StandardScaler)
- Pondération des classes (class_weight='balanced')
- 5 modèles comparés : Régression Logistique, SVM (RBF), Random Forest,
  Gradient Boosting, MLP (Perceptron Multicouches = "Deep Learning")
- Métriques : Accuracy, Précision, Recall, F1-score, AUC ROC

Entrée attendue : feature_dataset.csv (colonnes : date, pompe, anomalie,
+ variables explicatives déjà calculées par le pipeline ETL — voir
preparation_donnees_ETL_ML.xlsx pour le détail des 14 opérations).
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, roc_curve,
)


def load_dataset(path="feature_dataset.csv"):
    """Charge le jeu de données final (issu du pipeline ETL) et le trie
    chronologiquement — indispensable pour un split temporel correct."""
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def temporal_split(df, target_col="anomalie", test_frac=0.2,
                    exclude_cols=("date", "pompe")):
    """
    Sépare le jeu de données en train/test de manière TEMPORELLE
    (les observations les plus anciennes en train, les plus récentes en
    test) — jamais un split aléatoire pour une série temporelle, sous
    peine de fuite d'information (le modèle "verrait" indirectement le
    futur pendant l'entraînement).
    """
    feature_cols = [c for c in df.columns if c not in exclude_cols and c != target_col]
    n_test = int(len(df) * test_frac)
    n_train = len(df) - n_test

    X_train = df.iloc[:n_train][feature_cols]
    X_test = df.iloc[n_train:][feature_cols]
    y_train = df.iloc[:n_train][target_col]
    y_test = df.iloc[n_train:][target_col]

    return X_train, X_test, y_train, y_test, feature_cols


def build_models():
    """
    Définit les 5 modèles comparés (4 Machine Learning + 1 Deep Learning).

    Note environnement : TensorFlow / PyTorch / XGBoost non disponibles
    (pas d'accès internet pour l'installation). Le volet "Deep Learning"
    est donc représenté par un Perceptron Multicouches (MLPClassifier,
    scikit-learn) — un vrai réseau de neurones, entraîné par
    rétropropagation du gradient, mais sans les architectures séquentielles
    avancées (LSTM/GRU) qui nécessiteraient TensorFlow/Keras ou PyTorch.
    Si ces bibliothèques deviennent disponibles, remplacer directement
    ce bloc par un modèle Keras/PyTorch équivalent — le reste du
    pipeline (split, scaling, métriques) reste inchangé.
    """
    return {
        "Régression Logistique": LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=42
        ),
        "SVM (noyau RBF)": SVC(
            kernel="rbf", probability=True, class_weight="balanced", random_state=42
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, class_weight="balanced", random_state=42, n_jobs=-1
        ),
        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=200, random_state=42
            # GradientBoostingClassifier (scikit-learn) ne supporte pas
            # class_weight nativement -> pondération gérée via sample_weight
            # au moment du fit (voir train_and_evaluate).
        ),
        "MLP (Deep Learning)": MLPClassifier(
            hidden_layer_sizes=(64, 32), max_iter=500, random_state=42,
            early_stopping=True,
        ),
    }


def train_and_evaluate(models, X_train, X_test, y_train, y_test):
    """Entraîne chaque modèle et calcule les 5 métriques d'évaluation."""
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    # Poids d'échantillon pour Gradient Boosting (pas de class_weight natif)
    n_pos, n_neg = (y_train == 1).sum(), (y_train == 0).sum()
    sample_weight = np.where(y_train == 1, n_neg / n_pos, 1.0)

    results = []
    fitted_models = {}
    for name, model in models.items():
        if name == "Gradient Boosting":
            model.fit(X_train_s, y_train, sample_weight=sample_weight)
        else:
            model.fit(X_train_s, y_train)

        y_pred = model.predict(X_test_s)
        y_proba = model.predict_proba(X_test_s)[:, 1] if hasattr(model, "predict_proba") else y_pred

        results.append({
            "Modèle": name,
            "Accuracy": round(accuracy_score(y_test, y_pred), 3),
            "Précision": round(precision_score(y_test, y_pred, zero_division=0), 2),
            "Recall": round(recall_score(y_test, y_pred, zero_division=0), 2),
            "F1-score": round(f1_score(y_test, y_pred, zero_division=0), 2),
            "AUC ROC": round(roc_auc_score(y_test, y_proba), 2),
        })
        fitted_models[name] = (model, scaler)

    return pd.DataFrame(results).sort_values("F1-score", ascending=False), fitted_models


def feature_importance(model, feature_cols, top_n=12):
    """Extrait l'importance des variables (modèles arborescents uniquement)."""
    if not hasattr(model, "feature_importances_"):
        return None
    imp = pd.Series(model.feature_importances_, index=feature_cols)
    return imp.sort_values(ascending=False).head(top_n)


# ═══════════════════════════════════════════════════════════════════
# NOUVEAU : classification du TYPE de panne (pas seulement anomalie/non)
# ═══════════════════════════════════════════════════════════════════
#
# Les données actuelles (feature_dataset.csv) ne contiennent qu'une
# étiquette binaire "anomalie" (0/1) — le type de panne simulé
# initialement (chapitre 3.5 du rapport) n'a pas été conservé dans
# l'export final. Cette section reconstruit un type de panne PLAUSIBLE
# à partir de la "signature" de déviation entre les 4 variables
# (quelle variable s'écarte le plus de son comportement normal, et
# selon quelle combinaison) — une approximation raisonnable en
# l'absence des vraies étiquettes de simulation, à valider/remplacer
# dès que des données réelles étiquetées seront disponibles.

TYPES_PANNE = [
    "Normal",
    "Désalignement / usure roulement",
    "Cavitation",
    "Colmatage filtre/crépine",
    "Fuite circuit",
    "Défaut électrique",
]


def build_baseline(df):
    """Calcule la moyenne et l'écart-type 'normal' (hors anomalie) de
    chaque variable brute — sert de référence pour détecter quelle
    variable s'écarte le plus de son comportement habituel."""
    baseline = {}
    for col in ["vibration", "courant", "debit", "pression"]:
        normal = df.loc[df["anomalie"] == 0, col]
        baseline[col] = (normal.mean(), normal.std())
    return baseline


def classer_type_panne(row, baseline):
    """
    Détermine un type de panne plausible pour une observation en
    anomalie, à partir de sa signature de déviation (z-score) sur les
    4 variables. Logique :
      - Débit très bas + pression haute  -> Colmatage filtre/crépine
      - Débit très bas + pression basse  -> Cavitation
      - Pression basse (sans chute forte de débit) -> Fuite circuit
      - Sinon : la variable au plus grand écart absolu détermine le
        type (vibration -> désalignement, courant -> électrique, etc.)
    """
    if row["anomalie"] == 0:
        return "Normal"

    z = {}
    for col in ["vibration", "courant", "debit", "pression"]:
        m, s = baseline[col]
        z[col] = (row[col] - m) / s if s > 0 else 0.0

    if z["debit"] < -1.2 and z["pression"] > 1.2:
        return "Colmatage filtre/crépine"
    if z["debit"] < -1.2 and z["pression"] < -0.8:
        return "Cavitation"
    if z["pression"] < -1.2 and z["debit"] > -0.8:
        return "Fuite circuit"

    dominant = max(z, key=lambda k: abs(z[k]))
    mapping = {
        "vibration": "Désalignement / usure roulement",
        "courant": "Défaut électrique",
        "pression": "Fuite circuit",
        "debit": "Colmatage filtre/crépine",
    }
    return mapping[dominant]


def add_type_panne_column(df):
    """Ajoute la colonne 'type_panne' au DataFrame (voir classer_type_panne)."""
    baseline = build_baseline(df)
    df = df.copy()
    df["type_panne"] = df.apply(lambda r: classer_type_panne(r, baseline), axis=1)
    return df


def train_classifieur_type_panne(df, feature_cols, test_frac=0.2, random_state=42):
    """
    Entraîne un classifieur MULTI-CLASSES (Random Forest) qui prédit,
    pour une observation en anomalie, le type de panne le plus probable
    parmi TYPES_PANNE (hors 'Normal', qui n'a pas de sens à prédire ici).

    Retourne (model, scaler, rapport_texte).
    """
    from sklearn.metrics import classification_report

    df = add_type_panne_column(df) if "type_panne" not in df.columns else df
    df_anom = df[df["anomalie"] == 1].sort_values("date")

    n_test = max(1, int(len(df_anom) * test_frac))
    n_train = len(df_anom) - n_test
    train = df_anom.iloc[:n_train]
    test = df_anom.iloc[n_train:]

    scaler = StandardScaler()
    X_train = scaler.fit_transform(train[feature_cols])
    X_test = scaler.transform(test[feature_cols])
    y_train = train["type_panne"]
    y_test = test["type_panne"]

    model = RandomForestClassifier(n_estimators=200, random_state=random_state, class_weight="balanced")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    rapport = classification_report(y_test, y_pred, zero_division=0)

    return model, scaler, rapport


def predire_type_panne(model, scaler, feature_cols, row):
    """Prédit le type de panne le plus probable pour UNE observation
    donnée (ligne de DataFrame), avec sa probabilité."""
    X = row[feature_cols].values.reshape(1, -1)
    X_s = scaler.transform(X)
    proba = model.predict_proba(X_s)[0]
    classes = model.classes_
    idx_max = proba.argmax()
    return classes[idx_max], round(proba[idx_max] * 100, 1)


if __name__ == "__main__":
    df = load_dataset("feature_dataset.csv")
    X_train, X_test, y_train, y_test, feature_cols = temporal_split(df)

    print(f"Train : {len(X_train)} observations ({y_train.sum()} anomalies)")
    print(f"Test  : {len(X_test)} observations ({y_test.sum()} anomalies)")
    print()

    models = build_models()
    results_df, fitted = train_and_evaluate(models, X_train, X_test, y_train, y_test)

    print("=== Résultats comparatifs (triés par F1-score décroissant) ===")
    print(results_df.to_string(index=False))
    print()

    best_name = results_df.iloc[0]["Modèle"]
    print(f"Meilleur modèle (F1-score) : {best_name}")

    rf_model, _ = fitted.get("Random Forest", (None, None))
    if rf_model is not None:
        print()
        print("=== Importance des variables (Random Forest) ===")
        print(feature_importance(rf_model, feature_cols))

    # ── Type de panne ──
    print()
    print("=== Classification du type de panne (parmi les anomalies) ===")
    df_typed = add_type_panne_column(df)
    print(df_typed[df_typed["anomalie"] == 1]["type_panne"].value_counts())
    type_model, type_scaler, rapport = train_classifieur_type_panne(df_typed, feature_cols)
    print()
    print(rapport)

