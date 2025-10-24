from typing import List
from pydantic import BaseModel

class Vehicle(BaseModel):
    vin: str
    year: int
    make: str
    model: str
    type: str
    
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
    
    vehicles: List[Vehicle]

    # ➕ add these three
    company_id: str | None = None
    contact_id: str | None = None
    deal_id: str | None = None