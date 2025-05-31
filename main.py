import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

# --- Configuration from environment ---
TRAFFILOG_API_URL    = os.getenv("DATA_URL")         # e.g. https://api.traffilog.mx/clients/json
API_USERNAME         = os.getenv("API_USERNAME")
API_PASSWORD         = os.getenv("API_PASSWORD")
Maps_KEY      = os.getenv("Maps_API_KEY")
GOOGLE_GEOCODE_URL   = "https://maps.googleapis.com/maps/api/geocode/json"
OSM_REVERSE_URL      = "https://nominatim.openstreetmap.org/reverse"


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
    params = {"latlng": f"{lat},{lon}", "key": Maps_KEY}
    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_GEOCODE_URL, params=params)
        resp.raise_for_status()
        js = resp.json()
        results = js.get("results", [])

        if results:
            first_result = results[0]
            detailed_address = {
                "formatted_address": first_result.get("formatted_address"),
                "street_number": None,
                "route": None,
                "city": None,
                "state": None,
                "country": None,
                "postal_code": None,
                "plus_code": first_result.get("plus_code", {}).get("global_code")
            }

            for component in first_result.get("address_components", []):
                types = component.get("types", [])
                if "street_number" in types:
                    detailed_address["street_number"] = component.get("long_name")
                elif "route" in types:
                    detailed_address["route"] = component.get("long_name")
                elif "locality" in types:  # city
                    detailed_address["city"] = component.get("long_name")
                elif "administrative_area_level_1" in types:  # state/province
                    detailed_address["state"] = component.get("long_name")
                elif "country" in types:
                    detailed_address["country"] = component.get("long_name")
                elif "postal_code" in types:
                    detailed_address["postal_code"] = component.get("long_name")
            
            return detailed_address

    # Fallback to OpenStreetMap Nominatim
    # OSM Nominatim provides a less structured address, but we can still try to extract relevant parts.
    osm_params = {"lat": lat, "lon": lon, "format": "jsonv2"} # Use jsonv2 for more structured data
    headers = {"User-Agent": "liputraffic-app/1.0"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(OSM_REVERSE_URL, params=osm_params, headers=headers)
        resp.raise_for_status()
        js = resp.json()

        if "error" not in js and js.get("address"):
            osm_address = js.get("address", {})
            return {
                "formatted_address": js.get("display_name"),
                "street_number": osm_address.get("house_number"),
                "route": osm_address.get("road"),
                "city": osm_address.get("city") or osm_address.get("town") or osm_address.get("village"),
                "state": osm_address.get("state"),
                "country": osm_address.get("country"),
                "postal_code": osm_address.get("postcode"),
                "plus_code": None # OSM Nominatim doesn't provide Plus Codes
            }

    # Last fallback: raw coordinates if no geocoding service provides a result
    return {
        "formatted_address": f"{lat},{lon}",
        "street_number": None,
        "route": None,
        "city": None,
        "state": None,
        "country": None,
        "postal_code": None,
        "plus_code": None
    }


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
        detailed_address_info = await reverse_geocode(lat, lon) # Now returns a dict
        return detailed_address_info # Return the dictionary directly

    except httpx.HTTPStatusError as e:
        return JSONResponse(status_code=e.response.status_code, content={"error": e.response.text})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
