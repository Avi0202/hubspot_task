from fastapi import APIRouter, Query
from app.models.response import CompanyListResponse, CompanyDetailsResponse, MessageResponse, CompanyResponse
from app.services.hubspot_service import get_all_companies, get_company_details
from app.core.logger import get_logger

from typing import cast

hub_router = APIRouter(prefix="/hubspot", tags=["HubSpot"])
logger = get_logger("hubspot_router")


@hub_router.get("/companies", response_model=CompanyListResponse)
async def list_companies(limit: int = Query(100, ge=1, le=100), start_chars: str = Query(None, min_length=1)):
    """
    Returns a list of companies from HubSpot.
    """
    companies = await get_all_companies(100, start_chars=start_chars)
    return CompanyListResponse(count=len(companies), companies=companies)


@hub_router.get("/company/details", response_model=CompanyDetailsResponse)
async def company_details(company_name: str):
    """
    Fetch details for a specific company name.
    If not found, auto-create a company.
    """
    if not company_name.strip():
        logger.warning("Empty company_name in request, skipping HubSpot call.")
        return CompanyDetailsResponse()

    results = await get_company_details(company_name)

    if not results:
        logger.info("No results found")
        return CompanyDetailsResponse()

    props = results[0]["properties"]
    return CompanyDetailsResponse(
        name=props.get("name"),
        domain=props.get("domain"),
        phone=props.get("phone"),
        address_line1=props.get("address_line1"),
        address_line2=props.get("address_line2"),
        city=props.get("city"),
        state=props.get("state"),
        zip_code=props.get("zip"),
        country=props.get("country"),
    )