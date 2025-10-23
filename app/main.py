from fastapi import FastAPI
from app.routes.hubspot_router import hub_router
from app.routes.vin_router import vin_router
from app.routes.location_router import location_router
from app.routes.quote_router import quote_router
from contextlib import asynccontextmanager
from app.core.logger import get_logger
from app.core.middleware import log_requests

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info(" Application startup complete")

    yield  


    logger.info(" Application shutdown initiated")

app = FastAPI(lifespan=lifespan)
app.middleware("http")(log_requests)
app.include_router(hub_router)
app.include_router(vin_router)
app.include_router(location_router)
app.include_router(quote_router)