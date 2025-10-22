from fastapi import APIRouter, HTTPException
import httpx, json
from app.core.config import settings
from app.models.request import DecodeVinRequest
from app.models.response import DecodeVinResponse

vin_router = APIRouter(prefix="/vin", tags=["Vehicle"])

@vin_router.post("/details", response_model=DecodeVinResponse)
async def decode_vin(request: DecodeVinRequest):
    url = settings.VIN_API_URL
    headers = {
        "Authorization": f"Bearer {settings.VIN_API}",
        "Content-Type": "application/json"
    }
    payload = {
        "session_id": "1761024240367",
        "message": request.vin,
        "agent_id": "68d64fb8a2356c3108a44e44"
    }

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minutes timeout
            response = await client.post(url, headers=headers, json=payload)
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="VIN API request timed out")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"VIN API request failed: {str(e)}")

    if not response.is_success:
        raise HTTPException(status_code=response.status_code, detail="VIN API request failed")

    data = response.json()

    try:
        inner = json.loads(data["text"])
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid inner JSON structure")

    if inner.get("status") != "success":
        raise HTTPException(status_code=400, detail=inner.get("error_message", "VIN lookup failed"))

    vehicle = inner["vehicle"]

    return DecodeVinResponse(
        Vehicle=f"{vehicle['year']} {vehicle['make']} {vehicle['model']}",
        Type=vehicle.get("body_style", "Unknown")
    )