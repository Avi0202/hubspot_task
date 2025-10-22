
import time
from fastapi import Request
from app.core.logger import get_logger

logger = get_logger("request_logger")

async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"Started request {request.method} {request.url.path}")
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"Completed request {request.method} {request.url.path} "
        f"with status={response.status_code} in {duration:.3f}s"
    )
    return response