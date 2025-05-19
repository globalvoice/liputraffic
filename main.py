from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from location import get_location
from geocode import reverse_geocode

app = FastAPI()

class LocationRequest(BaseModel):
    license_nmbr: str

@app.get("/")
def root():
    return {"status": "liputraffic API is live"}

@app.post("/get-location")
async def get_address(request: LocationRequest):
    try:
        coords = await get_location(request.license_nmbr)
        address = await reverse_geocode(coords["lat"], coords["lon"])
        return {"address": address}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
