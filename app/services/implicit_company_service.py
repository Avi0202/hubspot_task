import aiohttp
import json
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

HUBSPOT_BASE_URL = settings.HUBSPOT_BASE_URL
HUBSPOT_ACCESS_TOKEN = settings.HUBSPOT_TOKEN
ENRICHMENT_URL = settings.COMPANY_DETAIL_EXTRACTOR_URL

async def enrich_company_data(company_id: str, company_name: str):
    """Fetch enrichment info and update HubSpot company."""
    try:
        async with aiohttp.ClientSession() as session:
            # Fetch the enrichment data
            payload = {
                "session_id": "1761633122763",  # static or from config
                "message": company_name,        # required as per your spec
                "agent_id": "68ff216f264610a11c1164a1"
            }

            # Send POST request
            async with session.post(ENRICHMENT_URL, json=payload) as res:
                data = await res.json()
                logger.info(f"Enrichment response for {company_name}: {data}")

            parsed = json.loads(data.get("text", "{}"))
            domain = parsed.get("domain")
            owner_name = parsed.get("Owner_name")

            if not domain and not owner_name:
                logger.warning(f"No enrichment data for company {company_name}")
                return

            payload = {
                "properties": {
                    "domain": domain,
                    "hubspot_owner_id": owner_name
                }
            }

            async with session.patch(
                f"{HUBSPOT_BASE_URL}/crm/v3/objects/0-2/{company_id}",
                headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"},
                json=payload
            ) as hubspot_res:
                text = await hubspot_res.text()
                logger.info(f"HubSpot update: {hubspot_res.status} {text}")

    except Exception as e:
        logger.exception(f"Error updating company {company_name} ({company_id}): {e}")

