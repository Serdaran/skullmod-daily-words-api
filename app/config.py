from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = "change-this-please"
    JWT_ISS: str = "skullmod"
    JWT_AUD: str = "skullmod-app"
    JWT_EXPIRE_DAYS: int = 30
    DATABASE_URL: str = "sqlite:///./skullmod.db"
    DEFAULT_TZ: str = "Europe/Istanbul"

    class Config:
        env_file = ".env"

settings = Settings()

