# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core.constants import QK, PK, CIBLE, LOWER_BETTER
from components.tables import html_classement
from components.charts import (
    show_grouped_hbar, show_hbar_thresholds, show_butterfly_single_domain,
    render_suivi_anomalies_semaine,
)


def render_dashboard_tab(vp: list, pscores: dict, qscores: dict,
                          pa: dict, qa: dict,
                          hist_df: pd.DataFrame = None,
                          now_ts: pd.Timestamp = None,
                          ano_map: dict = None,
                          ckdf: pd.DataFrame = None) -> None:
    # ── Bouton bascule Maroc Chimie / FEEDS — EN TOUT PREMIER, CONTRÔLE
    # TOUTE LA PAGE (demande explicite) ─────────────────────────────────
    # CORRIGÉ (demande explicite) : st.segmented_control au lieu de
    # st.radio — rendu en VRAIS BOUTONS connectés, pas de petits ronds.
    division_dash = st.segmented_control(
        "Division", ["🏭 Maroc Chimie", "🏭 FEEDS"],
        selection_mode="single", default="🏭 Maroc Chimie",
        label_visibility="collapsed", key="dash_division_toggle",
    )
    prefixe_div = "SF1" if division_dash == "🏭 Maroc Chimie" else "SF2"
    vp_div = [p for p in vp if str(p).startswith(prefixe_div)]

    st.markdown("---")

    # ── 1) Taux moyens par KPI — CORRIGÉ (demande explicite) : au lieu
    # de la moyenne brute des valeurs, chaque poste est classé par KPI
    # en 1 (vert = conforme, ou jaune = à moins de 5% de la cible) ou 0
    # (rouge = loin de la cible) ; pa_div/qa_div = moyenne de ces 1/0 sur
    # tous les postes de la division, pour CE KPI (taux de conformité,
    # pas moyenne des valeurs) ─────────────────────────────────────────
    from core.calcul_kpi import is_lb

    def _taux_conformite(ckdf_scope, liste_kpi):
        resultat = {}
        for kpi in liste_kpi:
            if kpi not in ckdf_scope.columns or ckdf_scope.empty:
                continue
            cible = CIBLE.get(kpi, 100)
            lower = is_lb(kpi)
            classifications = []
            for v in ckdf_scope[kpi].dropna():
                if lower:
                    conforme = (v <= cible) or (v <= cible * 1.05)
                else:
                    conforme = (v >= cible) or (v >= cible * 0.95)
                classifications.append(1 if conforme else 0)
            if classifications:
                resultat[kpi] = round(sum(classifications) / len(classifications) * 100, 1)
        return resultat

    if ckdf is not None and not ckdf.empty:
        vp_div_present = [p for p in vp_div if p in ckdf.index]
        ckdf_div = ckdf.loc[vp_div_present] if vp_div_present else ckdf.iloc[0:0]
        pa_div = _taux_conformite(ckdf_div, QK)
        qa_div = _taux_conformite(ckdf_div, PK)
    else:
        # Repli (si ckdf non fourni) : moyennes globales inchangées.
        pa_div, qa_div = pa, qa

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f'<div class="stl p">Indicateurs de Performance — {division_dash}</div>', unsafe_allow_html=True)
        labels = [k for k in QK if k in pa_div]
        values = [pa_div[k] for k in labels]
        show_hbar_thresholds(labels, values, f"Taux moyens — Performance — {division_dash}",
                             cible_map=CIBLE, lower_set=LOWER_BETTER)
    with col2:
        st.markdown(f'<div class="stl q">Indicateurs de Qualité — {division_dash}</div>', unsafe_allow_html=True)
        labels = [k for k in PK if k in qa_div]
        values = [qa_div[k] for k in labels]
        show_hbar_thresholds(labels, values, f"Taux moyens — Qualité — {division_dash}",
                             cible_map=CIBLE, lower_set=LOWER_BETTER)

    st.markdown("---")

    # ── 2) Score global par poste (division choisie) ───────────────────
    st.markdown(f'<div class="stl p">Scores globaux par poste — {division_dash}</div>', unsafe_allow_html=True)
    show_grouped_hbar(vp_div, pscores, qscores, f"Performance & Qualité — {division_dash}", thin=True)

    st.markdown("---")

    # ── 3) Comparaison Semaine Actuelle vs Semaine Précédente — CORRIGÉ
    # (demande explicite) : Performance et Qualité SÉPARÉES en 2
    # graphiques papillon, l'un à côté de l'autre (au lieu d'un seul
    # graphique fusionné) ────────────────────────────────────────────
    st.markdown('<div class="stl c">Comparaison Semaine Actuelle vs Semaine Précédente</div>', unsafe_allow_html=True)

    if hist_df is None or hist_df.empty or "Poste de travail" not in hist_df.columns:
        st.markdown(
            '<div style="padding:12px;color:#94a3b8;">'
            'Pas assez de données historiques pour comparer deux semaines. '
            'Au moins 2 dates d\'extraction enregistrées sont nécessaires.</div>',
            unsafe_allow_html=True,
        )
    else:
        _now = pd.Timestamp(now_ts) if now_ts is not None else pd.Timestamp.today()
        lundi_actuel = _now.normalize() - pd.Timedelta(days=_now.weekday())
        dimanche_actuel = lundi_actuel + pd.Timedelta(days=6)
        lundi_precedent = lundi_actuel - pd.Timedelta(days=7)
        dimanche_precedent = lundi_actuel - pd.Timedelta(days=1)

        dates_all = hist_df["Date_parsed"].dropna()
        dates_semaine_act = dates_all[(dates_all >= lundi_actuel) & (dates_all <= dimanche_actuel)]
        dates_semaine_prec = dates_all[(dates_all >= lundi_precedent) & (dates_all <= dimanche_precedent)]

        if dates_semaine_act.empty or dates_semaine_prec.empty:
            st.markdown(
                '<div style="padding:12px;color:#94a3b8;">'
                f'Semaine actuelle ({lundi_actuel:%d/%m}–{dimanche_actuel:%d/%m}) : '
                f'{"aucune" if dates_semaine_act.empty else len(dates_semaine_act.unique())} extraction(s). '
                f'Semaine précédente ({lundi_precedent:%d/%m}–{dimanche_precedent:%d/%m}) : '
                f'{"aucune" if dates_semaine_prec.empty else len(dates_semaine_prec.unique())} extraction(s). '
                'Il faut au moins une extraction dans chacune des deux semaines pour comparer.</div>',
                unsafe_allow_html=True,
            )
        else:
            date_act_ts = dates_semaine_act.max()
            date_prec_ts = dates_semaine_prec.max()
            date_prec = date_prec_ts.strftime("%d/%m/%Y")
            date_act = date_act_ts.strftime("%d/%m/%Y")
            st.markdown(
                f'<div style="margin-bottom:8px;font-size:11px;color:#64748b;">'
                f'📅 Préc. : <b>{date_prec}</b> &nbsp;→&nbsp; Actuelle : <b>{date_act}</b></div>',
                unsafe_allow_html=True,
            )

            perf_h = hist_df[hist_df["_section"] == "perf"]
            qual_h = hist_df[hist_df["_section"] == "qual"]
            postes_dispo = sorted([p for p in vp_div if p in hist_df["Poste de travail"].unique()])

            if not postes_dispo:
                st.markdown(
                    '<div style="padding:12px;color:#94a3b8;">Aucun poste du périmètre sélectionné '
                    'ne dispose d\'historique.</div>',
                    unsafe_allow_html=True,
                )
            else:
                postes_valides, perf_prec, perf_act, qual_prec, qual_act = [], [], [], [], []
                for poste in postes_dispo:
                    p_row_act = perf_h[(perf_h["Poste de travail"] == poste) & (perf_h["Date_parsed"] == date_act_ts)]
                    p_row_prec = perf_h[(perf_h["Poste de travail"] == poste) & (perf_h["Date_parsed"] == date_prec_ts)]
                    q_row_act = qual_h[(qual_h["Poste de travail"] == poste) & (qual_h["Date_parsed"] == date_act_ts)]
                    q_row_prec = qual_h[(qual_h["Poste de travail"] == poste) & (qual_h["Date_parsed"] == date_prec_ts)]

                    val_p_act = float(p_row_act["Score Performance"].iloc[0]) if not p_row_act.empty and "Score Performance" in p_row_act.columns else 0.0
                    val_p_prec = float(p_row_prec["Score Performance"].iloc[0]) if not p_row_prec.empty and "Score Performance" in p_row_prec.columns else 0.0
                    val_q_act = float(q_row_act["Score Qualite"].iloc[0]) if not q_row_act.empty and "Score Qualite" in q_row_act.columns else 0.0
                    val_q_prec = float(q_row_prec["Score Qualite"].iloc[0]) if not q_row_prec.empty and "Score Qualite" in q_row_prec.columns else 0.0

                    postes_valides.append(poste)
                    perf_prec.append(val_p_prec); perf_act.append(val_p_act)
                    qual_prec.append(val_q_prec); qual_act.append(val_q_act)

                col_bp, col_bq = st.columns(2)
                with col_bp:
                    show_butterfly_single_domain(
                        postes_valides, perf_prec, perf_act,
                        f"Performance — {division_dash}", f"Préc. ({date_prec})", f"Actuelle ({date_act})",
                        couleur_prec="#93c5fd", couleur_act="#1d4ed8",
                    )
                with col_bq:
                    show_butterfly_single_domain(
                        postes_valides, qual_prec, qual_act,
                        f"Qualité — {division_dash}", f"Préc. ({date_prec})", f"Actuelle ({date_act})",
                        couleur_prec="#86efac", couleur_act="#15803d",
                    )

    st.markdown("---")

    # ── 4) Suivi hebdomadaire des anomalies (division choisie) ──────────
    render_suivi_anomalies_semaine(vp, hist_df, now_ts, "dash", ano_map_actuel=ano_map, division=prefixe_div)

    st.markdown("---")

    # ── Classements — filtrés sur la division choisie ────────────────────
    pscores_div = {p: v for p, v in pscores.items() if p in vp_div}
    qscores_div = {p: v for p, v in qscores.items() if p in vp_div}

    st.markdown(f'<div class="stl c">Classement Performance — {division_dash}</div>', unsafe_allow_html=True)
    st.markdown(html_classement(pscores_div, "#10b981"), unsafe_allow_html=True)

    st.markdown(f'<div class="stl c">Classement Qualité — {division_dash}</div>', unsafe_allow_html=True)
    st.markdown(html_classement(qscores_div, "#3b82f6"), unsafe_allow_html=True)
