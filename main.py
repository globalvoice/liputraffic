import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

# --- Configuration from environment ---
TRAFFILOG_API_URL = os.getenv("DATA_URL")   # e.g. https://api.traffilog.mx/clients/json
API_USERNAME      = os.getenv("API_USERNAME")
API_PASSWORD      = os.getenv("API_PASSWORD")
GOOGLE_MAPS_KEY   = os.getenv("GOOGLE_MAPS_API_KEY")

# --- Helper functions ---

async def get_token():
    payload = {
        "action": {
            "name": "user_login",
            "parameters": {
                "login_name": API_USERNAME,
                "password": API_PASSWORD
            }
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(TRAFFILOG_API_URL, json=payload)
        resp.raise_for_status()
        js = resp.json()
        token = js.get("response", {}).get("properties", {}).get("session_token")
        if not token:
            raise Exception("Login failed: no session_token")
        return token

async def get_location_coords(session_token: str, license_nmbr: str):
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
        resp = await client.post(TRAFFILOG_API_URL, json=payload)
        resp.raise_for_status()
        js = resp.json()
        data_list = js.get("response", {}).get("properties", {}).get("data", [])
        if not data_list:
            raise Exception("No location data returned for that license")
        first = data_list[0]
        lat = first.get("latitude")
        lon = first.get("longitude")
        if lat is None or lon is None:
            raise Exception("Invalid location data (missing latitude/longitude)")
        return lat, lon

async def reverse_geocode(lat: float, lon: float):
    params = {"latlng": f"{lat},{lon}", "key": GOOGLE_MAPS_KEY}
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://maps.googleapis.com/maps/api/geocode/json", params=params)
        resp.raise_for_status()
        js = resp.json()
        results = js.get("results", [])
        if not results:
            raise Exception("Reverse geocoding returned no results")
        return results[0].get("formatted_address", "Unknown address")

# --- Endpoints ---

@app.get("/")
def root():
    return {"status": "liputraffic API is live"}

@app.post("/get-location")
async def get_location(request: Request):
    # 1. Parse incoming JSON
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    # 2. Support both Retell ({"args":{...}}) and raw body
    args = body.get("args", body)
    license_nmbr = args.get("license_nmbr")
    if not license_nmbr:
        return JSONResponse(status_code=422, content={"error": "Missing license_nmbr"})

    # 3. Perform the lookup flow
    try:
        token = await get_token()
        lat, lon = await get_location_coords(token, license_nmbr)
        address = await reverse_geocode(lat, lon)
        return {"address": address}

    except httpx.HTTPStatusError as e:
        # Propagate API errors (e.g., 401, 403, 404)
        return JSONResponse(status_code=e.response.status_code, content={"error": e.response.text})

    except Exception as e:
        # Catch-all
        return JSONResponse(status_code=500, content={"error": str(e)})
