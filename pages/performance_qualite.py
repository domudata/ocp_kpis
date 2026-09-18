# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core.constants import QK, PK, CIBLE, ACT_MAP, KPI_RESP_MAP
from core.calcul_kpi import gscore, is_lb


def _construire_lignes(vp, ckdf, ano_map, liste_kpi):
    """Une ligne par (Poste, KPI) : Valeur, Cible, Anomalies, Statut.
    Anomalies = ano_map (SOURCE UNIQUE, section 14 de la spécification) —
    jamais recalculées différemment ici."""
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
                "Valeur": valeur, "Cible": cible,
                "Anomalies": nb_anom, "Statut": statut,
            })
    return lignes


def _html_tableau_fusionne(lignes, cle_html):
    """Rendu HTML du tableau fusionné KPI + Anomalies (lecture seule —
    l'interaction se fait via les sélecteurs juste en dessous, section
    'Voir le détail d'une anomalie', car un tableau HTML statique ne peut
    pas déclencher d'action Streamlit au clic)."""
    if not lignes:
        return '<div style="padding:14px;color:#94a3b8;">Aucune donnée pour la sélection actuelle.</div>'

    h = f'<div style="overflow-x:auto;"><table id="{cle_html}" style="width:100%;border-collapse:collapse;font-size:12.5px;">'
    h += ('<tr style="background:#1e3a5f;color:#fff;">'
          '<th style="padding:8px 10px;text-align:left;">Poste de travail</th>'
          '<th style="padding:8px 10px;text-align:left;">KPI</th>'
          '<th style="padding:8px 10px;text-align:center;">Valeur</th>'
          '<th style="padding:8px 10px;text-align:center;">Cible</th>'
          '<th style="padding:8px 10px;text-align:center;">Anomalies</th>'
          '<th style="padding:8px 10px;text-align:center;">Statut</th></tr>')

    for i, l in enumerate(lignes):
        bg = "#f8fafc" if i % 2 == 0 else "#ffffff"
        anom_color = "#dc2626" if l["Anomalies"] > 0 else "#059669"
        h += (
            f'<tr style="background:{bg};border-bottom:1px solid #e2e8f0;">'
            f'<td style="padding:6px 10px;font-weight:600;">{l["Poste de travail"]}</td>'
            f'<td style="padding:6px 10px;">{l["KPI"]}</td>'
            f'<td style="padding:6px 10px;text-align:center;">{l["Valeur"]:.1f}%</td>'
            f'<td style="padding:6px 10px;text-align:center;color:#64748b;">{l["Cible"]:.0f}%</td>'
            f'<td style="padding:6px 10px;text-align:center;font-weight:700;color:{anom_color};">{l["Anomalies"]}</td>'
            f'<td style="padding:6px 10px;text-align:center;">{l["Statut"]}</td>'
            f'</tr>'
        )

    # Ligne Total général (moyenne des valeurs, somme des anomalies)
    if lignes:
        moy = sum(l["Valeur"] for l in lignes) / len(lignes)
        tot_anom = sum(l["Anomalies"] for l in lignes)
        h += (
            '<tr style="background:#e2e8f0;font-weight:800;border-top:2px solid #94a3b8;">'
            '<td style="padding:7px 10px;" colspan="2">Total général</td>'
            f'<td style="padding:7px 10px;text-align:center;">{moy:.1f}%</td>'
            '<td style="padding:7px 10px;text-align:center;">—</td>'
            f'<td style="padding:7px 10px;text-align:center;color:#dc2626;">{tot_anom}</td>'
            '<td style="padding:7px 10px;text-align:center;">—</td>'
            '</tr>'
        )
    h += '</table></div>'
    return h


def _section_detail_interactif(vp, liste_kpi, ano_map, anomaly_dfs, cle_prefix):
    """Remplace le 'clic sur le nombre' (impossible en HTML statique) par
    deux sélecteurs Poste + KPI (section 11-12 de la spécification) :
    affiche puis permet de télécharger UNIQUEMENT les OT/Avis du couple
    sélectionné, sous les filtres actuellement actifs — jamais l'ensemble
    des anomalies de l'application."""
    st.markdown("**🔍 Voir le détail d'une anomalie**")
    c1, c2 = st.columns(2)
    with c1:
        poste_sel = st.selectbox("Poste de travail", vp, key=f"{cle_prefix}_poste_sel")
    with c2:
        kpi_sel = st.selectbox("KPI", liste_kpi, key=f"{cle_prefix}_kpi_sel")

    nb = int(ano_map.get(kpi_sel, pd.Series(dtype=float)).get(poste_sel, 0))
    st.caption(f"**{nb}** anomalie(s) pour **{poste_sel}** — **{kpi_sel}** (filtres actifs appliqués)")

    if nb == 0:
        st.success("✅ Aucune anomalie — ce KPI est conforme pour ce poste.")
        return

    df_detail = anomaly_dfs.get(kpi_sel, pd.DataFrame())
    if df_detail.empty or "Poste travail princ." not in df_detail.columns:
        st.info("Détail non disponible pour ce KPI.")
        return

    df_poste = df_detail[df_detail["Poste travail princ."] == poste_sel].copy()

    colonnes_utiles = [c for c in [
        "Ordre", "Avis", "Désignation", "Poste travail princ.", "Poste technique",
        "Statut OT", "Statut système", "Statut utilisateur",
        "Créé le", "Date de début planifiée",
    ] if c in df_poste.columns]

    st.dataframe(df_poste[colonnes_utiles] if colonnes_utiles else df_poste,
                 use_container_width=True, hide_index=True, height=min(400, 45 + 35 * len(df_poste)))

    st.download_button(
        f"⬇️ Télécharger ces {len(df_poste)} anomalie(s) (CSV)",
        data=df_poste.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"anomalies_{poste_sel}_{kpi_sel.replace(' ', '_').replace('/', '-')}.csv",
        mime="text/csv",
        key=f"{cle_prefix}_dl",
    )


def render_performance_qualite_tab(vp: list, ckdf, ano_map: dict, anomaly_dfs: dict) -> None:
    """
    Page fusionnée Performance / Qualité conforme à la spécification
    reçue (sections 8 à 16) :
      - un seul tableau KPI + Anomalies par domaine (plus de tableaux
        séparés « Détail » / « Anomalies ») ;
      - Anomalies = SOURCE UNIQUE ano_map, réutilisée identiquement pour
        le tableau et pour le détail interactif ;
      - le détail (sélecteur Poste + KPI, remplaçant le clic sur un
        tableau HTML statique) respecte exactement les mêmes filtres que
        le tableau principal, car ano_map/anomaly_dfs sont déjà calculés
        sous ces filtres en amont (app.py) ;
      - Total général affiché en pied de tableau.
    """
    section = st.radio(
        "Domaine",
        ["✅ Performance Qualité", "📈 Performance"],
        horizontal=True,
        label_visibility="collapsed",
        key="perfqual_domaine",
    )

    if section == "✅ Performance Qualité":
        st.markdown('<div class="stl q">Performance Qualité — KPI et anomalies</div>', unsafe_allow_html=True)
        lignes = _construire_lignes(vp, ckdf, ano_map, PK)
        st.markdown(_html_tableau_fusionne(lignes, "tbl_qual"), unsafe_allow_html=True)
        st.markdown("---")
        _section_detail_interactif(vp, PK, ano_map, anomaly_dfs, "qual")
    else:
        st.markdown('<div class="stl p">Performance — KPI et anomalies</div>', unsafe_allow_html=True)
        lignes = _construire_lignes(vp, ckdf, ano_map, QK)
        st.markdown(_html_tableau_fusionne(lignes, "tbl_perf"), unsafe_allow_html=True)
        st.markdown("---")
        _section_detail_interactif(vp, QK, ano_map, anomaly_dfs, "perf")
