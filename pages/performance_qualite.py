# -*- coding: utf-8 -*-
import io
import pandas as pd
import streamlit as st

from core.constants import QK, PK, CIBLE, ACT_MAP
from core.calcul_kpi import gscore, is_lb

# AJOUTÉ (demande explicite) : abréviations courtes des noms de KPI pour
# les en-têtes de colonnes — st.dataframe ne permet pas de faire pivoter
# le texte des en-têtes (limitation confirmée de Glide Data Grid), donc
# on raccourcit les libellés à la place. Le nom complet reste visible en
# infobulle (help) au survol.
ABREV_KPI = {
    "TAUX_REALISATION_CORRECTIF/PT": "Taux Réal. Correctif",
    "OT préparation <1 mois": "Prép. <1m",
    "OT préparation 1mois< <3mois": "Prép. 1-3m",
    "OT préparation >3 mois": "Prép. >3m",
    "OT planification <1 mois": "Planif. <1m",
    "OT planification 1mois< <3mois": "Planif. 1-3m",
    "OT planification >3 mois": "Planif. >3m",
    "OT exécution <1 mois": "Exéc. <1m",
    "OT exécution 1mois< <3mois": "Exéc. 1-3m",
    "OT exécution >3 mois": "Exéc. >3m",
    "Performance Graissage": "Perf. Graissage",
    "Performance Inspection": "Perf. Inspection",
    "Performance Systématiques": "Perf. Systémat.",
    "Taux d'approbation des Avis": "Approb. Avis",
    "OT LANC ESTIME": "LANC Estimé",
    "Backlog préparation caractérisé": "Backlog Prép.",
    "Backlog planification caractérisé": "Backlog Planif.",
    "OT CONFIME": "OT Confirmé",
    "OT_COR_EGAL": "Coûts Égaux",
    "OT Fiabilité": "Fiabilité",
    "Total Avis de Panne": "Avis Panne",
}


def _abrev(kpi):
    return ABREV_KPI.get(kpi, kpi)


def _tableau_large(vp, ckdf, liste_kpi, nd_full, ano_map):
    """Tableau LARGE (une ligne par poste) — SIMPLIFIÉ (demande explicite,
    contrainte mathématique confirmée) : UNE seule colonne (%) par KPI,
    au lieu de 3 (%/Anomalies/Total). Avec 13-21 KPI, 3 colonnes chacun
    donnait 40+ colonnes au total — le défilement horizontal devient
    alors incontournable quelle que soit la largeur des colonnes
    individuelles (limite du composant Glide Data Grid de Streamlit).
    Les détails Anomalies/Total restent pleinement accessibles via le
    tableau interactif ci-dessous (sélection d'une ligne + choix du KPI).
    Une ligne CIBLE est ajoutée en tête.
    """
def _tableau_large(vp, ckdf, liste_kpi, nd_full, ano_map):
    """Tableau COMPACT (une seule colonne par KPI, 'style export') :
    Une seule colonne (%) par KPI.
    La ligne CIBLE est placée au-dessus de TOTAL GÉNÉRAL.
    Le TOTAL GÉNÉRAL applique la règle : si cellule rouge -> 0, sinon -> 1,
    somme / nb_postes * 100 (taux de conformité par indicateur).
    """
    from core.calcul_kpi import gscore

    lignes = []

    for poste in vp:
        if poste not in ckdf.index:
            continue
        r = ckdf.loc[poste]
        ligne = {"Poste de travail": poste}
        for kpi in liste_kpi:
            ligne[kpi] = int(round(float(r[kpi]))) if kpi in r.index and pd.notna(r[kpi]) else None
        lignes.append(ligne)

    # Ligne CIBLE déplacée en haut de TOTAL GÉNÉRAL
    ligne_cible = {"Poste de travail": "CIBLE"}
    for kpi in liste_kpi:
        ligne_cible[kpi] = int(round(CIBLE.get(kpi, 100)))
    lignes.append(ligne_cible)

    # Ligne TOTAL GÉNÉRAL : calcul conforme à la règle utilisateur
    # (si cellule rouge -> 0, sinon -> 1, somme / nb_postes * 100)
    if len(vp) > 0:
        tot_general = {"Poste de travail": "TOTAL GÉNÉRAL"}
        for kpi in liste_kpi:
            scores = []
            for rw in lignes:
                if rw.get("Poste de travail") not in ("CIBLE", "TOTAL GÉNÉRAL") and kpi in rw:
                    v = rw[kpi]
                    if v is not None and pd.notna(v):
                        try:
                            scores.append(gscore(kpi, float(v), CIBLE.get(kpi, 100)))
                        except Exception:
                            pass
            tot_general[kpi] = int(round(sum(scores) / len(scores) * 100)) if scores else None
        lignes.append(tot_general)

    df = pd.DataFrame(lignes)
    return df


def _tableau_anomalies_selectionnable(vp, ckdf, ano_map, liste_kpi):
    """Tableau LONG (une ligne par Poste × KPI) : Valeur, Cible, Statut —
    chaque ligne sélectionnable nativement (st.dataframe on_select).
    CORRIGÉ (demande explicite) : la colonne "Anomalies" n'est PLUS
    affichée ici — elle apparaît uniquement APRÈS sélection, dans le
    détail (_detail_et_telechargement, qui la recalcule indépendamment
    depuis ano_map)."""
    lignes = []
    for poste in vp:
        if poste not in ckdf.index:
            continue
        r = ckdf.loc[poste]
        for kpi in liste_kpi:
            if kpi not in r.index or pd.isna(r[kpi]):
                continue
            valeur = float(r[kpi])
            cible = CIBLE.get(kpi, 100)
            nb_anom = int(ano_map.get(kpi, pd.Series(dtype=float)).get(poste, 0))
            conforme = (valeur <= cible) if is_lb(kpi) else (valeur >= cible)
            statut = "✅ Conforme" if (nb_anom == 0 or conforme) else "❌ Non conforme"
            lignes.append({
                "Poste de travail": poste, "KPI": kpi,
                "Valeur (%)": round(valeur, 1), "Cible (%)": cible,
                "Statut": statut,
            })
    return pd.DataFrame(lignes)


def _detail_et_telechargement(poste, kpi, ano_map, anomaly_dfs, cle_prefix):
    """Affiche et permet de télécharger le détail EXACT (OT/Avis) du
    couple Poste + KPI sélectionné — mêmes filtres que le tableau
    principal (ano_map/anomaly_dfs sont déjà calculés sous ces filtres
    en amont, dans app.py)."""
    nb = int(ano_map.get(kpi, pd.Series(dtype=float)).get(poste, 0))
    st.markdown(f"**🔍 Détail sélectionné : {poste} — {kpi}** ({nb} anomalie(s))")

    if nb == 0:
        st.success("✅ Aucune anomalie — ce KPI est conforme pour ce poste.")
        return

    df_detail = anomaly_dfs.get(kpi, pd.DataFrame())
    if df_detail.empty or "Poste travail princ." not in df_detail.columns:
        st.info("Détail non disponible pour ce KPI.")
        return

    df_poste = df_detail[df_detail["Poste travail princ."] == poste].copy()
    colonnes_utiles = [c for c in [
        "Ordre", "Avis", "Désignation", "Poste travail princ.", "Poste technique",
        "Statut OT", "Statut système", "Statut utilisateur",
        "Créé le", "Date de début planifiée",
    ] if c in df_poste.columns]
    df_aff = df_poste[colonnes_utiles] if colonnes_utiles else df_poste

    st.dataframe(df_aff, use_container_width=True, hide_index=True,
                 height=min(350, 45 + 35 * len(df_poste)))

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_aff.to_excel(writer, sheet_name="Détail"[:31], index=False)
    st.download_button(
        f"⬇️ Télécharger ces {len(df_poste)} anomalie(s) (Excel)",
        data=buf.getvalue(),
        file_name=f"anomalies_{poste}_{kpi.replace(' ', '_').replace('/', '-')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{cle_prefix}_dl_xlsx",
    )


def _colorer_ligne_cible(row):
    """Ligne CIBLE en bleu marine et TOTAL GÉNÉRAL en fond sombre accentué."""
    if row.get("Poste de travail") == "CIBLE":
        return ["background-color:#1e3a5f;color:white;font-weight:700;"] * len(row)
    if row.get("Poste de travail") == "TOTAL GÉNÉRAL":
        return ["background-color:#0f172a;color:white;font-weight:800;"] * len(row)
    return [""] * len(row)


def _colorer_pct(colonne_pct, kpi, liste_kpi):
    """Couleur de fond vert/jaune/rouge pour une colonne '{KPI} (%)', selon la
    cible et le sens (LOWER_BETTER ou non) avec tolérance de 5% :
    - LOWER_BETTER (1-3m cible 15, >3m cible 5) :
        <= cible -> Vert
        <= cible + 5 -> Jaune
        > cible + 5 -> Rouge
    - KPIs normaux :
        >= cible -> Vert
        >= cible - 5 -> Jaune
        < cible - 5 -> Rouge
    """
    cible = CIBLE.get(kpi, 100)
    lower = is_lb(kpi)
    styles = []
    for v in colonne_pct:
        if pd.isna(v):
            styles.append("")
            continue
        try:
            val = float(v)
        except Exception:
            styles.append("")
            continue
        if lower:
            ok, mid = (val <= cible), (val <= cible + 5)
        elif kpi == "OT_COR_EGAL":
            ok, mid = (val <= 5), False
        else:
            ok, mid = (val >= cible), (val >= cible - 5)
        if ok:
            styles.append("background-color:#10b98133;color:#065f46;font-weight:600;")
        elif mid:
            styles.append("background-color:#f59e0b33;color:#92400e;font-weight:600;")
        else:
            styles.append("background-color:#ef444433;color:#991b1b;font-weight:600;")
    return styles


def _rendre_domaine(vp, ckdf, ano_map, anomaly_dfs, nd_full, liste_kpi, cle_prefix, style_stl):
    # AJOUTÉ (demande explicite) : bouton bascule Maroc Chimie/FEEDS —
    # le tableau ne montre que la division choisie. Poste PAR DÉFAUT
    # (comme si déjà cliqué) : SF1-ECU pour Maroc Chimie, SF2-MTSP pour FEEDS.
    # CORRIGÉ (demande explicite) : st.segmented_control (vrais boutons
    # connectés) au lieu de st.radio.
    division = st.segmented_control(
        "Division", ["🏭 Maroc Chimie", "🏭 FEEDS"],
        selection_mode="single", default="🏭 Maroc Chimie",
        label_visibility="collapsed", key=f"{cle_prefix}_division_toggle",
    )
    if division == "🏭 Maroc Chimie":
        vp = [p for p in vp if str(p).startswith("SF1")]
        poste_par_defaut = "SF1-ECU"
    else:
        vp = [p for p in vp if str(p).startswith("SF2")]
        poste_par_defaut = "SF2-MTSP"

    st.markdown(f'<div class="stl {style_stl}">Vue d\'ensemble (style export) — {division}</div>', unsafe_allow_html=True)
    tbl_large = _tableau_large(vp, ckdf, liste_kpi, nd_full, ano_map)

    # Coloration : (%) par KPI selon la cible, PUIS toute la ligne CIBLE
    # en dernier pour qu'elle prenne le dessus visuellement.
    styler = tbl_large.style
    for kpi in liste_kpi:
        if kpi in tbl_large.columns:
            styler = styler.apply(lambda s, k=kpi: _colorer_pct(s, k, liste_kpi), subset=[kpi])
    styler = styler.apply(_colorer_ligne_cible, axis=1)

    # CORRIGÉ (demande explicite) : use_container_width=True (au lieu de
    # False) pour que le tableau utilise toute la largeur disponible et
    # n'ait PAS besoin de défilement horizontal/vertical — les colonnes
    # column_config "small" ci-dessous garantissent qu'elles restent
    # compactes même en pleine largeur.
    config_colonnes = {"Poste de travail": st.column_config.TextColumn(width="medium")}
    for kpi in liste_kpi:
        if kpi in tbl_large.columns:
            config_colonnes[kpi] = st.column_config.NumberColumn(
                label=f"{_abrev(kpi)} %", width="small", format="%d",
                help=kpi,
            )

    event_large = st.dataframe(
        styler, use_container_width=True, hide_index=True,
        column_config=config_colonnes,
        on_select="rerun", selection_mode="single-row",
        height=45 + 35 * len(tbl_large),  # pas de plafond : tous les postes visibles sans defilement vertical
        key=f"{cle_prefix}_tbl_large_select",
    )
    lignes_large = event_large.selection.rows if event_large and event_large.selection else []
    if lignes_large:
        poste_sel = tbl_large.iloc[lignes_large[0]]["Poste de travail"]
        if poste_sel in ("TOTAL GÉNÉRAL", "CIBLE"):
            poste_sel = poste_par_defaut if poste_par_defaut in vp else None
    else:
        # AJOUTÉ (demande explicite) : « comme si on avait déjà cliqué »
        # sur le poste par défaut de cette division, sans attendre une
        # action de l'utilisateur.
        poste_sel = poste_par_defaut if poste_par_defaut in vp else (vp[0] if vp else None)

    if poste_sel:
            st.markdown(f"**📊 Détail par KPI — {poste_sel}**")
            lignes_resume = []
            for kpi in liste_kpi:
                nb_anom = int(ano_map.get(kpi, pd.Series(dtype=float)).get(poste_sel, 0))
                total_kpi = None
                if kpi in nd_full:
                    _, den_series = nd_full[kpi]
                    total_kpi = int(den_series.get(poste_sel, 0))
                lignes_resume.append({"KPI": kpi, "Anomalies": nb_anom, "Total": total_kpi})
            tbl_resume = pd.DataFrame(lignes_resume)
            st.dataframe(
                tbl_resume, use_container_width=True, hide_index=True,
                column_config={
                    "KPI": st.column_config.TextColumn(width="medium"),
                    "Anomalies": st.column_config.NumberColumn(width="small", format="%d"),
                    "Total": st.column_config.NumberColumn(width="small", format="%d"),
                },
                height=45 + 35 * len(tbl_resume),  # pas de plafond : tous les KPI visibles sans defilement vertical
            )

            kpi_sel = st.selectbox(
                f"Voir le détail OT/Avis (KPI) pour {poste_sel}", liste_kpi,
                key=f"{cle_prefix}_kpi_large_sel",
            )
            _detail_et_telechargement(poste_sel, kpi_sel, ano_map, anomaly_dfs, f"{cle_prefix}_large")
    else:
        st.caption("👆 Cliquez sur une ligne pour voir le détail par KPI de ce poste.")


def render_performance_qualite_tab(vp: list, ckdf, ano_map: dict, anomaly_dfs: dict, nd_full: dict) -> None:
    """
    Page fusionnée Performance / Qualité :
      - Performance affichée en PREMIER ;
      - tableau large façon export Excel (Poste × KPI, avec pour chaque
        KPI : %, Conforme OUI/NON, Total en nombre — demande explicite),
        LUI AUSSI sélectionnable pour télécharger le détail exact ;
      - puis un tableau KPI+Anomalies sélectionnable de la même façon.
    """
    section = st.radio(
        "Domaine",
        ["📈 Performance", "✅ Qualité"],
        horizontal=True,
        label_visibility="collapsed",
        key="perfqual_domaine",
    )

    if section == "📈 Performance":
        _rendre_domaine(vp, ckdf, ano_map, anomaly_dfs, nd_full, QK, "perf", "p")
    else:
        _rendre_domaine(vp, ckdf, ano_map, anomaly_dfs, nd_full, PK, "qual", "q")
