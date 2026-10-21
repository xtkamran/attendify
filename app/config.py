"""Application configuration."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    default_shift_end: str = "18:30"
    default_shift_start: str = "09:30"
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "attendance"
    jwt_secret_key: str = ""

    # Assignment rules
    timezone: str = "Asia/Kolkata"
    late_grace_minutes: int = 30
    max_session_minutes: int = 960
    min_session_minutes: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
