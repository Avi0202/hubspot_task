from typing import List
from pydantic import BaseModel, EmailStr

class VehicleShort(BaseModel):
    year: int
    make: str
    model: str

class EmailRequest(BaseModel):
    contact_name: str
    email: EmailStr
    vehicles: List[VehicleShort]
    pickup_city: str
    pickup_state: str
    delivery_city: str
    delivery_state: str
    final_quote_amount: float