# src/utils/exceptions.py - Custom exception classes
from typing import Optional, Dict, Any


class StockAnalysisException(Exception):
    """Base exception for stock analysis system"""
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}


class ValidationError(StockAnalysisException):
    """Input validation error"""
    pass


class DataSourceError(StockAnalysisException):
    """External data source error"""
    pass


class DatabaseError(StockAnalysisException):
    """Database operation error"""
    pass


class CacheError(StockAnalysisException):
    """Cache operation error"""
    pass


class RateLimitError(StockAnalysisException):
    """Rate limit exceeded error"""
    pass


class AuthenticationError(StockAnalysisException):
    """Authentication error"""
    pass


class AuthorizationError(StockAnalysisException):
    """Authorization error"""
    pass


class ConfigurationError(StockAnalysisException):
    """Configuration error"""
    pass


class AnalysisError(StockAnalysisException):
    """Stock analysis computation error"""
    pass