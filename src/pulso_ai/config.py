from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    port: int = 50051
    log_level: str = "INFO"
