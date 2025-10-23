import httpx
from app.core.config import settings


async def get_distance_miles(zip_from: str, zip_to: str) -> float:
    """
    Uses OpenRouteService to calculate driving distance between two ZIP codes (in miles).
    Steps:
      1. Geocode both ZIPs to lat/lon using ORS /geocode/search.
      2. Request /v2/directions/driving-car for driving distance.
    """
    ORS_KEY = settings.OPENROUTESERVICE_API_KEY
    if not ORS_KEY:
        raise ValueError("OPENROUTESERVICE_API_KEY not configured in settings.")

    async with httpx.AsyncClient(timeout=10) as client:
        # Step 1: Get coordinates for both ZIPs
        async def geocode(zipcode: str):
            res = await client.get(
                "https://api.openrouteservice.org/geocode/search",
                params={"api_key": ORS_KEY, "text": zipcode, "boundary.country": "US"},
            )
            data = res.json()
            features = data.get("features", [])
            if not features:
                raise ValueError(f"Geocode failed for ZIP {zipcode}")
            coords = features[0]["geometry"]["coordinates"]  # [lon, lat]
            return coords[1], coords[0]  # lat, lon

        from_lat, from_lon = await geocode(zip_from)
        to_lat, to_lon = await geocode(zip_to)

        # Step 2: Calculate driving distance
        route_res = await client.post(
            "https://api.openrouteservice.org/v2/directions/driving-car",
            headers={"Authorization": ORS_KEY, "Content-Type": "application/json"},
            json={"coordinates": [[from_lon, from_lat], [to_lon, to_lat]]},
        )
        route_data = route_res.json()

        if "routes" not in route_data:
            raise ValueError(f"OpenRouteService error: {route_data}")

        meters = route_data["routes"][0]["summary"]["distance"]
        miles = round(meters / 1609.34, 2)
        return miles