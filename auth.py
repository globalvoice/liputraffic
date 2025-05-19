import os
import httpx
from cachetools import TTLCache

# Cache token for 6 hours
token_cache = TTLCache(maxsize=1, ttl=21600)

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
        result = response.json()

        # ADD THIS TO DEBUG
        print("Login response JSON:", result)

        # Adjust this based on what prints
        token = result.get("token") or result.get("result", {}).get("session_token")

        if not token:
            raise Exception("No session_token returned from login response")

        token_cache["token"] = token
        return token
