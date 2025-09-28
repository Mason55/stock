# src/middleware/metrics_middleware.py - Flask middleware for automatic metrics collection
import time
import logging
from typing import Optional
from flask import Flask, request, Response, g
from functools import wraps
from src.monitoring import get_metrics_collector

logger = logging.getLogger(__name__)


class MetricsMiddleware:
    """Flask middleware for automatic metrics collection"""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize middleware with Flask app"""
        
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_request(self._teardown_request)
        
        # Add metrics endpoint
        @app.route('/metrics')
        def metrics_endpoint():
            """Prometheus metrics endpoint"""
            from src.monitoring import get_prometheus_metrics
            content, content_type = get_prometheus_metrics()
            return Response(content, mimetype=content_type)
        
        logger.info("Metrics middleware initialized")
    
    def _before_request(self):
        """Record request start time and metadata"""
        g.request_start_time = time.time()
        g.request_size = len(request.get_data()) if request.get_data() else 0
        
        # Record active connection (approximate)
        collector = get_metrics_collector()
        if collector and collector.enabled:
            # This is an approximation - in production you'd track actual DB connections
            collector.db_connections_active.inc()
    
    def _after_request(self, response: Response) -> Response:
        """Record request completion metrics"""
        
        collector = get_metrics_collector()
        if not collector or not collector.enabled:
            return response
        
        try:
            # Calculate request duration
            duration = time.time() - getattr(g, 'request_start_time', time.time())
            
            # Get request metadata
            method = request.method
            endpoint = self._normalize_endpoint(request.endpoint or 'unknown')
            status_code = response.status_code
            request_size = getattr(g, 'request_size', 0)
            response_size = len(response.get_data()) if response.get_data() else 0
            
            # Record HTTP metrics
            collector.record_http_request(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                duration=duration,
                request_size=request_size,
                response_size=response_size
            )
            
            # Record performance tracking
            if hasattr(collector, 'performance_tracker'):
                collector.performance_tracker.record_response_time(duration)
                collector.performance_tracker.record_error(status_code >= 400)
            
            # Log slow requests
            if duration > 2.0:
                logger.warning(f"Slow request: {method} {endpoint} took {duration:.2f}s")
                collector.record_error(
                    error_type='slow_request',
                    component='api',
                    severity='warning'
                )
            
        except Exception as e:
            logger.warning(f"Failed to record request metrics: {e}")
        
        return response
    
    def _teardown_request(self, exception=None):
        """Clean up request metrics"""
        
        collector = get_metrics_collector()
        if collector and collector.enabled:
            # Decrease active connection count
            collector.db_connections_active.dec()
            
            # Record any exception
            if exception:
                collector.record_error(
                    error_type=type(exception).__name__,
                    component='api',
                    severity='error'
                )
    
    def _normalize_endpoint(self, endpoint: str) -> str:
        """Normalize endpoint for metrics (remove variable parts)"""
        
        # Replace common variable patterns
        import re
        
        # Replace stock codes with placeholder
        endpoint = re.sub(r'/[A-Z0-9]{4,6}\.(SH|SZ|HK)', '/{{stock_code}}', endpoint)
        endpoint = re.sub(r'/[A-Z]{2,5}', '/{{symbol}}', endpoint)
        
        # Replace numeric IDs
        endpoint = re.sub(r'/\d+', '/{{id}}', endpoint)
        
        return endpoint or 'unknown'


def metrics_middleware_factory(app: Flask) -> MetricsMiddleware:
    """Factory function to create and configure metrics middleware"""
    return MetricsMiddleware(app)


# Decorator for monitoring specific endpoints
def monitor_endpoint(endpoint_name: str = None, track_params: bool = False):
    """Decorator for monitoring specific endpoints with custom metrics"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            if not collector or not collector.enabled:
                return func(*args, **kwargs)
            
            start_time = time.time()
            endpoint = endpoint_name or func.__name__
            
            try:
                result = func(*args, **kwargs)
                
                # Record custom endpoint metrics
                duration = time.time() - start_time
                
                # For stock analysis endpoints, record specific metrics
                if 'analysis' in endpoint.lower():
                    if args:  # Assume first arg is stock_code
                        stock_code = args[0] if args else 'unknown'
                        collector.record_analysis_request(
                            analysis_type=endpoint,
                            stock_code=stock_code,
                            duration=duration
                        )
                
                return result
                
            except Exception as e:
                collector.record_error(
                    error_type=type(e).__name__,
                    component=endpoint,
                    severity='error'
                )
                raise
        
        return wrapper
    return decorator