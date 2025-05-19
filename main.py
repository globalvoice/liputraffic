from fastapi import FastAPI, HTTPException, Query
from location import get_location
from geocode import reverse_geocode

app = FastAPI()

@app.get("/")
def root():
    return {"status": "liputraffic API is live"}

@app.get("/get-location")
async def get_address(license_nmbr: str = Query(..., alias="unit")):
    try:
        coords = await get_location(license_nmbr)
        address = await reverse_geocode(coords["lat"], coords["lon"])
        return {"address": address}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))