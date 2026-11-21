import functools
from typing import Any, cast, final

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseModel):
    title: str = "Course service title"
    description: str = "Course service description"
    summary: str = "Course service summary"
    version: str = "1.0.0"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"


class DatabaseSettings(BaseModel):
    url: str = "sqlite+aiosqlite:///./course.db"
    echo: bool = False


class JWTSettings(BaseModel):
    secret: str = Field(min_length=32)
    algorithm: str = "HS256"
    issuer: str = "course-service"
    audience: str = "course-service-clients"
    leeway: int = 5


class SecuritySettings(BaseModel):
    body_limit_bytes: int = 1_048_576


class ExternalServiceSettings(BaseModel):
    url: str | None = None
    timeout_seconds: float = Field(default=2.0, gt=0)
    max_concurrency: int = Field(default=5, ge=1)
    simulation_delay_seconds: float = Field(default=0.1, ge=0)


@final
class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jwt: JWTSettings
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    external: ExternalServiceSettings = Field(default_factory=ExternalServiceSettings)

    model_config = SettingsConfigDict(
        extra="allow",
        env_file=".env",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
    )


@functools.lru_cache
def get_settings() -> Settings:
    settings_type = cast(Any, Settings)
    return cast(Settings, settings_type())
