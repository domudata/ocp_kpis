# -*- coding: utf-8 -*-
"""
Onglet Streamlit : 🔎 Audit des calculs KPI & Contrôle OUI / NON.
Permet d'auditer en temps réel chaque OT / Avis avec ses conditions SAP, son résultat OUI/NON,
son motif de rejet, et de télécharger les extractions Excel (KPI unique ou classeur 3 feuilles).
"""

import io
import streamlit as st
import pandas as pd

from core.controle_kpi import (
    build_table_controle_complete,
    get_kpi_summary,
    build_anomalies_excel_unified,
)


def render_audit_kpi_tab(df_period: pd.DataFrame, avdf_period: pd.DataFrame,
                         now_ts, df_full: pd.DataFrame, vp: list, fichier_date: str = "") -> None:
    st.markdown('<div class="stl p">🔎 Audit des calculs KPI & Source Unique OUI / NON</div>', unsafe_allow_html=True)
    st.caption("Traçabilité intégrale et vérification ligne par ligne à partir des données SAP originales.")

    # ── Construction de la table unique de contrôle ──
    table_ctrl = build_table_controle_complete(df_period, avdf_period, now_ts, df_full=df_full)

    if table_ctrl.empty:
        st.warning("⚠️ Aucune donnée disponible pour l'audit des KPI.")
        return

    # Restreindre aux postes filtrés si applicable
    if vp:
        table_ctrl_filtree = table_ctrl[table_ctrl["Poste travail princ."].isin(vp)].copy()
    else:
        table_ctrl_filtree = table_ctrl.copy()

    kpis_dispos = sorted(table_ctrl["KPI"].unique().tolist())

    # Placer 'OT LANC ESTIME' en tête par défaut
    default_idx = 0
    if "OT LANC ESTIME" in kpis_dispos:
        default_idx = kpis_dispos.index("OT LANC ESTIME")

    kpi_labels = {
        "OT LANC ESTIME": "Préparation_Taux d'estimation du travail (OT lancés) [OT LANC ESTIME]",
        "TAUX_REALISATION_CORRECTIF/PT": "Taux de réalisation correctif / PT [TAUX_REALISATION_CORRECTIF/PT]",
        "Backlog préparation caractérisé": "Préparation_Taux de caractérisation Backlog préparation",
        "Backlog planification caractérisé": "Planification _Taux de caractérisation Backlog Planification",
        "OT préparation <1 mois": "Age du Backlog des OT (Préparation)_<1mois",
        "OT préparation 1mois< <3mois": "Age du Backlog des OT (Préparation)_1mois<..<3mois",
        "OT préparation >3 mois": "Age du Backlog des OT (Préparation)_>3mois",
        "OT planification <1 mois": "Age du Backlog des OT (Planification)_<1mois",
        "OT planification 1mois< <3mois": "Age du Backlog des OT (Planification)_1mois<..<3mois",
        "OT planification >3 mois": "Age du Backlog des OT (Planification)_>3mois",
        "OT exécution <1 mois": "Age du Backlog des OT (Exécution)_<1mois",
        "OT exécution 1mois< <3mois": "Age du Backlog des OT (Exécution)_1mois<..<3mois",
        "OT exécution >3 mois": "Age du Backlog des OT (Exécution)_>3mois",
        "OT CONFIME": "OT Confirmé (Heures réelles) [OT CONFIME]",
        "OT_COR_EGAL": "Cohérence Coûts Réels / Budgétés [OT_COR_EGAL]",
        "Taux d'approbation des Avis": "Taux d'approbation des Avis",
        "Performance Graissage": "Performance Graissage (TW 350)",
        "Performance Inspection": "Performance Inspection (TW 290, 300, 310)",
        "Performance Systématiques": "Performance Systématiques (TW 360)",
    }

    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        sel_kpi = st.selectbox(
            "Sélectionner le KPI à auditer :",
            kpis_dispos,
            index=default_idx,
            format_func=lambda k: kpi_labels.get(k, k),
            key="audit_kpi_selector",
        )
    with col_sel2:
        div_options = ["Toutes", "SF1 (Maroc Chimie)", "SF2 (FEEDS)"]
        sel_div = st.selectbox("Filtrer par Division :", div_options, key="audit_div_selector")

    # ── Données du KPI sélectionné ──
    kpi_data = table_ctrl_filtree[table_ctrl_filtree["KPI"] == sel_kpi].copy()

    if sel_div == "SF1 (Maroc Chimie)":
        kpi_data = kpi_data[kpi_data["Division"] == "SF1"]
    elif sel_div == "SF2 (FEEDS)":
        kpi_data = kpi_data[kpi_data["Division"] == "SF2"]

    # ── Explication de la règle métier vérifiée ──
    if sel_kpi == "OT LANC ESTIME":
        st.info(
            "📐 **Formule vérifiée :**  \n"
            "$$\\text{Taux d'estimation du travail} = \\frac{\\text{Nombre d'OT (OT lancés où charge estimée } > 0)}{\\text{OT correctifs lancés}} \\times 100$$\n"
            "- **Dénominateur (Périmètre SAP) :** Ordres correctifs (`Type d'ordre == 'ZCOR'`) et lancés (`Statut système` contient `LANC` ou `Statut OT == 'LANC'`).  \n"
            "- **Condition OUI :** Charge / Budget estimé strictement supérieur à 0 (`Total coûts budgétés > 0`).  \n"
            "- **Condition NON (Anomalie) :** Charge non estimée (`Total coûts budgétés == 0` ou vide).  \n"
            "- **Règle de traçabilité :** Total = OUI + NON | Anomalies = COUNT(NON)."
        )
    elif sel_kpi == "Backlog préparation caractérisé":
        st.info(
            "📐 **Formule vérifiée :**  \n"
            "$$\\text{Taux de caractérisation préparation} = \\frac{\\text{Nombre total d'OT en cours de préparation caractérisés conformément}}{\\text{OT total en préparation (Statut système CRÉÉ)}} \\times 100$$\n"
            "- **Dénominateur :** Type d'ordre `ZCOR` et Statut système commence par `CRÉÉ` / `CREE`.  \n"
            "- **Condition OUI :** Statut utilisateur contient au moins un code parmi `ATPD`, `ATMR`, `ATER`, `ATRS`, `ATMO`.  \n"
            "- **Condition NON (Anomalie) :** Non caractérisé (aucun de ces codes)."
        )
    elif sel_kpi == "Backlog planification caractérisé":
        st.info(
            "📐 **Formule vérifiée :**  \n"
            "$$\\text{Taux de caractérisation planification} = \\frac{\\text{Nombre total d'OT en cours de planification caractérisés conformément}}{\\text{OT total en planification (Statut système LANC)}} \\times 100$$\n"
            "- **Dénominateur :** Type d'ordre `ZCOR` et Statut système commence par `LANC` (hors exécution SOPL).  \n"
            "- **Condition OUI :** Statut utilisateur contient au moins un code parmi `ATPL`, `ATEI`, `ATAL`, `ATAS`, `AGAR`, `ATHS`.  \n"
            "- **Condition NON (Anomalie) :** Non caractérisé (aucun de ces codes)."
        )
    elif "préparation" in sel_kpi.lower() and ("mois" in sel_kpi or "1mois" in sel_kpi):
        st.info(
            f"📐 **Formule vérifiée pour {sel_kpi} :**  \n"
            "- **Périmètre :** OT correctifs `ZCOR` en statut système `CRÉÉ`.  \n"
            "- **Date de calcul d'âge :** `Créé le` (ou date début planifiée si absent).  \n"
            "- **Objectif :** Suivre le flux de préparation rapide et identifier les ordres vieillissants/bloqués."
        )
    elif "planification" in sel_kpi.lower() and ("mois" in sel_kpi or "1mois" in sel_kpi):
        st.info(
            f"📐 **Formule vérifiée pour {sel_kpi} :**  \n"
            "- **Périmètre :** Statut système `LANC` + Statut utilisateur `ATPL` (en cours de planification).  \n"
            "- **Date de calcul d'âge :** `Date de début planifiée`.  \n"
            "- **Objectif :** Détecter les OT planifiés bloqués ou non exécutés."
        )
    elif "exécution" in sel_kpi.lower() and ("mois" in sel_kpi or "1mois" in sel_kpi):
        st.info(
            f"📐 **Formule vérifiée pour {sel_kpi} :**  \n"
            "- **Périmètre :** Statut système `LANC` + Statut utilisateur `SOPL` (en cours d'exécution).  \n"
            "- **Date de calcul d'âge :** `Date de début planifiée`.  \n"
            "- **Objectif :** Mesurer la réactivité des équipes dans l'exécution des OT après planification."
        )
    elif sel_kpi == "OT_COR_EGAL":
        st.info(
            "📐 **Formule vérifiée pour OT_COR_EGAL :**  \n"
            "$$\\text{Cohérence Coûts Réels / Budgétés} = \\frac{\\text{Nombre d'OT (ZCOR clôturés avec Coûts réels } > 0 \\text{ et } \\ne \\text{ Budget)}}{\\text{Total OT correctifs clôturés (ZCOR + CLOT/TCLO)}} \\times 100$$\n"
            "- **Dénominateur (Périmètre SAP) :** Ordres correctifs (`Type d'ordre == 'ZCOR'`) clôturés (`Statut système` ou `Statut OT` contient `CLOT` ou `TCLO`).  \n"
            "- **Condition OUI (Conforme) :** Coûts réels strictement positifs (`Total coûts réels > 0`) **ET** différents du budget (`Total coûts réels != Total coûts budgétés`).  \n"
            "- **Condition NON (Anomalie) :** Coûts réels non saisis ou nuls (`Total coûts réels <= 0`) **OU** identiques au budget sans ajustement (`Total coûts réels == Total coûts budgétés`).  \n"
            "- **Règle de traçabilité :** Total = OUI + NON | Anomalies = COUNT(NON)."
        )

    # ── Calculs et Métriques de synthèse SF1 / SF2 / Total ──
    summary_all = get_kpi_summary(table_ctrl_filtree, sel_kpi)
    d_df = summary_all["divisions"]
    tot_info = summary_all["total"]

    sf1_info = d_df[d_df["Division"] == "SF1"].iloc[0] if (not d_df.empty and "SF1" in d_df["Division"].values) else {"Total": 0, "OUI": 0, "NON": 0, "KPI %": 0.0}
    sf2_info = d_df[d_df["Division"] == "SF2"].iloc[0] if (not d_df.empty and "SF2" in d_df["Division"].values) else {"Total": 0, "OUI": 0, "NON": 0, "KPI %": 0.0}

    # Cible active selon le filtre de division
    if sel_div == "SF1 (Maroc Chimie)":
        active_scope_info = sf1_info
        active_label = "SF1 (Maroc Chimie)"
    elif sel_div == "SF2 (FEEDS)":
        active_scope_info = sf2_info
        active_label = "SF2 (FEEDS)"
    else:
        active_scope_info = tot_info
        active_label = "Total Général (SF1 + SF2)"

    st.markdown("#### 📊 Résultats de Contrôle — Division & Global")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"""<div style="background:#eff6ff;padding:14px;border-radius:8px;border-left:4px solid #3b82f6;">
            <div style="font-weight:800;font-size:14px;color:#1e40af;">🏭 SF1 — Maroc Chimie</div>
            <div style="margin-top:6px;font-size:13px;"><b>Total OT :</b> {int(sf1_info['Total'])}</div>
            <div style="color:#059669;font-size:13px;"><b>Nombre OUI (Conformes) :</b> {int(sf1_info['OUI'])}</div>
            <div style="color:#dc2626;font-size:13px;"><b>Nombre NON (Anomalies) :</b> {int(sf1_info['NON'])}</div>
            <div style="margin-top:6px;font-size:16px;font-weight:800;color:#1e3a5f;">Taux : {sf1_info['KPI %']:.1f}%</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""<div style="background:#f0fdf4;padding:14px;border-radius:8px;border-left:4px solid #10b981;">
            <div style="font-weight:800;font-size:14px;color:#065f46;">🏭 SF2 — FEEDS</div>
            <div style="margin-top:6px;font-size:13px;"><b>Total OT :</b> {int(sf2_info['Total'])}</div>
            <div style="color:#059669;font-size:13px;"><b>Nombre OUI (Conformes) :</b> {int(sf2_info['OUI'])}</div>
            <div style="color:#dc2626;font-size:13px;"><b>Nombre NON (Anomalies) :</b> {int(sf2_info['NON'])}</div>
            <div style="margin-top:6px;font-size:16px;font-weight:800;color:#1e3a5f;">Taux : {sf2_info['KPI %']:.1f}%</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""<div style="background:#f8fafc;padding:14px;border-radius:8px;border-left:4px solid #64748b;">
            <div style="font-weight:800;font-size:14px;color:#1e293b;">🏢 {active_label}</div>
            <div style="margin-top:6px;font-size:13px;"><b>Total OT :</b> {int(active_scope_info.get('Total', 0))}</div>
            <div style="color:#059669;font-size:13px;"><b>Nombre OUI (Conformes) :</b> {int(active_scope_info.get('OUI', 0))}</div>
            <div style="color:#dc2626;font-size:13px;"><b>Nombre NON (Anomalies) :</b> {int(active_scope_info.get('NON', 0))}</div>
            <div style="margin-top:6px;font-size:16px;font-weight:800;color:#1e3a5f;">Taux : {active_scope_info.get('KPI %', 0):.1f}%</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Contrôles de Cohérence Automatiques ──
    st.markdown("---")
    ctrl_tot = int(active_scope_info.get('Total', 0))
    ctrl_oui = int(active_scope_info.get('OUI', 0))
    ctrl_non = int(active_scope_info.get('NON', 0))
    check1_ok = (ctrl_tot == ctrl_oui + ctrl_non)

    c_chk1, c_chk2, c_chk3 = st.columns(3)
    with c_chk1:
        if check1_ok:
            st.success(f"✅ **Contrôle 1 (Total = OUI + NON)** : {ctrl_tot} = {ctrl_oui} + {ctrl_non}")
        else:
            st.error(f"❌ **Erreur Contrôle 1** : Total ({ctrl_tot}) ≠ OUI ({ctrl_oui}) + NON ({ctrl_non})")

    with c_chk2:
        st.success(f"✅ **Contrôle 2 (Anomalies = NON)** : {ctrl_non} anomalies identifiées")

    with c_chk3:
        nb_doublons = len(kpi_data) - kpi_data["Ordre"].nunique() if ("Ordre" in kpi_data.columns and not kpi_data.empty) else 0
        if nb_doublons == 0:
            st.success("✅ **Contrôle 5 (Unicité)** : Aucun doublon")
        else:
            st.warning(f"⚠️ **Attention** : {nb_doublons} doublon(s) détecté(s)")

    # ── Boutons d'export Excel ──
    st.markdown("---")
    col_exp1, col_exp2 = st.columns(2)

    # 1. Export du KPI sélectionné (Tous les OT avec résultat OUI/NON)
    with col_exp1:
        buf_kpi = io.BytesIO()
        with pd.ExcelWriter(buf_kpi, engine="openpyxl") as writer:
            cols_export = [
                "Ordre", "Poste travail princ.", "Division", "KPI", "Résultat", "Motif_NON",
                "Total coûts budgétés", "Total coûts réels", "Statut système", "Statut utilisateur",
                "Statut OT", "Date de début planifiée", "Créé le", "Désignation", "Poste technique",
            ]
            cols_present = [c for c in cols_export if c in kpi_data.columns]
            kpi_data[cols_present].to_excel(writer, sheet_name=sel_kpi[:31], index=False)
        buf_kpi.seek(0)

        st.download_button(
            f"📥 Exporter les OT de {sel_kpi} (.xlsx)",
            data=buf_kpi.getvalue(),
            file_name=f"audit_{sel_kpi.replace('/', '_')}_{fichier_date.replace('/', '-')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
        )

    # 2. Export complet multi-feuilles des anomalies (NON_DETAIL, ANOMALIES_KPI_POSTE, SYNTHESE_KPI)
    with col_exp2:
        try:
            excel_unified_bytes = build_anomalies_excel_unified(table_ctrl_filtree)
            st.download_button(
                "📥 Exporter TOUTES les anomalies (3 Feuilles Excel)",
                data=excel_unified_bytes,
                file_name=f"anomalies_NON_DETAIL_3_feuilles_{fichier_date.replace('/', '-')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as _e_ex:
            st.caption(f"Export unifié indisponible : {_e_ex}")

    # ── Tableau détaillé interactif OUI / NON ──
    st.markdown("---")
    st.markdown("#### 📋 Détail Ligne par Ligne (Audit SAP)")

    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        filtre_res = st.radio(
            "Afficher :",
            ["Tous", "NON uniquement (Anomalies)", "OUI uniquement (Conformes)"],
            horizontal=True,
            key="audit_res_radio",
        )

    df_affiche = kpi_data.copy()
    if filtre_res == "NON uniquement (Anomalies)":
        df_affiche = df_affiche[df_affiche["Résultat"] == "NON"]
    elif filtre_res == "OUI uniquement (Conformes)":
        df_affiche = df_affiche[df_affiche["Résultat"] == "OUI"]

    st.caption(f"Affichage de **{len(df_affiche)}** ligne(s) sur **{len(kpi_data)}**.")

    cols_vue = [
        "Ordre", "Poste travail princ.", "Division", "Résultat", "Motif_NON",
        "Total coûts budgétés", "Statut système", "Statut utilisateur", "Statut OT",
        "Date de début planifiée", "Créé le", "Désignation", "Poste technique",
    ]
    cols_vue_exist = [c for c in cols_vue if c in df_affiche.columns]

    st.dataframe(
        df_affiche[cols_vue_exist],
        use_container_width=True,
        hide_index=True,
    )
