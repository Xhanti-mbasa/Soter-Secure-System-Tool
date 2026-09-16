from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    admin_api_key: str = Field(min_length=32)
    database_url: str = "sqlite:///./secure.db"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    artifact_root: Path = Path("data/scans")
    zap_api_url: str = "http://zap:8080"
    zap_api_key: str = Field(min_length=32)
    dev_allow_private_targets: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
