from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    # Database settings
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "taaft")

    # JWT settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")
    )

    # Chat settings
    DEFAULT_CHAT_MODEL: str = os.getenv("DEFAULT_CHAT_MODEL", "gpt4")
    MAX_MESSAGES_PER_SESSION: int = int(os.getenv("MAX_MESSAGES_PER_SESSION", "100"))

    # SMTP settings for email
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("hxndgvqecwvpvigo", "hxndgvqecwvpvigo")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@example.com")
    EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "False").lower() == "true"

    # Redis cache settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", None)
    REDIS_CACHE_ENABLED: bool = (
        os.getenv("REDIS_CACHE_ENABLED", "true").lower() == "true"
    )
    REDIS_CACHE_TTL: int = int(os.getenv("REDIS_CACHE_TTL", "300"))  # 5 minutes default

    # API settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "TAAFT Backend"

    class Config:
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
