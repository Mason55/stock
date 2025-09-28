# src/middleware/auth.py - Authentication middleware
import hashlib
import hmac
import time
import logging
from typing import Optional, Dict, Any
from functools import wraps
from flask import request, g, jsonify
from src.utils.exceptions import AuthenticationError, AuthorizationError
from config.settings import settings

logger = logging.getLogger(__name__)


class APIKeyAuth:
    """API Key based authentication"""
    
    # In production, this would be stored in database or external service
    VALID_API_KEYS = {
        'demo_key_123': {
            'name': 'Demo Client',
            'permissions': ['read', 'analysis'],
            'rate_limit': 100,  # requests per minute
            'created_at': '2025-09-28'
        },
        'premium_key_456': {
            'name': 'Premium Client', 
            'permissions': ['read', 'analysis', 'batch', 'realtime'],
            'rate_limit': 500,
            'created_at': '2025-09-28'
        }
    }
    
    def __init__(self):
        self.secret_key = getattr(settings, 'SECRET_KEY', 'default-secret-key')
    
    def authenticate_request(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Authenticate API key and return client info"""
        if not api_key:
            return None
        
        # Remove 'Bearer ' prefix if present
        if api_key.startswith('Bearer '):
            api_key = api_key[7:]
        
        client_info = self.VALID_API_KEYS.get(api_key)
        if not client_info:
            return None
        
        return {
            'api_key': api_key,
            'client_name': client_info['name'],
            'permissions': client_info['permissions'],
            'rate_limit': client_info['rate_limit']
        }
    
    def generate_signature(self, method: str, path: str, timestamp: str, api_key: str) -> str:
        """Generate request signature for enhanced security"""
        message = f"{method}|{path}|{timestamp}|{api_key}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def verify_signature(self, signature: str, method: str, path: str, 
                        timestamp: str, api_key: str) -> bool:
        """Verify request signature"""
        expected_signature = self.generate_signature(method, path, timestamp, api_key)
        return hmac.compare_digest(signature, expected_signature)


# Global auth instance
auth_manager = APIKeyAuth()


def require_auth(permissions: list = None):
    """Decorator to require authentication for endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get API key from headers
            api_key = request.headers.get('Authorization') or request.headers.get('X-API-Key')
            
            if not api_key:
                raise AuthenticationError("API key required")
            
            # Authenticate the request
            client_info = auth_manager.authenticate_request(api_key)
            if not client_info:
                raise AuthenticationError("Invalid API key")
            
            # Check permissions if specified
            if permissions:
                client_permissions = client_info.get('permissions', [])
                if not any(perm in client_permissions for perm in permissions):
                    raise AuthorizationError(f"Missing required permissions: {permissions}")
            
            # Store client info in request context
            g.client_info = client_info
            g.api_key = api_key
            
            logger.info(f"Authenticated request from {client_info['client_name']}")
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_signature():
    """Decorator to require request signature verification"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get signature components from headers
            signature = request.headers.get('X-Signature')
            timestamp = request.headers.get('X-Timestamp')
            api_key = getattr(g, 'api_key', None)
            
            if not all([signature, timestamp, api_key]):
                raise AuthenticationError("Missing signature components")
            
            # Check timestamp validity (prevent replay attacks)
            try:
                request_time = int(timestamp)
                current_time = int(time.time())
                if abs(current_time - request_time) > 300:  # 5 minutes tolerance
                    raise AuthenticationError("Request timestamp expired")
            except ValueError:
                raise AuthenticationError("Invalid timestamp format")
            
            # Verify signature
            if not auth_manager.verify_signature(
                signature, request.method, request.path, timestamp, api_key
            ):
                raise AuthenticationError("Invalid signature")
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def optional_auth():
    """Decorator for optional authentication (degraded functionality if not authenticated)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_key = request.headers.get('Authorization') or request.headers.get('X-API-Key')
            
            if api_key:
                client_info = auth_manager.authenticate_request(api_key)
                if client_info:
                    g.client_info = client_info
                    g.api_key = api_key
                    g.authenticated = True
                else:
                    g.authenticated = False
            else:
                g.authenticated = False
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def get_client_rate_limit() -> int:
    """Get rate limit for current client"""
    if hasattr(g, 'client_info'):
        return g.client_info.get('rate_limit', 60)  # Default 60 requests/minute
    return 10  # Unauthenticated users get lower limit


def has_permission(permission: str) -> bool:
    """Check if current client has specific permission"""
    if not hasattr(g, 'client_info'):
        return False
    
    client_permissions = g.client_info.get('permissions', [])
    return permission in client_permissions


def is_authenticated() -> bool:
    """Check if current request is authenticated"""
    return getattr(g, 'authenticated', False)


class AuthMiddleware:
    """Authentication middleware for Flask app"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize authentication middleware"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """Process authentication before each request"""
        # Add request ID for tracking
        import uuid
        g.request_id = str(uuid.uuid4())
        
        # Log request with authentication status
        api_key = request.headers.get('Authorization') or request.headers.get('X-API-Key')
        auth_status = 'authenticated' if api_key else 'anonymous'
        
        logger.info(f"Request {g.request_id}: {request.method} {request.path} [{auth_status}]")
    
    def after_request(self, response):
        """Process response after each request"""
        # Add request ID to response headers
        if hasattr(g, 'request_id'):
            response.headers['X-Request-ID'] = g.request_id
        
        # Add authentication info to response headers (for debugging)
        if hasattr(g, 'client_info'):
            response.headers['X-Client-Name'] = g.client_info['client_name']
        
        return response