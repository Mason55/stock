# src/utils/di_container.py
"""Dependency injection container for managing service dependencies"""
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ServiceContainer:
    """Simple dependency injection container"""

    session_factory: Optional[Any] = None
    cache_manager: Optional[Any] = None
    rate_limiter: Optional[Any] = None
    data_fetcher: Optional[Any] = None
    _extras: Dict[str, Any] = None

    def __post_init__(self):
        if self._extras is None:
            self._extras = {}

    def register(self, name: str, instance: Any) -> None:
        """Register a service instance"""
        self._extras[name] = instance
        logger.debug(f"Registered service: {name}")

    def get(self, name: str, default: Any = None) -> Any:
        """Get a service instance"""
        return self._extras.get(name, default)

    def has(self, name: str) -> bool:
        """Check if a service is registered"""
        return name in self._extras


# Global container instance (initialized at app startup)
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get the global service container"""
    global _container
    if _container is None:
        raise RuntimeError("Service container not initialized. Call init_container() first.")
    return _container


def init_container(**kwargs) -> ServiceContainer:
    """Initialize the global service container"""
    global _container
    _container = ServiceContainer(**kwargs)
    logger.info("Service container initialized")
    return _container


def reset_container() -> None:
    """Reset the container (for testing)"""
    global _container
    _container = None
