import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

# --- Configuration from environment ---
TRAFFILOG_API_URL = os.getenv("DATA_URL")      # e.g. https://api.traffilog.mx/clients/json
API_USERNAME      = os.getenv("API_USERNAME")
API_PASSWORD      = os.getenv("API_PASSWORD")
GOOGLE_MAPS_KEY   = os.getenv("GOOGLE_MAPS_API_KEY")

# --- Helper functions ---

async def get_token():
    """
    Logs in and retrieves a session token from Traffilog.
    """
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
    """
    Calls Traffilog to fetch latitude and longitude for the given license number.
    """
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
        # Traffilog field names may vary; adjust if needed:
        lat = first.get("latitude") or first.get("latitud")
        lon = first.get("longitude") or first.get("longitud")
        if lat is None or lon is None:
            raise Exception("Invalid location data (missing latitude/longitude)")
        return lat, lon

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

    # 2. Support both Retell ({"args": {...}}) and raw body from Postman
    args = body.get("args", body)
    license_nmbr = args.get("license_nmbr")
    if not license_nmbr:
        return JSONResponse(status_code=422, content={"error": "Missing license_nmbr"})

    # 3. Perform the lookup flow
    try:
        token = await get_token()
        lat, lon = await get_location_coords(token, license_nmbr)

        # --- DEBUG OUTPUT: return raw coordinates ---
        return {"latitude": lat, "longitude": lon}

    except httpx.HTTPStatusError as e:
        # Propagate API HTTP errors
        return JSONResponse(status_code=e.response.status_code, content={"error": e.response.text})
    except Exception as e:
        # Catch-all for any other errors
        return JSONResponse(status_code=500, content={"error": str(e)})
