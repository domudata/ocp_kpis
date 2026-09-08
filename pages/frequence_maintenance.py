# -*- coding: utf-8 -*-
"""
Onglet "Fréquence de Maintenance" — classification ML de l'adéquation
de la fréquence de maintenance préventive, sur données réelles SAP PM.

À placer dans : pages/frequence_maintenance.py
Utilise : core/frequency_model.py (à placer dans core/)
Données : frequence_maintenance_avec_impact.csv (déjà calculé, à la
racine du dépôt — ou recalculé à la volée si absent, voir plus bas).
"""
import os
import streamlit as st
import pandas as pd
import numpy as np


COULEUR_CLASSE = {"Adéquat": "#10B981", "Insuffisant": "#EF4444", "Trop fréquent": "#F59E0B"}
EMOJI_CLASSE = {"Adéquat": "🟢", "Insuffisant": "🔴", "Trop fréquent": "🟠"}


@st.cache_data(show_spinner="Chargement du modèle de fréquence de maintenance...")
def _charger_donnees(chemin_csv):
    if not os.path.exists(chemin_csv):
        return None
    return pd.read_csv(chemin_csv)


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


def render_frequence_maintenance_tab(chemin_csv="frequence_maintenance_avec_impact.csv"):
    st.markdown("### 🔄 Fréquence de Maintenance Préventive")
    st.caption(
        "Classification par Machine Learning de l'adéquation de la fréquence de maintenance "
        "préventive de chaque équipement — données réelles SAP PM (ot.xlsx)."
    )

    ds = _charger_donnees(chemin_csv)
    if ds is None:
        st.warning(
            f"⚠️ Fichier `{chemin_csv}` introuvable. Générez-le via `core/frequency_model.py` "
            f"et placez-le à la racine du dépôt."
        )
        return

    # ══════════════════════════════════════════════════════════════
    # 1) Cartes de synthèse
    # ══════════════════════════════════════════════════════════════
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
    _carte_kpi(c5, "💰 Économie estimée", f"{economie_totale/1e6:.1f} M MAD", "#0D9488", "par an")

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════
    # 2) Entonnoir de sélection des données (transparence méthodologique)
    # ══════════════════════════════════════════════════════════════
    with st.expander("🔍 D'où viennent ces chiffres ? (entonnoir de sélection des données)", expanded=False):
        st.caption(
            "Sur les **12 156 plans d'entretien** présents dans ot.xlsx, tous ne peuvent pas "
            "être analysés : un historique minimum est nécessaire pour calculer une fréquence "
            "et un écart-type fiables."
        )
        etapes = pd.DataFrame([
            {"Étape": "Plans d'entretien dans ot.xlsx (tous types d'ordre)", "Nombre": 12156},
            {"Étape": "… dont ordres préventifs/systématiques (ZPRV/ZEST)", "Nombre": 10130},
            {"Étape": "… avec ≥ 3 dates d'exécution distinctes (seuil minimal)", "Nombre": 6098},
            {"Étape": "… répartis par type de travail (triplets analysés)", "Nombre": 6559},
        ])
        st.dataframe(etapes, use_container_width=True, hide_index=True)
        st.caption(
            "**4 032 plans exclus** faute d'historique suffisant (< 3 exécutions enregistrées "
            "sur la période) — limite méthodologique nécessaire, pas une erreur : il faut au "
            "moins 2 intervalles pour calculer une moyenne et un écart-type significatifs."
        )

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════
    # 3) Analyse par corps de métier
    # ══════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════
    # 4) Table détaillée filtrable
    # ══════════════════════════════════════════════════════════════
    st.markdown("#### 📋 Détail par équipement")

    c1, c2 = st.columns(2)
    filtre_metier = c1.selectbox("Filtrer par corps de métier", ["Tous"] + sorted(ds["corps_metier"].unique().tolist()))
    filtre_classe = c2.selectbox("Filtrer par classe", ["Toutes"] + list(COULEUR_CLASSE.keys()))

    ds_filtre = ds.copy()
    if filtre_metier != "Tous":
        ds_filtre = ds_filtre[ds_filtre["corps_metier"] == filtre_metier]
    if filtre_classe != "Toutes":
        ds_filtre = ds_filtre[ds_filtre["classe_frequence"] == filtre_classe]

    ds_filtre = ds_filtre.sort_values("economie_estimee_mad", ascending=False)
    ds_affiche = ds_filtre[[
        "poste_technique", "plan_entretien", "categorie_travail", "corps_metier",
        "frequence_actuelle_jours", "frequence_recommandee_jours",
        "classe_frequence", "economie_estimee_mad",
    ]].rename(columns={
        "poste_technique": "Poste technique", "plan_entretien": "Plan", "categorie_travail": "Catégorie",
        "corps_metier": "Corps de métier", "frequence_actuelle_jours": "Fréq. actuelle (j)",
        "frequence_recommandee_jours": "Fréq. recommandée (j)", "classe_frequence": "Classe",
        "economie_estimee_mad": "Économie (MAD/an)",
    })
    ds_affiche["Classe"] = ds_affiche["Classe"].apply(lambda c: f"{EMOJI_CLASSE.get(c,'')} {c}")

    st.dataframe(
        ds_affiche, use_container_width=True, hide_index=True, height=380,
        column_config={
            "Économie (MAD/an)": st.column_config.NumberColumn("Économie (MAD/an)", format="%d MAD"),
        },
    )
    st.caption(f"{len(ds_filtre):,} équipement(s) affiché(s) sur {n_total:,}".replace(",", " "))

    st.markdown("---")
    st.caption(
        "⚠️ Fréquence basée sur l'intervalle OBSERVÉ entre exécutions réelles (et non sur un "
        "référentiel de fréquence nominale officielle, dont l'interprétation pour les plans "
        "multi-tâches reste à confirmer avec l'équipe planification — voir rapport, section limites)."
    )
