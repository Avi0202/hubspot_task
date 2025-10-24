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
async def get_or_create_company(company_name: str, phone: str, address: str):
    """
    Find an existing company by name in HubSpot, or create it if it doesn't exist.
    """
    logger.info(f"Checking if company '{company_name}' exists in HubSpot")

    existing_company = await hubspot_find_company_by_name(company_name)  # Implement this separately
    if existing_company:
        logger.info(f"Found existing company: {existing_company['id']}")
        return existing_company

    logger.info(f"Company '{company_name}' not found. Creating new company in HubSpot.")

    new_company_payload = {
        "properties": {
            "name": company_name,
            "phone": phone,
            "address": address
        }
    }

    new_company = await hubspot_create_company(new_company_payload)  # Implement this separately
    logger.info(f"Created company '{company_name}' with ID: {new_company['id']}")
    return new_company

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
            logger.info(f"Associated Deal {deal_id}  with  Company {company_id}")

        if deal_id and contact_id:
            await session.put(
                f"https://api.hubapi.com/crm/v4/associations/deals/contacts/{deal_id}/{contact_id}"
            )
            logger.info(f"Associated Deal {deal_id}  with  Contact {contact_id}")

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

from datetime import datetime, timezone
import aiohttp

async def send_quote_email(data: dict):
    """
    Updates the deal with distance & quote amount,
    creates an EMAIL engagement, then associates it to the deal/contact/company.
    """
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # 1. Update deal custom properties
        deal_payload = {
            "properties": {
                "distance_miles": data["distance_miles"],
                "quote_amount": data["quote_amount"]
            }
        }

        async with session.patch(
            f"{HUBSPOT_BASE_URL}/deals/{data['deal_id']}",
            json=deal_payload,
        ) as res:
            deal_text = await res.text()
            logger.info(f"Deal update response: {res.status} {deal_text}")

        # 2. Create EMAIL engagement (no associations here)
        hs_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

        email_props = {
            "hs_email_direction": "EMAIL",
            "hs_email_subject": data["email_subject"],
            "hs_email_text": data["email_body"],
            "hs_timestamp": hs_timestamp
        }

        async with session.post(
            "https://api.hubapi.com/crm/v3/objects/emails",
            json={"properties": email_props},
        ) as res:
            email_create_text = await res.text()
            logger.info(f"Email create response: {res.status} {email_create_text}")

            email_json = {}
            try:
                email_json = await res.json()
            except Exception:
                pass

            email_id = email_json.get("id")

        # 3. Associate email with deal, contact, and company using v4 associations
        async def assoc(from_type: str, to_type: str, from_id: str, to_id: str, assoc_type: str):
            url = (
                f"https://api.hubapi.com/crm/v4/associations/"
                f"{from_type}/{to_type}/batch/create"
            )
            payload = {
                "inputs": [
                    {"from": {"id": from_id}, "to": {"id": to_id}, "type": assoc_type}
                ]
            }
            async with session.post(url, json=payload) as r:
                logger.info(
                    f"Assoc {from_type}->{to_type} ({assoc_type}) response: "
                    f"{r.status} {await r.text()}"
                )

        if email_id:
            await assoc("emails", "deals", email_id, data["deal_id"], "email_to_deal")
            await assoc("emails", "contacts", email_id, data["contact_id"], "email_to_contact")
            if data.get("company_id"):
                await assoc("emails", "companies", email_id, data["company_id"], "email_to_company")

        return {"deal_id": data["deal_id"], "email_id": email_id}
    

async def hubspot_find_company_by_name(company_name: str):
    """
    Search HubSpot for a company by name.
    Returns the first matching record or None if not found.
    """
    url = "https://api.hubapi.com/crm/v3/objects/companies/search"
    headers = {"Authorization": f"Bearer {HUBSPOT_TOKEN}"}
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "name",
                "operator": "EQ",
                "value": company_name
            }]
        }]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            results = data.get("results", [])
            return results[0] if results else None


async def hubspot_create_company(company_payload: dict):
    """
    Creates a new HubSpot company.
    """
    url = "https://api.hubapi.com/crm/v3/objects/companies"
    headers = {"Authorization": f"Bearer {HUBSPOT_TOKEN}"}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=company_payload) as resp:
            return await resp.json()