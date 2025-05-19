import os
import httpx
from cachetools import TTLCache

token_cache = TTLCache(maxsize=1, ttl=21600)  # 6 hours

async def get_token():
    if "token" in token_cache:
        return token_cache["token"]

    payload = {
        "action": {
            "name": "user_login",
            "parameters": {
                "login_name": os.getenv("API_USERNAME"),
                "password": os.getenv("API_PASSWORD")
            }
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(os.getenv("LOGIN_URL"), json=payload)
        response.raise_for_status()
        token = response.json().get("token") or response.json().get("result", {}).get("session_token")
        token_cache["token"] = token
        return token