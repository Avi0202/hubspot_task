from pydantic import BaseModel, EmailStr

class QuoteEmailRequest(BaseModel):
    company_id: str
    contact_id: str
    deal_id: str
    email_subject: str
    email_body: str
    quote_amount: float