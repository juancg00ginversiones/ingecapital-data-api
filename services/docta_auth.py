import time
import httpx
from typing import Dict, Any, Optional

DOCTA_BASE = "https://api.doctacapital.com.ar/api/v1"

_token_cache: Dict[str, Any] = {"access_token": None, "expires_at": 0}

async def get_access_token(client_id: str, client_secret: str, scope: str, timeout: float = 20.0) -> str:
    # Cache token
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scope,
    }

    # probamos sin slash y con slash
    token_urls = [
        f"{DOCTA_BASE}/auth/token",
        f"{DOCTA_BASE}/auth/token/",
    ]

    last_error: Optional[str] = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        for url in token_urls:
            r = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            if r.status_code == 200:
                j = r.json()
                access_token = j.get("access_token")
                expires_in = int(j.get("expires_in", 3600))
                if not access_token:
                    last_error = f"Token response missing access_token: {j}"
                    continue

                # guardamos con margen
                _token_cache["access_token"] = access_token
                _token_cache["expires_at"] = time.time() + max(60, expires_in - 60)
                return access_token

            last_error = f"{r.status_code} {r.text}"

    raise RuntimeError(f"Docta auth failed. Last error: {last_error}")
