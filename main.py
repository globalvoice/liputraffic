from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

async def get_real_address_from_license(license_nmbr: str):
    # Replace this with your real business logic
    return f"Simulated address for vehicle {license_nmbr}"

@app.post("/get-location")
async def get_location_handler(request: Request):
    try:
        body = await request.json()

        # Check if Retell-style: {"args": {"license_nmbr": "1659"}}
        if "args" in body:
            args = body["args"]
        else:
            args = body  # fallback to raw body from Postman

        license_nmbr = args.get("license_nmbr")

        if not license_nmbr:
            return JSONResponse(status_code=422, content={"error": "Missing license_nmbr"})

        address = await get_real_address_from_license(license_nmbr)
        return {"address": address}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
