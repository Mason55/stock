# src/utils/config_validator.py
"""Configuration validation on application startup"""
import logging
import re
from typing import List, Tuple

from config.settings import settings

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Configuration validation error"""

    pass


class ConfigValidator:
    """Validate application configuration on startup"""

    @staticmethod
    def validate_database_url(url: str) -> Tuple[bool, str]:
        """Validate DATABASE_URL format"""
        # Basic URL pattern check
        patterns = [
            r"^postgresql://[\w\-]+:[\w\-]+@[\w\.\-]+:\d+/[\w\-]+$",  # PostgreSQL
            r"^sqlite:///[\w/\.\-]+\.db$",  # SQLite file
            r"^sqlite:///:memory:$",  # SQLite memory
        ]

        for pattern in patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True, ""

        return False, f"Invalid DATABASE_URL format: {url[:20]}..."

    @staticmethod
    def validate_redis_url(url: str) -> Tuple[bool, str]:
        """Validate REDIS_URL format"""
        pattern = r"^redis://[\w\.\-]+(:\d+)?(/\d+)?$"
        if re.match(pattern, url, re.IGNORECASE):
            return True, ""
        return False, f"Invalid REDIS_URL format: {url}"

    @staticmethod
    def validate_port(port: int, name: str) -> Tuple[bool, str]:
        """Validate port number"""
        if 1 <= port <= 65535:
            return True, ""
        return False, f"Invalid {name}: must be between 1-65535, got {port}"

    @staticmethod
    def validate_timeout(timeout: float, name: str) -> Tuple[bool, str]:
        """Validate timeout value"""
        if timeout > 0:
            return True, ""
        return False, f"Invalid {name}: must be positive, got {timeout}"

    @staticmethod
    def validate_pool_size(size: int, name: str) -> Tuple[bool, str]:
        """Validate pool size"""
        if size > 0:
            return True, ""
        return False, f"Invalid {name}: must be positive, got {size}"

    @staticmethod
    def validate_all() -> List[str]:
        """Validate all critical configuration values"""
        errors = []

        # Database URL
        valid, msg = ConfigValidator.validate_database_url(settings.DATABASE_URL)
        if not valid:
            errors.append(msg)

        # Redis URL (if enabled)
        if settings.USE_REDIS:
            valid, msg = ConfigValidator.validate_redis_url(settings.REDIS_URL)
            if not valid:
                errors.append(msg)

        # API Port
        valid, msg = ConfigValidator.validate_port(settings.API_PORT, "API_PORT")
        if not valid:
            errors.append(msg)

        # Timeouts
        valid, msg = ConfigValidator.validate_timeout(settings.API_TIMEOUT, "API_TIMEOUT")
        if not valid:
            errors.append(msg)

        valid, msg = ConfigValidator.validate_timeout(
            settings.EXTERNAL_API_TIMEOUT, "EXTERNAL_API_TIMEOUT"
        )
        if not valid:
            errors.append(msg)

        # Database pool configuration
        valid, msg = ConfigValidator.validate_pool_size(settings.DB_POOL_SIZE, "DB_POOL_SIZE")
        if not valid:
            errors.append(msg)

        valid, msg = ConfigValidator.validate_pool_size(settings.DB_MAX_OVERFLOW, "DB_MAX_OVERFLOW")
        if not valid:
            errors.append(msg)

        # Cache TTL
        if settings.CACHE_TTL < 0:
            errors.append(f"Invalid CACHE_TTL: must be non-negative, got {settings.CACHE_TTL}")

        # Deployment mode
        valid_modes = ["development", "production", "test"]
        if settings.DEPLOYMENT_MODE.lower() not in valid_modes:
            errors.append(
                f"Invalid DEPLOYMENT_MODE: must be one of {valid_modes}, "
                f"got '{settings.DEPLOYMENT_MODE}'"
            )

        return errors

    @staticmethod
    def validate_and_raise():
        """Validate configuration and raise if any errors found"""
        errors = ConfigValidator.validate_all()

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ConfigValidationError(error_msg)

        logger.info("Configuration validation passed")

    @staticmethod
    def validate_and_warn():
        """Validate configuration and log warnings if any errors found"""
        errors = ConfigValidator.validate_all()

        if errors:
            logger.warning("Configuration validation warnings:")
            for error in errors:
                logger.warning(f"  - {error}")
        else:
            logger.info("Configuration validation passed")
