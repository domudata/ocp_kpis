# -*- coding: utf-8 -*-

import os
import time
import importlib

import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURATION
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

    .main-title {
        font-size: 30px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .sub-title {
        font-size: 15px;
        color: #64748b;
        margin-bottom: 20px;
    }

    .footer {
        margin-top: 40px;
        padding: 15px;
        text-align: center;
        color: #64748b;
        font-size: 12px;
    }

    .hse-mode {
        padding: 10px 15px;
        border-radius: 8px;
        background-color: #ecfdf5;
        border: 1px solid #a7f3d0;
        color: #065f46;
        font-weight: 600;
        margin-bottom: 15px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# IMPORT PREPARE DATA
# ============================================================

try:

    from core.prepare_data import (
        prepare_data,
        get_date_from_file,
    )

except Exception as e:

    st.error(
        f"""
        ❌ Erreur lors du chargement de `core.prepare_data`.

        **Détail :**
        `{e}`
        """
    )

    st.stop()


# ============================================================
# IMPORT DYNAMIQUE DU MODULE HSE
# ============================================================

try:

    hse_module = importlib.import_module(
        "pages.suivi_hse"
    )

except Exception as e:

    st.error(
        f"""
        ❌ Impossible de charger `pages.suivi_hse`.

        **Détail :**
        `{e}`
        """
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
        """
        ❌ La fonction

        `render_suivi_hse_tab`

        n'existe pas dans :

        `pages/suivi_hse.py`
        """
    )

    st.stop()


render_suivi_hse_tab = (
    hse_module.render_suivi_hse_tab
)


# ============================================================
# SPLASH SCREEN HSE
# ============================================================

if "hse_affiche" not in st.session_state:

    st.session_state.hse_affiche = False


if not st.session_state.hse_affiche:

    st.markdown(
        """
        <div style="
            text-align:center;
            margin-top:100px;
        ">

        <div style="
            font-size:70px;
        ">
            🦺
        </div>

        <div style="
            font-size:34px;
            font-weight:800;
        ">
            Suivi HSE
        </div>

        <div style="
            font-size:18px;
            color:#64748b;
            margin-top:10px;
        ">
            Maroc Chimie
        </div>

        <div style="
            font-size:14px;
            color:#94a3b8;
            margin-top:20px;
        ">
            Chargement du module HSE...
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    time.sleep(2)

    st.session_state.hse_affiche = True

    st.rerun()


# ============================================================
# DATE DU FICHIER
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
    <div class="main-title">
        🦺 Suivi HSE — Maroc Chimie
    </div>

    <div class="sub-title">
        Suivi des avis HSE, sécurité, OMS et contrôle structure
    </div>

    <div class="hse-mode">
        🟢 Mode HSE uniquement — calculs KPI désactivés
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🦺 Navigation")

    st.success(
        "Mode HSE uniquement"
    )

    st.markdown("---")

    st.markdown(
        """
        ### ⚙️ Mode actuel

        Les modules suivants sont temporairement désactivés :

        - ❌ Calcul des KPI
        - ❌ Scores Performance
        - ❌ Scores Qualité
        - ❌ Calcul des anomalies
        - ❌ Plan d'action
        - ❌ Historique
        - ❌ Variations
        - ❌ Backlog KPI
        - ❌ Fréquence Maintenance
        - ❌ Export KPI

        Module actif :

        - 🦺 **Suivi HSE**
        """
    )

    if fichier_date:

        st.markdown("---")

        st.caption(
            f"📅 Date fichier : **{fichier_date}**"
        )


# ============================================================
# CHARGEMENT DES FICHIERS
# ============================================================

ot_path = "ot.xlsx"
avis_path = "avis.xlsx"


# ------------------------------------------------------------
# Vérification OT
# ------------------------------------------------------------

if not os.path.exists(ot_path):

    st.error(
        f"""
        ❌ Le fichier `{ot_path}` est introuvable.

        Placez `ot.xlsx` à la racine du projet.
        """
    )

    st.stop()


# ------------------------------------------------------------
# Vérification AVIS
# ------------------------------------------------------------

if not os.path.exists(avis_path):

    st.error(
        f"""
        ❌ Le fichier `{avis_path}` est introuvable.

        Placez `avis.xlsx` à la racine du projet.
        """
    )

    st.stop()


# ============================================================
# LECTURE DES FICHIERS
# ============================================================

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
        f"""
        ❌ Erreur de lecture des fichiers Excel.

        `{e}`
        """
    )

    st.stop()


# ============================================================
# FONCTION DE PREPARATION HSE
# ============================================================

@st.cache_data(
    show_spinner="Préparation des données HSE..."
)
def prepare_hse_data(
    ot_data,
    avis_data,
    date_str
):

    return prepare_data(
        ot_data,
        avis_data,
        date_str
    )


# ============================================================
# PREPARATION DES DONNEES
# ============================================================

try:

    result = prepare_hse_data(
        ot_bytes,
        av_bytes,
        fichier_date
    )

except Exception as e:

    st.error(
        f"""
        ❌ Erreur pendant la préparation des données HSE.

        **Détail :**

        `{e}`
        """
    )

    st.exception(e)

    st.stop()


# ============================================================
# VERIFICATION DU RESULTAT
# ============================================================

if not isinstance(
    result,
    tuple
):

    st.error(
        """
        ❌ `prepare_data()` ne retourne pas le résultat attendu.

        Le résultat attendu est :

        ```text
        df_full
        av_full
        apm
        now_ts
        avis_complet_full
        ```
        """
    )

    st.stop()


if len(result) < 5:

    st.error(
        f"""
        ❌ `prepare_data()` retourne seulement
        **{len(result)} éléments**.

        Il faut au minimum 5 éléments.
        """
    )

    st.stop()


# ============================================================
# RECUPERATION DES DONNEES
# ============================================================

df_full = result[0]

av_full = result[1]

apm = result[2]

now_ts = result[3]

avis_complet_full = result[4]


# ============================================================
# SECURITE DATAFRAME OT
# ============================================================

if df_full is None:

    st.error(
        "❌ Les données OT sont vides.
