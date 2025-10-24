from typing import List
from pydantic import BaseModel

class RouteHistory(BaseModel):
    origin: str
    destination: str
    distance_miles: float
    date: str
    status: str  # Won or Lost
    price: float
    company: str

class QuoteResponse(BaseModel):
    origin: str
    destination: str
    distance_miles: float
    super_dispatch_price: float
    internal_ai_price: float
    quote_amount: float
    markup_percentage: float
    route_history: List[RouteHistory]

    # ➕ add these three
    company_id: str | None = None
    contact_id: str | None = None
    deal_id: str | None = None