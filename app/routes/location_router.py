from fastapi import APIRouter, HTTPException
import httpx
from app.core.config import settings

location_router = APIRouter(prefix="/location", tags=["Location"])

ZIPPO_BASE_URL = settings.ZIPPO_BASE_URL

@location_router.get("/{zipcode}")
async def get_location(zipcode: str):
    """Return city and state for a given ZIP code."""
    url = f"{ZIPPO_BASE_URL}/{zipcode}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Invalid or unknown ZIP code")

    data = response.json()

    place = data.get("places", [{}])[0]
    city = place.get("place name")
    state = place.get("state")
    state_abbr = place.get("state abbreviation")

    return {"zip": zipcode, "city": city, "state": state, "state_abbr": state_abbr}