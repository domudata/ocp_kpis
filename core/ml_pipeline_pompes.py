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
