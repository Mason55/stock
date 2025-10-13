# config/settings.py - System configuration management with portability options
import os
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:password@localhost:5432/stockdb"
    )

    # Redis configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    USE_REDIS: bool = os.getenv("USE_REDIS", "true").lower() == "true"

    # Kafka configuration
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    # API configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "5000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # CORS configuration for better portability
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

    # Offline/Mock mode for improved portability
    # Note: MOCK_DATA_ENABLED is deprecated, use OFFLINE_MODE instead
    OFFLINE_MODE: bool = os.getenv("OFFLINE_MODE", "false").lower() == "true"
    MOCK_DATA_ENABLED: bool = (
        os.getenv("MOCK_DATA_ENABLED", "false").lower() == "true"
    )  # deprecated

    # Logging configuration
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Data source configuration
    STOCK_DATA_API_KEY: Optional[str] = os.getenv("STOCK_DATA_API_KEY")
    STOCK_DATA_BASE_URL: str = os.getenv("STOCK_DATA_BASE_URL", "https://api.example.com")
    FUNDAMENTAL_DATA_API: Optional[str] = os.getenv("FUNDAMENTAL_DATA_API")
    FUNDAMENTAL_DATA_PATH: Optional[str] = os.getenv("FUNDAMENTAL_DATA_PATH")
    FUNDAMENTAL_DATA_TIMEOUT: float = float(os.getenv("FUNDAMENTAL_DATA_TIMEOUT", "3.0"))
    SENTIMENT_DATA_API: Optional[str] = os.getenv("SENTIMENT_DATA_API")
    SENTIMENT_DATA_PATH: Optional[str] = os.getenv("SENTIMENT_DATA_PATH")
    SENTIMENT_DATA_TIMEOUT: float = float(os.getenv("SENTIMENT_DATA_TIMEOUT", "3.0"))

    # External service timeouts
    EXTERNAL_API_TIMEOUT: float = float(os.getenv("EXTERNAL_API_TIMEOUT", "5.0"))
    EXTERNAL_API_RETRIES: int = int(os.getenv("EXTERNAL_API_RETRIES", "3"))

    # Database pool configuration
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    # Model configuration
    MODEL_UPDATE_INTERVAL: int = int(os.getenv("MODEL_UPDATE_INTERVAL", "3600"))  # seconds

    # Cache configuration - unified TTL management
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # default
    CACHE_TTL_REALTIME: int = int(os.getenv("CACHE_TTL_REALTIME", "30"))  # realtime quotes
    CACHE_TTL_HISTORICAL: int = int(os.getenv("CACHE_TTL_HISTORICAL", "3600"))  # historical data
    CACHE_TTL_ANALYSIS: int = int(os.getenv("CACHE_TTL_ANALYSIS", "600"))  # analysis results

    # Performance thresholds
    API_TIMEOUT: float = float(os.getenv("API_TIMEOUT", "1.5"))
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "1000"))

    # Deployment mode
    DEPLOYMENT_MODE: str = os.getenv(
        "DEPLOYMENT_MODE", "development"
    )  # development, production, test

    def get_cors_origins(self) -> List[str]:
        """Get CORS origins as a list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.DEPLOYMENT_MODE.lower() == "production"

    def is_offline_mode(self) -> bool:
        """Check if offline mode is enabled

        Note: MOCK_DATA_ENABLED is deprecated but supported for backward compatibility
        """
        if self.MOCK_DATA_ENABLED and not self.OFFLINE_MODE:
            import warnings

            warnings.warn(
                "MOCK_DATA_ENABLED is deprecated, use OFFLINE_MODE instead",
                DeprecationWarning,
                stacklevel=2,
            )
        return self.OFFLINE_MODE or self.MOCK_DATA_ENABLED

    class Config:
        env_file = ".env"


settings = Settings()
