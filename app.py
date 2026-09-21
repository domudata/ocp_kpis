# -*- coding: utf-8 -*-

import os
import time

import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURATION STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Suivi HSE - Maroc Chimie",
    page_icon="🦺",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# MODE HSE UNIQUEMENT
# ============================================================

HSE_ONLY = True


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    [data-testid="stToolbar"] {
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

    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    .hse-title {
        font-size: 30px;
        font-weight: 800;
        color: #123B5D;
        margin-bottom: 0px;
    }

    .hse-subtitle {
        font-size: 15px;
        color: #64748B;
        margin-bottom: 20px;
    }

    .footer {
        margin-top: 30px;
        padding-top: 12px;
        border-top: 1px solid #E2E8F0;
        text-align: center;
        color: #64748B;
        font-size: 12px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# IMPORTS
# ============================================================

try:

    from core.prepare_data import (
        prepare_data,
        get_date_from_file,
    )

except Exception as e:

    st.error("❌ Impossible de charger core.prepare_data")

    st.code(
        str(e),
        language="text",
    )

    st.stop()


# ============================================================
# IMPORT DU MODULE HSE
# ============================================================

try:

    from pages.suivi_hse import (
        render_suivi_hse_tab,
    )

except Exception as e:

    st.error(
        "❌ Impossible de charger pages/suivi_hse.py"
    )

    st.code(
        str(e),
        language="text",
    )

    st.markdown(
        """
        ### Vérification

        Le fichier doit contenir cette fonction :

        ```python
        def render_suivi_hse_tab(dfp, avf, vp, date_str=""):
            ...
        ```
        """,
    )

    st.stop()


# ============================================================
# SPLASH SCREEN HSE
# ============================================================

if "hse_splash_done" not in st.session_state:

    st.session_state.hse_splash_done = False


if not st.session_state.hse_splash_done:

    st.markdown(
        """
        <div style="
            text-align:center;
            padding-top:120px;
            padding-bottom:120px;
        ">

            <div style="
                font-size:65px;
                margin-bottom:20px;
            ">
                🦺
            </div>

            <div style="
                font-size:36px;
                font-weight:800;
                color:#123B5D;
            ">
                Suivi HSE
            </div>

            <div style="
                font-size:20px;
                color:#64748B;
                margin-top:10px;
            ">
                Maroc Chimie
            </div>

            <div style="
                font-size:14px;
                color:#94A3B8;
                margin-top:25px;
            ">
                Chargement des données...
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    time.sleep(2)

    st.session_state.hse_splash_done = True

    st.rerun()


# ============================================================
# DATE D'EXTRACTION
# ============================================================

try:

    fichier_date = get_date_from_file()

except Exception:

    fichier_date = ""


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="hse-title">
        🦺 Suivi HSE — Maroc Chimie
    </div>

    <div class="hse-subtitle">
        Avis d'inspection et HSE, OT sécurité, OMS et contrôle structure
    </div>
    """,
    unsafe_allow_html=True,
)


if fichier_date:

    st.caption(
        f"📅 Date d'extraction : {fichier_date}"
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🦺 Suivi HSE"
    )

    st.info(
        "Mode HSE uniquement"
    )

    st.markdown("---")

    st.markdown(
        "### 📁 Fichiers utilisés"
    )

    st.write("• `ot.xlsx`")
    st.write("• `avis.xlsx`")

    st.markdown("---")


# ============================================================
# FICHIERS EXCEL
# ============================================================

OT_FILE = "ot.xlsx"
AVIS_FILE = "avis.xlsx"


if not os.path.exists(OT_FILE):

    st.error(
        "❌ Le fichier `ot.xlsx` est introuvable."
    )

    st.info(
        "Ajoutez `ot.xlsx` à la racine du dépôt GitHub."
    )

    st.stop()


if not os.path.exists(AVIS_FILE):

    st.error(
        "❌ Le fichier `avis.xlsx` est introuvable."
    )

    st.info(
        "Ajoutez `avis.xlsx` à la racine du dépôt GitHub."
    )

    st.stop()


# ============================================================
# LECTURE DES FICHIERS
# ============================================================

try:

    with open(
        OT_FILE,
        "rb",
    ) as f:

        ot_bytes = f.read()


    with open(
        AVIS_FILE,
        "rb",
    ) as f:
