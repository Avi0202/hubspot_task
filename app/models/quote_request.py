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
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    zip_code: str
    country: str
    state: str
    city: str
    vehicles: List[Vehicle]
    pickup: Location
    delivery: Location