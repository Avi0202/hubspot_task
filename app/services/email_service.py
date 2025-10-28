import json
import aiohttp
from app.core.logger import get_logger
from app.core.config import settings

EMAIL_GENERATION_URL = settings.EMAIL_GENERATION_URL
logger = get_logger(__name__)

SESSION_ID = "1761653686716"
AGENT_ID = "6900b36599417c626e85542d"

async def generate_email(quote_payload: dict) -> dict:
    request_payload = {
        "session_id": SESSION_ID,
        "message": quote_payload.json(),
        "agent_id": AGENT_ID
    }

    logger.info(f"Sending email generation request with payload: {request_payload}")

    async with aiohttp.ClientSession() as session:
        async with session.post(EMAIL_GENERATION_URL, json=request_payload) as response:
            response.raise_for_status()
            data = await response.json()
            logger.info(f"Received email generation response: {data}")

    # 🔧 FIX: clean the text before parsing (strip newlines & spaces)
    text_content = (data.get("text") or "{}").strip()

    try:
        parsed_content = json.loads(text_content)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse text content: {text_content}")
        parsed_content = {}
    
    output={
        "subject": parsed_content.get("subject", ""),
        "body": parsed_content.get("body", "")
    }
    # logger.info(f"Parsed email content: {output}")
    return output