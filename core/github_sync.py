# -*- coding: utf-8 -*-
"""
Synchronisation GitHub : committe un fichier (bytes) dans le repo,
en ECRASANT la version precedente au meme chemin.

Configuration requise (Streamlit Cloud -> Settings -> Secrets) :
    GITHUB_TOKEN = "ghp_..."          # Personal Access Token, scope 'repo'
    GITHUB_REPO  = "domudata/ocp_kpis" # owner/repo
    GITHUB_BRANCH = "main"             # optionnel, defaut "main"

Obtenir un token : github.com -> Settings -> Developer settings ->
Personal access tokens -> Tokens (classic) -> Generate new token
(cocher le scope 'repo').
"""
import base64
import json
import streamlit as st

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

API_BASE = "https://api.github.com"


def _get_config():
    token = st.secrets.get("GITHUB_TOKEN", None)
    repo = st.secrets.get("GITHUB_REPO", None)
    branch = st.secrets.get("GITHUB_BRANCH", "main")
    return token, repo, branch


def is_configured() -> bool:
    token, repo, _ = _get_config()
    return bool(token and repo and REQUESTS_AVAILABLE)


def push_file_to_github(path: str, content_bytes: bytes, commit_message: str) -> tuple:
    """
    Committe (cree ou ECRASE) un fichier dans le repo GitHub configure.

    path            : chemin du fichier dans le repo (ex: "ot.xlsx")
    content_bytes   : contenu binaire du fichier
    commit_message  : message de commit

    Retourne (succes: bool, message: str)
    """
    if not REQUESTS_AVAILABLE:
        return False, "Le module 'requests' n'est pas installe (ajoutez-le a requirements.txt)."

    token, repo, branch = _get_config()
    if not token or not repo:
        return False, (
            "GitHub non configure. Ajoutez GITHUB_TOKEN et GITHUB_REPO "
            "dans Manage app -> Settings -> Secrets."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    url = f"{API_BASE}/repos/{repo}/contents/{path}"

    # 1. Recuperer le SHA du fichier existant (necessaire pour ECRASER,
    #    sinon GitHub refuse et cree un conflit)
    sha = None
    try:
        r_get = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
        if r_get.status_code == 200:
            sha = r_get.json().get("sha")
        elif r_get.status_code not in (404,):
            return False, f"Erreur lecture fichier existant ({r_get.status_code}) : {r_get.text[:200]}"
    except Exception as e:
        return False, f"Erreur reseau (lecture) : {e}"

    # 2. Push (create si sha=None, update/ecrase sinon)
    payload = {
        "message": commit_message,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    try:
        r_put = requests.put(url, headers=headers, data=json.dumps(payload), timeout=30)
        if r_put.status_code in (200, 201):
            action = "mis a jour (ecrase)" if sha else "cree"
            return True, f"✅ {path} {action} sur GitHub avec succes."
        else:
            return False, f"Erreur commit GitHub ({r_put.status_code}) : {r_put.text[:300]}"
    except Exception as e:
        return False, f"Erreur reseau (ecriture) : {e}"


def push_multiple_files(files: dict, commit_message: str) -> list:
    """
    Committe plusieurs fichiers. files = {chemin: contenu_bytes}.
    Retourne une liste de (path, succes, message) pour chaque fichier.
    """
    results = []
    for path, content in files.items():
        ok, msg = push_file_to_github(path, content, commit_message)
        results.append((path, ok, msg))
    return results
