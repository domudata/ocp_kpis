# -*- coding: utf-8 -*-
"""
Publication automatique de fichiers sur GitHub, via l'API REST "Contents"
(https://docs.github.com/en/rest/repos/contents), en utilisant un
Personal Access Token (PAT) stocké dans st.secrets["GITHUB_TOKEN"].

Nécessite dans Streamlit Cloud → Settings → Secrets :
    GITHUB_TOKEN = "ghp_xxx..."   (scope minimal requis : "repo" sur le dépôt cible)
    GITHUB_REPO  = "compte/nom-du-repo"   (ex: "domudata/ocp_kpis")
    GITHUB_BRANCH = "main"   (optionnel, defaut "main")

⚠️ Le token doit être un PAT "classic" avec le scope `repo`, ou un token
"fine-grained" avec accès Contents (lecture+écriture) sur CE dépôt précis.
Ne jamais coller le token en clair dans le code ou dans le chat — toujours
via st.secrets.
"""
import base64
import requests
import streamlit as st

API_ROOT = "https://api.github.com"
TIMEOUT = 30


def _get_config():
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]
    except Exception:
        return None, None, None
    branch = None
    try:
        branch = st.secrets.get("GITHUB_BRANCH", "main")
    except Exception:
        branch = "main"
    # Nettoyage défensif : espaces en trop, guillemets accidentellement
    # inclus dans la valeur (ex: si collé avec les guillemets du TOML).
    if isinstance(token, str):
        token = token.strip().strip('"').strip("'")
    if isinstance(repo, str):
        repo = repo.strip().strip('"').strip("'")
    if isinstance(branch, str):
        branch = branch.strip().strip('"').strip("'")
    return token, repo, branch


def is_configured() -> bool:
    token, repo, _ = _get_config()
    return bool(token and repo)


def debug_config() -> str:
    """Retourne un résumé SANS le token (masqué), pour diagnostiquer un
    problème de configuration sans jamais exposer le secret."""
    token, repo, branch = _get_config()
    token_masked = f"{token[:7]}...{token[-4:]} (longueur {len(token)})" if token else "ABSENT"
    return f"repo={repo!r}  branch={branch!r}  token={token_masked}"


def upload_file(path_in_repo: str, content_bytes: bytes, commit_message: str):
    """
    Crée ou met à jour un fichier dans le dépôt GitHub configuré.
    path_in_repo : chemin relatif dans le repo, ex: "presentation/SF1-ECU/rapport.pptx"
    Retourne (ok: bool, message: str).
    """
    token, repo, branch = _get_config()
    if not token or not repo:
        return False, "GITHUB_TOKEN / GITHUB_REPO non configurés dans les secrets."

    url = f"{API_ROOT}/repos/{repo}/contents/{path_in_repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # 1) Vérifier si le fichier existe déjà (pour récupérer son sha —
    # obligatoire pour une mise à jour, sinon GitHub refuse l'écrasement).
    sha = None
    try:
        r = requests.get(url, headers=headers, params={"ref": branch}, timeout=TIMEOUT)
        if r.status_code == 200:
            sha = r.json().get("sha")
        elif r.status_code not in (404,):
            return False, f"Erreur vérification existence ({r.status_code}) sur {url} : {r.text[:200]}"
    except requests.exceptions.RequestException as e:
        return False, f"Erreur réseau (vérification) sur {url} : {e}"

    # 2) Créer ou mettre à jour
    payload = {
        "message": commit_message,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    try:
        r = requests.put(url, headers=headers, json=payload, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        return False, f"Erreur réseau (envoi) sur {url} : {e}"

    if r.status_code in (200, 201):
        return True, "OK"
    # CORRIGÉ : inclut désormais l'URL exacte utilisée (sans le token) dans
    # le message d'erreur, pour diagnostiquer un GITHUB_REPO/branch mal
    # formé (espace, guillemets parasites...) — un 404 systématique sur
    # tous les fichiers, malgré un token valide, pointe presque toujours
    # vers une valeur GITHUB_REPO incorrecte plutôt qu'un problème de droits.
    return False, f"Échec envoi ({r.status_code}) sur {url} [branch={branch!r}] : {r.text[:300]}"
