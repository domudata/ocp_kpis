# -*- coding: utf-8 -*-

import locale
import os
import random
import time
import traceback

import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURATION STREAMLIT
# ============================================================

st.set_page_config(
    layout="wide",
    page_title="Suivi HSE",
    initial_sidebar_state="expanded"
)


# ============================================================
# MODE ACTUEL
# ============================================================
#
# True  = uniquement Suivi HSE
# False = ancien dashboard complet
#
# Pour réactiver plus tard tout le dashboard :
#
# HSE_ONLY = False
#
# ============================================================

HSE_ONLY = True


# ============================================================
# IMPORTS PROTEGES
# ============================================================

try:

    from core.constants import CONSIGNES_HSE

    from core.prepare_data import (
        prepare_data,
        get_date_from_file
    )

    from components.styles import inject_custom_css

    from pages.suivi_hse import render_suivi_hse_tab

    _IMPORT_ERROR = None

except Exception as _e:

    _IMPORT_ERROR = traceback.format_exc()


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def main() -> None:

    # --------------------------------------------------------
    # Vérification imports
    # --------------------------------------------------------

    if _IMPORT_ERROR is not None:

        st.error(
            "❌ Erreur lors du chargement des modules."
        )

        st.code(
            _IMPORT_ERROR,
            language="python"
        )

        st.stop()


    # --------------------------------------------------------
    # Locale française
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # CSS
    # --------------------------------------------------------

    try:

        inject_custom_css()

    except Exception:

        pass


    # --------------------------------------------------------
    # Masquer éléments Streamlit inutiles
    # --------------------------------------------------------

    st.markdown(
        """
        <style>

        [data-testid="stSidebarNav"] {
            display: none;
        }

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


    # ========================================================
    # DATE EXTRACTION
    # ========================================================

    try:

        fichier_date = get_date_from_file()

    except Exception:

        fichier_date = ""


    # ========================================================
    # PAGE HSE - CONSIGNE DE SECURITE
    # ========================================================

    if "hse_affiche" not in st.session_state:

        st.session_state.hse_affiche = False


    # --------------------------------------------------------
    # Première ouverture : écran HSE
    # --------------------------------------------------------

    if not st.session_state.hse_affiche:

        try:

            c = random.choice(
                CONSIGNES_HSE
            )

        except Exception:

            c = (
                "Aucun travail n'est plus urgent "
                "que la sécurité."
            )


        st.markdown(
            """
            <div style="
                min-height:100vh;
                display:flex;
                flex-direction:column;
                align-items:center;
                justify-content:center;
                background:
                    linear-gradient(
                        135deg,
                        #1a365d,
                        #2d3748,
                        #1a365d
                    );
                padding:40px;
            ">

                <div style="
                    font-size:64px;
                    margin-bottom:20px;
                ">
                    &#128282;
                </div>

                <h1 style="
                    text-align:center;
                    font-size:46px;
                    color:#fff;
                    font-weight:900;
                    margin:0;
                ">
                    HSE - CONSIGNE DE SECURITE
                </h1>

                <p style="
                    text-align:center;
                    color:rgba(255,255,255,.6);
                    font-size:22px;
                    margin-top:8px;
                    letter-spacing:3px;
                    text-transform:uppercase;
                ">
                    Securite - Sante - Environnement
                </p>

                <div style="
                    background:
                        linear-gradient(
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
                        0 20px 60px rgba(0,0,0,.3);
                ">
                    %s
                </div>

                <h2 style="
                    text-align:center;
                    color:#48bb78;
                    font-size:36px;
                    font-weight:900;
                ">
                    Aucun travail n'est plus urgent
                    que la securite
                </h2>

                <div style="
                    margin-top:40px;
                    width:200px;
                    height:4px;
                    background:rgba(255,255,255,.1);
                    border-radius:2px;
                    overflow:hidden;
                ">

                    <div style="
                        width:100%%;
                        height:100%%;
                        background:
                            linear-gradient(
                                90deg,
                                #48bb78,
                                #38a169
                            );
                        border-radius:2px;
                        animation:
                            ld 5.5s
                            ease-in-out
                            forwards;
                    ">
                    </div>

                </div>

                <style>

                @keyframes ld {

                    from {
                        width:0;
                    }

                    to {
                        width:100%%;
                    }

                }

                </style>

            </div>
            """
            % c,
            unsafe_allow_html=True
        )


        # ----------------------------------------------------
        # Attente écran HSE
        # ----------------------------------------------------

        time.sleep(6)

        st.session_state.hse_affiche = True

        st.rerun()

        st.stop()


    # ========================================================
    # MODE HSE UNIQUEMENT
    # ========================================================

    if HSE_ONLY:

        # ----------------------------------------------------
        # Sidebar minimale
        # ----------------------------------------------------

        with st.sidebar:

            st.markdown(
                """
                <h2 style="
                    text-align:center;
                    margin-bottom:20px;
                ">
                    🦺 Suivi HSE
                </h2>
                """,
                unsafe_allow_html=True
            )

            st.info(
                "Mode HSE uniquement.\n\n"
                "Les calculs KPI sont désactivés."
            )

            st.markdown("---")

            st.caption(
                f"Date extraction : {fichier_date}"
            )


        # ====================================================
        # CHARGEMENT DES FICHIERS
        # ====================================================

        ot_path = "ot.xlsx"
        avis_path = "avis.xlsx"


        # ----------------------------------------------------
        # Vérification OT
        # ----------------------------------------------------

        if not os.path.exists(ot_path):

            st.error(
                "❌ Le fichier `ot.xlsx` est introuvable."
            )

            st.info(
                "Placez `ot.xlsx` à la racine du projet."
            )

            st.stop()


        # ----------------------------------------------------
        # Vérification AVIS
        # ----------------------------------------------------

        if not os.path.exists(avis_path):

            st.error(
                "❌ Le fichier `avis.xlsx` est introuvable."
            )

            st.info(
                "Placez `avis.xlsx` à la racine du projet."
            )

            st.stop()


        # ====================================================
        # LECTURE DES FICHIERS
        # ====================================================

        try:

            with open(
                ot_path,
                "rb"
            ) as f:

                ot_bytes = f.read()


            with open(
                avis_path,
                "rb"
            ) as f:

                av_bytes = f.read()


        except Exception as e:

            st.error(
                f"❌ Erreur lecture fichiers : {e}"
            )

            st.stop()


        # ====================================================
        # PREPARATION DES DONNEES HSE
        # ====================================================
        #
        # IMPORTANT :
        #
        # prepare_data() reste nécessaire ici uniquement
        # parce que la page HSE actuelle utilise les données
        # préparées.
        #
        # Aucun calc_kpis()
        # Aucun anomaly
        # Aucun historique
        # Aucun score
        # Aucun rapport
        #
        # ====================================================

        try:

            result = prepare_data(
                ot_bytes,
                av_bytes,
                fichier_date
            )


            # ------------------------------------------------
            # Compatibilité avec les différentes versions
            # de prepare_data()
            # ------------------------------------------------

            if len(result) == 5:

                (
                    df_full,
                    av_full,
                    apm,
                    now_ts,
                    avis_complet_full
                ) = result

            elif len(result) == 4:

                (
                    df_full,
                    av_full,
                    apm,
                    now_ts
                ) = result

                avis_complet_full = av_full.copy()

            else:

                st.error(
                    "❌ Format inattendu retourné "
                    "par prepare_data()."
                )

                st.stop()


        except Exception as e:

            st.error(
                "❌ Erreur lors de la préparation "
                "des données HSE."
            )

            st.exception(e)

            st.stop()


        # ====================================================
        # VERIFICATION DATA
        # ====================================================

        if df_full is None:

            st.error(
                "❌ Les données OT sont vides."
            )

            st.stop()


        if not isinstance(
            df_full,
            pd.DataFrame
        ):

            st.error(
                "❌ df_full n'est pas un DataFrame."
            )

            st.stop()


        if df_full.empty:

            st.warning(
                "⚠️ Aucune donnée OT disponible."
            )

            st.stop()


        # ====================================================
        # POSTES DISPONIBLES
        # ====================================================

        try:

            if (
                "Poste travail princ."
                in df_full.columns
            ):

                postes_disponibles = sorted(
                    df_full[
                        "Poste travail princ."
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )

            else:

                postes_disponibles = []


        except Exception:

            postes_disponibles = []


        # ====================================================
        # FILTRE POSTES HSE
        # ====================================================

        with st.sidebar:

            if postes_disponibles:

                vp = st.multiselect(
                    "Poste de travail",
                    options=postes_disponibles,
                    default=postes_disponibles,
                    key="hse_postes"
                )

            else:

                vp = []


        # ====================================================
        # APPLICATION FILTRE HSE
        # ====================================================

        if vp:

            try:

                df_hse = df_full[
                    df_full[
                        "Poste travail princ."
                    ].astype(str).isin(vp)
                ].copy()

            except Exception:

                df_hse = df_full.copy()


            try:

                if (
                    isinstance(
                        avis_complet_full,
                        pd.DataFrame
                    )
                    and
                    "Poste travail princ."
                    in avis_complet_full.columns
                ):

                    avis_hse = avis_complet_full[
                        avis_complet_full[
                            "Poste travail princ."
                        ].astype(str).isin(vp)
                    ].copy()

                else:

                    avis_hse = avis_complet_full

            except Exception:

                avis_hse = avis_complet_full

        else:

            # Aucun poste sélectionné
            df_hse = df_full.iloc[0:0].copy()

            if isinstance(
                avis_complet_full,
                pd.DataFrame
            ):

                avis_hse = avis_complet_full.iloc[0:0].copy()

            else:

                avis_hse = avis_complet_full


        # ====================================================
        # HEADER HSE
        # ====================================================

        st.markdown(
            """
            <div style="
                padding:18px 24px;
                border-radius:12px;
                background:
                    linear-gradient(
                        135deg,
                        #1a365d,
                        #2d3748
                    );
                color:white;
                margin-bottom:20px;
            ">

                <h1 style="
                    margin:0;
                    font-size:30px;
                    font-weight:900;
                ">
                    🦺 Suivi HSE
                </h1>

                <div style="
                    margin-top:5px;
                    opacity:.75;
                    font-size:14px;
                ">
                    Suivi Hygiène - Sécurité -
                    Environnement
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )


        # ====================================================
        # PAGE SUIVI HSE
        # ====================================================

        try:

            render_suivi_hse_tab(
                df_hse,
                avis_hse,
                vp,
                fichier_date
            )

        except Exception as e:

            st.error(
                "❌ Suivi HSE indisponible."
            )

            st.exception(e)


        # ====================================================
        # FOOTER
        # ====================================================

        st.markdown(
            """
            <div style="
                text-align:center;
                margin-top:40px;
                padding:15px;
                color:#718096;
                font-size:12px;
            ">
                Bureau Methodes Maroc Chimie 2026
                — Mode HSE uniquement
            </div>
            """,
            unsafe_allow_html=True
        )


        # ====================================================
        # STOP IMPORTANT
        # ====================================================
        #
        # Cette ligne empêche Streamlit de continuer vers
        # tout l'ancien code KPI situé plus bas.
        #
        # ====================================================

        st.stop()


    # ========================================================
    # MODE DASHBOARD COMPLET
    # ========================================================
    #
    # Ce bloc n'est pas exécuté lorsque :
    #
    # HSE_ONLY = True
    #
    # Il est conservé volontairement pour permettre de
    # réactiver le dashboard plus tard.
    #
    # ========================================================

    st.info(
        "Mode Dashboard complet activé."
    )

    st.warning(
        "Le code du dashboard complet est désactivé "
        "dans cette version HSE."
    )


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":

    main()
