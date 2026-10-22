from functools import lru_cache
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ReconcileAI"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_str: str = "/api/v1"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/reconcile_ai"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0, le=1440)
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173,"
        "http://localhost:8443,http://127.0.0.1:8443"
    )
    gemini_api_key: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def auth_cookie_secure(self) -> bool:
        return self.app_env.casefold() in {"production", "prod"}

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if self.app_env.casefold() in {"production", "prod"}:
            if self.secret_key == "change-me-in-production" or len(self.secret_key.encode()) < 32:
                raise ValueError("Production SECRET_KEY must contain at least 32 bytes.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
