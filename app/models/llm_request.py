from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional


class Location(BaseModel):
    location_name: str
    city: str
    state: str
    zip: str


class PricingRecommendations(BaseModel):
    super_dispatch: float = Field(..., description="AI pricing from Super Dispatch")
    internal_system: float = Field(..., description="AI pricing from internal system")


class RouteHistoryItem(BaseModel):
    route: str
    distance_miles: float
    date: str
    client: str
    status: str  # "Won" or "Lost"
    price: float


class Quote(BaseModel):
    base_price: float
    markup_percent: float
    customer_quote: float


class SenderInfo(BaseModel):
    name: str
    company: str
    email: EmailStr


class GenerateEmailRequest(BaseModel):
    pickup: Location
    delivery: Location
    distance_miles: float
    ai_pricing_recommendations: PricingRecommendations
    similar_route_history: List[RouteHistoryItem]
    quote: Quote
    sender_info: SenderInfo
    email_purpose: str = Field(..., description="Purpose of email, e.g., 'customer_quote'")
    tone: Optional[str] = Field("professional_friendly", description="Tone of the email")