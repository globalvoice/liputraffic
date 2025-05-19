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
            "session_token": token  # This is the likely mistake
        }
    }

    print("Sending payload to DATA_URL:", payload)

    async with httpx.AsyncClient() as client:
        response = await client.post(os.getenv("DATA_URL"), json=payload)

        # Print raw response for debugging
        print("Response text:", response.text)

        response.raise_for_status()
        data = response.json()

        loc = data["response"]["properties"]["data"][0]  # Adjust after seeing result
        return {"lat": loc["latitude"], "lon": loc["longitude"]}
