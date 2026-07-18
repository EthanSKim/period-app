import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Generated VAPID key pair — safe defaults for local development.
# NEVER commit real production keys to source control.
# Override via .env file or environment variables.
_DEFAULT_VAPID_PUBLIC_KEY = (
    "BFVx3FQcJyCUKpPyQxDaWLzhWArjsvfGyE1dNu-9srhlA8LTCL02Gpmc8Nal"
    "tAONAkQCZTVUJ0vDiAMfJFCnpUI"
)
_DEFAULT_VAPID_PRIVATE_KEY = (
    "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgxS178kx00JlU"
    "_-FVqVFqZT2iEaogSudiPLuxnuHvRemhRANCAARVcdxUHCcglCqT8kMQ2li8"
    "4VgK47L3xshNXTbvvbK4ZQPC0wi9NhqZnPDWpbQDjQJEAmU1VCdLw4gDHyR"
    "Qp6VC"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@db:5432/period_db"
    )
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "super-secret-key-change-in-production-1234567890"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7

    # Web Push / VAPID configuration
    # Generate your own keys with: python scripts/generate_vapid_keys.py
    VAPID_PUBLIC_KEY: str = _DEFAULT_VAPID_PUBLIC_KEY
    VAPID_PRIVATE_KEY: str = _DEFAULT_VAPID_PRIVATE_KEY
    VAPID_CLAIM_EMAIL: str = "mailto:admin@period-app.example.com"


settings = Settings()
