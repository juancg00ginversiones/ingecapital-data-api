import requests
from config import DOCTA_CLIENT_ID, DOCTA_CLIENT_SECRET, DOCTA_BASE_URL

def get_docta_token():
    url = f"{DOCTA_BASE_URL}/api/v1/auth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": DOCTA_CLIENT_ID,
        "client_secret": DOCTA_CLIENT_SECRET
    }
    headers = {"Content-Type": "application/json"}

    r = requests.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        raise Exception(f"Docta auth error: {r.text}")

    return r.json()["access_token"]

def docta_get(endpoint: str, token: str, params=None):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{DOCTA_BASE_URL}{endpoint}"
    return requests.get(url, headers=headers, params=params)

def docta_post(endpoint: str, token: str, payload: dict):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    url = f"{DOCTA_BASE_URL}{endpoint}"
    return requests.post(url, headers=headers, json=payload)
