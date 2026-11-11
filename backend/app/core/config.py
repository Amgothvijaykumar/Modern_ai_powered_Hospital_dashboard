from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Hospital Operations AI Agent"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "Asia/Kolkata"

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/hospital_ai"
    TEST_DATABASE_URL: str = ""

    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    ALLOW_DEMO_AUTH: bool = True
    DEMO_JWT_SECRET: str = "local-dev-demo-jwt-secret-change-in-production-32chars"
    DEMO_USER_PASSWORD: str = "HospitalDemo!2026"

    CONFIRMATION_TOKEN_SECRET: str = "local-dev-confirmation-secret-change-in-prod-32chars"
    CONFIRMATION_TTL_SECONDS: int = 600

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    PROMPT_VERSION: str = "v1.0.0"

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
