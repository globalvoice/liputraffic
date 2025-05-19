import os
import httpx
from auth import get_token

async def get_location(license_nmbr: str):
    token = await get_token()

    payload = {
        "action": {
            "name": "api_get_data",
            "parameters": [{
                "last_time": "",
                "license_nmbr": license_nmbr,
                "group_id": "",
                "version": "4"
            }],
            "session_token": token
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(os.getenv("DATA_URL"), json=payload)
        response.raise_for_status()
        return response.json()  # or handle as needed
