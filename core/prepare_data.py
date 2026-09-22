# -*- coding: utf-8 -*-

import io
import os
import numpy as np
import pandas as pd
import streamlit as st

from core.constants import MP_KW, MPLAN_KW


# ══════════════════════════════════════════════════════════════
# CONSTANTES AVIS
# ══════════════════════════════════════════════════════════════

# Types d'Avis à exclure des calculs du KPI d'approbation
# et du calcul des anomalies Avis.
TYPES_AVIS_EXCLUS = {
    "ZU",
    "Z4",
    "ZR",
    "ZP",
}


# ══════════════════════════════════════════════════════════════
# UTILITAIRES BASIQUES
# ══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=300)
def _lire_date_github():
    """
    Lit date.txt directement depuis le dépôt GitHub configuré.

    Protection anti-gel :
      1. cache 300 secondes ;
      2. désactivation des tentatives après un échec ;
      3. try/except large.
    """

    if st.session_state.get("_github_date_indisponible"):
        return (
            None,
            "GitHub désactivé pour cette session "
            "(échec précédent)"
        )

    try:
        from core.github_publish import download_file, is_configured

        if not is_configured():
            st.session_state["_github_date_indisponible"] = True
            return None, "GitHub non configuré"

        contenu, err = download_file("date.txt")

        if contenu:
            valeur = contenu.decode("utf-8").strip()

            if valeur:
                return valeur, "GitHub"

        st.session_state["_github_date_indisponible"] = True

        return None, err or "date.txt absent du dépôt"

    except Exception as e:

        st.session_state["_github_date_indisponible"] = True

        return None, f"lecture GitHub impossible : {e}"


def get_date_from_file() -> str:
    """
    Date de l'extraction courante.

    Ordre :
        1. GitHub
        2. date.txt local
        3. date du jour
    """

    date_gh, _source = _lire_date_github()

    if date_gh:
        return date_gh

    if os.path.exists("date.txt"):

        try:

            with open(
                "date.txt",
                "r",
                encoding="utf-8"
            ) as f:

                valeur = f.read().strip()

                if valeur:
                    return valeur

        except Exception:
            pass

    return pd.Timestamp.today().strftime("%d/%m/%Y")


def contient_mot(t, lm) -> bool:
    """
    Vérifie si une valeur contient au moins un mot
    appartenant à une liste de mots-clés.
    """

    t = str(t)

    return any(
        m in t
        for l in lm
        for m in l.split()
    )


def cat_age(a) -> str:
    """
    Catégorisation de l'âge :

        <= 1 mois       -> <1 mois
        >= 3 mois       -> >3 mois
        sinon           -> 1 mois < <3 mois
    """

    if pd.isna(a):
        return ">3 mois"

    if a <= 1:
        return "<1 mois"

    elif a >= 3:
        return ">3 mois"

    return "1 mois < <3 mois"


def excr(df: pd.DataFrame) -> pd.DataFrame:
    """
    Exclut les postes contenant 'cresseur'.
    """

    if "Poste travail princ." in df.columns:

        return df[
            ~df["Poste travail princ."]
            .astype(str)
            .str.contains(
                "cresseur",
                case=False,
                na=False
            )
        ].copy()

    return df


# ══════════════════════════════════════════════════════════════
# DÉTECTION DU TYPE D'AVIS
# ══════════════════════════════════════════════════════════════

def trouver_colonne_type_avis(df: pd.DataFrame):
    """
    Recherche automatiquement la colonne contenant le type d'Avis.

    Plusieurs noms possibles sont supportés.
    """

    candidats = [
        "Type",
        "Type avis",
        "Type Avis",
        "Type d'avis",
        "Type d’Avis",
        "Type de avis",
        "Type de Avis",
        "Type demande",
        "Type de demande",
        "Type de l'avis",
        "Type de l'avis",
        "Catégorie",
        "Categorie",
    ]

    # Recherche exacte
    for col in candidats:

        if col in df.columns:
            return col

    # Recherche souple
    for col in df.columns:

        c = (
            str(col)
            .strip()
            .lower()
            .replace("’", "'")
        )

        if (
            c == "type"
            or "type avis" in c
            or "type d'avis" in c
            or "type de avis" in c
            or "type demande" in c
            or "type de demande" in c
        ):
            return col

    return None


def normaliser_type_avis(value) -> str:
    """
    Normalise le code type Avis.

    Exemple :
        ' ZU ' -> 'ZU'
        'z4'   -> 'Z4'
    """

    if pd.isna(value):
        return ""

    return (
        str(value)
        .strip()
        .upper()
    )


# ══════════════════════════════════════════════════════════════
# PRÉPARATION DES AVIS
# ══════════════════════════════════════════════════════════════

def preparer_avis(raw_av: pd.DataFrame) -> pd.DataFrame:
    """
    Prépare le fichier Avis.

    Colonnes ajoutées :

        _type_avis
        _avis_type_exclu
        _avis_aprv
        _avis_anomalie
        Avis APRV
        Avis anomalie

    Règles :

    KPI APPROBATION
    ----------------
    Avis APRV uniquement.

    Les types suivants sont exclus :
        ZU
        Z4
        ZR
        ZP

    ANOMALIES AVIS
    --------------
    Statut système = AOUV
    ET
    Statut utilisateur = APRQ

    avec exclusion des types :
        ZU
        Z4
        ZR
        ZP
    """

    av = raw_av.copy()

    # ──────────────────────────────────────────────
    # Type Avis
    # ──────────────────────────────────────────────

    col_type = trouver_colonne_type_avis(av)

    if col_type is not None:

        av["_type_avis"] = (
            av[col_type]
            .apply(normaliser_type_avis)
        )

    else:

        # Si aucune colonne type n'est trouvée,
        # aucune exclusion ne peut être appliquée.
        av["_type_avis"] = ""

    av["_avis_type_exclu"] = (
        av["_type_avis"]
        .isin(TYPES_AVIS_EXCLUS)
    )

    # ──────────────────────────────────────────────
    # Statut système
    # ──────────────────────────────────────────────

    if "Statut système" in av.columns:

        statut_systeme = (
            av["Statut système"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

    else:

        statut_systeme = pd.Series(
            "",
            index=av.index
        )

    # ──────────────────────────────────────────────
    # Statut utilisateur
    # ──────────────────────────────────────────────

    if "Statut utilisateur" in av.columns:

        statut_utilisateur = (
            av["Statut utilisateur"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

    else:

        statut_utilisateur = pd.Series(
            "",
            index=av.index
        )

    # ──────────────────────────────────────────────
    # AVIS APRV
    # ──────────────────────────────────────────────

    av["_avis_aprv"] = (
        statut_systeme
        .str.contains(
            r"\bAPRV\b",
            regex=True,
            na=False
        )
        &
        ~av["_avis_type_exclu"]
    )

    av["Avis APRV"] = np.where(
        av["_avis_aprv"],
        1,
        0
    )

    # ──────────────────────────────────────────────
    # ANOMALIES AVIS
    # ──────────────────────────────────────────────
    #
    # RÈGLE EXACTE :
    #
    # Statut système     = AOUV
    # Statut utilisateur = APRQ
    #
    # ET exclusion :
    # ZU / Z4 / ZR / ZP
    # ──────────────────────────────────────────────

    av["_avis_anomalie"] = (
        statut_systeme
        .str.contains(
            r"\bAOUV\b",
            regex=True,
            na=False
        )
        &
        statut_utilisateur
        .str.contains(
            r"\bAPRQ\b",
            regex=True,
            na=False
        )
        &
        ~av["_avis_type_exclu"]
    )

    av["Avis anomalie"] = np.where(
        av["_avis_anomalie"],
        1,
        0
    )

    return av


# ══════════════════════════════════════════════════════════════
# LECTURE EXCEL ROBUSTE
# ══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def read_excel_safe(bytes_data: bytes) -> pd.DataFrame:
    """
    Lit un fichier Excel en détectant automatiquement
    le vrai format.
    """

    bio = io.BytesIO(bytes_data)

    header = bytes_data[:8]

    # XLSX / ZIP
    if header[:4] in (
        b'PK\x03\x04',
        b'PK\x05\x06'
    ):

        for engine in [
            "openpyxl",
            "calamine"
        ]:

            try:

                return pd.read_excel(
                    bio,
                    engine=engine
                )

            except Exception:

                bio.seek(0)

    # XLS ancien format
    if header == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':

        for engine in [
            "xlrd",
            "calamine"
        ]:

            try:

                return pd.read_excel(
                    bio,
                    engine=engine
                )

            except Exception:

                bio.seek(0)

    # Dernier recours
    for engine in [
        "openpyxl",
        "xlrd",
        "calamine"
    ]:

        try:

            bio.seek(0)

            return pd.read_excel(
                bio,
                engine=engine
            )

        except Exception:

            continue

    raise ValueError(
        "Format de fichier non reconnu. "
        "Le fichier n'est ni un .xlsx ni un .xls valide.\n"
        "Vérifiez que le fichier n'est pas corrompu "
        "ou protégé par mot de passe."
    )


# ══════════════════════════════════════════════════════════════
# PRÉPARATION DES DONNÉES
# ══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def prepare_data(
    ot_bytes: bytes,
    av_bytes: bytes,
    date_str: str
):

    # ══════════════════════════════════════════════
    # LECTURE
    # ══════════════════════════════════════════════

    raw_ot = read_excel_safe(ot_bytes)
    raw_av = read_excel_safe(av_bytes)

    # Exclusion CRESSEUR
    raw_ot = excr(raw_ot)
    raw_av = excr(raw_av)

    # ══════════════════════════════════════════════
    # DATES OT
    # ══════════════════════════════════════════════

    for c in [
        "Créé le",
        "Date de début planifiée",
        "Date de clôture",
        "Début réel",
        "Fin réelle"
    ]:

        if c in raw_ot.columns:

            raw_ot[c] = pd.to_datetime(
                raw_ot[c],
                errors="coerce"
            )

    # ══════════════════════════════════════════════
    # DATES AVIS
    # ══════════════════════════════════════════════

    for c in [
        "Créé le",
        "Début souhaité",
        "Date de la clôture"
    ]:

        if c in raw_av.columns:

            raw_av[c] = pd.to_datetime(
                raw_av[c],
                errors="coerce"
            )

    # ══════════════════════════════════════════════
    # DATE DE RÉFÉRENCE
    # ══════════════════════════════════════════════

    try:

        now_ts = pd.to_datetime(
            date_str,
            format="%d/%m/%Y"
        )

    except Exception:

        try:

            now_ts = pd.to_datetime(
                date_str,
                dayfirst=True
            )

        except Exception:

            now_ts = pd.Timestamp.today()

    # ══════════════════════════════════════════════
    # DATAFRAME OT COMPLET
    # ══════════════════════════════════════════════

    df = raw_ot.copy()

    # ══════════════════════════════════════════════
    # BACKLOG PRÉPARATION
    # ══════════════════════════════════════════════

    if "Statut utilisateur" in df.columns:

        df["Backlog preparation"] = np.where(
            df["Statut utilisateur"].apply(
                lambda x: contient_mot(
                    x,
                    MP_KW
                )
            ),
            "CARACTERISE",
            "NON CARACTERISE"
        )

    else:

        df["Backlog preparation"] = "NON CARACTERISE"

    # ══════════════════════════════════════════════
    # BACKLOG PLANIFICATION
    # ══════════════════════════════════════════════

    if "Statut utilisateur" in df.columns:

        df["Backlog planification"] = np.where(
            df["Statut utilisateur"].apply(
                lambda x: contient_mot(
                    x,
                    MPLAN_KW
                )
            ),
            "CARACTERISE",
            "NON CARACTERISE"
        )

    else:

        df["Backlog planification"] = "NON CARACTERISE"

    # ══════════════════════════════════════════════
    # TYPE CARAC PRÉPARATION
    # ══════════════════════════════════════════════

    if "Statut utilisateur" in df.columns:

        df["Type Carac Prep"] = (
            df["Statut utilisateur"]
            .apply(
                lambda x:
                next(
                    (
                        kw.split()[0]
                        for kw in MP_KW
                        if kw in str(x)
                    ),
                    "NON CARACTERISE"
                )
            )
        )

    else:

        df["Type Carac Prep"] = "NON CARACTERISE"

    # ══════════════════════════════════════════════
    # TYPE CARAC PLANIFICATION
    # ══════════════════════════════════════════════

    if "Statut utilisateur" in df.columns:

        df["Type Carac Plan"] = (
            df["Statut utilisateur"]
            .apply(
                lambda x:
                next(
                    (
                        kw.split()[0]
                        for kw in MPLAN_KW
                        if kw in str(x)
                    ),
                    "NON CARACTERISE"
                )
            )
        )

    else:

        df["Type Carac Plan"] = "NON CARACTERISE"

    # ══════════════════════════════════════════════
    # ÂGE DES OT
    # ══════════════════════════════════════════════

    for dc, am, ac in [

        (
            "Créé le",
            "amp",
            "ap"
        ),

        (
            "Date de début planifiée",
            "amlp",
            "alp"
        ),

        (
            "Date de début planifiée",
            "amex",
            "aex"
        ),

    ]:

        if dc in df.columns:

            df[am] = (
                (
                    now_ts.year
                    - df[dc].dt.year
                ) * 12
                +
                (
                    now_ts.month
                    - df[dc].dt.month
                )
            ).round(2)

            df[ac] = df[am].apply(cat_age)

        else:

            df[am] = np.nan
            df[ac] = ">3 mois"

    # ══════════════════════════════════════════════
    # STATUT OT
    # ══════════════════════════════════════════════

    if "Statut système" in df.columns:

        df["Statut OT"] = (
            df["Statut système"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.split()
            .str[0]
        )

    else:

        df["Statut OT"] = ""

    # ══════════════════════════════════════════════
    # OT CONFIRMÉ
    # ══════════════════════════════════════════════

    if "Statut système" in df.columns:

        statut_systeme_ot = (
            df["Statut système"]
            .fillna("")
            .astype(str)
        )

        df["OT CONFIME"] = np.where(
            statut_systeme_ot.str.contains(
                "CLOT|TCLO",
                na=False
            )
            &
            statut_systeme_ot.str.contains(
                "CONF",
                na=False
            ),
            "OUI",
            "NON"
        )

    else:

        df["OT CONFIME"] = "NON"

    # ══════════════════════════════════════════════
    # CONTIENT SOPL
    # ══════════════════════════════════════════════

    if "Statut utilisateur" in df.columns:

        df["Contient SOPL"] = (
            df["Statut utilisateur"]
            .fillna("")
            .astype(str)
            .str.contains(
                "SOPL",
                na=False
            )
            .map({
                True: 1,
                False: 0
            })
        )

    else:

        df["Contient SOPL"] = 0

    # ══════════════════════════════════════════════
    # OT LANC ESTIME
    # ══════════════════════════════════════════════

    if "Total coûts budgétés" in df.columns:

        cout_budget = pd.to_numeric(
            df["Total coûts budgétés"],
            errors="coerce"
        ).fillna(0)

        df["OT LANC ESTIME"] = np.where(
            cout_budget == 0,
            "NON",
            "OUI"
        )

    else:

        df["OT LANC ESTIME"] = "NON"

    # ══════════════════════════════════════════════
    # OT COR = RÉEL
    # ══════════════════════════════════════════════

    budget = (
        pd.to_numeric(
            df["Total coûts budgétés"],
            errors="coerce"
        ).fillna(0)
        if "Total coûts budgétés" in df.columns
        else pd.Series(
            0,
            index=df.index
        )
    )

    reel = (
        pd.to_numeric(
            df["Total coûts réels"],
            errors="coerce"
        ).fillna(0)
        if "Total coûts réels" in df.columns
        else pd.Series(
            0,
            index=df.index
        )
    )

    df["OT_COR_EGAL"] = np.where(
        (budget - reel) == 0,
        "OUI",
        "NON"
    )

    # ══════════════════════════════════════════════
    # TYPE DE TRAVAIL NUMÉRIQUE
    # ══════════════════════════════════════════════

    if "Type de travail" in df.columns:

        df["_tw_num"] = pd.to_numeric(
            df["Type de travail"],
            errors="coerce"
        )

    else:

        df["_tw_num"] = np.nan

    # ══════════════════════════════════════════════
    # IMPORTANT :
    # ÂGE D'EXÉCUTION
    # ══════════════════════════════════════════════
    #
    # Les KPI d'âge d'exécution devront utiliser :
    #
    #     Statut OT = LANC
    #     ET
    #     Contient SOPL = 1
    #
    # Aucun filtre Type de travail.
    #
    # On conserve _tw_num pour les autres KPI qui peuvent
    # encore l'utiliser (Graissage, Inspection, etc.).
    #
    # ══════════════════════════════════════════════

    df["_eligible_age_execution"] = (
        (
            df["Statut OT"]
            .astype(str)
            .str.upper()
            .str.strip()
            == "LANC"
        )
        &
        (
            pd.to_numeric(
                df["Contient SOPL"],
                errors="coerce"
            )
            .fillna(0)
            == 1
        )
    )

    # ══════════════════════════════════════════════
    # PRÉPARATION AVIS
    # ══════════════════════════════════════════════

    avis_complet = preparer_avis(raw_av)

    # ══════════════════════════════════════════════
    # AVIS AOUV SANS ORDRE
    # ══════════════════════════════════════════════
    #
    # avf est conservé pour compatibilité avec le reste
    # de l'application.
    #
    # IMPORTANT :
    # Le filtre d'exclusion ZU/Z4/ZR/ZP n'est PAS appliqué
    # ici à avf afin de ne pas casser les autres fonctionnalités.
    #
    # Le calcul du KPI Approbation et le calcul des anomalies
    # utilisent "avis_complet" avec les règles spécifiques.
    # ══════════════════════════════════════════════════════════════

    if "Statut système" in raw_av.columns:

        is_aouv = (
            raw_av["Statut système"]
            .fillna("")
            .astype(str)
            .str.contains(
                "AOUV",
                na=False
            )
        )

    else:

        is_aouv = pd.Series(
            True,
            index=raw_av.index
        )

    if "Ordre" in raw_av.columns:

        sans_ordre = (
            raw_av["Ordre"].isna()
            |
            (
                raw_av["Ordre"]
                .astype(str)
                .str.strip()
                == ""
            )
        )

    else:

        sans_ordre = pd.Series(
            True,
            index=raw_av.index
        )

    avf = raw_av[
        sans_ordre
        &
        is_aouv
    ].copy()

    # ══════════════════════════════════════════════
    # APPEL POSTES SF1 / SF2
    # ══════════════════════════════════════════════

    if "Poste travail princ." in df.columns:

        apm = sorted(
            df[
                df["Poste travail princ."]
                .astype(str)
                .str.startswith(
                    (
                        "SF1",
                        "SF2"
                    ),
                    na=False
                )
            ][
                "Poste travail princ."
            ]
            .dropna()
            .unique()
            .tolist()
        )

    else:

        apm = []

    # ══════════════════════════════════════════════
    # INFORMATIONS COMPLÉMENTAIRES POUR LES KPI
    # ══════════════════════════════════════════════

    # Nombre total OT CRÉÉ.
    df["_ot_cree"] = (
        df["Statut OT"]
        .astype(str)
        .str.upper()
        .str.strip()
        == "CRÉÉ"
    )

    # Compatibilité avec SAP pouvant utiliser "CREE"
    df["_ot_cree"] = (
        df["Statut OT"]
        .astype(str)
        .str.upper()
        .str.strip()
        .isin([
            "CRÉÉ",
            "CREE"
        ])
    )

    # ══════════════════════════════════════════════
    # RETOUR
    # ══════════════════════════════════════════════

    return (
        df,
        avf,
        apm,
        now_ts,
        avis_complet
    )
