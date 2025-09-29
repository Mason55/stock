# src/utils/error_handler.py - Centralized error handling
import logging
import traceback
from typing import Tuple, Dict, Any
from flask import request, jsonify, g
from werkzeug.exceptions import HTTPException
from src.utils.exceptions import (
    StockAnalysisException, ValidationError, DataSourceError,
    DatabaseError, CacheError, RateLimitError, AuthenticationError,
    AuthorizationError, ConfigurationError, AnalysisError
)

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling for the application"""
    
    @staticmethod
    def handle_exception(error: Exception) -> Tuple[Dict[str, Any], int]:
        """Handle different types of exceptions and return appropriate response"""
        
        # Generate request ID for tracking
        request_id = getattr(g, 'request_id', None) or getattr(request, 'id', 'unknown')
        
        # Log the error with context
        error_context = {
            'request_id': request_id,
            'path': request.path if request else 'unknown',
            'method': request.method if request else 'unknown',
            'remote_addr': request.remote_addr if request else 'unknown',
            'error_type': type(error).__name__,
            'error_message': str(error)
        }
        
        if isinstance(error, HTTPException):
            return ErrorHandler._handle_http_exception(error, error_context)
        elif isinstance(error, ValidationError):
            return ErrorHandler._handle_validation_error(error, error_context)
        elif isinstance(error, DataSourceError):
            return ErrorHandler._handle_data_source_error(error, error_context)
        elif isinstance(error, DatabaseError):
            return ErrorHandler._handle_database_error(error, error_context)
        elif isinstance(error, RateLimitError):
            return ErrorHandler._handle_rate_limit_error(error, error_context)
        elif isinstance(error, AuthenticationError):
            return ErrorHandler._handle_auth_error(error, error_context)
        elif isinstance(error, AuthorizationError):
            return ErrorHandler._handle_authorization_error(error, error_context)
        elif isinstance(error, AnalysisError):
            return ErrorHandler._handle_analysis_error(error, error_context)
        elif isinstance(error, StockAnalysisException):
            return ErrorHandler._handle_custom_error(error, error_context)
        else:
            return ErrorHandler._handle_generic_error(error, error_context)
    
    @staticmethod
    def _handle_http_exception(error: HTTPException, context: Dict) -> Tuple[Dict[str, Any], int]:
        """Handle HTTP exceptions"""
        logger.warning(f"HTTP error {error.code}: {error.description}", extra=context)
        
        return {
            'error': 'http_error',
            'message': error.description,
            'code': error.code,
            'request_id': context['request_id']
        }, error.code
    
    @staticmethod
    def _handle_validation_error(error: ValidationError, context: Dict) -> Tuple[Dict[str, Any], int]:
        """Handle validation errors"""
        logger.warning(f"Validation error: {error.message}", extra=context)
        
        return {
            'error': 'validation_error',
            'message': error.message,
            'code': 400,
            'details': error.details,
            'request_id': context['request_id']
        }, 400
    
    @staticmethod
    def _handle_data_source_error(error: DataSourceError, context: Dict) -> Tuple[Dict[str, Any], int]:
        """Handle data source errors"""
        logger.error(f"Data source error: {error.message}", extra=context)
        
        return {
            'error': 'data_source_error',
            'message': 'External data source temporarily unavailable',
            'code': 503,
            'request_id': context['request_id']
        }, 503
    
    @staticmethod
    def _handle_database_error(error: DatabaseError, context: Dict) -> Tuple[Dict[str, Any], int]:
        """Handle database errors"""
        logger.error(f"Database error: {error.message}", extra=context)
        
        return {
            'error': 'database_error',
            'message': 'Database operation failed',
            'code': 500,
            'request_id': context['request_id']
        }, 500
    
    @staticmethod
    def _handle_rate_limit_error(error: RateLimitError, context: Dict) -> Tuple[Dict[str, Any], int]:
        """Handle rate limit errors"""
        logger.warning(f"Rate limit exceeded: {error.message}", extra=context)
        
        return {
            'error': 'rate_limit_exceeded',
            'message': 'Request rate limit exceeded',
            'code': 429,
            'details': error.details,
            'request_id': context['request_id']
        }, 429
    
    @staticmethod
    def _handle_auth_error(error: AuthenticationError, context: Dict) -> Tuple[Dict[str, Any], int]:
        """Handle authentication errors"""
        logger.warning(f"Authentication error: {error.message}", extra=context)
        
        return {
            'error': 'authentication_error',
            'message': 'Authentication required',
            'code': 401,
            'request_id': context['request_id']
        }, 401
    
    @staticmethod
    def _handle_authorization_error(error: AuthorizationError, context: Dict) -> Tuple[Dict[str, Any], int]:
        """Handle authorization errors"""
        logger.warning(f"Authorization error: {error.message}", extra=context)
        
        return {
            'error': 'authorization_error',
            'message': 'Insufficient permissions',
            'code': 403,
            'request_id': context['request_id']
        }, 403
    
    @staticmethod
    def _handle_analysis_error(error: AnalysisError, context: Dict) -> Tuple[Dict[str, Any], int]:
        """Handle analysis computation errors"""
        logger.error(f"Analysis error: {error.message}", extra=context)
        
        return {
            'error': 'analysis_error',
            'message': 'Stock analysis computation failed',
            'code': 500,
            'details': error.details,
            'request_id': context['request_id']
        }, 500
    
    @staticmethod
    def _handle_custom_error(error: StockAnalysisException, context: Dict) -> Tuple[Dict[str, Any], int]:
        """Handle custom application errors"""
        logger.error(f"Application error: {error.message}", extra=context)
        
        return {
            'error': error.error_code,
            'message': error.message,
            'code': 500,
            'details': error.details,
            'request_id': context['request_id']
        }, 500
    
    @staticmethod
    def _handle_generic_error(error: Exception, context: Dict) -> Tuple[Dict[str, Any], int]:
        """Handle unexpected errors"""
        logger.error(f"Unexpected error: {str(error)}", extra=context, exc_info=True)
        
        # Don't expose internal error details in production
        return {
            'error': 'internal_error',
            'message': 'An unexpected error occurred',
            'code': 500,
            'request_id': context['request_id']
        }, 500


def register_error_handlers(app):
    """Register error handlers with Flask app"""
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Global exception handler"""
        response_data, status_code = ErrorHandler.handle_exception(error)
        return jsonify(response_data), status_code
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 errors"""
        return jsonify({
            'error': 'not_found',
            'message': 'Resource not found',
            'code': 404,
            'request_id': getattr(request, 'id', 'unknown')
        }), 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        """Handle 405 errors"""
        return jsonify({
            'error': 'method_not_allowed',
            'message': 'Method not allowed',
            'code': 405,
            'request_id': getattr(request, 'id', 'unknown')
        }), 405
