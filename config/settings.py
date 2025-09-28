# config/settings.py - System configuration management
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/stockdb")
    
    # Redis configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Kafka configuration
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    # API configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "5000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Data source configuration
    STOCK_DATA_API_KEY: Optional[str] = os.getenv("STOCK_DATA_API_KEY")
    STOCK_DATA_BASE_URL: str = os.getenv("STOCK_DATA_BASE_URL", "https://api.example.com")
    
    # Model configuration
    MODEL_UPDATE_INTERVAL: int = int(os.getenv("MODEL_UPDATE_INTERVAL", "3600"))  # seconds
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # seconds
    
    # Performance thresholds
    API_TIMEOUT: float = float(os.getenv("API_TIMEOUT", "1.5"))
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "1000"))
    
    class Config:
        env_file = ".env"


settings = Settings()