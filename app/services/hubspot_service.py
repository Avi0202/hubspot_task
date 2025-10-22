import httpx
from fastapi import HTTPException
from app.core.config import settings
from app.core.logger import get_logger
from app.models.response import CompanyResponse

logger = get_logger("hubspot_service")

HUBSPOT_BASE_URL = settings.HUBSPOT_BASE_URL
HUBSPOT_TOKEN = settings.HUBSPOT_TOKEN


# ----------------------------- COMMON HUBSPOT REQUEST -----------------------------
async def hubspot_request(method: str, endpoint: str, params=None, json=None):
    """
    Generic HubSpot request helper that can be reused for any type of object.
    """
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }

    logger.info(f"HubSpot {method} request to {endpoint}")

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=f"{HUBSPOT_BASE_URL}{endpoint}",
            headers=headers,
            params=params,
            json=json,
        )

        if response.status_code >= 400:
            logger.error(f"HubSpot API Error: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        return response.json()


# ----------------------------- COMPANY SERVICES -----------------------------
async def create_company(company_data: dict) -> CompanyResponse:
    """
    Create a company in HubSpot.
    """
    endpoint = "/crm/v3/objects/companies"
    payload = {"properties": company_data}

    data = await hubspot_request("POST", endpoint, json=payload)
    props = data.get("properties", {})

    logger.info(f"Created company: {props.get('name')}")
    return CompanyResponse(
        id=data.get("id"),
        name=props.get("name"),
        domain=props.get("domain"),
        phone=props.get("phone"),
        address=props.get("address"),
    )


async def get_all_companies(limit: int = 10):
    """
    Retrieve multiple companies from HubSpot.
    """
    endpoint = "/crm/v3/objects/companies"
    params = {"limit": limit, "properties": "name,domain,phone,address"}

    data = await hubspot_request("GET", endpoint, params=params)
    results = data.get("results", [])

    return [
        CompanyResponse(
            id=company["id"],
            name=company["properties"].get("name"),
            domain=company["properties"].get("domain"),
            phone=company["properties"].get("phone"),
            address=company["properties"].get("address"),
        )
        for company in results
    ]


async def get_company_details(company_name: str):
    """
    Search company by name — if not found, optionally create one later.
    """
    endpoint = "/crm/v3/objects/companies/search"
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "name",
                        "operator": "CONTAINS_TOKEN",
                        "value": company_name,
                    }
                ]
            }
        ],
        "properties": ["name", "domain", "phone", "address"],
    }

    data = await hubspot_request("POST", endpoint, json=payload)
    return data.get("results", [])