from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/get-location")
async def get_address(request: Request):
    body = await request.body()
    print("RAW BODY RECEIVED:", body)

    try:
        json_data = await request.json()
        return {"json_received": json_data}
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid JSON",
                "raw_body": body.decode(),
                "exception": str(e)
            }
        )
