# -*- coding: utf-8 -*-

import os
import time
import traceback
import importlib
import locale

import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Suivi HSE",
    page_icon="🦺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# MODE HSE UNIQUEMENT
# ============================================================
#
# True  -> uniquement Suivi HSE
# False -> ancien dashboard KPI
#
# Pour le moment : True
# ============================================================

HSE_ONLY = True


# ============================================================
# IMPORT DU MODULE PREPARE DATA
# ============================================================

try:

    from core.prepare_data import (
        prepare_data,
        get_date_from_file,
    )

except Exception:

    st.error(
        "❌ Impossible de charger `core.prepare_data`."
    )

    st.code(
        traceback.format_exc(),
        language="python"
    )

    st.stop()


# ============================================================
# IMPORT DYNAMIQUE DU MODULE HSE
# ============================================================
#
# On évite :
#
# from pages.suivi_hse import render_suivi_hse_tab
#
# afin d'avoir un diagnostic beaucoup plus clair si le fichier
# HSE n'est pas la bonne version sur GitHub.
# ============================================================

try:

    hse_module = importlib.import_module(
        "pages.suivi_hse"
    )

except Exception:

    st.error(
        "❌ Impossible de charger `pages.suivi_hse`."
    )

    st.code(
        traceback.format_exc(),
        language="python"
    )

    st.stop()


# ============================================================
# VERIFICATION DE LA FONCTION HSE
# ============================================================

if not hasattr(
    hse_module,
    "render_suivi_hse_tab"
):

    st.error(
        "❌ La fonction `render_suivi_hse_tab()` "
        "est absente de `pages/suivi_hse.py`."
    )

    st.markdown(
        """
        ### Vérification à faire dans GitHub

        Le fichier doit contenir exactement une fonction de ce type :

        ```python
        def render_suivi_hse_tab(dfp, avf, vp, date_str=""):
            ...
        ```

        Vérifiez également que le fichier déployé est bien :

        `pages/suivi_hse.py`
        """
    )

    st.stop()


render_suivi_hse_tab = (
    hse_module.render_suivi_hse_tab
)


# ============================================================
# CSS
# ============================================================

def inject_css():

    st.markdown(
        """
        <style>

        /* ================================================== */
        /* GENERAL                                            */
        /* ================================================== */

        .stApp {
            background-color: #f7f9fb;
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

        #MainMenu {
            visibility: hidden !important;
        }

        footer {
            visibility: hidden !important;
        }

        /* ================================================== */
        /* BADGE MODE HSE                                     */
        /* ================================================== */

        .hse-mode {
            background: #ecfdf5;
            border: 1px solid #10b981;
            border-radius: 10px;
            padding: 10px 16px;
            margin-bottom: 15px;
            color: #047857;
            font-weight: 700;
            text-align: center;
        }

        /* ================================================== */
        /* FOOTER                                             */
        /* ================================================== */

        .hse-footer {
            margin-top: 40px;
            padding: 15px;
            text-align: center;
            color: #64748b;
            font-size: 13px;
            border-top: 1px solid #e2e8f0;
        }

        </style>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# SPLASH SCREEN
# ============================================================

def render_splash():

    if st.session_state.get(
        "hse_splash_done",
        False
    ):
        return

    st.markdown(
        """
        <div style="
            min-height:70vh;
            display:flex;
            align-items:center;
            justify-content:center;
        ">

            <div style="
                width:800px;
                padding:55px;
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
                    SUIVI HSE
                </h1>

                <p style="
                    color:#d1d5db;
                    font-size:19px;
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
                    padding:25px;
                    border-radius:18px;
                    margin-top:30px;
                    color:#1a202c;
                    font-size:24px;
                    font-weight:700;
                ">
                    Aucun travail n'est plus urgent
                    que la sécurité
                </div>

                <div style="
                    margin-top:35px;
                    color:#9ca3af;
                    font-size:14px;
                ">
                    Chargement du suivi HSE...
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    # Petit délai uniquement pour le splash
    time.sleep(2)

    st.session_state.hse_splash_done = True

    st.rerun()

    st.stop()


# ============================================================
# CHARGEMENT DES FICHIERS
# ============================================================

def load_files():

    ot_bytes = None
    avis_bytes = None

    # --------------------------------------------------------
    # OT
    # --------------------------------------------------------

    if os.path.exists("ot.xlsx"):

        try:

            with open(
                "ot.xlsx",
                "rb"
            ) as f:

                ot_bytes = f.read()

        except Exception as e:

            st.error(
                f"❌ Erreur lecture `ot.xlsx` : {e}"
            )

    # --------------------------------------------------------
    # AVIS
    # --------------------------------------------------------

    if os.path.exists("avis.xlsx"):

        try:

            with open(
                "avis.xlsx",
                "rb"
            ) as f:

                avis_bytes = f.read()

        except Exception as e:

            st.error(
                f"❌ Erreur lecture `avis.xlsx` : {e}"
            )

    return ot_bytes, avis_bytes


# ============================================================
# PREPARATION HSE
# ============================================================
#
# On garde uniquement prepare_data().
#
# Aucun :
# calc_kpis()
# build_ano_map()
# historique
# score
# plan d'action
# export KPI
# etc.
#
# Cela réduit fortement la charge CPU.
# ============================================================

@st.cache_data(
    show_spinner="Préparation des données HSE...",
    max_entries=2
)
def prepare_hse_data(
    ot_bytes,
    avis_bytes,
    fichier_date
):

    return prepare_data(
        ot_bytes,
        avis_bytes,
        fichier_date
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # CSS
    # ========================================================

    inject_css()


    # ========================================================
    # SPLASH
    # ========================================================

    render_splash()


    # ========================================================
    # BADGE
    # ========================================================

    st.markdown(
        """
        <div class="hse-mode">
            🦺 MODE HSE UNIQUEMENT
            — CALCULS KPI DÉSACTIVÉS
        </div>
        """,
        unsafe_allow_html=True
    )


    # ========================================================
    # SIDEBAR
    # ========================================================

    with st.sidebar:

        st.markdown(
            "## 🦺 Suivi HSE"
        )

        st.info(
            "Le dashboard KPI est temporairement "
            "désactivé afin de réduire la charge CPU."
        )

        st.markdown(
            "---"
        )

        st.markdown(
            "**Module actif :**"
        )

        st.success(
            "🦺 Suivi HSE"
        )

        st.markdown(
            "---"
        )

        st.caption(
            "Mode temporaire HSE uniquement"
        )


    # ========================================================
    # DATE EXTRACTION
    # ========================================================

    try:

        fichier_date = get_date_from_file()

    except Exception:

        fichier_date = (
            pd.Timestamp.now()
            .strftime("%d/%m/%Y")
        )


    # ========================================================
    # CHARGEMENT OT / AVIS
    # ========================================================

    ot_bytes, avis_bytes = load_files()


    # ========================================================
    # VERIFICATION OT
    # ========================================================

    if not ot_bytes:

        st.error(
            "❌ Le fichier `ot.xlsx` est introuvable."
        )

        st.info(
            "Vérifiez que `ot.xlsx` est présent "
            "à la racine du dépôt GitHub."
        )

        st.stop()


    # ========================================================
    # VERIFICATION AVIS
    # ========================================================

    if not avis_bytes:

        st.error(
            "❌ Le fichier `avis.xlsx` est introuvable."
        )

        st.info(
            "Vérifiez que `avis.xlsx` est présent "
            "à la racine du dépôt GitHub."
        )

        st.stop()


    # ========================================================
    # PREPARATION DES DONNEES
    # ========================================================

    try:

        result = prepare_hse_data(
            ot_bytes,
            avis_bytes,
            fichier_date
        )

    except Exception:

        st.error(
            "❌ Erreur pendant la préparation "
            "des données HSE."
        )

        st.code(
            traceback.format_exc(),
            language="python"
        )

        st.stop()


    # ========================================================
    # RECUPERATION DU RESULTAT
    # ========================================================

    try:

        (
            df_full,
            av_full,
            apm,
            now_ts,
            avis_complet_full
        ) = result

    except Exception:

        st.error(
            "❌ Format inattendu retourné par "
            "`prepare_data()`."
        )

        st.write(
            "Résultat retourné :",
            type(result)
        )

        st.stop()


    # ========================================================
    # VERIFICATION DATA OT
    # ========================================================

    if (
        df_full is None
        or df_full.empty
    ):

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
    # INFORMATIONS TECHNIQUES
    # ========================================================

    with st.expander(
        "ℹ️ Informations techniques",
        expanded=False
    ):

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "OT",
                f"{len(df_full):,}"
            )

        with col2:

            if (
                avis_complet_full is not None
                and hasattr(
                    avis_complet_full,
                    "__len__"
                )
            ):

                st.metric(
                    "Avis",
                    f"{len(avis_complet_full):,}"
                )

            else:

                st.metric(
                    "Avis",
                    "0"
                )

        with col3:

            st.metric(
                "Postes",
                f"{len(vp):,}"
            )

        st.caption(
            f"Date d'extraction : {fichier_date}"
        )


    # ========================================================
    # RENDU HSE
    # ========================================================

    try:

        render_suivi_hse_tab(
            df_full,
            avis_complet_full,
            vp,
            fichier_date
        )

    except Exception:

        st.error(
            "❌ Erreur pendant l'affichage du "
            "Suivi HSE."
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
            — Suivi HSE
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":

    main()
