from pydantic import BaseModel


class GenerateEmailResponse(BaseModel):
    email_subject: str
    email_body: str