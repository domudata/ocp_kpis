# -*- coding: utf-8 -*-

import locale
import os
import random
import time
import traceback
import hashlib as _hashlib

import numpy as np
import pandas as pd
import streamlit as st


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION STREAMLIT
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    layout="wide",
    page_title="Dashboard KPI",
    initial_sidebar_state="expanded"
)


# ═══════════════════════════════════════════════════════════════════════════
# IMPORTS PROTEGES
# ═══════════════════════════════════════════════════════════════════════════

try:

    from core.constants import (
        QK,
        PK,
        ALL_KPI,
        CIBLE,
        ACT_MAP,
        KPI_RESP_MAP,
        LOWER_BETTER,
        CONSIGNES_HSE,
    )

    from core.prepare_data import (
        prepare_data,
        get_date_from_file,
    )

    from core.calcul_kpi import (
        calc_kpis,
        gscore,
        is_lb,
    )

    from core.anomalies import (
        build_ano_map,
        build_ano_rows,
        build_anomaly_dfs,
    )

    from core.historique import (
        load_historical_kpis,
        calculate_variations,
        generate_journal,
        calculate_rankings,
    )

    from core.export_excel import save_kpis_to_excel

    from components.styles import inject_custom_css
    from components.header import render_header
    from components.cards import (
        get_previous_card_values,
        render_cards,
    )
    from components.sidebar import render_sidebar

    from pages.dashboard import render_dashboard_tab

    from pages.performance_qualite import (
        render_performance_qualite_tab
    )

    from pages.backlog import render_backlog_page

    from pages.evolution import render_evolution_tab

    from pages.plan_action import render_plan_action_tab

    from pages.frequence_maintenance import (
        render_frequence_maintenance_tab
    )

    from pages.suivi_hse import (
        render_suivi_hse_tab
    )

    _IMPORT_ERROR = None

except Exception as _e:

    _IMPORT_ERROR = traceback.format_exc()


# ═══════════════════════════════════════════════════════════════════════════
# VERSION AUTOMATIQUE DU CALCUL
# ═══════════════════════════════════════════════════════════════════════════

def _calc_signature():

    h = _hashlib.md5()

    base_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    found_any = False

    for _f in (
        "core/calcul_kpi.py",
        "core/anomalies.py",
        "core/prepare_data.py",
    ):

        _path = os.path.join(
            base_dir,
            _f
        )

        try:

            with open(_path, "rb") as _fh:

                h.update(
                    _fh.read()
                )

                found_any = True

        except Exception:

            pass

    if not found_any:

        h.update(
            str(
                os.path.getmtime(
                    os.path.abspath(__file__)
                )
            ).encode()
        )

    return (
        h.hexdigest()[:12],
        found_any
    )


CALC_VERSION, _CALC_SIG_OK = _calc_signature()


# ═══════════════════════════════════════════════════════════════════════════
# CACHE CALCUL KPI
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_data(
    show_spinner="Calcul des KPIs en cours..."
)
def calc_kpis_cached(
    df_period,
    avdf_period,
    now_ts,
    apm_tuple,
    fichier_date,
    sdt,
    edt,
    df_toutes_dates,
    avf_approve=None,
    calc_version=CALC_VERSION
):

    return calc_kpis(
        df_period,
        avdf_period,
        now_ts,
        list(apm_tuple),
        df_toutes_dates=df_toutes_dates,
        av_approve_i=avf_approve
    )


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():

    # ═══════════════════════════════════════════════════════════════════════
    # VERIFICATION IMPORTS
    # ═══════════════════════════════════════════════════════════════════════

    if _IMPORT_ERROR is not None:

        st.error(
            "❌ Erreur lors du chargement des modules (import). "
            "Copiez ce texte :"
        )

        st.code(
            _IMPORT_ERROR,
            language="python"
        )

        st.stop()


    # ═══════════════════════════════════════════════════════════════════════
    # LOCALE FRANÇAISE
    # ═══════════════════════════════════════════════════════════════════════

    try:

        locale.setlocale(
            locale.LC_ALL,
            "fr_FR.UTF-8"
        )

    except Exception:

        try:

            locale.setlocale(
                locale.LC_ALL,
                "fr_FR"
            )

        except Exception:

            pass


    # ═══════════════════════════════════════════════════════════════════════
    # CSS
    # ═══════════════════════════════════════════════════════════════════════

    inject_custom_css()

    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


    st.markdown(
        """
        <style>

        [data-testid="stToolbar"] {
            display: none !important;
        }

        [data-testid="stToolbarActions"] {
            display: none !important;
        }

        [data-testid="stStatusWidget"] {
            display: none !important;
        }

        [data-testid="stDecoration"] {
            display: none !important;
        }

        #MainMenu {
            visibility: hidden !important;
        }

        [data-testid="collapsedControl"] {
            visibility: visible !important;
            display: block !important;
            position: fixed !important;
            top: 0.5rem !important;
            left: 0.5rem !important;
            z-index: 999999 !important;
        }

        footer {
            visibility: hidden !important;
        }

        .stAppDeployButton {
            display: none !important;
        }

        .viewerBadge_container__1QSob {
            display: none !important;
        }

        </style>
        """,
        unsafe_allow_html=True
    )


    st.markdown(
        """
        <style>

        .cr {
            display:flex;
            flex-wrap:nowrap;
            gap:8px;
            margin-bottom:8px;
            overflow-x:auto;
        }

        .cc {
            flex:1 1 0;
            min-width:0;
            padding:10px 8px;
            text-align:center;
            background:#fff;
            border-radius:8px;
            border-left:3px solid #cbd5e1;
            box-shadow:0 1px 3px rgba(0,0,0,0.06);
        }

        .cc .cv {
            font-size:18px;
            font-weight:800;
            line-height:1.1;
            white-space:nowrap;
        }

        .cc .cd {
            font-size:10px;
            color:#f59e0b;
            margin:2px 0;
        }

        .cc .cl {
            font-size:10px;
            font-weight:700;
            color:#475569;
            text-transform:uppercase;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
        }

        .c1 {
            border-left-color:#3b82f6;
        }

        .c1 .cv {
            color:#3b82f6;
        }

        .c4 {
            border-left-color:#ef4444;
        }

        .c4 .cv {
            color:#ef4444;
        }

        .c5 {
            border-left-color:#14b8a6;
        }

        .c5 .cv {
            color:#14b8a6;
        }

        .c6 {
            border-left-color:#8b5cf6;
        }

        .c6 .cv {
            color:#8b5cf6;
        }

        .c7 {
            border-left-color:#f59e0b;
        }

        .c7 .cv {
            color:#f59e0b;
        }

        .c8 {
            border-left-color:#f97316;
        }

        .c8 .cv {
            color:#f97316;
        }

        @media (max-width: 768px) {

            .cc .cv {
                font-size:14px;
            }

            .cc .cl {
                font-size:8px;
            }

        }

        </style>
        """,
        unsafe_allow_html=True
    )


    # ═══════════════════════════════════════════════════════════════════════
    # DATE EXTRACTION
    # ═══════════════════════════════════════════════════════════════════════

    fichier_date = get_date_from_file()


    # ═══════════════════════════════════════════════════════════════════════
    # INITIALISATION ET ECRAN HSE
    # ═══════════════════════════════════════════════════════════════════════

    if "hse_affiche" not in st.session_state:

        st.session_state.hse_affiche = False


    if not st.session_state.hse_affiche:

        c = random.choice(
            CONSIGNES_HSE
        )

        st.markdown(
            """
            <div style="
                min-height:100vh;
                display:flex;
                flex-direction:column;
                align-items:center;
                justify-content:center;
                background:linear-gradient(
                    135deg,
                    #1a365d,
                    #2d3748,
                    #1a365d
                );
                padding:40px
            ">

            <div style="
                font-size:64px;
                margin-bottom:20px
            ">
            &#128282;
            </div>

            <h1 style="
                text-align:center;
                font-size:46px;
                color:#fff;
                font-weight:900;
                margin:0
            ">
            HSE - CONSIGNE DE SECURITE
            </h1>

            <p style="
                text-align:center;
                color:rgba(255,255,255,.6);
                font-size:22px;
                margin-top:8px;
                letter-spacing:3px;
                text-transform:uppercase
            ">
            Securite - Sante - Environnement
            </p>

            <div style="
                background:linear-gradient(
                    135deg,
                    #f6e05e,
                    #ed8936
                );
                padding:36px 48px;
                border-radius:20px;
                font-size:32px;
                font-weight:700;
                text-align:center;
                margin:40px 0;
                color:#1a202c;
                max-width:800px;
                box-shadow:
                    0 20px 60px rgba(0,0,0,.3)
            ">
            %s
            </div>

            <h2 style="
                text-align:center;
                color:#48bb78;
                font-size:36px;
                font-weight:900
            ">
            Aucun travail n'est plus urgent que la securite
            </h2>

            <div style="
                margin-top:40px;
                width:200px;
                height:4px;
                background:rgba(255,255,255,.1);
                border-radius:2px;
                overflow:hidden
            ">

            <div style="
                width:100%%;
                height:100%%;
                background:linear-gradient(
                    90deg,
                    #48bb78,
                    #38a169
                );
                border-radius:2px;
                animation:ld 5.5s ease-in-out forwards
            ">
            </div>

            </div>

            <style>

            @keyframes ld {
                from {
                    width:0
                }

                to {
                    width:100%%
                }
            }

            </style>

            </div>
            """ % c,
            unsafe_allow_html=True
        )

        time.sleep(6)

        st.session_state.hse_affiche = True

        st.rerun()

        st.stop()


    # ═══════════════════════════════════════════════════════════════════════
    # INITIALISATION DES ETATS POUR LES PAGES LOURDES
    # ═══════════════════════════════════════════════════════════════════════

    if "hse_charge" not in st.session_state:

        st.session_state.hse_charge = False


    if "frequence_chargee" not in st.session_state:

        st.session_state.frequence_chargee = False


    # ═══════════════════════════════════════════════════════════════════════
    # CHARGEMENT DES FICHIERS
    # ═══════════════════════════════════════════════════════════════════════

    ot_bytes = None
    av_bytes = None


    if (
        os.path.exists("ot.xlsx")
        and
        os.path.exists("avis.xlsx")
    ):

        with open(
            "ot.xlsx",
            "rb"
        ) as f:

            ot_bytes = f.read()


        with open(
            "avis.xlsx",
            "rb"
        ) as f:

            av_bytes = f.read()


    # ═══════════════════════════════════════════════════════════════════════
    # PREPARATION DES DONNEES
    # ═══════════════════════════════════════════════════════════════════════

    if ot_bytes and av_bytes:

        (
            df_full,
            av_full,
            apm,
            now_ts,
            avis_complet_full,
            avf_approve_full
        ) = prepare_data(
            ot_bytes,
            av_bytes,
            fichier_date
        )

    else:

        (
            df_full,
            av_full,
            apm,
            now_ts
        ) = (
            pd.DataFrame(),
            pd.DataFrame(),
            [],
            pd.Timestamp.now()
        )

        avis_complet_full = pd.DataFrame()

        avf_approve_full = pd.DataFrame()


    # ═══════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ═══════════════════════════════════════════════════════════════════════

    ctx = render_sidebar(
        fichier_date,
        apm,
        df_full,
        av_full,
        now_ts
    )


    vp = ctx["vp"]

    df_full = ctx["df_full"]

    av_full = ctx["av_full"]

    apm = ctx["apm"]

    now_ts = ctx["now_ts"]


    # ═══════════════════════════════════════════════════════════════════════
    # SI PAS DE DONNEES
    # ═══════════════════════════════════════════════════════════════════════

    if df_full.empty:

        st.markdown(
            """
            <div class="es">
            Veuillez charger les fichiers OT et AVIS
            via le panneau de filtres.
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            """
            <div class="footer">
            Bureau Methodes Maroc Chimie 2026
            </div>
            """,
            unsafe_allow_html=True
        )

        return


    # ═══════════════════════════════════════════════════════════════════════
    # CALCUL PRINCIPAL
    # ═══════════════════════════════════════════════════════════════════════

    try:

        sdt = ctx["sdt"]

        edt = ctx["edt"]


        # ───────────────────────────────────────────────────────────────────
        # FILTRE OT
        # ───────────────────────────────────────────────────────────────────

        df_period = df_full[
            df_full[
                "Date de début planifiée"
            ].between(
                sdt,
                edt
            )
        ].copy()


        # ───────────────────────────────────────────────────────────────────
        # FILTRE AVIS
        # ───────────────────────────────────────────────────────────────────

        avdf_period = av_full.copy()


        if "Créé le" in avdf_period.columns:

            avdf_period = avdf_period[
                avdf_period[
                    "Créé le"
                ].between(
                    sdt,
                    edt
                )
            ]


        # ═══════════════════════════════════════════════════════════════════
        # CALCUL KPI
        # ═══════════════════════════════════════════════════════════════════

        res = calc_kpis_cached(
            df_period,
            avdf_period,
            now_ts,
            tuple(apm),
            fichier_date,
            sdt,
            edt,
            df_period,
            avf_approve=avf_approve_full
        )


        ckdf_full = res["ckdf"]

        nd_full = res.get(
            "nd",
            {}
        )

        dfp_full = res["dfp"]

        avf_full = res["avf"]

        avf_approve_res = res.get(
            "avf_approve",
            avf_approve_full
        )


        # ═══════════════════════════════════════════════════════════════════
        # FILTRE POSTES
        # ═══════════════════════════════════════════════════════════════════

        vp_present = [
            p
            for p in vp
            if p in ckdf_full.index
        ]


        if vp_present:

            ckdf = ckdf_full.loc[
                vp_present
            ]

        else:

            ckdf = ckdf_full.iloc[
                0:0
            ]


        dfp = dfp_full[
            dfp_full[
                "Poste travail princ."
            ].isin(vp)
        ]


        if (
            "Poste travail princ."
            in avf_full.columns
        ):

            avf = avf_full[
                avf_full[
                    "Poste travail princ."
                ].isin(vp)
            ]

        else:

            avf = avf_full


        if (
            "Poste travail princ."
            in avf_approve_res.columns
        ):

            avf_approve = avf_approve_res[
                avf_approve_res[
                    "Poste travail princ."
                ].isin(vp)
            ]

        else:

            avf_approve = avf_approve_res


        if (
            "Poste travail princ."
            in avis_complet_full.columns
        ):

            avis_complet = avis_complet_full[
                avis_complet_full[
                    "Poste travail princ."
                ].isin(vp)
            ]

        else:

            avis_complet = avis_complet_full


        df = dfp


        # ═══════════════════════════════════════════════════════════════════
        # MOYENNES KPI
        # ═══════════════════════════════════════════════════════════════════

        pa = {
            k: round(
                ckdf[k].mean(
                    skipna=True
                ),
                2
            )
            for k in QK
        }


        qa = {
            k: round(
                ckdf[k].mean(
                    skipna=True
                ),
                2
            )
            for k in PK
        }


        # ═══════════════════════════════════════════════════════════════════
        # SCORE PERFORMANCE / QUALITE PAR POSTE
        # ═══════════════════════════════════════════════════════════════════

        pscores = {}

        qscores = {}


        for poste in ckdf.index:

            r = ckdf.loc[
                poste
            ]


            valid_q = [
                k
                for k in QK
                if k in r.index
                and pd.notna(r[k])
            ]


            valid_p = [
                k
                for k in PK
                if k in r.index
                and pd.notna(r[k])
            ]


            pscores[poste] = (

                sum(
                    gscore(
                        k,
                        r[k],
                        CIBLE[k]
                    )
                    for k in valid_q
                )
                /
                len(valid_q)
                *
                100

            ) if valid_q else 0


            qscores[poste] = (

                sum(
                    gscore(
                        k,
                        r[k],
                        CIBLE[k]
                    )
                    for k in valid_p
                )
                /
                len(valid_p)
                *
                100

            ) if valid_p else 0


        # ═══════════════════════════════════════════════════════════════════
        # SF1 / SF2
        # ═══════════════════════════════════════════════════════════════════

        sf1_posts = [
            p
            for p in vp
            if str(p).startswith("SF1")
        ]


        sf2_posts = [
            p
            for p in vp
            if str(p).startswith("SF2")
        ]


        # ═══════════════════════════════════════════════════════════════════
        # SCORE CELLULES
        # ═══════════════════════════════════════════════════════════════════

        def calc_score_cellules(
            postes,
            liste_kpi
        ):

            total = 0

            nombre_kpi = 0


            for poste in postes:

                if poste not in ckdf.index:

                    continue


                r = ckdf.loc[
                    poste
                ]


                for kpi in liste_kpi:

                    if kpi not in r.index:

                        continue


                    val = r[kpi]


                    if pd.isna(val):

                        continue


                    total += gscore(
                        kpi,
                        float(val),
                        CIBLE[kpi]
                    )


                    nombre_kpi += 1


            return round(

                (
                    total
                    /
                    nombre_kpi
                )
                * 100,
                2

            ) if nombre_kpi else 0


        # ═══════════════════════════════════════════════════════════════════
        # ANOMALIES
        # ═══════════════════════════════════════════════════════════════════

        ano_map = build_ano_map(
            dfp,
            avf,
            now_ts,
            dfp_toutes_dates=df_period,
            avf_approve=avf_approve
        )


        # ═══════════════════════════════════════════════════════════════════
        # SCORE SF1 / SF2
        # ═══════════════════════════════════════════════════════════════════

        sf1_p = int(
            calc_score_cellules(
                sf1_posts,
                QK
            )
        )

        sf1_q = int(
            calc_score_cellules(
                sf1_posts,
                PK
            )
        )

        sf2_p = int(
            calc_score_cellules(
                sf2_posts,
                QK
            )
        )

        sf2_q = int(
            calc_score_cellules(
                sf2_posts,
                PK
            )
        )


        # ═══════════════════════════════════════════════════════════════════
        # TABLEAUX ANOMALIES
        # ═══════════════════════════════════════════════════════════════════

        ano_p_rows = build_ano_rows(
            vp,
            ano_map,
            QK
        )


        ano_q_rows = build_ano_rows(
            vp,
            ano_map,
            PK,
            fixed_zero=[
                "OT Fiabilité",
                "Total Avis de Panne"
            ]
        )


        ano_p_cols = [
            "Poste de travail"
        ] + QK + [
            "Total Anomalies"
        ]


        ano_q_cols = [
            "Poste de travail"
        ] + PK + [
            "Total Anomalies"
        ]


        anomaly_dfs = build_anomaly_dfs(
            dfp,
            avf,
            now_ts,
            dfp_toutes_dates=df_period,
            avf_approve=avf_approve
        )


        # ═══════════════════════════════════════════════════════════════════
        # EXPORT ANOMALIES
        # ═══════════════════════════════════════════════════════════════════

        with st.sidebar:

            with st.expander(
                "📥 Export anomalies (OT + Avis)",
                expanded=False
            ):

                try:

                    from core.export_anomalies import (
                        build_anomalies_workbook
                    )


                    _xlsx_bytes = build_anomalies_workbook(
                        anomaly_dfs,
                        KPI_RESP_MAP,
                        ACT_MAP
                    )


                    st.download_button(
                        "⬇️ Télécharger le fichier anomalies (.xlsx)",
                        data=_xlsx_bytes,
                        file_name=(
                            "anomalies_OT_Avis_"
                            f"{fichier_date.replace('/','-')}.xlsx"
                        ),
                        mime=(
                            "application/vnd.openxmlformats-"
                            "officedocument.spreadsheetml.sheet"
                        ),
                        use_container_width=True,
                    )


                    st.caption(
                        "Contient 2 feuilles : Anomalies OT et "
                        "Anomalies Avis, avec Responsable et Action "
                        "recommandée."
                    )


                except Exception as _e:

                    st.caption(
                        f"Export indisponible : {_e}"
                    )


        # ═══════════════════════════════════════════════════════════════════
        # TABLEAUX PERFORMANCE / QUALITE
        # ═══════════════════════════════════════════════════════════════════

        pcols = [
            "Poste de travail"
        ] + QK + [
            "Score Performance"
        ]


        qcols = [
            "Poste de travail"
        ] + PK + [
            "Score Qualite"
        ]


        prows = []

        qrows = []


        for poste in ckdf.index:

            r = ckdf.loc[
                poste
            ]


            prw = {
                "Poste de travail": poste
            }


            for k in QK:

                prw[k] = (
                    "%.1f" % r[k]
                    if k in r.index
                    else "0.0"
                )


            prw[
                "Score Performance"
            ] = "%.2f" % pscores.get(
                poste,
                0
            )


            prows.append(
                prw
            )


            qrw = {
                "Poste de travail": poste
            }


            for k in PK:

                qrw[k] = (
                    "%.1f" % r[k]
                    if k in r.index
                    else "0.0"
                )


            qrw[
                "Score Qualite"
            ] = "%.2f" % qscores.get(
                poste,
                0
            )


            qrows.append(
                qrw
            )


        # ═══════════════════════════════════════════════════════════════════
        # LIGNE CIBLE
        # ═══════════════════════════════════════════════════════════════════

        cible_p = {
            "Poste de travail": "CIBLE",
            "_t": "cible"
        }


        for k in QK:

            cible_p[k] = "%.0f" % CIBLE.get(
                k,
                100
            )


        cible_p[
            "Score Performance"
        ] = "100"


        prows.append(
            cible_p
        )


        cible_q = {
            "Poste de travail": "CIBLE",
            "_t": "cible"
        }


        for k in PK:

            cible_q[k] = "%.0f" % CIBLE.get(
                k,
                100
            )


        cible_q[
            "Score Qualite"
        ] = "100"


        qrows.append(
            cible_q
        )


        # ═══════════════════════════════════════════════════════════════════
        # TOTAL GENERAL PERFORMANCE
        # ═══════════════════════════════════════════════════════════════════

        tot_p = {
            "Poste de travail": "Total general",
            "_t": "total"
        }


        for k in QK:

            cc = 0

            tc = 0


            for rw in prows:

                if (
                    k in rw
                    and rw.get("_t")
                    not in (
                        "cible",
                        "total"
                    )
                ):

                    try:

                        fv = float(
                            rw[k]
                        )


                        if pd.notna(fv):

                            cc += gscore(
                                k,
                                fv,
                                CIBLE.get(
                                    k,
                                    100
                                )
                            )

                            tc += 1


                    except Exception:

                        pass


            tot_p[k] = (

                "%.1f"
                %
                (
                    (
                        cc
                        /
                        tc
                    )
                    * 100
                )

            ) if tc > 0 else "nan"


        tot_p[
            "Score Performance"
        ] = "%.2f" % calc_score_cellules(
            vp,
            QK
        )


        prows.append(
            tot_p
        )


        # ═══════════════════════════════════════════════════════════════════
        # TOTAL GENERAL QUALITE
        # ═══════════════════════════════════════════════════════════════════

        tot_q = {
            "Poste de travail": "Total general",
            "_t": "total"
        }


        for k in PK:

            cc = 0

            tc = 0


            for rw in qrows:

                if (
                    k in rw
                    and rw.get("_t")
                    not in (
                        "cible",
                        "total"
                    )
                ):

                    try:

                        fv = float(
                            rw[k]
                        )


                        if pd.notna(fv):

                            cc += gscore(
                                k,
                                fv,
                                CIBLE.get(
                                    k,
                                    100
                                )
                            )

                            tc += 1


                    except Exception:

                        pass


            tot_q[k] = (

                "%.1f"
                %
                (
                    (
                        cc
                        /
                        tc
                    )
                    * 100
                )

            ) if tc > 0 else "nan"


        tot_q[
            "Score Qualite"
        ] = "%.2f" % calc_score_cellules(
            vp,
            PK
        )


        qrows.append(
            tot_q
        )


        # ═══════════════════════════════════════════════════════════════════
        # SAUVEGARDE HISTORIQUE EXCEL
        # ═══════════════════════════════════════════════════════════════════

        save_kpis_to_excel(
            prows,
            pcols,
            qrows,
            qcols,
            ano_p_rows,
            ano_p_cols,
            ano_q_rows,
            ano_q_cols,
            fichier_date,
        )


        # ═══════════════════════════════════════════════════════════════════
        # HISTORIQUE
        # ═══════════════════════════════════════════════════════════════════

        from core.export_excel import (
            charger_historique_depuis_github
        )


        hist_df, _hist_msg = (
            charger_historique_depuis_github()
        )


        var_df = calculate_variations(
            hist_df
        )


        journal_df = generate_journal(
            var_df
        )


        top5_df, bot5_df = calculate_rankings(
            var_df
        )


        # ═══════════════════════════════════════════════════════════════════
        # EXPORT SUIVI DATE SIDEBAR
        # ═══════════════════════════════════════════════════════════════════

        from core.export_excel import render_sidebar_suivi_date_export

        render_sidebar_suivi_date_export(
            fichier_date=fichier_date,
            prows=prows,
            pcols=pcols,
            qrows=qrows,
            qcols=qcols,
            ano_p_r=ano_p_rows,
            ano_p_c=ano_p_cols,
            ano_q_r=ano_q_rows,
            ano_q_c=ano_q_cols,
            hist_df=hist_df,
            var_df=var_df,
            sdt=sdt,
            edt=edt,
        )


        # ═══════════════════════════════════════════════════════════════════
        # SYNTHESE
        # ═══════════════════════════════════════════════════════════════════

        synth_perf = {}

        synth_qual = {}


        if (
            not var_df.empty
            and
            "Date precedente" in var_df.columns
        ):

            for poste in vp:

                synth_perf[poste] = {}

                synth_qual[poste] = {}


                pv = var_df[
                    var_df["Poste"] == poste
                ]


                for kpi in QK:

                    kpi_v = pv[
                        pv["KPI"] == kpi
                    ]


                    if not kpi_v.empty:

                        synth_perf[
                            poste
                        ][kpi] = {
                            "diff":
                            "%+.1f"
                            %
                            kpi_v.iloc[-1][
                                "Ecart"
                            ]
                        }

                    else:

                        synth_perf[
                            poste
                        ][kpi] = {
                            "diff": "---"
                        }


                for kpi in PK:

                    kpi_v = pv[
                        pv["KPI"] == kpi
                    ]


                    if not kpi_v.empty:

                        synth_qual[
                            poste
                        ][kpi] = {
                            "diff":
                            "%+.1f"
                            %
                            kpi_v.iloc[-1][
                                "Ecart"
                            ]
                        }

                    else:

                        synth_qual[
                            poste
                        ][kpi] = {
                            "diff": "---"
                        }


        # ═══════════════════════════════════════════════════════════════════
        # PLAN D'ACTION
        # ═══════════════════════════════════════════════════════════════════

        plan_actions_rows = []


        for poste in vp:

            if poste not in ckdf.index:

                continue


            poste_data = ckdf.loc[
                poste
            ]


            for kpi in ALL_KPI:

                actual = float(
                    poste_data.get(
                        kpi,
                        100
                    )
                )


                target = CIBLE.get(
                    kpi,
                    100
                )


                nb_anom = int(
                    ano_map
                    .get(
                        kpi,
                        pd.Series()
                    )
                    .get(
                        poste,
                        0
                    )
                )


                lower = is_lb(
                    kpi
                )


                ecart = (
                    target - actual
                    if lower
                    else
                    actual - target
                )


                if nb_anom == 0:

                    ecart = 0.0


                conforme = (
                    actual <= target
                    if lower
                    else
                    actual >= target
                )


                if nb_anom == 0:

                    status = "non_vert"

                elif conforme:

                    status = "oui_vert"

                else:

                    status = "oui_rouge"


                if nb_anom > 0:

                    plan_actions_rows.append(
                        {
                            "poste": poste,
                            "kpi": kpi,
                            "needs_action":
                                nb_anom > 0,
                            "status": status,
                            "ecart": ecart,
                            "nb_anom": nb_anom,
                            "actual": actual,
                            "target": target,
                            "responsable":
                                KPI_RESP_MAP.get(
                                    kpi,
                                    "Non assigne"
                                ),
                            "action":
                                ACT_MAP.get(
                                    kpi,
                                    ""
                                ),
                            "delai": "",
                        }
                    )


        sf1_rows = [
            r
            for r in plan_actions_rows
            if str(
                r["poste"]
            ).startswith("SF1")
        ]


        sf2_rows = [
            r
            for r in plan_actions_rows
            if str(
                r["poste"]
            ).startswith("SF2")
        ]


        # ═══════════════════════════════════════════════════════════════════
        # ETOILES
        # ═══════════════════════════════════════════════════════════════════

        poste_stars = {}


        for poste in vp:

            ps = pscores.get(
                poste
            )

            qs = qscores.get(
                poste
            )


            vals = [
                v
                for v in (
                    ps,
                    qs
                )
                if v is not None
                and pd.notna(v)
            ]


            if vals:

                score_global = (
                    sum(vals)
                    /
                    len(vals)
                )


                stars = round(
                    score_global
                    /
                    20
                )


                stars = max(
                    0,
                    min(
                        5,
                        stars
                    )
                )


            else:

                score_global = None

                stars = 0


            poste_stars[
                poste
            ] = {
                "score":
                    score_global,
                "stars":
                    stars
            }


        # ═══════════════════════════════════════════════════════════════════
        # SCORES GENERAUX
        # ═══════════════════════════════════════════════════════════════════

        try:

            avg_p_score = float(
                tot_p[
                    "Score Performance"
                ]
            )

        except Exception:

            avg_p_score = 0


        try:

            avg_q_score = float(
                tot_q[
                    "Score Qualite"
                ]
            )

        except Exception:

            avg_q_score = 0


        total_ano_p = sum(
            r[
                "Total Anomalies"
            ]
            for r in ano_p_rows
            if r.get(
                "Poste de travail"
            ) != "Total"
        )


        total_ano_q = sum(
            r[
                "Total Anomalies"
            ]
            for r in ano_q_rows
            if r.get(
                "Poste de travail"
            ) != "Total"
        )


        total_ot = len(
            df
        )


        # ═══════════════════════════════════════════════════════════════════
        # HEADER
        # ═══════════════════════════════════════════════════════════════════

        render_header(
            fichier_date
        )


        prev_values = get_previous_card_values(
            hist_df
        )


        render_cards(
            total_ot,
            avg_p_score,
            avg_q_score,
            total_ano_p + total_ano_q,
            sf1_p,
            sf1_q,
            sf2_p,
            sf2_q,
            prev_values,
        )


        # ═══════════════════════════════════════════════════════════════════
        # TABS
        #
        # Taux de Réalisation SUPPRIME
        # ═══════════════════════════════════════════════════════════════════

        tabs = st.tabs(
            [
                "🏠 Tableau de Bord",
                "📊 Performance / Qualité",
                "📂 Backlog",
                "📋 Suivi & Evolution",
                "🎯 Plan d'action",
                "🦺 Suivi HSE",
                "🔄 Fréquence Maintenance",
            ]
        )


        # ═══════════════════════════════════════════════════════════════════
        # TAB 0 — TABLEAU DE BORD
        # ═══════════════════════════════════════════════════════════════════

        with tabs[0]:

            render_dashboard_tab(
                vp,
                pscores,
                qscores,
                pa,
                qa,
                hist_df,
                now_ts,
                ano_map,
                ckdf,
                sdt,
                edt
            )


        # ═══════════════════════════════════════════════════════════════════
        # TAB 1 — PERFORMANCE / QUALITE
        # ═══════════════════════════════════════════════════════════════════

        with tabs[1]:

            render_performance_qualite_tab(
                vp,
                ckdf,
                ano_map,
                anomaly_dfs,
                nd_full
            )


        # ═══════════════════════════════════════════════════════════════════
        # TAB 2 — BACKLOG
        # ═══════════════════════════════════════════════════════════════════

        with tabs[2]:

            render_backlog_page(
                dfp,
                vp
            )


        # ═══════════════════════════════════════════════════════════════════
        # TAB 3 — EVOLUTION
        # ═══════════════════════════════════════════════════════════════════

        with tabs[3]:

            n_dates = 0


            if (
                not hist_df.empty
                and
                "Date" in hist_df.columns
            ):

                n_dates = hist_df[
                    "Date"
                ].nunique()


            with st.expander(
                f"📁 Historique : {n_dates} date(s) "
                "enregistrée(s) — cliquez pour détails",
                expanded=(
                    n_dates < 2
                )
            ):

                st.caption(
                    f"Source : GitHub — {_hist_msg}"
                )


                if n_dates < 2:

                    st.info(
                        "ℹ️ Il faut **au moins 2 dates** "
                        "pour calculer des variations. "
                        f"Actuellement, l'historique contient "
                        f"{n_dates} date(s).\n\n"
                        "**L'enregistrement est désormais "
                        "automatique** : à chaque chargement "
                        "d'une extraction avec une nouvelle date "
                        "dans `date.txt`, la date est ajoutée "
                        "directement à `kpis/indicateurs_kpis.xlsx` "
                        "sur GitHub."
                    )

                else:

                    st.success(
                        f"✅ {n_dates} dates enregistrées sur GitHub. "
                        "Chaque nouvelle extraction est ajoutée "
                        "automatiquement."
                    )


                try:

                    from core.export_excel import get_historique_bytes

                    _bytes_hist, _dates_hist = get_historique_bytes()

                    if _bytes_hist:

                        st.download_button(
                            "⬇️ Télécharger l'historique complet "
                            "(indicateurs_kpis.xlsx)",
                            data=_bytes_hist,
                            file_name=(
                                "indicateurs_kpis.xlsx"
                            ),
                            mime=(
                                "application/vnd.openxmlformats-"
                                "officedocument.spreadsheetml.sheet"
                            ),
                            use_container_width=True,
                            key="dl_hist_complet_tab3",
                        )


                except Exception as _e_dl:

                    st.caption(
                        f"Téléchargement indisponible : {_e_dl}"
                    )


            render_evolution_tab(
                hist_df,
                var_df,
                journal_df,
                top5_df,
                bot5_df,
                synth_perf,
                synth_qual,
                vp,
                now_ts,
                df_full,
                av_full,
                apm,
            )


        # ═══════════════════════════════════════════════════════════════════
        # TAB 4 — PLAN D'ACTION
        # ═══════════════════════════════════════════════════════════════════

        with tabs[4]:

            try:

                from core.export_pptx import (
                    build_presentation
                )


                pptx_bytes = build_presentation(
                    vp,
                    ckdf,
                    ano_map,
                    pa,
                    qa,
                    pscores,
                    qscores,
                    hist_df,
                    fichier_date,
                )


                _ent = (
                    "Maroc_Chimie"
                    if all(
                        str(p).startswith("SF1")
                        for p in vp
                    )
                    else (
                        "FEEDS"
                        if all(
                            str(p).startswith("SF2")
                            for p in vp
                        )
                        else "OCP"
                    )
                )


                st.download_button(
                    "📊 Exporter la présentation PowerPoint",
                    data=pptx_bytes,
                    file_name=(
                        f"Presentation_KPIs_"
                        f"{_ent}_"
                        f"{fichier_date.replace('/','-')}.pptx"
                    ),
                    mime=(
                        "application/vnd.openxmlformats-"
                        "officedocument.presentationml.presentation"
                    ),
                    use_container_width=True,
                )


            except Exception as _e:

                st.caption(
                    f"Export PowerPoint indisponible : {_e}"
                )


            st.markdown("---")


            st.markdown(
                "#### 📤 Rapports KPI par poste (PDF + Excel)"
            )


            _publication_ok = True


            try:

                from core.publish_reports import (
                    generate_and_publish_all_postes
                )

                from core.github_publish import (
                    is_configured as _github_configured
                )

                from core.github_publish import (
                    debug_config as _github_debug_config
                )


                st.caption(
                    "🔧 Config GitHub détectée : "
                    f"{_github_debug_config()}"
                )


            except Exception as _e_imp:

                _publication_ok = False


                st.error(
                    "❌ Module de publication des rapports "
                    f"indisponible : {_e_imp}\n\n"
                    "Le plan d'action reste consultable ci-dessous."
                )


            if (
                _publication_ok
                and
                not _github_configured()
            ):

                st.caption(
                    "⚠️ Publication GitHub non configurée "
                    "(GITHUB_TOKEN / GITHUB_REPO absents des secrets). "
                    "Les rapports seront générés mais pas publiés."
                )


            if _publication_ok:

                _col_pub, _col_dry = st.columns(2)

            else:

                _col_pub = None

                _col_dry = None


            _launch_publish = False

            _launch_dry = False


            if _publication_ok:

                with _col_pub:

                    _launch_publish = st.button(
                        f"🚀 Générer et publier les rapports "
                        f"({len(vp)} poste(s))",
                        use_container_width=True,
                        type="primary",
                        key="btn_publish_all",
                    )


                with _col_dry:

                    _launch_dry = st.button(
                        "🧪 Générer seulement "
                        "(test, sans publier)",
                        use_container_width=True,
                        key="btn_dry_all",
                    )


            if (
                _publication_ok
                and
                (
                    _launch_publish
                    or
                    _launch_dry
                )
            ):

                _progress = st.progress(
                    0,
                    text="Démarrage..."
                )


                _status_area = st.empty()


                def _on_progress(
                    i,
                    n,
                    poste
                ):

                    _progress.progress(
                        i / n,
                        text=f"[{i + 1}/{n}] {poste}..."
                    )


                _kwargs_pub = {}
                try:
                    import inspect
                    _sig = inspect.signature(generate_and_publish_all_postes)
                    if "dfp_toutes_dates" in _sig.parameters:
                        _kwargs_pub["dfp_toutes_dates"] = df_period
                    if "hist_df" in _sig.parameters:
                        _kwargs_pub["hist_df"] = hist_df
                except Exception:
                    pass

                _results = (
                    generate_and_publish_all_postes(
                        ckdf,
                        pscores,
                        qscores,
                        ano_map,
                        dfp,
                        avf,
                        now_ts,
                        date_str=fichier_date,
                        postes=list(vp),
                        dry_run=_launch_dry,
                        progress_callback=_on_progress,
                        **_kwargs_pub,
                    )
                )


                _progress.progress(
                    1.0,
                    text="Terminé."
                )


                _ok_pdf = sum(
                    1
                    for r in _results
                    if r.get("pdf")
                )


                _ok_xlsx = sum(
                    1
                    for r in _results
                    if r.get("xlsx")
                )


                _ok_pub = sum(
                    1
                    for r in _results
                    if r.get("pdf_published")
                )


                with _status_area.container():

                    if _launch_dry:

                        st.success(
                            f"✅ Génération test terminée : "
                            f"{_ok_pdf}/{len(_results)} PDF, "
                            f"{_ok_xlsx}/{len(_results)} Excel."
                        )

                    else:

                        st.success(
                            f"✅ {_ok_pub}/{len(_results)} "
                            "postes publiés sur GitHub "
                            "(presentation/<poste>/) — "
                            f"{_ok_pdf} PDF, "
                            f"{_ok_xlsx} Excel générés."
                        )


                    with st.expander(
                        "Détail par poste"
                    ):

                        for r in _results:

                            _icons = "".join(
                                [
                                    "📄"
                                    if r.get("pdf")
                                    else "❌",

                                    "📈"
                                    if r.get("xlsx")
                                    else "❌",
                                ]
                            )


                            st.caption(
                                f"{_icons}  "
                                f"**{r['poste']}** — "
                                +
                                " / ".join(
                                    r.get(
                                        "messages",
                                        []
                                    )
                                )
                            )


                    # ═══════════════════════════════════════════════════
                    # POWER AUTOMATE / ONEDRIVE
                    # ═══════════════════════════════════════════════════

                    if (
                        not _launch_dry
                        and
                        _ok_pub > 0
                    ):

                        try:

                            _pa_url = st.secrets.get(
                                "POWER_AUTOMATE_WEBHOOK_URL"
                            )

                        except Exception:

                            _pa_url = None


                        if _pa_url:

                            try:

                                import requests as _requests


                                try:

                                    _repo = st.secrets.get(
                                        "GITHUB_REPO",
                                        ""
                                    )

                                    _branch = st.secrets.get(
                                        "GITHUB_BRANCH",
                                        "main"
                                    )

                                except Exception:

                                    _repo = ""

                                    _branch = "main"


                                _fichiers = []


                                for _r in _results:

                                    if not _r.get(
                                        "pdf_published"
                                    ):

                                        continue


                                    _dossier = "".join(
                                        c
                                        if (
                                            c.isalnum()
                                            or
                                            c in "-_"
                                        )
                                        else "_"
                                        for c in str(
                                            _r["poste"]
                                        )
                                    )


                                    _base = (
                                        f"presentation/"
                                        f"{_dossier}"
                                    )


                                    _entree = {

                                        "poste":
                                            _r["poste"],

                                        "dossier":
                                            _dossier,

                                        "pdf":
                                            f"{_base}/rapport.pdf",

                                        "pdf_url": (
                                            f"https://raw.githubusercontent.com/"
                                            f"{_repo}/"
                                            f"{_branch}/"
                                            f"{_base}/rapport.pdf"
                                            if _repo
                                            else ""
                                        ),
                                    }


                                    if _r.get(
                                        "xlsx_published"
                                    ):

                                        _entree[
                                            "xlsx"
                                        ] = (
                                            f"{_base}/"
                                            "anomalies.xlsx"
                                        )


                                        _entree[
                                            "xlsx_url"
                                        ] = (
                                            f"https://raw.githubusercontent.com/"
                                            f"{_repo}/"
                                            f"{_branch}/"
                                            f"{_base}/"
                                            "anomalies.xlsx"
                                            if _repo
                                            else ""
                                        )


                                    _fichiers.append(
                                        _entree
                                    )


                                _payload = {

                                    "date_extraction":
                                        fichier_date,

                                    "dossier_onedrive":
                                        "presentation",

                                    "repo":
                                        _repo,

                                    "branche":
                                        _branch,

                                    "nb_postes":
                                        len(
                                            _fichiers
                                        ),

                                    "fichiers":
                                        _fichiers,
                                }


                                _pa_resp = (
                                    _requests.post(
                                        _pa_url,
                                        json=_payload,
                                        timeout=30
                                    )
                                )


                                if _pa_resp.status_code in (
                                    200,
                                    201,
                                    202
                                ):

                                    st.success(
                                        "☁️ Enregistrement "
                                        "OneDrive déclenché : "
                                        f"{len(_fichiers)} "
                                        "rapport(s) envoyé(s)."
                                    )


                                    with st.expander(
                                        "Détail de ce qui a été "
                                        "transmis à Power Automate"
                                    ):

                                        st.json(
                                            _payload
                                        )


                                else:

                                    st.warning(
                                        "⚠️ Power Automate a répondu "
                                        f"{_pa_resp.status_code} : "
                                        f"{_pa_resp.text[:200]}"
                                    )


                            except Exception as _pa_e:

                                st.warning(
                                    "⚠️ Impossible de déclencher "
                                    f"Power Automate : {_pa_e}"
                                )


                        else:

                            st.warning(
                                "⚠️ Les rapports sont publiés sur "
                                "GitHub mais pas encore copiés vers "
                                "OneDrive : le secret "
                                "`POWER_AUTOMATE_WEBHOOK_URL` est absent."
                            )


            # ═══════════════════════════════════════════════════════════════
            # PLAN D'ACTION
            # ═══════════════════════════════════════════════════════════════

            render_plan_action_tab(
                plan_actions_rows,
                sf1_rows,
                sf2_rows,
                anomaly_dfs,
                fichier_date=fichier_date,
                poste_stars=poste_stars
            )


        # ═══════════════════════════════════════════════════════════════════
        # TAB 5 — SUIVI HSE
        #
        # IMPORTANT :
        # Aucun calcul render_suivi_hse_tab() au démarrage.
        # Il est exécuté uniquement après clic.
        # ═══════════════════════════════════════════════════════════════════

        with tabs[5]:

            st.markdown(
                "### 🦺 Suivi HSE"
            )


            if not st.session_state.hse_charge:

                st.info(
                    "ℹ️ Le Suivi HSE n'est pas chargé automatiquement "
                    "afin d'optimiser les ressources de l'application."
                )


                if st.button(
                    "▶️ Afficher le Suivi HSE",
                    type="primary",
                    use_container_width=True,
                    key="btn_charger_hse",
                ):

                    st.session_state.hse_charge = True

                    st.rerun()


            else:

                col_hse_1, col_hse_2 = st.columns(
                    [4, 1]
                )


                with col_hse_1:

                    st.success(
                        "✅ Suivi HSE activé"
                    )


                with col_hse_2:

                    if st.button(
                        "⏹ Masquer",
                        use_container_width=True,
                        key="btn_masquer_hse",
                    ):

                        st.session_state.hse_charge = False

                        st.rerun()


                try:

                    render_suivi_hse_tab(
                        dfp,
                        avis_complet,
                        vp,
                        fichier_date
                    )


                except Exception as _e:

                    st.error(
                        "Suivi HSE indisponible : "
                        f"{_e}"
                    )


        # ═══════════════════════════════════════════════════════════════════
        # TAB 6 — FREQUENCE MAINTENANCE
        #
        # IMPORTANT :
        # Aucun calcul render_frequence_maintenance_tab() au démarrage.
        # Il est exécuté uniquement après clic.
        # ═══════════════════════════════════════════════════════════════════

        with tabs[6]:

            st.markdown(
                "### 🔄 Fréquence Maintenance"
            )


            if not st.session_state.frequence_chargee:

                st.info(
                    "ℹ️ La Fréquence Maintenance n'est pas calculée "
                    "automatiquement afin d'optimiser les ressources "
                    "de l'application."
                )


                if st.button(
                    "▶️ Afficher la Fréquence Maintenance",
                    type="primary",
                    use_container_width=True,
                    key="btn_charger_frequence",
                ):

                    st.session_state.frequence_chargee = True

                    st.rerun()


            else:

                col_freq_1, col_freq_2 = st.columns(
                    [4, 1]
                )


                with col_freq_1:

                    st.success(
                        "✅ Fréquence Maintenance activée"
                    )


                with col_freq_2:

                    if st.button(
                        "⏹ Masquer",
                        use_container_width=True,
                        key="btn_masquer_frequence",
                    ):

                        st.session_state.frequence_chargee = False

                        st.rerun()


                try:

                    render_frequence_maintenance_tab(
                        df_full
                    )


                except Exception as _e:

                    st.error(
                        "Fréquence de maintenance indisponible : "
                        f"{_e}"
                    )


    # ═══════════════════════════════════════════════════════════════════════
    # ERREUR GENERALE
    # ═══════════════════════════════════════════════════════════════════════

    except Exception as e:

        st.error(
            "Erreur lors du chargement des donnees : "
            f"{str(e)}"
        )


        st.markdown(
            """
            <div class="es">
            Veuillez verifier que les fichiers
            ot.xlsx et avis.xlsx sont presents.
            </div>
            """,
            unsafe_allow_html=True
        )


    # ═══════════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════════

    st.markdown(
        """
        <div class="footer">
        Bureau Methodes Maroc Chimie 2026
        </div>
        """,
        unsafe_allow_html=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    main()
