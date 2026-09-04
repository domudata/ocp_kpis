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
from core.vibration_analysis import (
    toutes_frequences_pompe, generer_spectre, diagnostiquer_spectre,
    z_score_vibration_journaliere, necessite_analyse_spectrale, historique_7_jours,
    POINTS_MESURE, DIRECTIONS,
)

STATUS_COLORS = {"normal": "#10B981", "surveillance": "#F59E0B", "alerte": "#EF4444"}


def _generer_rapport_intervention(pompe_id, point, direction, etat):
    """Génère un rapport PDF simple comparant l'état avant/après
    intervention pour un point/direction de mesure donné."""
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    NAVY = colors.HexColor("#1E3A5F")
    GREEN = colors.HexColor("#10B981")
    ORANGE = colors.HexColor("#F59E0B")
    RED = colors.HexColor("#EF4444")
    GREY = colors.HexColor("#64748B")
    couleur_gravite = {"normal": GREEN, "surveillance": ORANGE, "alerte": RED}

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitreR", fontSize=18, textColor=NAVY, fontName="Helvetica-Bold", spaceAfter=10))
    styles.add(ParagraphStyle(name="H2R", fontSize=13, textColor=NAVY, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="CorpsR", fontSize=10, fontName="Helvetica", spaceAfter=6))

    story = [
        Paragraph(f"Rapport d'intervention — Pompe IP0{pompe_id}", styles["TitreR"]),
        Paragraph(f"Point de mesure : {point} — Direction : {direction}", styles["CorpsR"]),
        Spacer(1, 10),
    ]

    for phase_key, phase_label in [("avant", "État AVANT intervention"), ("apres", "État APRÈS intervention")]:
        d = etat.get(phase_key, {})
        story.append(Paragraph(phase_label, styles["H2R"]))
        cell_style = ParagraphStyle(name=f"Cell_{phase_key}", fontSize=9.5, fontName="Helvetica", leading=12)
        cell_style_white = ParagraphStyle(name=f"CellW_{phase_key}", fontSize=9.5, fontName="Helvetica", leading=12, textColor=colors.white)
        rows = [
            ["Date de relevé", Paragraph(d.get("date", "—"), cell_style)],
            ["Amplitude max mesurée", Paragraph(f"{d.get('amplitude_max', '—')} mm/s", cell_style)],
            ["Température", Paragraph(f"{d.get('temperature', '—')} °C", cell_style)],
            ["Diagnostic", Paragraph(d.get("diagnostic", "—"), cell_style_white)],
        ]
        t = Table(rows, colWidths=[5 * cm, 11 * cm])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (1, 3), (1, 3), couleur_gravite.get(d.get("gravite", "normal"), GREY)),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


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
    pompes_alerte_spectrale = []
    for pompe_id in pompes:
        last_row, risque = _risque_pour_poste(df, fitted, feature_cols, pompe_id, model_choice)
        risques[pompe_id] = (last_row, risque)
        statut = _statut_depuis_risque(risque)

        # NOUVEAU : contrôle du seuil sur la mesure journalière brute
        # (z-score > 3 par rapport à la moyenne normale de la pompe) —
        # déclenche le besoin d'une analyse spectrale détaillée,
        # indépendamment du risque prédit par le modèle ML.
        _, z_vib, _ = z_score_vibration_journaliere(df, pompe_id)
        analyse_requise = z_vib > 3.0
        if analyse_requise:
            statut = "alerte"  # une vibration journalière anormale prime sur le reste
            pompes_alerte_spectrale.append(pompe_id)

        emoji = {"normal": "🟢", "surveillance": "🟠", "alerte": "🔴"}[statut]
        if last_row is not None:
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
                "Analyse spectrale requise": "⚠️ Oui" if analyse_requise else "—",
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
        "🟢 Normal (fonctionne bien) · 🟠 Surveillance (problème mineur) · 🔴 Alerte (problème grave) "
        "— statut basé sur le risque prédit par le modèle ET sur le dépassement de seuil de la "
        "mesure journalière brute (vibration)."
    )

    if pompes_alerte_spectrale:
        noms = ", ".join(f"IP0{p}" for p in pompes_alerte_spectrale)
        st.error(
            f"⚠️ **{noms}** : la dernière mesure de vibration journalière dépasse le seuil "
            f"normal (écart > 3 écarts-types) — une **analyse spectrale détaillée** est requise "
            f"(voir section ci-dessous)."
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

    # ═══════════════════════════════════════════════════════════════
    # NOUVEAU : Analyse spectrale détaillée (7 jours + spectre + diagnostic)
    # ═══════════════════════════════════════════════════════════════
    st.markdown("#### 📡 Analyse spectrale détaillée")
    st.caption(
        "Déclenchée automatiquement quand la vibration journalière dépasse le seuil "
        "(3 écarts-types) — consultable aussi manuellement pour n'importe quelle pompe."
    )

    default_idx = pompes.index(pompes_alerte_spectrale[0]) if pompes_alerte_spectrale else 0
    spec_pompe = st.selectbox(
        "Pompe à analyser", pompes, index=default_idx, format_func=lambda p: f"IP0{p}", key="spec_pompe_select"
    )

    # 7 derniers jours (mesure journaliere simple)
    hist7 = historique_7_jours(df, spec_pompe)
    st.markdown("**Tendance sur 7 jours (vibration journalière)**")
    st.line_chart(hist7.set_index("date")[["vibration"]])

    # Selection du point et de la direction pour le spectre
    c1, c2 = st.columns(2)
    point_sel = c1.selectbox("Point de mesure", POINTS_MESURE, key="point_sel",
                               format_func=lambda p: {"moteur_DE": "Moteur — côté accouplement (DE)",
                                                        "moteur_NDE": "Moteur — côté opposé (NDE)",
                                                        "pompe": "Pompe"}[p])
    direction_sel = c2.selectbox("Direction", DIRECTIONS, key="direction_sel",
                                   format_func=lambda d: {"H": "Horizontal", "V": "Vertical", "A": "Axial"}[d])

    # État avant/après intervention, conservé en session
    if "intervention_state" not in st.session_state:
        st.session_state.intervention_state = {}
    key_etat = f"{spec_pompe}_{point_sel}_{direction_sel}"

    phase = st.radio("Phase d'analyse", ["Avant intervention", "Après intervention"],
                      horizontal=True, key=f"phase_{key_etat}")

    st.markdown("**Valeurs mesurées (modifiables manuellement)**")
    c3, c4 = st.columns(2)
    # Génère un spectre de démonstration ; en base réelle, remplacer par
    # les valeurs effectivement relevées sur le terrain (chapitre 7).
    defaut_demo = (spec_pompe in pompes_alerte_spectrale) and phase == "Avant intervention"
    type_defaut_demo = "roulement" if point_sel != "moteur_DE" else "alignement"
    freq_axis, amplitude = generer_spectre(
        spec_pompe, point_sel, direction_sel, en_defaut=defaut_demo, type_defaut=type_defaut_demo,
        seed=hash(key_etat + phase) % 10000,
    )
    amp_max_saisie = c3.number_input("Amplitude max mesurée (mm/s)", value=float(round(amplitude.max(), 2)),
                                       min_value=0.0, step=0.1, key=f"amp_{key_etat}_{phase}")
    temp_saisie = c4.number_input("Température du point (°C)", value=54.0, min_value=0.0, step=0.5,
                                    key=f"temp_{key_etat}_{phase}")
    # Ajuste l'amplitude du spectre a la valeur saisie manuellement (mise a l'echelle)
    if amplitude.max() > 0:
        amplitude = amplitude * (amp_max_saisie / amplitude.max())

    st.markdown("**Spectre vibratoire (FFT)**")
    spectre_df = pd.DataFrame({"Fréquence (Hz)": freq_axis, "Amplitude (mm/s)": amplitude}).set_index("Fréquence (Hz)")
    st.line_chart(spectre_df)

    diagnostic = diagnostiquer_spectre(freq_axis, amplitude, spec_pompe, point_sel)
    freqs_ref = toutes_frequences_pompe(spec_pompe)
    with st.expander("Fréquences caractéristiques de référence (calculées depuis la fiche technique)"):
        ref_rows = [{"Repère": "1x (rotation)", "Fréquence (Hz)": freqs_ref["1x"]},
                     {"Repère": "2x", "Fréquence (Hz)": freqs_ref["2x"]}]
        for k, v in freqs_ref[point_sel].items():
            if k != "type_roulement":
                ref_rows.append({"Repère": k, "Fréquence (Hz)": v})
        st.dataframe(pd.DataFrame(ref_rows), use_container_width=True, hide_index=True)
        st.caption(f"Roulement : {freqs_ref[point_sel]['type_roulement']} (valeurs typiques — à remplacer par la fiche technique réelle).")

    gravite_colors = {"normal": "#10B981", "surveillance": "#F59E0B", "alerte": "#EF4444"}
    st.markdown(
        f"""<div style="background:{gravite_colors[diagnostic['gravite']]};color:white;padding:12px;
        border-radius:8px;font-weight:600;">Diagnostic : {diagnostic['diagnostic']}</div>""",
        unsafe_allow_html=True,
    )

    # Enregistrer l'etat (avant/apres) pour le rapport
    st.session_state.intervention_state.setdefault(key_etat, {})
    st.session_state.intervention_state[key_etat]["avant" if phase == "Avant intervention" else "apres"] = {
        "diagnostic": diagnostic["diagnostic"], "gravite": diagnostic["gravite"],
        "amplitude_max": amp_max_saisie, "temperature": temp_saisie,
        "date": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
    }

    etat_actuel = st.session_state.intervention_state[key_etat]
    if "avant" in etat_actuel and "apres" in etat_actuel:
        st.success("✅ États 'avant' et 'après' intervention disponibles — rapport prêt à générer.")
        if st.button("📄 Générer le rapport avant/après intervention", type="primary"):
            pdf_bytes = _generer_rapport_intervention(spec_pompe, point_sel, direction_sel, etat_actuel)
            st.download_button(
                "⬇️ Télécharger le rapport PDF", data=pdf_bytes,
                file_name=f"rapport_intervention_IP0{spec_pompe}_{point_sel}_{direction_sel}.pdf",
                mime="application/pdf",
            )
    else:
        manquant = "après" if "avant" in etat_actuel else "avant"
        st.info(f"ℹ️ Complétez également l'état « {manquant} intervention » pour pouvoir générer le rapport.")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # NOUVEAU : Historique des défauts passés (base de connaissances)
    # ═══════════════════════════════════════════════════════════════
    st.markdown("#### 📚 Historique des défauts passés")
    st.caption(
        "Base de connaissances des cas de défaut détectés sur les 3 dernières années "
        "(mesures hebdomadaires détaillées : vibration H/V/axiale + température), "
        "avec indication des cas déclenchés par une vibration générale journalière anormale."
    )

    if os.path.exists("historique_defauts_pompes.csv"):
        histo = pd.read_csv("historique_defauts_pompes.csv")
        pompe_filtre = st.selectbox(
            "Filtrer par pompe", ["Toutes"] + [f"IP0{p}" for p in pompes], key="histo_pompe_filtre"
        )
        histo_affiche = histo if pompe_filtre == "Toutes" else histo[histo["pompe"] == pompe_filtre]

        st.dataframe(
            histo_affiche.rename(columns={
                "date": "Date", "pompe": "Pompe", "point": "Point",
                "vibration_H_mm_s": "H (mm/s)", "vibration_V_mm_s": "V (mm/s)",
                "vibration_axiale_A_mm_s": "Axial A (mm/s)", "temperature_C": "Température (°C)",
                "declenche_par_vibration_generale_journaliere": "Déclenché par vib. générale",
                "type_panne_diagnostique": "Type de panne", "gravite": "Gravité",
            })[["Date", "Pompe", "Point", "H (mm/s)", "V (mm/s)", "Axial A (mm/s)", "Température (°C)",
                "Déclenché par vib. générale", "Type de panne", "Gravité"]],
            use_container_width=True, hide_index=True, height=320,
        )
        n_total = len(histo_affiche)
        n_declenches = int(histo_affiche["declenche_par_vibration_generale_journaliere"].sum())
        st.caption(
            f"{n_total} cas enregistrés, dont {n_declenches} détectés suite à un dépassement "
            f"de la vibration générale journalière (déclenchement automatique de l'analyse spectrale)."
        )
    else:
        st.info(
            "Fichier `historique_defauts_pompes.csv` introuvable — générez-le via "
            "`vib_analysis/build_fault_history.py` et placez-le à la racine du dépôt."
        )

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

        # Construire une observation modifiee. Sur demande explicite, le
        # débit simulé influence désormais AUSSI le courant, la vibration
        # ET la température estimés, selon une approximation physique
        # simplifiée — PAS une corrélation apprise à partir des données :
        #   - Courant : approximativement proportionnel au débit près du
        #     point de fonctionnement (plus de débit = plus de puissance
        #     hydraulique = plus de courant moteur), avec un terme
        #     constant (charge à vide du moteur) pour éviter une
        #     proportionnalité irréaliste à débit nul ;
        #   - Vibration : augmente à mesure que l'on s'éloigne du débit
        #     actuel (fonctionnement hors du point de conception optimal,
        #     dans un sens comme dans l'autre) ;
        #   - Température : suit principalement l'échauffement lié au
        #     courant (effet Joule, facteur dominant), avec une
        #     contribution secondaire de l'écart de vibration (frottement
        #     mécanique accru). Le point de départ est la dernière
        #     température hebdomadaire moyenne connue de la pompe
        #     (donnees_vibration_hebdo.csv), et non une valeur journalière
        #     (la température n'est mesurée qu'hebdomadairement).
        # Ces coefficients sont des ordres de grandeur plausibles, à
        # calibrer avec des données réelles constructeur (chapitre 7).
        sim_row = last_row.copy()
        ratio = debit_simule / debit_actuel if debit_actuel else 1.0

        courant_actuel = float(last_row["courant"])
        vibration_actuelle = float(last_row["vibration"])
        courant_ratio = 0.3 + 0.7 * ratio
        vibration_ratio = 1 + 0.4 * abs(ratio - 1)

        for col in feature_cols:
            if col.startswith("debit"):
                sim_row[col] = sim_row[col] * ratio
            elif col.startswith("courant"):
                sim_row[col] = sim_row[col] * courant_ratio
            elif col.startswith("vibration"):
                sim_row[col] = sim_row[col] * vibration_ratio
        sim_row["courant"] = courant_actuel * courant_ratio
        sim_row["vibration"] = vibration_actuelle * vibration_ratio

        # Temperature de reference : derniere moyenne hebdomadaire connue
        # de la pompe (moyenne des 3 points), issue des donnees hebdo.
        temp_baseline = None
        if os.path.exists("donnees_vibration_hebdo.csv"):
            hebdo_ref = pd.read_csv("donnees_vibration_hebdo.csv")
            hebdo_pompe = hebdo_ref[hebdo_ref["pompe"] == sim_pompe].sort_values("date")
            if not hebdo_pompe.empty:
                derniere_semaine = hebdo_pompe["date"].max()
                temp_baseline = hebdo_pompe[hebdo_pompe["date"] == derniere_semaine]["temperature"].mean()
        if temp_baseline is None:
            temp_baseline = 54.0  # valeur par defaut (moyenne cible du parc)

        temperature_simulee = temp_baseline * (1 + 0.5 * (courant_ratio - 1) + 0.2 * (vibration_ratio - 1))

        model, scaler = fitted[model_choice]
        X_sim = sim_row[feature_cols].values.reshape(1, -1)
        X_sim_s = scaler.transform(X_sim)
        proba_sim = model.predict_proba(X_sim_s)[0, 1] * 100 if hasattr(model, "predict_proba") else 0.0
        delta_risque = proba_sim - risques[sim_pompe][1]

        st.caption(
            "ℹ️ Le courant, la vibration ET la température affichés ci-dessous sont recalculés "
            "en fonction du débit simulé, via une approximation physique simplifiée — et non une "
            "corrélation apprise à partir de données mesurées. À calibrer avec des données réelles "
            "ou des courbes constructeur (chapitre 7). Température de référence : dernière moyenne "
            f"hebdomadaire connue ({temp_baseline:.1f}°C)."
        )

        # CORRIGÉ : l'affichage en 3 colonnes (st.columns) ne s'adapte pas
        # bien aux écrans étroits (mobile) — mêmes symptômes que pour le
        # tableau des pompes plus haut (colonnes écrasées, valeurs
        # invisibles). Remplacé par un tableau simple.
        st.dataframe(
            pd.DataFrame([{
                "Vibration estimée (mm/s)": round(sim_row["vibration"], 1),
                "Courant estimé (A)": round(sim_row["courant"], 1),
                "Température estimée (°C)": round(temperature_simulee, 1),
                "Risque estimé (%)": round(proba_sim, 0),
                "Variation vs actuel": f"{delta_risque:+.0f} pts",
            }]),
            use_container_width=True, hide_index=True,
        )

        if temperature_simulee > 70:
            st.warning(f"⚠️ Température estimée ({temperature_simulee:.1f}°C) au-delà du seuil d'alerte (70°C) — risque de surchauffe palier dans ce scénario.")

        if proba_sim >= 15:
            type_pred_sim, type_proba_sim = predire_type_panne(
                type_model, type_scaler, feature_cols, sim_row
            )
            st.info(f"**Type de panne probable dans ce scénario :** {type_pred_sim} ({type_proba_sim}%)")
        else:
            st.caption("Risque estimé faible — aucun type de panne particulier à signaler dans ce scénario.")

    st.markdown("---")

    # ── NOUVEAU : Prédiction manuelle à partir de valeurs saisies ───────
    # L'utilisateur saisit de nouvelles valeurs (vibration, courant, débit,
    # pression) pour une pompe. Ces valeurs sont combinées avec les 6
    # derniers jours RÉELS de la pompe (issus de l'historique) pour
    # recalculer les variables dérivées (moyennes mobiles, écarts-types,
    # deltas) exactement comme le fait le pipeline ETL (chapitre 3.4 du
    # rapport) — les valeurs saisies servent de "point de départ" du jour
    # courant, le reste du contexte venant de l'historique réel de la pompe.
    st.markdown("#### ✍️ Prédiction à partir de valeurs saisies")
    st.caption(
        "Saisissez de nouvelles mesures pour une pompe : elles sont combinées avec "
        "les 6 derniers jours réels de son historique pour recalculer les tendances "
        "(moyennes mobiles, écarts-types) et produire une prédiction."
    )

    pred_pompe = st.selectbox("Pompe", pompes, format_func=lambda p: f"IP0{p}", key="pred_manuelle_pompe")
    sub_hist = df[df["pompe"] == pred_pompe].sort_values("date")
    raw_cols = ["vibration", "courant", "debit", "pression"]

    if len(sub_hist) < 7:
        st.warning("Historique insuffisant pour cette pompe (moins de 7 jours disponibles).")
    else:
        derniers_jours = sub_hist.iloc[-7:][["date"] + raw_cols].reset_index(drop=True)
        dernier_jour = sub_hist.iloc[-1]

        with st.form("form_prediction_manuelle"):
            st.caption(f"Valeurs par défaut = dernière mesure connue de IP0{pred_pompe} "
                       f"(le {pd.to_datetime(dernier_jour['date']).strftime('%d/%m/%Y')}) — modifiez-les librement.")
            # 2x2 plutôt que 4 colonnes cote a cote : plus robuste sur les
            # ecrans etroits (mobile), evite l'ecrasement observe ailleurs
            # dans cette page avec des rangees de 3-4 colonnes.
            r1c1, r1c2 = st.columns(2)
            v_vib = r1c1.number_input("Vibration (mm/s)", value=float(dernier_jour["vibration"]), min_value=0.0, step=0.1)
            v_cour = r1c2.number_input("Courant (A)", value=float(dernier_jour["courant"]), min_value=0.0, step=1.0)
            r2c1, r2c2 = st.columns(2)
            v_deb = r2c1.number_input("Débit (m³/h)", value=float(dernier_jour["debit"]), min_value=0.0, step=100.0)
            v_pres = r2c2.number_input("Pression (barg)", value=float(dernier_jour["pression"]), min_value=0.0, step=0.1)
            submitted = st.form_submit_button("🔮 Prédire", type="primary", use_container_width=True)

        if submitted:
            # Reconstituer une fenetre de 7 jours : les 6 derniers jours
            # reels + le nouveau jour saisi, pour recalculer les features
            # derivees exactement comme le pipeline ETL.
            nouveau_jour = pd.DataFrame([{
                "date": pd.to_datetime(dernier_jour["date"]) + pd.Timedelta(days=1),
                "vibration": v_vib, "courant": v_cour, "debit": v_deb, "pression": v_pres,
            }])
            fenetre = pd.concat([derniers_jours, nouveau_jour], ignore_index=True)

            for col in raw_cols:
                fenetre[f"{col}_lag1"] = fenetre[col].shift(1)
                fenetre[f"{col}_roll3_mean"] = fenetre[col].shift(1).rolling(3).mean()
                fenetre[f"{col}_roll7_mean"] = fenetre[col].shift(1).rolling(7).mean()
                fenetre[f"{col}_roll7_std"] = fenetre[col].shift(1).rolling(7).std()
                fenetre[f"{col}_delta1"] = fenetre[col].shift(1) - fenetre[col].shift(2)
            fenetre["dow"] = pd.to_datetime(fenetre["date"]).dt.dayofweek

            nouvelle_ligne = fenetre.iloc[-1]
            manque = [c for c in feature_cols if pd.isna(nouvelle_ligne.get(c))]
            if manque:
                st.error(f"Impossible de calculer certaines variables dérivées (historique trop court) : {manque}")
            else:
                model, scaler = fitted[model_choice]
                X_new = nouvelle_ligne[feature_cols].values.reshape(1, -1).astype(float)
                X_new_s = scaler.transform(X_new)
                proba_new = model.predict_proba(X_new_s)[0, 1] * 100 if hasattr(model, "predict_proba") else 0.0
                statut_new = _statut_depuis_risque(proba_new)
                color_new = STATUS_COLORS[statut_new]

                st.markdown(
                    f"""<div style="background:{color_new};color:white;padding:14px;
                    border-radius:8px;text-align:center;font-size:20px;font-weight:700;">
                    Risque prédit : {proba_new:.0f}% — {statut_new.capitalize()}</div>""",
                    unsafe_allow_html=True,
                )

                if proba_new >= 15:
                    type_pred_new, type_proba_new = predire_type_panne(
                        type_model, type_scaler, feature_cols, nouvelle_ligne
                    )
                    st.info(f"**Type de panne le plus probable :** {type_pred_new} ({type_proba_new}%)")
                else:
                    st.caption("Risque faible — aucun type de panne particulier à signaler.")

                with st.expander("Détail du calcul (variables dérivées utilisées)"):
                    st.dataframe(fenetre, use_container_width=True, hide_index=True)


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
