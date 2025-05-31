import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
from typing import List, Dict, Union # Import Union for type hinting flexibility
import datetime # Import datetime for handling current timestamps

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

# MODIFIED: Added logic to try to get the latest data
async def get_location_coords(session_token: str, license_nmbr: str):
    # Option 1: Send a recent timestamp (common for "latest data")
    # This assumes 'last_time' means "get data since this time"
    # If it means "get data before this time", you'd need to send a future timestamp
    # If the API simply provides the last known location when `last_time` is absent or "null",
    # then you might remove the "last_time" key entirely from the parameters.
    
    # As a robust attempt to get the latest, we'll try to provide a very recent timestamp.
    # This makes the assumption that 'last_time' is a filter for data *newer than* the provided timestamp.
    # If this still gives stale data, you MUST consult Traffilog's API docs.
    current_time_gmt = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "action": {
            "name": "api_get_data",
            "parameters": [{
                "last_time": current_time_gmt, # Attempt to get the latest data
                "license_nmbr": license_nmbr,
                "group_id": "",
                "version": "4"
            }],
            "session_token": session_token
        }
    }
    
    # If the Traffilog API returns multiple points and you always want the very latest,
    # you would need to sort by timestamp (if available in the response) and pick the newest.
    # Given your original code expects `data[0]`, we'll stick to that,
    # but the `last_time` parameter is the main way to control freshness on the API side.

    async with httpx.AsyncClient() as client:
        resp = await client.post(TRAFFILOG_API_URL, json=payload)
        resp.raise_for_status()
        js = resp.json()
        data_list = js.get("response", {}).get("properties", {}).get("data", [])
        
        if not data_list:
            # If no data is returned with the recent timestamp,
            # try again with an empty `last_time` (which might give the absolute last known)
            print(f"No fresh data for {license_nmbr} using recent timestamp. Trying with empty last_time.")
            payload["action"]["parameters"][0]["last_time"] = "" 
            resp_fallback = await client.post(TRAFFILOG_API_URL, json=payload)
            resp_fallback.raise_for_status()
            js_fallback = resp_fallback.json()
            data_list = js_fallback.get("response", {}).get("properties", {}).get("data", [])
            
            if not data_list:
                raise Exception("No location data returned for that license even with fallback.")


        first = data_list[0] # Assuming the API returns the freshest data as the first element
        
        # Check for timestamp if available and if you want to be extra sure
        # if "timestamp" in first:
        #    print(f"Data timestamp for {license_nmbr}: {first['timestamp']}")

        # Handle possible field names
        lat_str = first.get("latitude") or first.get("latitud")
        lon_str = first.get("longitude") or first.get("longitud")
        if not lat_str or not lon_str:
            raise Exception("Invalid location data (missing latitude/longitude)")
        try:
            return float(lat_str), float(lon_str)
        except ValueError:
            raise Exception(f"Invalid coordinate format: {lat_str}, {lon_str}")

# REVISED: reverse_geocode to return detailed info (as in previous answer)
async def reverse_geocode(lat: float, lon: float) -> Dict[str, Union[str, None]]:
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

# MODIFIED: get_location endpoint to handle single or multiple license numbers
@app.post("/get-location") # Keep original name
async def get_location(request: Request):
    # 1. Parse incoming JSON
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    # 2. Support both Retell and Postman payloads, and now a list of license numbers
    args = body.get("args", body) # This line remains to support 'args' key if present

    license_nmbrs: List[str] = []

    # Check if 'license_nmbrs' (plural) is provided as a list
    if isinstance(args.get("license_nmbrs"), list):
        license_nmbrs = [str(num) for num in args["license_nmbrs"]] # Ensure they are strings
    elif isinstance(args.get("license_nmbr"), str):
        # Check if 'license_nmbr' (singular) is provided as a string
        license_nmbrs = [args["license_nmbr"]]
    else:
        return JSONResponse(status_code=422, content={"error": "Missing 'license_nmbr' (string) or 'license_nmbrs' (list of strings) in the request."})

    results = {}
    token = None # Initialize token outside the loop

    try:
        # Get token once for all requests in the batch for efficiency
        token = await get_token()

        for license_nmbr in license_nmbrs:
            try:
                lat, lon = await get_location_coords(token, license_nmbr)
                detailed_address_info = await reverse_geocode(lat, lon)
                results[license_nmbr] = {
                    "status": "success",
                    "data": detailed_address_info
                }
            except Exception as e:
                results[license_nmbr] = {
                    "status": "error",
                    "message": str(e)
                }

    except httpx.HTTPStatusError as e:
        # Handle HTTP errors from Traffilog API or Google Geocoding
        return JSONResponse(status_code=e.response.status_code, content={"error": e.response.text})
    except Exception as e:
        # Catch any other unexpected errors during token retrieval or general process
        return JSONResponse(status_code=500, content={"error": str(e)})
    
    # If only one license number was requested, return just its result directly for simplicity
    if len(license_nmbrs) == 1 and license_nmbrs[0] in results:
        return results[license_nmbrs[0]]
    
    # Otherwise, return the full dictionary of results
    return JSONResponse(content=results)
