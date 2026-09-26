import functools
from typing import final

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    title: str = "Course service title"
    description: str = "Course service description"
    summary: str = "Course service summary"
    version: str = "0.1.0"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"

    model_config = SettingsConfigDict(extra="allow")


@final
class Settings(BaseSettings):
    app: AppSettings = AppSettings()

    model_config = SettingsConfigDict(
        extra="allow",
        env_file=".env",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
    )


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()