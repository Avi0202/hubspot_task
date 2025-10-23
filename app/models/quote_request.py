from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

class Vehicle(BaseModel):
    vin: str
    year: int
    make: str
    model: str
    type: str

class Location(BaseModel):
    name: str
    street: Optional[str] = None
    city: str
    state: str
    zip: str = Field(..., min_length=5, max_length=10)

class QuoteRequest(BaseModel):
    company_name: str
    contact_name: str
    email: EmailStr
    phone: str
    billing_address: Optional[str] = None
    vehicles: List[Vehicle]
    pickup: Location
    delivery: Location