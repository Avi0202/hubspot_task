from fastapi import APIRouter, HTTPException, Query
from app.core.config import settings
from app.core.logger import get_logger
from app.models.request import CompanySearchRequest, CreateCompanyRequest
from app.models.response import (
    CompanyResponse,
    CompanyListResponse,
    CompanyDetailsResponse,
    MessageResponse,
)
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


# Helper to create a company ---------------------------------------------------
async def create_company_helper(company_data: dict) -> CompanyResponse:
    endpoint = "/crm/v3/objects/companies"
    payload = {"properties": company_data}
    data = await hubspot_request("POST", endpoint, json=payload)

    props = data.get("properties", {})
    return CompanyResponse(
        id=data.get("id"),
        name=props.get("name"),
        domain=props.get("domain"),
        phone=props.get("phone"),
        address=props.get("address"),
    )


# Route: get all companies -----------------------------------------------------
@hub_router.get("/companies", response_model=CompanyListResponse)
async def get_all_companies(limit: int = Query(10, ge=1, le=100)):
    endpoint = "/crm/v3/objects/companies"
    params = {"limit": limit, "properties": "name,domain,phone,address"}

    logger.info(f"Fetching up to {limit} companies from HubSpot")
    data = await hubspot_request("GET", endpoint, params=params)

    companies = [
        CompanyResponse(
            id=company["id"],
            name=company["properties"].get("name"),
            domain=company["properties"].get("domain"),
            phone=company["properties"].get("phone"),
            address=company["properties"].get("address"),
        )
        for company in data.get("results", [])
    ]

    return CompanyListResponse(count=len(companies), companies=companies)


# Route: get company details ---------------------------------------------------
@hub_router.get("/company/details", response_model=CompanyDetailsResponse)
async def get_company_details(company_name: str):
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

    if not data.get("results"):
        logger.info(f"No results found for company name: {company_name}")
        await create_company_helper({"name": company_name})
        logger.info(f"Company '{company_name}' added successfully.")
        return MessageResponse(message=f"No results found for '{company_name}', added new company.")

    props = data["results"][0]["properties"]
    return CompanyDetailsResponse(
        name=props.get("name"),
        domain=props.get("domain"),
        phone=props.get("phone"),
        address=props.get("address"),
    )