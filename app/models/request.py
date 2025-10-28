from pydantic import BaseModel,Field
from typing import Optional

class CompanySearchRequest(BaseModel):
    
    company_name: str
class GetCompaniesRequest(BaseModel):
    start_chars: str
class CreateCompanyRequest(BaseModel):
    name: str
    domain: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class LocationRequest(BaseModel):
    zipcode: str
    
class DecodeVinRequest(BaseModel):
    vin: str = Field(..., description="17-character Vehicle Identification Number to decode")