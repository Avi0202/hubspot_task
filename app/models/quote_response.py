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
    distance_miles: float
    super_dispatch_price: float
    internal_ai_price: float
    final_quote_amount: float
    markup_percentage: float
    route_history: List[RouteHistory]