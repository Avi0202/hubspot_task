import httpx
from app.core.config import settings


async def get_distance_miles(zip_from: str, zip_to: str, use_truck_profile: bool = False) -> float:
    """
    Calculate driving distance (in miles) between two U.S. ZIP codes
    using OpenRouteService.
    
    Steps:
      1. Convert both ZIP codes to coordinates via ORS /geocode/search.
      2. Request /v2/directions/ driving-car OR driving-hgv for the route.
         - driving-hgv is a truck routing profile.
    """
    ORS_KEY = settings.OPENROUTESERVICE_API_KEY
    if not ORS_KEY:
        raise ValueError("OPENROUTESERVICE_API_KEY not configured in settings.")

    # Select routing profile
    profile = "driving-hgv" if use_truck_profile else "driving-car"
    directions_url = f"https://api.openrouteservice.org/v2/directions/{profile}"
    geocode_url = "https://api.openrouteservice.org/geocode/search"

    async with httpx.AsyncClient(timeout=10) as client:

        async def geocode(zipcode: str) -> tuple[float, float]:
            """Look up a ZIP code and return (latitude, longitude) using ORS geocoding."""
            try:
                response = await client.get(
                    geocode_url,
                    params={
                        "api_key": ORS_KEY,
                        "text": zipcode,
                        "boundary.country": "US",
                    },
                )
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                raise ValueError(f"Error geocoding ZIP {zipcode}: {e}")

            features = data.get("features", [])
            if not features:
                raise ValueError(f"Geocode failed for ZIP {zipcode}")

            lon, lat = features[0]["geometry"]["coordinates"]
            return lat, lon

        # Step 1: Get coordinates for both ZIPs
        from_lat, from_lon = await geocode(zip_from)
        to_lat, to_lon = await geocode(zip_to)

        # Step 2: Calculate driving or truck distance
        payload = {
            "coordinates": [[from_lon, from_lat], [to_lon, to_lat]],
            "radiuses": [5000, 5000],  # 🔹 increase search radius to 5 km on each end
            "options": {
                "profile_params": {
                    "restrictions": {
                        "vehicle_type": "truck",
                        "width": 2.6,
                        "height": 4.0,
                        "length": 12.0,
                        "weight": 40.0
                    }
                }
            } if use_truck_profile else {}
        }

        try:
            route_res = await client.post(
                directions_url,
                headers={
                    "Authorization": ORS_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            route_res.raise_for_status()
            route_data = route_res.json()
        except Exception as e:
            raise ValueError(f"OpenRouteService API error: {e}")

        # Validate response
        routes = route_data.get("routes")
        if not routes:
            raise ValueError(f"OpenRouteService error: {route_data}")

        # Extract distance and convert to miles
        meters = routes[0]["summary"]["distance"]
        miles = round(meters / 1609.34, 2)

        return miles