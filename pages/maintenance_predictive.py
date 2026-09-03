# -*- coding: utf-8 -*-
"""
Onglet "Maintenance Prédictive" — jumeau numérique des pompes.

À placer dans : pages/maintenance_predictive.py
Utilise : core/ml_pipeline_pompes.py (déjà fourni)

Ajout minimal requis dans app.py (voir instructions à la fin de ce fichier,
en commentaire).
"""
import os
import streamlit as st
import pandas as pd
import numpy as np

from core.ml_pipeline_pompes import (
    load_dataset, temporal_split, build_models, train_and_evaluate,
    feature_importance, add_type_panne_column, train_classifieur_type_panne,
    predire_type_panne,
)

STATUS_COLORS = {"normal": "#10B981", "surveillance": "#F59E0B", "alerte": "#EF4444"}


@st.cache_data(show_spinner="Entraînement des modèles en cours...")
def _get_trained_models(path):
    """Mis en cache : ne réentraîne que si le fichier de données change."""
    df = load_dataset(path)
    X_train, X_test, y_train, y_test, feature_cols = temporal_split(df)
    models = build_models()
    results_df, fitted = train_and_evaluate(models, X_train, X_test, y_train, y_test)

    # Type de panne (nouveau) : entraîné uniquement sur les observations
    # en anomalie, avec un type reconstruit par signature de déviation
    # (voir core/ml_pipeline_pompes.py — pas de vraie étiquette de type
    # disponible dans les données actuelles).
    df_typed = add_type_panne_column(df)
    type_model, type_scaler, type_rapport = train_classifieur_type_panne(df_typed, feature_cols)

    return df_typed, results_df, fitted, feature_cols, type_model, type_scaler, type_rapport


def _risque_pour_poste(df, fitted, feature_cols, pompe_id, model_name="Random Forest"):
    """Calcule le risque prédit (probabilité de la classe 'anomalie') pour
    la dernière observation disponible d'une pompe donnée."""
    model, scaler = fitted[model_name]
    sub = df[df["pompe"] == pompe_id].sort_values("date")
    if sub.empty:
        return None, None
    last_row = sub.iloc[-1]
    X = last_row[feature_cols].values.reshape(1, -1)
    X_s = scaler.transform(X)
    proba = model.predict_proba(X_s)[0, 1] if hasattr(model, "predict_proba") else 0.0
    return last_row, round(proba * 100, 1)


def _statut_depuis_risque(risque_pct):
    if risque_pct is None:
        return "normal"
    if risque_pct >= 50:
        return "alerte"
    if risque_pct >= 15:
        return "surveillance"
    return "normal"


def render_maintenance_predictive_tab(dataset_path="feature_dataset.csv"):
    st.markdown("### 🔧 Maintenance Prédictive — Jumeau numérique des pompes")

    if not os.path.exists(dataset_path):
        st.warning(
            f"⚠️ Fichier `{dataset_path}` introuvable. Ce module nécessite le jeu de "
            f"données de capteurs (voir Partie II du rapport, chapitre 3 — ETL). "
            f"Une fois le serveur de collecte (chapitre 7) en place, ce fichier sera "
            f"généré automatiquement plutôt que fourni manuellement."
        )
        return

    df, results_df, fitted, feature_cols, type_model, type_scaler, type_rapport = _get_trained_models(dataset_path)

    # ── Tableau comparatif des modèles (repris du rapport, chapitre 5) ──
    with st.expander("📊 Comparaison des modèles ML / Deep Learning", expanded=False):
        st.dataframe(results_df, use_container_width=True, hide_index=True)
        best_model_name = results_df.iloc[0]["Modèle"]
        st.caption(f"Modèle utilisé pour les prédictions ci-dessous : **{best_model_name}**")

        rf_model, _ = fitted.get("Random Forest", (None, None))
        if rf_model is not None:
            st.markdown("**Importance des variables (Random Forest)**")
            imp = feature_importance(rf_model, feature_cols, top_n=10)
            st.bar_chart(imp)

    st.markdown("---")

    # ── Tableau des pompes (jumeau numerique) ──
    # CORRIGÉ : l'affichage en colonnes côte à côte (st.columns) ne
    # s'adapte pas bien aux écrans étroits (mobile) — grands espaces
    # vides, éléments mal alignés. Remplacé par un tableau simple,
    # qui reste lisible quel que soit le format d'écran.
    model_choice = "Random Forest"  # modele retenu par defaut (voir rapport 5.5)

    pompes = sorted(df["pompe"].unique())
    rows = []
    risques = {}
    for pompe_id in pompes:
        last_row, risque = _risque_pour_poste(df, fitted, feature_cols, pompe_id, model_choice)
        risques[pompe_id] = (last_row, risque)
        statut = _statut_depuis_risque(risque)
        emoji = {"normal": "🟢", "surveillance": "🟠", "alerte": "🔴"}[statut]
        if last_row is not None:
            # Type de panne le plus probable — affiché seulement si un
            # risque non négligeable est détecté (sinon peu de sens de
            # prédire un "type" pour une pompe en état normal).
            if risque >= 15:
                type_pred, type_proba = predire_type_panne(type_model, type_scaler, feature_cols, last_row)
                type_txt = f"{type_pred} ({type_proba}%)"
            else:
                type_txt = "—"
            rows.append({
                "Pompe": f"IP0{pompe_id}",
                "Statut": f"{emoji} {statut.capitalize()}",
                "Vibration (mm/s)": round(last_row["vibration"], 1),
                "Courant (A)": round(last_row["courant"], 1),
                "Risque prédit (%)": risque,
                "Type de panne probable": type_txt,
            })

    st.markdown("#### 🖥️ Jumeau numérique — état actuel des pompes")
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True, hide_index=True,
        column_config={
            "Risque prédit (%)": st.column_config.ProgressColumn(
                "Risque prédit (%)", min_value=0, max_value=100, format="%d%%",
            ),
        },
    )
    st.caption(
        "🟢 Normal (risque < 15%) · 🟠 Surveillance (15-50%) · 🔴 Alerte prédictive (≥ 50%) "
        "— risque de défaillance estimé par le modèle sur la dernière mesure disponible."
    )

    with st.expander("🔍 Détail du classifieur de type de panne", expanded=False):
        st.caption(
            "⚠️ Le type de panne est reconstruit à partir de la signature de déviation "
            "entre les 4 mesures (quelle variable s'écarte le plus de la normale), en "
            "l'absence d'étiquette de type réelle dans les données actuelles — voir "
            "core/ml_pipeline_pompes.py, fonction classer_type_panne()."
        )
        st.code(type_rapport, language="text")

    st.markdown("---")

    # ── Module de simulation what-if ──
    st.markdown("#### 🧪 Module de simulation (what-if)")
    st.caption(
        "⚠️ **Simulation uniquement — non connecté aux actionneurs réels.** "
        "Voir rapport, chapitre 8.3."
    )

    sim_pompe = st.selectbox("Pompe à simuler", pompes, format_func=lambda p: f"IP0{p}")
    last_row, _ = risques[sim_pompe]

    if last_row is not None:
        debit_actuel = float(last_row["debit"])
        debit_simule = st.slider(
            "Débit simulé (m³/h)",
            min_value=float(debit_actuel * 0.5),
            max_value=float(debit_actuel * 1.5),
            value=debit_actuel,
            step=50.0,
        )

        # Construire une observation modifiee : on remplace le debit (et ses
        # derivees directes) par la valeur simulee, en gardant le reste
        # inchange -- approximation simple, suffisante pour une demonstration.
        sim_row = last_row.copy()
        ratio = debit_simule / debit_actuel if debit_actuel else 1.0
        for col in feature_cols:
            if col.startswith("debit"):
                sim_row[col] = sim_row[col] * ratio

        model, scaler = fitted[model_choice]
        X_sim = sim_row[feature_cols].values.reshape(1, -1)
        X_sim_s = scaler.transform(X_sim)
        proba_sim = model.predict_proba(X_sim_s)[0, 1] * 100 if hasattr(model, "predict_proba") else 0.0

        c1, c2, c3 = st.columns(3)
        c1.metric("Vibration estimée", f"{sim_row['vibration']:.1f} mm/s")
        c2.metric("Courant estimé", f"{sim_row['courant']:.1f} A")
        c3.metric("Risque de défaillance estimé", f"{proba_sim:.0f}%",
                    delta=f"{proba_sim - risques[sim_pompe][1]:+.0f} pts vs actuel",
                    delta_color="inverse")


# ═══════════════════════════════════════════════════════════════════
# INSTRUCTIONS D'INTÉGRATION DANS app.py
# ═══════════════════════════════════════════════════════════════════
#
# 1) Ajouter l'import en haut d'app.py, avec les autres imports de pages :
#
#    from pages.maintenance_predictive import render_maintenance_predictive_tab
#
# 2) Ajouter un 8e onglet dans la liste des tabs (chercher `tabs = st.tabs([`) :
#
#    tabs = st.tabs([
#        "🏠 Tableau de Bord", "📈 Performance", "✅ Qualite", "📂 Backlog",
#        "📋 Suivi & Evolution", "🎯 Plan d'action", "🤖 Assistant IA",
#        "🔧 Maintenance Prédictive",          # <-- NOUVEAU
#    ])
#
# 3) Ajouter le bloc correspondant (à la fin, après `with tabs[6]:` de
#    l'Assistant IA) :
#
#    with tabs[7]:
#        render_maintenance_predictive_tab("feature_dataset.csv")
#
# Rien d'autre à changer : le module gère lui-même son cache
# (@st.cache_data), donc il ne recalculera les modèles que si le fichier
# feature_dataset.csv change.
