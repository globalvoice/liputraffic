from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json
import httpx

app = FastAPI()

# Placeholder: replace with your actual get_location logic
async def get_real_address_from_license(license_nmbr: str):
    # Example fixed response (replace this with your real logic)
    return f"Simulated address for vehicle {license_nmbr}"

@app.post("/get-location")
async def get_location_handler(request: Request):
    try:
        body = await request.json()
        print("Full body received:", body)

        # Retell sends 'args' as a string
        args_raw = body.get("args")

        if isinstance(args_raw, str):
            try:
                args = json.loads(args_raw)
            except Exception as e:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid JSON in 'args'",
                        "raw_args": args_raw,
                        "exception": str(e)
                    }
                )
        else:
            args = args_raw

        license_nmbr = args.get("license_nmbr")

        if not license_nmbr:
            return JSONResponse(
                status_code=422,
                content={"error": "Missing license_nmbr"}
            )

        # Call your real function (replace this with API logic)
        address = await get_real_address_from_license(license_nmbr)

        return {"address": address}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
