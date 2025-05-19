
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests

app = FastAPI()

LOGIN_URL = os.getenv("LOGIN_URL")
DATA_URL = os.getenv("DATA_URL")
USERNAME = os.getenv("API_USERNAME")
PASSWORD = os.getenv("API_PASSWORD")

@app.post("/get-location")
async def get_location(request: Request):
    try:
        body = await request.json()
        license_nmbr = body.get("license_nmbr")

        if not license_nmbr:
            return JSONResponse(status_code=400, content={"error": "Missing license_nmbr"})

        # Step 1: Login
        login_payload = {
            "action": {
                "name": "user_login",
                "parameters": [
                    {
                        "login_name": USERNAME,
                        "password": PASSWORD,
                        "version": "4"
                    }
                ]
            }
        }

        login_response = requests.post(LOGIN_URL, json=login_payload)
        login_response.raise_for_status()
        login_data = login_response.json()

        session_token = login_data["response"]["properties"].get("session_token")

        if not session_token:
            return JSONResponse(
                status_code=401,
                content={"error": "Login failed", "details": login_data}
            )

        # Step 2: Get location using session_token
        location_payload = {
            "action": {
                "name": "api_get_data",
                "parameters": [
                    {
                        "last_time": "",
                        "license_nmbr": license_nmbr,
                        "group_id": "",
                        "version": "4"
                    }
                ]
            },
            "session_token": session_token
        }

        location_response = requests.post(DATA_URL, json=location_payload)
        location_response.raise_for_status()
        location_data = location_response.json()

        # Step 3: Extract address or handle error
        data_list = location_data["response"]["properties"].get("data", [])
        if data_list and isinstance(data_list, list):
            item = data_list[0]
            if "error_code" in item:
                return JSONResponse(
                    status_code=404,
                    content={"error": "Not authorized or vehicle not found", "details": item}
                )

            address = item.get("address")
            if address:
                return {"address": address}

        return JSONResponse(
            status_code=404,
            content={"error": "Location not found", "raw_response": location_data}
        )

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Server error", "details": str(e)})
