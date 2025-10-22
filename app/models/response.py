from pydantic import BaseModel
from typing import List, Optional

class CompanyResponse(BaseModel):
    id: str
    name: Optional[str]
    domain: Optional[str]
    phone: Optional[str]
    address: Optional[str] = None

class CompanyListResponse(BaseModel):
    count: int
    companies: List[CompanyResponse]

class CompanyDetailsResponse(BaseModel):
    name: Optional[str]
    domain: Optional[str]
    phone: Optional[str]
    address: Optional[str] = None

class MessageResponse(BaseModel):
    message: str