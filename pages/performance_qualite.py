# -*- coding: utf-8 -*-
import io
import pandas as pd
import streamlit as st

from core.constants import QK, PK, CIBLE, ACT_MAP
from core.calcul_kpi import gscore, is_lb


def _tableau_large(vp, ckdf, liste_kpi, nd_full, ano_map):
    """Tableau LARGE (une ligne par poste) — style du fichier Excel de
    référence : pour CHAQUE KPI, 3 colonnes (demande explicite) :
      - {KPI} (%)         : la valeur du KPI
      - {KPI} (Anomalies) : le NOMBRE d'anomalies (pas OUI/NON — corrigé
        sur demande explicite), issu de ano_map (source unique)
      - {KPI} (Total)     : le nombre total d'OT/Avis concernés (dénominateur)
    """
    lignes = []
    for poste in vp:
        if poste not in ckdf.index:
            continue
        r = ckdf.loc[poste]
        ligne = {"Poste de travail": poste}
        for kpi in liste_kpi:
            if kpi not in r.index or pd.isna(r[kpi]):
                ligne[f"{kpi} (%)"] = None
                ligne[f"{kpi} (Anomalies)"] = None
                ligne[f"{kpi} (Total)"] = None
                continue
            valeur = float(r[kpi])
            ligne[f"{kpi} (%)"] = round(valeur, 1)
            ligne[f"{kpi} (Anomalies)"] = int(ano_map.get(kpi, pd.Series(dtype=float)).get(poste, 0))
            if kpi in nd_full:
                _, den_series = nd_full[kpi]
                ligne[f"{kpi} (Total)"] = int(den_series.get(poste, 0))
            else:
                ligne[f"{kpi} (Total)"] = None
        lignes.append(ligne)
    df = pd.DataFrame(lignes)
    if not df.empty:
        moyenne = {"Poste de travail": "TOTAL GÉNÉRAL"}
        for kpi in liste_kpi:
            col_pct = f"{kpi} (%)"
            col_anom = f"{kpi} (Anomalies)"
            col_tot = f"{kpi} (Total)"
            if col_pct in df.columns:
                moyenne[col_pct] = round(df[col_pct].mean(skipna=True), 1)
            if col_anom in df.columns:
                moyenne[col_anom] = int(df[col_anom].sum(skipna=True))
            if col_tot in df.columns:
                moyenne[col_tot] = int(df[col_tot].sum(skipna=True))
        df = pd.concat([df, pd.DataFrame([moyenne])], ignore_index=True)
    return df


def _tableau_anomalies_selectionnable(vp, ckdf, ano_map, liste_kpi):
    """Tableau LONG (une ligne par Poste × KPI) : Valeur, Cible, Anomalies,
    Statut — chaque ligne sélectionnable nativement (st.dataframe on_select),
    ce qui permet un vrai clic pour télécharger le détail correspondant."""
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
                "Anomalies": nb_anom, "Statut": statut,
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


def _rendre_domaine(vp, ckdf, ano_map, anomaly_dfs, nd_full, liste_kpi, cle_prefix, style_stl):
    st.markdown(f'<div class="stl {style_stl}">Vue d\'ensemble (style export)</div>', unsafe_allow_html=True)
    tbl_large = _tableau_large(vp, ckdf, liste_kpi, nd_full, ano_map)
    event_large = st.dataframe(
        tbl_large, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row",
        height=min(500, 45 + 35 * len(tbl_large)),
        key=f"{cle_prefix}_tbl_large_select",
    )
    lignes_large = event_large.selection.rows if event_large and event_large.selection else []
    if lignes_large:
        poste_sel = tbl_large.iloc[lignes_large[0]]["Poste de travail"]
        if poste_sel != "TOTAL GÉNÉRAL":
            kpi_sel = st.selectbox(
                f"KPI à télécharger pour {poste_sel}", liste_kpi,
                key=f"{cle_prefix}_kpi_large_sel",
            )
            _detail_et_telechargement(poste_sel, kpi_sel, ano_map, anomaly_dfs, f"{cle_prefix}_large")
    else:
        st.caption("👆 Cliquez sur une ligne pour choisir un KPI et télécharger son détail (OT/Avis).")

    st.markdown("---")
    st.markdown(f'<div class="stl a">KPI et anomalies — cliquez une ligne pour télécharger son détail</div>', unsafe_allow_html=True)
    tbl_anom = _tableau_anomalies_selectionnable(vp, ckdf, ano_map, liste_kpi)

    if tbl_anom.empty:
        st.info("Aucune donnée pour la sélection actuelle.")
        return

    event = st.dataframe(
        tbl_anom, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row",
        height=min(450, 45 + 35 * len(tbl_anom)),
        key=f"{cle_prefix}_tbl_select",
    )

    st.markdown("---")
    lignes_selectionnees = event.selection.rows if event and event.selection else []
    if lignes_selectionnees:
        ligne = tbl_anom.iloc[lignes_selectionnees[0]]
        _detail_et_telechargement(ligne["Poste de travail"], ligne["KPI"], ano_map, anomaly_dfs, cle_prefix)
    else:
        st.caption("👆 Cliquez sur une ligne du tableau ci-dessus pour voir et télécharger son détail (OT/Avis).")


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
