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
    DATABASE_URL: str = ""

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

    # Cost-Optimized AI Provider
    PRIMARY_AI_PROVIDER: str = "deepseek"  # or "claude" for upgrade
    DEEPSEEK_API_KEY: str = ""

    # File Storage (Cloudinary)
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_UPLOAD_PRESET: str = ""

    # RAG Settings (OpenAI Embeddings)
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536  # OpenAI small model

    # OCR Cleaning Settings
    ENABLE_OCR_CLEANING: bool = True
    OCR_CLEANING_AGGRESSIVE: bool = True  # More thorough corrections

    # Hybrid OCR Settings (Tesseract + Google Vision fallback)
    GOOGLE_VISION_ENABLED: bool = True  # Enable Google Vision fallback
    GOOGLE_VISION_THRESHOLD: float = (
        0.65  # Fallback when Tesseract confidence below this
    )
    PREMIUM_ALWAYS_USE_GOOGLE_VISION: bool = False  # For paying users
    ALLOW_USER_REQUESTED_REPROCESS: bool = (
        True  # Let user click "Improve transcription"
    )

    # Feature Flags
    ENABLE_FACT_CHECK: bool = True
    ENABLE_PRE_CLASS_RESEARCH: bool = True
    ENABLE_VOICE_GRADING: bool = True

    # CORS — comma-separated in .env, e.g. https://example.com,https://other.com
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS as a comma-separated string."""
        raw = self.CORS_ORIGINS.strip()
        if raw.startswith("["):
            import json
            return json.loads(raw)
        return [o.strip() for o in raw.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        Return the database URL formatted for asyncpg.
        Handles postgresql:// and postgres:// -> postgresql+asyncpg://
        Removes sslmode/channel_binding parameters which are handled by connect_args.
        """
        import re

        url = self.DATABASE_URL
        # Convert schema
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)

        # Remove sslmode/channel_binding query params
        if "sslmode=" in url:
            url = re.sub(r"[\?&]sslmode=[^&]*", "", url)
        if "channel_binding=" in url:
            url = re.sub(r"[\?&]channel_binding=[^&]*", "", url)

        # Cleanup trailing characters
        url = re.sub(r"[\?&]$", "", url)
        url = url.replace("?&", "?")

        return url

    # Set to "true" when connecting to a remote DB that requires SSL (e.g. Neon)
    DATABASE_SSL: bool = False

    @property
    def DB_CONNECT_ARGS(self) -> dict:
        """Return connection arguments. Enables SSL only when DATABASE_SSL=true."""
        if self.DATABASE_SSL:
            import ssl

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            return {"ssl": ssl_context}
        return {}


settings = Settings()
