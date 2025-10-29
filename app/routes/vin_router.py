from fastapi import APIRouter, HTTPException
import httpx
from app.core.logger import get_logger
from app.models.request import DecodeVinRequest
from app.models.response import DecodeVinResponse

vin_router = APIRouter(prefix="/vin", tags=["Vehicle"])
logger = get_logger(__name__)

@vin_router.post("/details", response_model=DecodeVinResponse)
async def decode_vin(request: DecodeVinRequest):
    vin = request.vin.strip().upper()
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"

    logger.info(f"Calling NHTSA API for VIN: {vin}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="NHTSA VIN API request timed out")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"NHTSA VIN API request failed: {str(e)}")

    if not response.is_success:
        raise HTTPException(status_code=response.status_code, detail="NHTSA VIN API request failed")

    data = response.json()

    try:
        results = data["Results"][0]  # results is a list with one dict
    except (KeyError, IndexError):
        raise HTTPException(status_code=500, detail="Unexpected NHTSA API response structure")

    # Extract the required fields
    vehicle = {
        "year": results.get("ModelYear"),
        "make": results.get("Make"),
        "model": results.get("Model"),
        "type": results.get("BodyClass", "Unknown")
    }

    return DecodeVinResponse(
        year=vehicle["year"],
        make=vehicle["make"],
        model=vehicle["model"],
        type=vehicle["type"]
    )