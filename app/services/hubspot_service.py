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
HUBSPOT_BASE_URL = settings.HUBSPOT_BASE_URL
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
async def get_or_create_company(company_name: str, phone: str, address: dict):
    logger.info(f"Checking if company '{company_name}' exists in HubSpot")

    existing_company = await hubspot_find_company_by_name(company_name)
    if existing_company:
        logger.info(f"Found existing company: {existing_company['id']}")
        return existing_company

    logger.info(f"Company '{company_name}' not found. Creating new company in HubSpot.")

    new_company_payload = {
        "properties": {
            "name": company_name,
            "phone": phone,
            "address": address.get("address_line1", ""),
            "address2": address.get("address_line2", ""),
            "city": address.get("city", ""),
            "state": address.get("state", ""),
            "zip": address.get("zip_code", ""),
            "country": address.get("country", "")
        }
    }

    logger.info(f"New company payload sent to HubSpot: {new_company_payload}")
    new_company = await hubspot_create_company(new_company_payload)
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
    company_name = (company_name or "").strip()
    if not company_name or len(company_name) < 3:
        logger.warning(f"Skipping HubSpot search for invalid company name: '{company_name}'")
        return []
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

from fastapi import HTTPException
from app.core.logger import get_logger

logger = get_logger("hubspot_service")

# HUBSPOT_BASE_URL = "https://api.hubapi.com/crm/v3/objects"
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}


async def create_transport_deal(data: dict):
    """
    Creates or reuses HubSpot contact, company, and deal entities,
    associates them together (bi-directional), and returns their IDs.
    """
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        company_id = data.get("company_id")

        # --------------------------------------------------------------
        # 1️⃣ Create or reuse Contact
        # --------------------------------------------------------------
        contact_payload = {
            "properties": {
                "firstname": data.get("contact_name"),
                "email": data.get("email"),
                "phone": data.get("phone", "")
            }
        }
        contact_id = None

        async with session.post(f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts", json=contact_payload) as res:
            text = await res.text()
            logger.info(f"Contact response: {res.status} {text}")
            try:
                body = await res.json()
            except Exception:
                body = {}

            if res.status in (200, 201):
                contact_id = body.get("id")
            elif res.status == 409:
                msg = body.get("message", "")
                if "Existing ID:" in msg:
                    contact_id = msg.split("Existing ID:")[-1].strip()
                logger.info(f"Contact already exists: {contact_id}")
            else:
                raise HTTPException(status_code=res.status, detail=text)

        # --------------------------------------------------------------
        # 2️⃣ Create Deal
        # --------------------------------------------------------------
        pickup = data.get("pickup", {}) or {}
        delivery = data.get("delivery", {}) or {}
        vehicles = data.get("vehicles", []) or []

        # 🔧 Compose deal name dynamically
        if vehicles:
            vehicle_names = [f"{v.get('year', '')} {v.get('make', '')} {v.get('model', '')}".strip() for v in vehicles]
            if len(vehicle_names) == 1:
                vehicle_str = vehicle_names[0]
            else:
                vehicle_str = ", ".join(vehicle_names[:-1]) + f" and {vehicle_names[-1]}"
            deal_name = f"{data.get('contact_name')} Quote for {vehicle_str}"
        else:
            deal_name = f"{data.get('contact_name')} Quote"

        deal_payload = {
            "properties": {
                "dealname": deal_name,
                "pickup_city": pickup.get("city", ""),
                "delivery_city": delivery.get("city", ""),
                "vehicles_json": str(vehicles)
            }
        }

        deal_id = None
        async with session.post(f"{HUBSPOT_BASE_URL}/crm/v3/objects/deals", json=deal_payload) as res:
            text = await res.text()
            logger.info(f"Deal response: {res.status} {text}")
            try:
                body = await res.json()
            except Exception:
                body = {}

            if res.status in (200, 201):
                deal_id = body.get("id")
            elif res.status == 409:
                msg = body.get("message", "")
                if "Existing ID:" in msg:
                    deal_id = msg.split("Existing ID:")[-1].strip()
                logger.info(f"Deal already exists: {deal_id}")
            else:
                raise HTTPException(status_code=res.status, detail=text)

        # --------------------------------------------------------------
        # 3️⃣ Create ASSOCIATIONS (bi‑directional)
        # --------------------------------------------------------------
        async def associate(from_type, to_type, from_id, to_id, assoc_type):
            url = f"https://api.hubapi.com/crm/v3/associations/{from_type}/{to_type}/batch/create"
            payload = {"inputs": [{"from": {"id": from_id}, "to": {"id": to_id}, "type": assoc_type}]}
            async with session.post(url, json=payload) as res:
                logger.info(f"Assoc {from_type}->{to_type} ({assoc_type}): {res.status} {await res.text()}")

        # Deal ↔ Company
        if deal_id and company_id:
            await associate("deals", "companies", deal_id, company_id, "deal_to_company")
            await associate("companies", "deals", company_id, deal_id, "company_to_deal")

        # Deal ↔ Contact
        if deal_id and contact_id:
            await associate("deals", "contacts", deal_id, contact_id, "deal_to_contact")
            await associate("contacts", "deals", contact_id, deal_id, "contact_to_deal")

        # Company ↔ Contact
        if company_id and contact_id:
            await associate("companies", "contacts", company_id, contact_id, "company_to_contact")
            await associate("contacts", "companies", contact_id, company_id, "contact_to_company")

        # --------------------------------------------------------------
        # 4️⃣ Return IDs
        # --------------------------------------------------------------
        logger.info(f"HubSpot IDs → Company: {company_id}, Contact: {contact_id}, Deal: {deal_id}")
        return {"company_id": company_id, "contact_id": contact_id, "deal_id": deal_id}

from datetime import datetime, timezone
import aiohttp

async def send_quote_email(data: dict):
    """
    Updates the deal with distance & quote amount,
    creates an EMAIL engagement, and associates it
    bidirectionally with the deal.
    """
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # ---------------------------------------------------------
        # 1️⃣ Update deal custom properties
        # ---------------------------------------------------------
        deal_payload = {
            "properties": {
                "distance_miles": data["distance_miles"],
                "quote_amount": data["quote_amount"]
            }
        }
        logger.info(f"Updating deal {type(data['deal_id'])} with distance and quote amount {deal_payload}")
        async with session.patch(
            f"{HUBSPOT_BASE_URL}/crm/v3/objects/0-3/{data['deal_id']}",
            json=deal_payload,
        ) as res:
            deal_text = await res.text()
            logger.info(f"Deal update response: {res.status} {res}")

        # ---------------------------------------------------------
        # 2️⃣ Create EMAIL engagement
        # ---------------------------------------------------------
        hs_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        email_props = {
            "hs_email_direction": "EMAIL",
            "hs_email_subject": data["email_subject"],
            "hs_email_text": data["email_body"],
            "hs_timestamp": hs_timestamp,
        }

        async with session.post(
            f"{HUBSPOT_BASE_URL}/crm/v3/objects/emails",
            json={"properties": email_props},
        ) as res:
            create_text = await res.text()
            logger.info(f"Email create response: {res.status} {res}")
            try:
                email_json = await res.json()
            except Exception:
                email_json = {}
            email_id = email_json.get("id")

        # ---------------------------------------------------------
        # 3️⃣ Bidirectional association: Email ↔ Deal
        # ---------------------------------------------------------
        async def associate(from_type, to_type, from_id, to_id, assoc_type):
            url = f"https://api.hubapi.com/crm/v3/associations/{from_type}/{to_type}/batch/create"
            payload = {"inputs": [{"from": {"id": from_id}, "to": {"id": to_id}, "type": assoc_type}]}
            async with session.post(url, json=payload) as r:
                text = await r.text()
                logger.info(f"Assoc {from_type}->{to_type} ({assoc_type}): {r.status} {text}")

        if email_id:
            # Email → Deal
            await associate("emails", "deals", email_id, data["deal_id"], "email_to_deal")
            # Deal → Email
            await associate("deals", "emails", data["deal_id"], email_id, "deal_to_email")
        else:
            logger.warning("No email_id returned; skipping associations.")

        # ---------------------------------------------------------
        # 4️⃣ Return IDs
        # ---------------------------------------------------------
        logger.info(f"HubSpot email↔deal association complete: Email {email_id}, Deal {data['deal_id']}")
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