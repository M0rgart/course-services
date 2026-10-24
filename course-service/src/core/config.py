import functools
from typing import final

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    title: str = "Course service title"
    description: str = "Course service description"
    summary: str = "Course service summary"
    version: str = "1.0.0"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"

    model_config = SettingsConfigDict(extra="allow")


class DatabaseSettings(BaseSettings):
    url: str = "sqlite+aiosqlite:///./course.db"
    echo: bool = False


class JWTSettings(BaseSettings):
    secret: str = "change-me-in-env"
    algorithm: str = "HS256"
    issuer: str = "course-service"
    audience: str = "course-service-clients"
    leeway: int = 5


class SecuritySettings(BaseSettings):
    body_limit_bytes: int = 1_048_576


@final
class Settings(BaseSettings):
    app: AppSettings = AppSettings()
    db: DatabaseSettings = DatabaseSettings()
    jwt: JWTSettings = JWTSettings()
    security: SecuritySettings = SecuritySettings()

    model_config = SettingsConfigDict(
        extra="allow",
        env_file=".env",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
    )


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()