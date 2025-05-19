from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import os

app = FastAPI()

# Configuration (replace with real values or use environment variables)
LOGIN_URL = "https://api.traffilog.mx/login/json"
DATA_URL = "https://api.traffilog.mx/location/json"
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GOOGLE_MAPS_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

LOGIN_PAYLOAD = {
    "action": {
        "name": "user_login",
        "parameters": {
            "login_name": "your_username",
            "password": "your_password"
        }
    }
}

async def get_token():
    async with httpx.AsyncClient() as client:
        response = await client.post(LOGIN_URL, json=LOGIN_PAYLOAD)
        response.raise_for_status()
        data = response.json()
        return data["response"]["properties"]["session_token"]

async def get_location_data(session_token, license_nmbr):
    payload = {
        "action": {
            "name": "api_get_data",
            "parameters": [{
                "last_time": "",
                "license_nmbr": license_nmbr,
                "group_id": "",
                "version": "4"
            }],
            "session_token": session_token
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(DATA_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        coordinates = data["response"]["properties"]["data"][0]
        return coordinates["lat"], coordinates["lon"]

async def reverse_geocode(lat, lon):
    params = {
        "latlng": f"{lat},{lon}",
        "key": GOOGLE_MAPS_API_KEY
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(GOOGLE_MAPS_GEOCODE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if data["results"]:
            return data["results"][0]["formatted_address"]
        return "Unknown location"

@app.post("/get-location")
async def get_location_handler(request: Request):
    try:
        body = await request.json()
        args = body.get("args", body)
        license_nmbr = args.get("license_nmbr")

        if not license_nmbr:
            return JSONResponse(status_code=422, content={"error": "Missing license_nmbr"})

        session_token = await get_token()
        lat, lon = await get_location_data(session_token, license_nmbr)
        address = await reverse_geocode(lat, lon)

        return {"address": address}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
