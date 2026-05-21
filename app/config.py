from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    SECRET_KEY: str = "change-this-please"
    ENV: str = "development"
    JWT_ISS: str = "skullmod"
    JWT_AUD: str = "skullmod-app"
    JWT_EXPIRE_DAYS: int = 30
    DATABASE_URL: str = "sqlite:///./skullmod.db"
    DEFAULT_TZ: str = "Europe/Istanbul"
    CORS_ORIGINS: str = "*"
    PUBLIC_NFC_BASE_URL: str = "https://skullmod.app"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if not value or value == "change-this-please":
            raise ValueError("SECRET_KEY must be set in the environment")
        if len(value) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return [origin for origin in origins if origin]

settings = Settings()
