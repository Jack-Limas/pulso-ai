from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    port: int = 50051
    log_level: str = "INFO"
    internal_api_key: str = Field(min_length=32)
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
