# -*- coding: utf-8 -*-
"""
Chargement automatique des données (ot.xlsx, avis.xlsx, date) depuis des
liens de partage OneDrive Entreprise / SharePoint ("Toute personne dans
l'organisation avec le lien" ou public) — PAS d'authentification
interactive Microsoft.

Configuration (Streamlit Cloud → Settings → Secrets), format TOML :
    ONEDRIVE_OT_URL = "https://eocp-my.sharepoint.com/:x:/g/personal/m_benmoussa_ocpgroup_ma/IQAOdnffldv6QYtGHJmIoyArAYBM13a0OSo0CTvmH-mePyY?e=2PtZuz"
    ONEDRIVE_AVIS_URL = "https://eocp-my.sharepoint.com/:x:/g/personal/m_benmoussa_ocpgroup_ma/IQDQtfXEY5N-RY4Uq2tV__4YAbNm8sGrrGNfFd5tnhfRF-g?e=3cW3Gl"
    ONEDRIVE_DATE_URL = "https://eocp-my.sharepoint.com/:t:/g/personal/m_benmoussa_ocpgroup_ma/IQCnHSm2MW4lTImL-HqPH7lQAX_8v64udMNHnzmyLtJ8kI0?e=0XgVa2"

Si ces secrets ne sont pas définis, load_data_from_onedrive() retourne
(None, None, None, None) sans erreur → l'app retombe sur les fichiers
locaux (ot.xlsx/avis.xlsx chargés manuellement), comportement inchangé.

⚠️ Le lien doit être un lien de partage "Toute personne dans
[organisation] avec le lien" (ou public), PAS "Personnes spécifiques" —
ce dernier nécessite une connexion Microsoft interactive que ce
mécanisme ne gère pas (pas d'OAuth ici, volontairement, sur demande).

Automatique : appelé à chaque ouverture/rechargement de l'app → récupère
toujours la DERNIÈRE version du fichier partagé (le lien pointe vers le
contenu live, pas un snapshot figé) — pas besoin de logique séparée de
"détection de nouveau fichier".
"""
import requests
import streamlit as st

TIMEOUT = 20  # secondes

def _to_direct_download_url(share_url: str) -> str:
    """
    Convertit un lien de partage SharePoint/OneDrive Entreprise en URL de
    téléchargement direct, en forçant le paramètre download=1.
    """
    if not share_url:
        return share_url
    if "download=1" in share_url:
        return share_url
    sep = "&" if "?" in share_url else "?"
    return f"{share_url}{sep}download=1"

def fetch_bytes(share_url: str):
    """Télécharge le contenu d'un lien de partage. Retourne (bytes, erreur)."""
    if not share_url:
        return None, None
    url = _to_direct_download_url(share_url)
    try:
        resp = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        content = resp.content
        # Détection basique : une page de connexion Microsoft renvoyée au
        # lieu du fichier (lien pas assez ouvert / auth requise) ressemble
        # à du HTML, pas à un classeur Excel (qui commence par PK ou D0CF).
        if content[:2] not in (b"PK", b"\xd0\xcf") and len(content) < 5000:
            return None, (
                "le lien n'a pas renvoyé de fichier Excel valide "
                "(probablement un lien qui nécessite une connexion "
                "Microsoft — utilisez un lien « Toute personne avec le "
                "lien » ou « Toute personne dans l'organisation »)."
            )
        return content, None
    except requests.exceptions.Timeout:
        return None, "délai dépassé en contactant OneDrive."
    except requests.exceptions.RequestException as e:
        return None, f"erreur réseau ({e})."

def fetch_text(share_url: str):
    """Télécharge un fichier texte (ex: date.txt). Retourne (str, erreur)."""
    content, err = fetch_bytes(share_url)
    if err:
        return None, err
    if content is None:
        return None, None
    try:
        return content.decode("utf-8").strip(), None
    except Exception as e:
        return None, f"impossible de décoder le fichier texte ({e})."

def load_data_from_onedrive():
    """
    Charge ot.xlsx, avis.xlsx et (optionnellement) la date depuis les
    liens configurés dans st.secrets.

    Retourne (ot_bytes, av_bytes, date_str, error_message).
    - Si OneDrive non configuré (secrets ONEDRIVE_OT_URL/ONEDRIVE_AVIS_URL
      absents) : (None, None, None, None) → l'appelant doit retomber sur
      les fichiers locaux, aucune erreur affichée.
    - Si configuré mais échec réseau/format : (None, None, None, "message
      d'erreur explicite") → l'appelant doit afficher l'erreur ET quand
      même retomber sur les fichiers locaux si disponibles.
    """
    try:
        ot_url = st.secrets.get("ONEDRIVE_OT_URL")
        av_url = st.secrets.get("ONEDRIVE_AVIS_URL")
        date_url = st.secrets.get("ONEDRIVE_DATE_URL")
    except Exception:
        return None, None, None, None

    if not ot_url or not av_url:
        return None, None, None, None  # OneDrive non configuré → fallback local

    ot_bytes, ot_err = fetch_bytes(ot_url)
    if ot_err:
        return None, None, None, f"ot.xlsx : {ot_err}"

    av_bytes, av_err = fetch_bytes(av_url)
    if av_err:
        return None, None, None, f"avis.xlsx : {av_err}"

    date_str = None
    if date_url:
        date_str, date_err = fetch_text(date_url)
        if date_err:
            date_str = None  # non bloquant : on garde la date locale/par défaut

    return ot_bytes, av_bytes, date_str, None
