"""
NotesOS Configuration - Environment Variables and Settings
"""

from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "NotesOS"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://notesos:notesos_dev_password@localhost:5432/notesos"
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT Authentication
    JWT_SECRET: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI Services
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    VOYAGE_AI_API_KEY: str = ""
    SERPER_API_KEY: str = ""

    # File Storage (Cloudinary)
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_UPLOAD_PRESET: str = "notesos_uploads"

    # Feature Flags
    ENABLE_FACT_CHECK: bool = True
    ENABLE_PRE_CLASS_RESEARCH: bool = True
    ENABLE_VOICE_GRADING: bool = True

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
