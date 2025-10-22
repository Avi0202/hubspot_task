from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "My FastAPI Application"
    HUBSPOT_BASE_URL: str = "https://api.hubapi.com"
    HUBSPOT_TOKEN: str
    VIN_API_URL: str = "https://admin-apis.isometrik.io/v1/agent/chat/strands/"
    VIN_API: str
    ZIPPO_BASE_URL: str = "https://api.zippopotam.us/us"

    class Config:
        env_file = ".env"

settings = Settings()
    