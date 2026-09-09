# -*- coding: utf-8 -*-
"""
Onglet "Fréquence de Maintenance" — lit plan_entretien.xlsx et
frequence.xlsx directement à la racine du dépôt (même principe que
ot.xlsx / avis.xlsx), sans bouton d'upload dans l'application.

À placer dans : pages/frequence_maintenance.py
Utilise : core/frequency_model.py
Fichiers requis à la racine du dépôt (à committer sur GitHub, comme
ot.xlsx et avis.xlsx) : plan_entretien.xlsx, frequence.xlsx
"""
import os
import streamlit as st
import pandas as pd
import numpy as np

from core.frequency_model import (
    charger_reference_plans_actifs, charger_reference_frequence_officielle,
    construire_dataset_frequence, classer_frequence, calculer_couts_reference,
    estimer_impact_financier, entrainer_classifieur_frequence,
)

COULEUR_CLASSE = {"Adéquat": "#10B981", "Insuffisant": "#EF4444", "Trop fréquent": "#F59E0B"}
EMOJI_CLASSE = {"Adéquat": "🟢", "Insuffisant": "🔴", "Trop fréquent": "🟠"}


def _carte_kpi(col, label, valeur, couleur, sous_texte=""):
    col.markdown(
        f"""<div style="background:{couleur}15;border:1px solid {couleur}40;border-radius:10px;
        padding:16px 14px;text-align:center;">
            <div style="font-size:12px;color:#64748B;font-weight:700;text-transform:uppercase;
            letter-spacing:0.5px;margin-bottom:6px;">{label}</div>
            <div style="font-size:28px;font-weight:800;color:{couleur};line-height:1.1;">{valeur}</div>
            <div style="font-size:11px;color:#64748B;margin-top:4px;">{sous_texte}</div>
        </div>""",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner="Analyse de la fréquence de maintenance en cours...")
def _calculer_pipeline_complet(df_ot, chemin_plan, chemin_freq):
    plans_actifs, type_travail_map = charger_reference_plans_actifs(chemin_plan)
    freq_officielle_map = charger_reference_frequence_officielle(chemin_freq)

    ds = construire_dataset_frequence(
        df_ot, plans_actifs=plans_actifs, type_travail_map=type_travail_map,
        freq_officielle_map=freq_officielle_map,
    )
    if ds.empty:
        return None, None

    ds["classe_frequence"] = ds.apply(classer_frequence, axis=1)
    cout_prev, cout_correctif = calculer_couts_reference(df_ot)
    impacts = ds.apply(lambda r: estimer_impact_financier(r, cout_prev, cout_correctif), axis=1)
    impacts_df = pd.DataFrame(list(impacts))
    ds_final = pd.concat([ds.reset_index(drop=True), impacts_df], axis=1)

    results_df, _ = entrainer_classifieur_frequence(ds)
    return ds_final, results_df


def render_frequence_maintenance_tab(df_ot, chemin_plan="poste_maintenace.xlsx", chemin_freq="freq_plan_maint.xlsx"):
    """
    df_ot : DataFrame des ordres de travail (réutilisé depuis
    l'application principale — ot.xlsx déjà chargé, pas de nouvel
    upload nécessaire).
    chemin_plan / chemin_freq : fichiers attendus à la racine du dépôt,
    committés sur GitHub comme ot.xlsx et avis.xlsx.
    Noms réels utilisés : poste_maintenace.xlsx, freq_plan_maint.xlsx
    """
    st.markdown("### 🔄 Fréquence de Maintenance Préventive")
    st.caption(
        "Classification par Machine Learning de l'adéquation de la fréquence de maintenance "
        "préventive de chaque équipement — données réelles SAP PM."
    )

    if not os.path.exists(chemin_plan) or not os.path.exists(chemin_freq):
        st.warning(
            f"⚠️ Fichier(s) manquant(s) à la racine du dépôt : "
            f"{'`' + chemin_plan + '` ' if not os.path.exists(chemin_plan) else ''}"
            f"{'`' + chemin_freq + '`' if not os.path.exists(chemin_freq) else ''}. "
            f"Committez-les sur GitHub, comme ot.xlsx et avis.xlsx."
        )
        return

    if df_ot is None or df_ot.empty:
        st.warning("⚠️ Aucune donnée OT disponible. Chargez d'abord ot.xlsx / avis.xlsx via le panneau latéral.")
        return

    ds, results_modeles = _calculer_pipeline_complet(df_ot, chemin_plan, chemin_freq)

    if ds is None or ds.empty:
        st.error("❌ Aucun triplet (poste, plan, type de travail) exploitable trouvé.")
        return

    n_total = len(ds)
    n_adequat = (ds["classe_frequence"] == "Adéquat").sum()
    n_insuffisant = (ds["classe_frequence"] == "Insuffisant").sum()
    n_trop = (ds["classe_frequence"] == "Trop fréquent").sum()
    economie_totale = ds["economie_estimee_mad"].sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    _carte_kpi(c1, "Analysés", f"{n_total:,}".replace(",", " "), "#1E3A5F", "triplets poste+plan+travail")
    _carte_kpi(c2, "🟢 Adéquat", f"{n_adequat/n_total*100:.0f}%", COULEUR_CLASSE["Adéquat"], f"{n_adequat:,}".replace(",", " "))
    _carte_kpi(c3, "🔴 Insuffisant", f"{n_insuffisant/n_total*100:.0f}%", COULEUR_CLASSE["Insuffisant"], f"{n_insuffisant:,}".replace(",", " "))
    _carte_kpi(c4, "🟠 Trop fréquent", f"{n_trop/n_total*100:.0f}%", COULEUR_CLASSE["Trop fréquent"], f"{n_trop:,}".replace(",", " "))
    _carte_kpi(c5, "💰 Économie estimée", f"{economie_totale/1e6:.1f} M MAD", "#0D9488", "par an (parc analysé)")

    st.markdown("---")

    with st.expander("🧠 Performance du modèle de classification (5 modèles comparés)", expanded=False):
        st.dataframe(results_modeles, use_container_width=True, hide_index=True)

    with st.expander("🔍 Méthodologie", expanded=False):
        st.caption(
            "Unité d'analyse : triplet (poste technique, plan d'entretien, type de travail). "
            "Fréquence recommandée arrondie aux valeurs standard utilisées en pratique "
            "(7, 15, 30, 60, 90, 180, 365, 730 jours). Fréquence basée sur l'intervalle OBSERVÉ "
            "entre exécutions réelles — l'« Intervalle d'appels » du référentiel officiel présente "
            "une ambiguïté non résolue sur les plans multi-tâches (voir rapport, chapitre Limites)."
        )

    st.markdown("---")
    st.markdown("#### 🔧 Répartition par corps de métier")
    tab_metier = ds.groupby(["corps_metier", "classe_frequence"]).size().unstack(fill_value=0)
    for c in ["Adéquat", "Insuffisant", "Trop fréquent"]:
        if c not in tab_metier.columns:
            tab_metier[c] = 0
    tab_metier = tab_metier[["Adéquat", "Insuffisant", "Trop fréquent"]]
    tab_metier_pct = tab_metier.div(tab_metier.sum(axis=1), axis=0) * 100

    affichage = tab_metier_pct.round(0).astype(int).astype(str) + "%"
    affichage.insert(0, "Total équipements", tab_metier.sum(axis=1))
    st.dataframe(
        affichage.reset_index().rename(columns={"corps_metier": "Corps de métier"}),
        use_container_width=True, hide_index=True,
    )
    st.bar_chart(tab_metier_pct)

    st.markdown("---")

    # CORRIGÉ : ajout de "Désignation" (description avis/OT) et
    # "Désignation du poste technique" (description équipement) à côté
    # de "Poste technique" ; colonne "Économie" retirée de ce tableau.
    st.markdown("#### 📋 Détail par équipement")

    c1, c2 = st.columns(2)
    filtre_metier = c1.selectbox("Filtrer par corps de métier", ["Tous"] + sorted(ds["corps_metier"].unique().tolist()))
    filtre_classe = c2.selectbox("Filtrer par classe", ["Toutes"] + list(COULEUR_CLASSE.keys()))

    ds_filtre = ds.copy()
    if filtre_metier != "Tous":
        ds_filtre = ds_filtre[ds_filtre["corps_metier"] == filtre_metier]
    if filtre_classe != "Toutes":
        ds_filtre = ds_filtre[ds_filtre["classe_frequence"] == filtre_classe]

    ds_filtre = ds_filtre.sort_values("frequence_actuelle_jours", ascending=False)
    ds_affiche = ds_filtre[[
        "poste_technique", "designation", "designation_poste_technique", "corps_metier",
        "categorie_travail", "frequence_actuelle_jours", "frequence_recommandee_jours",
        "classe_frequence",
    ]].rename(columns={
        "poste_technique": "Poste technique", "designation": "Désignation",
        "designation_poste_technique": "Désignation du poste technique",
        "corps_metier": "Corps de métier", "categorie_travail": "Catégorie",
        "frequence_actuelle_jours": "Fréq. actuelle (j)",
        "frequence_recommandee_jours": "Fréq. recommandée (j)", "classe_frequence": "Classe",
    })
    ds_affiche["Classe"] = ds_affiche["Classe"].apply(lambda c: f"{EMOJI_CLASSE.get(c,'')} {c}")

    st.dataframe(ds_affiche, use_container_width=True, hide_index=True, height=400)
    st.caption(f"{len(ds_filtre):,} équipement(s) affiché(s) sur {n_total:,}".replace(",", " "))

    st.download_button(
        "⬇️ Télécharger l'analyse complète (CSV)",
        data=ds.to_csv(index=False).encode("utf-8"),
        file_name="frequence_maintenance_avec_impact.csv",
        mime="text/csv",
        use_container_width=True,
    )
