import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

# --- Configuration from environment ---
TRAFFILOG_API_URL   = os.getenv("DATA_URL")           # e.g. https://api.traffilog.mx/clients/json
API_USERNAME       = os.getenv("API_USERNAME")
API_PASSWORD       = os.getenv("API_PASSWORD")
GOOGLE_MAPS_KEY    = os.getenv("GOOGLE_MAPS_API_KEY")
GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
OSM_REVERSE_URL    = "https://nominatim.openstreetmap.org/reverse"


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
        # Handle possible field names
        lat_str = first.get("latitude") or first.get("latitud")
        lon_str = first.get("longitude") or first.get("longitud")
        if not lat_str or not lon_str:
            raise Exception("Invalid location data (missing latitude/longitude)")
        try:
            return float(lat_str), float(lon_str)
        except ValueError:
            raise Exception(f"Invalid coordinate format: {lat_str}, {lon_str}")

async def reverse_geocode(lat: float, lon: float):
    # First try Google
    params = {"latlng": f"{lat},{lon}", "key": GOOGLE_MAPS_KEY}
    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_GEOCODE_URL, params=params)
        resp.raise_for_status()
        js = resp.json()
        results = js.get("results", [])
        if results:
            return results[0].get("formatted_address")

    # Fallback to OpenStreetMap Nominatim
    osm_params = {"lat": lat, "lon": lon, "format": "json"}
    headers = {"User-Agent": "liputraffic-app/1.0"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(OSM_REVERSE_URL, params=osm_params, headers=headers)
        resp.raise_for_status()
        js = resp.json()
        if "error" not in js and js.get("display_name"):
            return js["display_name"]

    # Last fallback: raw coordinates
    return f"{lat},{lon}"


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

    # 2. Support both Retell and Postman payloads
    args = body.get("args", body)
    license_nmbr = args.get("license_nmbr")
    if not license_nmbr:
        return JSONResponse(status_code=422, content={"error": "Missing license_nmbr"})

    # 3. Lookup + geocode
    try:
        token = await get_token()
        lat, lon = await get_location_coords(token, license_nmbr)
        address = await reverse_geocode(lat, lon)
        return {"address": address}

    except httpx.HTTPStatusError as e:
        return JSONResponse(status_code=e.response.status_code, content={"error": e.response.text})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
