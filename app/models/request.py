from pydantic import BaseModel
from typing import Optional

class CompanySearchRequest(BaseModel):
    company_name: str

class CreateCompanyRequest(BaseModel):
    name: str
    domain: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None