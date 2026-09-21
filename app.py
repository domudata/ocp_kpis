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
        f"Erreur lors du chargement de core.prepare_data : {e}"
    )
    st.stop()


# ============================================================
# IMPORT MODULE HSE
# ============================================================

try:
    hse_module = importlib.import_module(
        "pages.suivi_hse"
    )

except Exception as e:
    st.error(
        f"Impossible de charger pages.suivi_hse : {e}"
    )
    st.stop()


# ============================================================
# VERIFICATION FONCTION HSE
# ============================================================

if not hasattr(
    hse_module,
    "render_suivi_hse_tab"
):
    st.error(
        "La fonction render_suivi_hse_tab "
        "n'existe pas dans pages/suivi_hse.py."
    )
    st.stop()


render_suivi_hse_tab = (
    hse_module.render_suivi_hse_tab
)


# ============================================================
# SPLASH SCREEN
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

        <div style="font-size:70px;">
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
# DATE
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

    st.success("Mode HSE uniquement")

    st.markdown("---")

    st.markdown(
        """
        ### Modules désactivés

        ❌ Calcul KPI  
        ❌ Scores Performance  
        ❌ Scores Qualité  
        ❌ Anomalies  
        ❌ Plan d'action  
        ❌ Historique  
        ❌ Variations  
        ❌ Backlog KPI  
        ❌ Fréquence Maintenance  
        ❌ Export KPI  

        ### Module actif

        🦺 **Suivi HSE**
        """
    )

    if fichier_date:
        st.markdown("---")
        st.caption(
            f"📅 Date fichier : **{fichier_date}**"
        )


# ============================================================
# FICHIERS
# ============================================================

ot_path = "ot.xlsx"
avis_path = "avis.xlsx"


if not os.path.exists(ot_path):
    st.error(
        "Le fichier ot.xlsx est introuvable."
    )
    st.stop()


if not os.path.exists(avis_path):
    st.error(
        "Le fichier avis.xlsx est introuvable."
    )
    st.stop()


# ============================================================
# LECTURE FICHIERS
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
        f"Erreur pendant la lecture des fichiers Excel : {e}"
    )

    st.stop()


# ============================================================
# PREPARATION DONNEES
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
# EXECUTION PREPARE DATA
# ============================================================

try:

    result = prepare_hse_data(
        ot_bytes,
        av_bytes,
        fichier_date
    )

except Exception as e:

    st.error(
        f"Erreur pendant la préparation des données HSE : {e}"
    )

    st.exception(e)

    st.stop()


# ============================================================
# VERIFICATION RESULTAT
# ============================================================

if result is None:

    st.error(
        "prepare_data() n'a retourné aucune donnée."
    )

    st.stop()


if not isinstance(
    result,
    tuple
):

    st.error(
        "prepare_data() ne retourne pas un tuple."
    )

    st.stop()


if len(result) < 5:

    st.error(
        f"prepare_data() retourne {len(result)} "
        "éléments alors que 5 sont attendus."
    )

    st.stop()


# ============================================================
# RECUPERATION
# ============================================================

df_full = result[0]

av_full = result[1]

apm = result[2]

now_ts = result[3]

avis_complet_full = result[4]


# ============================================================
# VERIFICATION OT
# ============================================================

if df_full is None:

    st.error(
        "Les données OT sont vides."
    )

    st.stop()


if not isinstance(
    df_full,
    pd.DataFrame
):

    st.error(
        "df_full n'est pas un DataFrame."
    )

    st.stop()


if df_full.empty:

    st.warning(
        "Le fichier OT ne contient aucune donnée."
    )

    st.stop()


# ============================================================
# VERIFICATION AVIS
# ============================================================

if av_full is None:
    av_full = pd.DataFrame()


if not isinstance(
    av_full,
    pd.DataFrame
):

    av_full = pd.DataFrame(
        av_full
    )


# ============================================================
# AVIS COMPLETS
# ============================================================

if avis_complet_full is None:

    avis_complet_full = av_full.copy()


if not isinstance(
    avis_complet_full,
    pd.DataFrame
):

    avis_complet_full = pd.DataFrame(
        avis_complet_full
    )


# ============================================================
# LISTE POSTES
# ============================================================

if apm is None:

    apm = []


try:

    vp = list(apm)

except Exception:

    vp = []


# ============================================================
# SI APM VIDE
# ============================================================

if not vp:

    if "Poste travail princ." in df_full.columns:

        vp = sorted(
            df_full[
                "Poste travail princ."
            ]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    else:

        vp = []


# ============================================================
# SIDEBAR STATISTIQUES
# ============================================================

with st.sidebar:

    st.markdown("---")

    st.markdown("### 📊 Données HSE")

    st.metric(
        "Nombre OT",
        f"{len(df_full):,}"
    )

    st.metric(
        "Nombre Avis",
        f"{len(av_full):,}"
    )

    st.metric(
        "Nombre Postes",
        f"{len(vp):,}"
    )


# ============================================================
# RENDU HSE
# ============================================================

try:

    render_suivi_hse_tab(
        df_full,
        avis_complet_full,
        vp,
        fichier_date
    )

except Exception as e:

    st.error(
        f"Erreur dans le module Suivi HSE : {e}"
    )

    st.exception(e)

    st.stop()


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        Bureau Méthodes Maroc Chimie — 2026
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# FIN
# ============================================================

st.stop()
