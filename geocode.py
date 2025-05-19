import os
import httpx

async def reverse_geocode(lat: float, lon: float):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={os.getenv('GEOCODE_KEY')}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return data["results"][0]["formatted_address"]