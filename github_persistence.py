import base64
import requests
import streamlit as st

GITHUB_OWNER = "rajnakviliam"
GITHUB_REPO = "tennis-surface-elo"
GITHUB_BRANCH = "main"

def _github_token():
    try:
        return st.secrets["GITHUB_TOKEN"]
    except Exception:
        return None

def persist_file_to_github(local_filename, repo_path=None, commit_message=None):
    token = _github_token()
    if not token:
        return False, (
            "V Streamlit secrets chýba GITHUB_TOKEN. "
            "Lokálna zmena zostala iba v aktuálnom runtime."
        )

    if repo_path is None:
        repo_path = local_filename
    if commit_message is None:
        commit_message = f"Update {repo_path} from Streamlit"

    api_url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/{repo_path}"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = requests.get(
        api_url,
        headers=headers,
        params={"ref": GITHUB_BRANCH},
        timeout=30,
    )

    if response.status_code == 200:
        sha = response.json().get("sha")
    elif response.status_code == 404:
        sha = None
    else:
        return False, (
            "GitHub read zlyhal: "
            f"{response.status_code} {response.text[:300]}"
        )

    with open(local_filename, "rb") as f:
        raw = f.read()

    payload = {
        "message": commit_message,
        "content": base64.b64encode(raw).decode("ascii"),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(
        api_url,
        headers=headers,
        json=payload,
        timeout=30,
    )

    if response.status_code in (200, 201):
        return True, f"{repo_path} bol uložený aj do GitHubu."

    return False, (
        "GitHub zápis zlyhal: "
        f"{response.status_code} {response.text[:300]}"
    )
