from fastapi import APIRouter, Query
from app.models.response import CompanyListResponse, CompanyDetailsResponse, MessageResponse, CompanyResponse
from app.services.hubspot_service import get_all_companies, get_company_details, create_company
from app.core.logger import get_logger

from typing import cast

hub_router = APIRouter(prefix="/hubspot", tags=["HubSpot"])
logger = get_logger("hubspot_router")


@hub_router.get("/companies", response_model=CompanyListResponse)
async def list_companies(limit: int = Query(10, ge=1, le=100)):
    """
    Returns a list of companies from HubSpot.
    """
    companies = await get_all_companies(limit)
    return CompanyListResponse(count=len(companies), companies=companies)


@hub_router.get("/company/details", response_model=CompanyDetailsResponse)
async def company_details(company_name: str):
    """
    Fetch details for a specific company name.
    If not found, auto-create a company.
    """
    results = await get_company_details(company_name)

    if not results:
        logger.info(f"No results found, creating company {company_name}")
        return cast(CompanyDetailsResponse, await create_company({"name": company_name}))

    props = results[0]["properties"]
    return CompanyDetailsResponse(
        name=props.get("name"),
        domain=props.get("domain"),
        phone=props.get("phone"),
        address=props.get("address"),
    )