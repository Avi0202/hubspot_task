from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.core.logger import get_logger
import httpx

hub_router = APIRouter(prefix="/hubspot", tags=["HubSpot"])
logger = get_logger("hubspot_router")
HUBSPOT_BASE_URL = settings.HUBSPOT_BASE_URL
HUBSPOT_TOKEN = settings.HUBSPOT_TOKEN


async def hubspot_request(method: str, endpoint: str, params=None, json=None):
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }
    logger.info(f"Making {method} request to HubSpot API: {endpoint}")
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=f"{HUBSPOT_BASE_URL}{endpoint}",
            headers=headers,
            params=params,
            json=json,
        )
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()


async def search_company_by_name(company_name: str):
    endpoint = "/crm/v3/objects/companies/search"
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {"propertyName": "name", "operator": "EQ", "value": company_name}
                ]
            }
        ],
        "properties": ["name", "domain", "phone"],
    }
    data = await hubspot_request("POST", endpoint, json=payload)
    if data.get("results"):
        return data["results"][0]
    return None

@hub_router.get("/companies")
async def get_all_companies(limit: int = 10):
    """
    Fetch a list of companies from HubSpot.
    Limit defaults to 10, but you can override it with ?limit=20, etc.
    """
    endpoint = "/crm/v3/objects/companies"

    # HubSpot allows pagination — 'after' param can also be used if you want to fetch next pages
    params = {
        "limit": limit,
        "properties": "name,domain,phone,address"
    }
    logger.info(f"Fetching up to {limit} companies from HubSpot")
    data = await hubspot_request("GET", endpoint, params=params)

    # Only return relevant fields for easier readability
    companies = [
        {
            "id": company["id"],
            "name": company["properties"].get("name"),
            "domain": company["properties"].get("domain"),
            "phone": company["properties"].get("phone"),
            
        }
        for company in data.get("results", [])
    ]

    return {
        "count": len(companies),
        "companies": companies
    }



async def create_company_helper(company_data: dict):
    """
    Shared helper — creates a new company in HubSpot.
    Accepts a dict of company fields.
    """
    endpoint = "/crm/v3/objects/companies"
    payload = {"properties": company_data}

    data = await hubspot_request("POST", endpoint, json=payload)

    props = data.get("properties", {})
    return {
        "id": data.get("id"),
        "name": props.get("name"),
        "domain": props.get("domain"),
        "phone": props.get("phone"),
        "address": props.get("address"),
    }
@hub_router.get("/company/details")
async def get_company_details(company_name: str):
    endpoint = "/crm/v3/objects/companies/search"
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "name",
                        "operator": "CONTAINS_TOKEN",
                        "value": company_name
                    }
                ]
            }
        ],
        "properties": ["name", "domain", "phone"]
    }
    data = await hubspot_request("POST", endpoint, json=payload)

    if not data.get("results"):
        logger.info(f"No results found for company name: {company_name}")
        logger.info(f"Adding new company to HubSpot: {company_name}")
        await create_company_helper({"name": company_name})
        logger.info(f"Company '{company_name}' added successfully.")
        return {"message": f"No results found for '{company_name}', added new company."}

    props = data["results"][0]["properties"]

    # return a clean JSON object
    return {
        "name": props.get("name"),
        "domain": props.get("domain"),
        "phone": props.get("phone")
    }