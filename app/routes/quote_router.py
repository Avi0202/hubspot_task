import asyncio
from fastapi import APIRouter, HTTPException
from app.models.quote_request import QuoteRequest
from app.models.quote_response import QuoteResponse, RouteHistory
from app.models.email_request import EmailRequest
from app.models.email_response import EmailResponse
from app.services.distance_service import get_distance_miles
from app.core.logger import get_logger
from app.services.hubspot_service import create_transport_deal,get_or_create_company
from app.services.email_service import generate_email
from app.models.quote_email_request import QuoteEmailRequest
from app.services.hubspot_service import send_quote_email
import random

from app.services.implicit_company_service import enrich_company_data

quote_router = APIRouter(prefix="/quote", tags=["Quote"])

logger = get_logger(__name__)

@quote_router.post("/generate", response_model=QuoteResponse)
async def generate_quote(payload: QuoteRequest):
    
    deal_data = {
        "company_name": getattr(payload, "company_name", "").strip() or "Individual Customer",
        "contact_name": payload.contact_name,
        "email": payload.email,
        "phone": payload.phone,
        "vehicles": [v.dict() for v in payload.vehicles],
        "pickup": payload.pickup.dict(),
        "delivery": payload.delivery.dict(),
        # "billing_address": getattr(payload, "billing_address", None)
    }

    company_name = deal_data.get("company_name")
    phone = deal_data.get("phone")
    
    address = {
    "address_line1": payload.address_line1,
    "address_line2": payload.address_line2,
    "city": payload.city,
    "state": payload.state,
    "zip_code": payload.zip_code,
    "country": payload.country,
}

    # ✅ ensure company exists and attach ID
    company = await get_or_create_company(company_name, phone, address)
    company_id = company["id"]
    asyncio.create_task(enrich_company_data(company_id, company_name))
    logger.info(f"Started enrichment task for company {company_name}")
    deal_data["company_id"] = company_id  # ✅ pass company id forward

    logger.info("Calling transport deal creation in HubSpot")

    hubspot_response = await create_transport_deal(deal_data)
    ...
    logger.info(f"HubSpot deal created: {hubspot_response}")

    logger.info(f"calling distance service for {payload.pickup.zip} to {payload.delivery.zip}")
    try:
        # Step 1: Calculate distance
        distance_miles = await get_distance_miles(
            payload.pickup.zip, payload.delivery.zip
        )
        # distance_miles=round(random.uniform(500, 3000), 2)  # Dummy distance for testing

        # Step 2: Dummy Super Dispatch and Internal AI Prices
        super_dispatch_price = round(distance_miles * 1.0, 2)  # $1/mi dummy logic
        internal_ai_price = round(super_dispatch_price * random.uniform(0.95, 1.05), 2)
        markup_percentage = 12
        quote_amount = round(super_dispatch_price * (1 + markup_percentage / 100), 2)

        # Step 3: Dummy Similar Route History
        route_history = [
            RouteHistory(
                origin="Hayward, CA",
                destination="Arlington, VA",
                distance_miles=2845.1,
                date="2024-08-15",
                status="Won",
                price=3200,
                company="Reed Auto Group"
            ),
            RouteHistory(
                origin="San Francisco, CA",
                destination="Aldie, VA",
                distance_miles=2887.3,
                date="2024-07-22",
                status="Lost",
                price=3050,
                company="America’s Auto Auction"
            )
        ]

        # Step 4: Return response
        return QuoteResponse(
             origin=f"{payload.pickup.city}, {payload.pickup.state}, {payload.pickup.zip}",
             destination=f"{payload.delivery.city}, {payload.delivery.state}, {payload.delivery.zip}",
             distance_miles=distance_miles,
             super_dispatch_price=super_dispatch_price,
             internal_ai_price=internal_ai_price,
             markup_percentage=markup_percentage,
             quote_amount=quote_amount,
             route_history=route_history,
             # ➕ include IDs from HubSpot
             vehicles=[v.dict() for v in payload.vehicles],
             company_id=hubspot_response.get("company_id"),
             contact_id=hubspot_response.get("contact_id"),
             deal_id=hubspot_response.get("deal_id")
         )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@quote_router.post("/generate-email", response_model=EmailResponse)
async def generate(payload: EmailRequest):
    
    email_data = await generate_email(payload)
    # logger.info(f"Generated email data: {email_data}")

    # FIXED: access attributes directly instead of .get()
    subject = email_data.get("subject") or "Your Vehicle Shipping Quote"
    body = email_data.get("body") or (
    "Dear Customer,\n\nThank you for requesting a vehicle shipping quote. "
    "We will get back to you shortly with the details.\n\nBest regards,\nVehicle Shipping Team"
)
    # logger.info(f"Final email subject:{body} {subject}")
    return EmailResponse(subject=subject, body=body)

@quote_router.post("/send-quote-email")
async def send_quote_email_route(payload: QuoteEmailRequest):
    logger.info(f"Sending quote email for deal {payload.deal_id}")
    result = await send_quote_email(payload.dict())
    return {"status": "Email logged", "email_id": result.get("email_id")}