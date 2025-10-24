import httpx
import aiohttp
from fastapi import HTTPException
from app.core.config import settings
from app.core.logger import get_logger
from app.models.response import CompanyResponse

logger = get_logger("hubspot_service")

# -------------------------------------------------------------------
# ONE correct base URL and token
# -------------------------------------------------------------------
HUBSPOT_BASE_URL = "https://api.hubapi.com/crm/v3/objects"
HUBSPOT_TOKEN = settings.HUBSPOT_TOKEN
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}

# -------------------------------------------------------------------
# Common helper for httpx‑based endpoints
# -------------------------------------------------------------------
async def hubspot_request(method: str, endpoint: str, params=None, json=None):
    headers = HEADERS
    full_url = f"{HUBSPOT_BASE_URL}{endpoint}"
    logger.info(f"HubSpot {method} request to {full_url}")

    async with httpx.AsyncClient() as client:
        resp = await client.request(method, full_url, headers=headers, params=params, json=json)
        if resp.status_code >= 400:
            logger.error(f"HubSpot error {resp.status_code}: {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()

# -------------------------------------------------------------------
# Company utilities (unchanged)
# -------------------------------------------------------------------
async def create_company(company_data: dict) -> CompanyResponse:
    endpoint = "/companies"
    payload = {"properties": company_data}
    data = await hubspot_request("POST", endpoint, json=payload)
    props = data.get("properties", {})
    logger.info(f"Created company: {props.get('name')}")
    return CompanyResponse(
        id=data.get("id"),
        name=props.get("name"),
        domain=props.get("domain"),
        phone=props.get("phone"),
        address=props.get("address")
    )

async def get_all_companies(limit: int = 10):
    endpoint = "/companies"
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
    endpoint = "/companies/search"
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "name",
                "operator": "CONTAINS_TOKEN",
                "value": company_name
            }]
        }],
        "properties": ["name", "domain", "phone", "address"]
    }
    data = await hubspot_request("POST", endpoint, json=payload)
    return data.get("results", [])

# -------------------------------------------------------------------
# create_transport_deal – main async HubSpot integration
# -------------------------------------------------------------------
import aiohttp

async def create_transport_deal(data: dict):
    """
    Creates or reuses HubSpot company, contact, and deal entities,
    associates them together, and returns their IDs.
    Handles 409 conflicts (already exists) and logs useful info.
    """

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # ------------------------------------------------------------------
        # 1️⃣ Create or reuse Company
        # ------------------------------------------------------------------
        company_name = data.get("company_name", "Individual Customer")
        company_payload = {"properties": {"name": company_name}}
        company_id = None

        async with session.post(f"{HUBSPOT_BASE_URL}/companies", json=company_payload) as res:
            company_text = await res.text()
            logger.info(f"Company response: {res.status} {company_text}")

            try:
                company_json = await res.json()
            except Exception:
                company_json = {}

            # handle both success and duplicate (409)
            if res.status in (200, 201):
                company_id = company_json.get("id")
            elif res.status == 409:
                # HubSpot sends detail about existing ID inside the message
                msg = company_json.get("message", "")
                if "Existing ID:" in msg:
                    company_id = msg.split("Existing ID:")[-1].strip()
                logger.info(f"Company already exists. Using existing ID: {company_id}")
            else:
                logger.warning(f"Company creation failed: {company_text}")

        # ------------------------------------------------------------------
        # 2️⃣ Create or reuse Contact
        # ------------------------------------------------------------------
        contact_payload = {
            "properties": {
                "firstname": data.get("contact_name"),
                "email": data.get("email"),
                "phone": data.get("phone", "")
            }
        }
        contact_id = None

        async with session.post(f"{HUBSPOT_BASE_URL}/contacts", json=contact_payload) as res:
            contact_text = await res.text()
            logger.info(f"Contact response: {res.status} {contact_text}")

            try:
                contact_json = await res.json()
            except Exception:
                contact_json = {}

            if res.status in (200, 201):
                contact_id = contact_json.get("id")
            elif res.status == 409:
                msg = contact_json.get("message", "")
                if "Existing ID:" in msg:
                    contact_id = msg.split("Existing ID:")[-1].strip()
                logger.info(f"Contact already exists. Using existing ID: {contact_id}")
            else:
                logger.warning(f"Contact creation failed: {contact_text}")

        # ------------------------------------------------------------------
        # 3️⃣ Create Deal
        # ------------------------------------------------------------------
        pickup = data.get("pickup", {}) or {}
        delivery = data.get("delivery", {}) or {}

        deal_payload = {
            "properties": {
                "dealname": f"{data.get('contact_name')} Quote",
                "pickup_city": pickup.get("city", ""),
                "delivery_city": delivery.get("city", ""),
                "vehicles_json": str(data.get("vehicles", []))
            }
        }

        deal_id = None
        async with session.post(f"{HUBSPOT_BASE_URL}/deals", json=deal_payload) as res:
            deal_text = await res.text()
            logger.info(f"Deal response: {res.status} {deal_text}")

            try:
                deal_json = await res.json()
            except Exception:
                deal_json = {}

            if res.status in (200, 201):
                deal_id = deal_json.get("id")
            elif res.status == 409:
                msg = deal_json.get("message", "")
                if "Existing ID:" in msg:
                    deal_id = msg.split("Existing ID:")[-1].strip()
                logger.info(f"Deal already exists. Using existing ID: {deal_id}")
            else:
                logger.warning(f"Deal creation failed: {deal_text}")

        # ------------------------------------------------------------------
        # 4️⃣ Create Associations (only if IDs exist)
        # ------------------------------------------------------------------
        if deal_id and company_id:
            await session.put(
                f"https://api.hubapi.com/crm/v4/associations/deals/companies/{deal_id}/{company_id}"
            )
            logger.info(f"Associated Deal {deal_id} ↔ Company {company_id}")

        if deal_id and contact_id:
            await session.put(
                f"https://api.hubapi.com/crm/v4/associations/deals/contacts/{deal_id}/{contact_id}"
            )
            logger.info(f"Associated Deal {deal_id} ↔ Contact {contact_id}")

        # ------------------------------------------------------------------
        # 5️⃣ Return all IDs for the API response
        # ------------------------------------------------------------------
        logger.info(
            f"HubSpot IDs => Company: {company_id}, Contact: {contact_id}, Deal: {deal_id}"
        )

        return {
            "company_id": company_id,
            "contact_id": contact_id,
            "deal_id": deal_id,
        }

async def send_quote_email(data: dict):
    """
    Creates a quote object and logs/sends the email via HubSpot.
    """
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # 1️⃣ create quote (native "quotes" object)
        quote_payload = {
            "properties": {
                "hs_title": f"Quote for deal {data['deal_id']}",
                "hs_quote_amount": data["quote_amount"]
            },
            "associations": [
                {
                    "to": {"id": data["deal_id"]},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 65}]
                },
                {
                    "to": {"id": data["contact_id"]},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}]
                }
            ]
        }
        async with session.post(f"{HUBSPOT_BASE_URL}/quotes", json=quote_payload) as res:
            quote_text = await res.text()
            logger.info(f"Quote create response: {res.status} {quote_text}")
            quote_json = {}
            try:
                quote_json = await res.json()
            except Exception:
                pass
            quote_id = quote_json.get("id")

        # 2️⃣ log email engagement under  deal/contact/company
        email_payload = {
            "properties": {
                "hs_email_direction": "OUTGOING",
                "hs_email_subject": data["email_subject"],
                "hs_email_text": data["email_body"]
            },
            "associations": [
                {
                    "to": {"id": data["deal_id"]},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 65}]
                },
                {
                    "to": {"id": data["contact_id"]},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}]
                }
            ]
        }

        async with session.post("https://api.hubapi.com/crm/v3/objects/emails", json=email_payload) as res:
            email_text = await res.text()
            logger.info(f"Email log response: {res.status} {email_text}")

        return {"quote_id": quote_id}