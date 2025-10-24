from fastapi import APIRouter, HTTPException
from app.models.quote_request import QuoteRequest
from app.models.quote_response import QuoteResponse, RouteHistory
from app.models.email_request import EmailRequest
from app.models.email_response import EmailResponse
from app.services.distance_service import get_distance_miles
from app.core.logger import get_logger
from app.services.hubspot_service import create_transport_deal
from app.models.quote_email_request import QuoteEmailRequest
from app.services.hubspot_service import send_quote_email
import random

quote_router = APIRouter(prefix="/quote", tags=["Quote"])

logger = get_logger(__name__)

@quote_router.post("/generate", response_model=QuoteResponse)
async def generate_quote(payload: QuoteRequest):
    """
    Accepts pickup/delivery info and vehicles, 
    calculates distance between ZIP codes, 
    and returns pricing & dummy route history.
    """
    logger.info("Calling transport deal creation in HubSpot")

# Build a flat dict exactly like your incoming JSON
    deal_data = {
        "company_name": getattr(payload, "company_name", "Individual Customer"),
        "contact_name": payload.contact_name,
        "email": payload.email,
        "phone": payload.phone,
        "vehicles": [v.dict() for v in payload.vehicles],
        "pickup": payload.pickup.dict(),
        "delivery": payload.delivery.dict()
    }
    
    # Create HubSpot records
    hubspot_response = await create_transport_deal(deal_data)
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
        final_quote_amount = round(super_dispatch_price * (1 + markup_percentage / 100), 2)

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
             final_quote_amount=final_quote_amount,
             route_history=route_history,
             # ➕ include IDs from HubSpot
             company_id=hubspot_response.get("company_id"),
             contact_id=hubspot_response.get("contact_id"),
             deal_id=hubspot_response.get("deal_id")
         )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@quote_router.post("/generate-email", response_model=EmailResponse)
async def generate_email(payload: EmailRequest):
    """
    Generates a personalized transport quote email using provided details.
    """
    name = payload.contact_name
    # Format vehicle list nicely
    vehicles = [f"{v.year} {v.make} {v.model}" for v in payload.vehicles]
    if len(vehicles) == 1:
        vehicle_text = vehicles[0]
    else:
        vehicle_text = ", ".join(vehicles[:-1]) + f" and {vehicles[-1]}"

    pickup = f"{payload.pickup_city}, {payload.pickup_state}"
    delivery = f"{payload.delivery_city}, {payload.delivery_state}"
    amount = f"${payload.final_quote_amount:,.0f}"

    subject = f"Auto Transport Quote - {pickup} to {delivery}"

    body = (
        f"Hi {name},\n\n"
        f"Thank you for your inquiry about shipping your {vehicle_text} "
        f"from {pickup} to {delivery}.\n\n"
        f"I'm pleased to provide you with a quote of {amount} for this transport. "
        f"This includes:\n\n"
        f"• Full insurance coverage during transport\n"
        f"• Door-to-door service\n"
        f"• Real-time tracking updates\n"
        f"• Estimated delivery within 3-5 business days\n\n"
        f"Our team has successfully completed similar routes recently with excellent customer satisfaction. "
        f"If you'd like to proceed or have any questions, please don't hesitate to reach out.\n\n"
        f"Best regards,\n"
        f"Ethan Valentine\n"
        f"First Source Auto"
    )
    return EmailResponse(subject=subject, body=body)

@quote_router.post("/send-quote-email")
async def send_quote_email_route(payload: QuoteEmailRequest):
    """
    Takes the deal/contact/company IDs, AI‑generated email,
    and quote amount, creates the quote record, and logs/sends the email.
    """
    logger.info(f"Sending quote email for deal {payload.deal_id}")
    result = await send_quote_email(payload.dict())
    return {"status": "Email logged", "quote_id": result.get("quote_id")}