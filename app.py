# -*- coding: utf-8 -*-

import locale
import os
import time
import traceback

import numpy as np
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
# MODE HSE UNIQUEMENT
# ============================================================
#
# True  = uniquement Suivi HSE
# False = ancien dashboard KPI
#
# Pour le moment on laisse True afin de réduire fortement
# la charge CPU sur Streamlit Cloud.
# ============================================================

HSE_ONLY = True


# ============================================================
# IMPORTS
# ============================================================

_IMPORT_ERROR = None

try:

    # Préparation des données nécessaire au module HSE
    from core.prepare_data import (
        prepare_data,
        get_date_from_file,
    )

    # Module HSE
    from pages.suivi_hse import (
        render_suivi_hse_tab,
    )

except Exception:
    _IMPORT_ERROR = traceback.format_exc()


# ============================================================
# CSS
# ============================================================

def inject_hse_css():

    st.markdown(
        """
        <style>

        /* Cacher la navigation Streamlit */
        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        /* Cacher certains éléments Streamlit */
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

        footer {
            visibility: hidden !important;
        }

        /* Fond général */
        .stApp {
            background-color: #f7f9fb;
        }

        /* Footer */
        .hse-footer {
            margin-top: 40px;
            padding: 15px;
            text-align: center;
            color: #777;
            font-size: 13px;
            border-top: 1px solid #ddd;
        }

        /* Badge mode HSE */
        .hse-mode {
            background: #e8f5e9;
            border: 1px solid #81c784;
            border-radius: 8px;
            padding: 8px 14px;
            margin-bottom: 15px;
            color: #2e7d32;
            font-weight: 600;
        }

        </style>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# SPLASH SCREEN HSE
# ============================================================

def render_hse_splash():

    if st.session_state.get("hse_affiche", False):
        return

    # On évite de refaire le splash à chaque rerun
    st.markdown(
        """
        <div style="
            min-height:70vh;
            display:flex;
            align-items:center;
            justify-content:center;
        ">

            <div style="
                width:850px;
                padding:60px;
                border-radius:25px;
                background:
                    linear-gradient(
                        135deg,
                        #111827,
                        #1f2937
                    );
                box-shadow:
                    0 20px 60px rgba(0,0,0,.25);
                text-align:center;
            ">

                <div style="
                    font-size:70px;
                    margin-bottom:15px;
                ">
                    🦺
                </div>

                <h1 style="
                    color:white;
                    font-size:44px;
                    font-weight:900;
                    margin-bottom:10px;
                ">
                    HSE
                </h1>

                <p style="
                    color:#d1d5db;
                    font-size:20px;
                    letter-spacing:2px;
                ">
                    SÉCURITÉ · SANTÉ · ENVIRONNEMENT
                </p>

                <div style="
                    background:
                        linear-gradient(
                            135deg,
                            #f6e05e,
                            #ed8936
                        );
                    padding:30px;
                    border-radius:18px;
                    margin-top:35px;
                    color:#1a202c;
                    font-size:27px;
                    font-weight:700;
                ">
                    Aucun travail n'est plus urgent
                    que la sécurité
                </div>

                <div style="
                    margin-top:40px;
                    color:#9ca3af;
                    font-size:15px;
                ">
                    Chargement du suivi HSE...
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    # Ancien délai de 6 secondes :
    # on le réduit pour éviter une attente inutile.
    time.sleep(2)

    st.session_state.hse_affiche = True

    st.rerun()

    st.stop()


# ============================================================
# CHARGEMENT DES FICHIERS
# ============================================================

def load_input_files():

    ot_bytes = None
    av_bytes = None

    # --------------------------------------------------------
    # OT
    # --------------------------------------------------------

    if os.path.exists("ot.xlsx"):

        try:

            with open("ot.xlsx", "rb") as f:
                ot_bytes = f.read()

        except Exception as e:

            st.error(
                f"❌ Impossible de lire `ot.xlsx` : {e}"
            )

    # --------------------------------------------------------
    # AVIS
    # --------------------------------------------------------

    if os.path.exists("avis.xlsx"):

        try:

            with open("avis.xlsx", "rb") as f:
                av_bytes = f.read()

        except Exception as e:

            st.error(
                f"❌ Impossible de lire `avis.xlsx` : {e}"
            )

    return ot_bytes, av_bytes


# ============================================================
# PREPARATION DES DONNEES HSE
# ============================================================

@st.cache_data(
    show_spinner="Préparation des données HSE...",
    max_entries=4
)
def prepare_hse_data(
    ot_bytes,
    av_bytes,
    fichier_date
):

    return prepare_data(
        ot_bytes,
        av_bytes,
        fichier_date
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # ERREUR IMPORT
    # ========================================================

    if _IMPORT_ERROR is not None:

        st.error(
            "❌ Erreur lors du chargement des modules."
        )

        st.code(
            _IMPORT_ERROR,
            language="python"
        )

        st.stop()


    # ========================================================
    # LOCALE
    # ========================================================

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


    # ========================================================
    # CSS
    # ========================================================

    inject_hse_css()


    # ========================================================
    # SPLASH HSE
    # ========================================================

    render_hse_splash()


    # ========================================================
    # TITRE
    # ========================================================

    st.markdown(
        """
        <div class="hse-mode">
            🦺 MODE HSE UNIQUEMENT — Calculs KPI désactivés
        </div>
        """,
        unsafe_allow_html=True
    )


    # ========================================================
    # DATE DU FICHIER
    # ========================================================

    try:

        fichier_date = get_date_from_file()

    except Exception:

        fichier_date = (
            pd.Timestamp.now()
            .strftime("%d/%m/%Y")
        )


    # ========================================================
    # CHARGEMENT OT + AVIS
    # ========================================================

    ot_bytes, av_bytes = load_input_files()


    # ========================================================
    # VERIFICATION
    # ========================================================

    if not ot_bytes:

        st.error(
            "❌ Le fichier `ot.xlsx` est introuvable."
        )

        st.info(
            "Placez `ot.xlsx` à la racine du projet."
        )

        st.stop()


    if not av_bytes:

        st.error(
            "❌ Le fichier `avis.xlsx` est introuvable."
        )

        st.info(
            "Placez `avis.xlsx` à la racine du projet."
        )

        st.stop()


    # ========================================================
    # PREPARATION
    # ========================================================

    try:

        (
            df_full,
            av_full,
            apm,
            now_ts,
            avis_complet_full
        ) = prepare_hse_data(
            ot_bytes,
            av_bytes,
            fichier_date
        )

    except Exception as e:

        st.error(
            "❌ Erreur lors de la préparation des données HSE."
        )

        st.code(
            traceback.format_exc(),
            language="python"
        )

        st.stop()


    # ========================================================
    # VERIFICATION DATAFRAME OT
    # ========================================================

    if df_full is None or df_full.empty:

        st.warning(
            "⚠️ Aucune donnée OT disponible."
        )

        st.stop()


    # ========================================================
    # POSTES
    # ========================================================

    try:

        vp = list(apm)

    except Exception:

        vp = []


    # ========================================================
    # FILTRAGE SECURITE
    # ========================================================
    #
    # On conserve ici les données préparées.
    # Le module HSE réalise ensuite ses propres filtres.
    # ========================================================

    try:

        render_suivi_hse_tab(
            df_full,
            avis_complet_full,
            vp,
            fichier_date
        )

    except Exception as e:

        st.error(
            "❌ Erreur dans le module Suivi HSE."
        )

        st.code(
            traceback.format_exc(),
            language="python"
        )

        st.stop()


    # ========================================================
    # FOOTER
    # ========================================================

    st.markdown(
        """
        <div class="hse-footer">
            Bureau Méthodes Maroc Chimie 2026
            — Mode HSE uniquement
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":
    main()
