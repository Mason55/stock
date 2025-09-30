# src/app.py - Flask application main entry point with improved portability
import logging
import time
import os
from flask import Flask, request, g, send_from_directory
from flask_cors import CORS
from config.settings import settings
from src.database import db_manager, get_session_factory, init_database
from src.api.stock_api import stock_bp
from src.api.metrics import metrics_bp, before_request_metrics, after_request_metrics
from src.utils.logger import setup_logger, RequestLogger
from src.utils.error_handler import register_error_handlers
from src.utils.di_container import init_container, get_container
from src.utils.config_validator import ConfigValidator
from src.middleware.rate_limiter import RateLimiter, get_redis_client
from src.middleware.cache import CacheManager
from src.middleware.auth import AuthMiddleware

# Compatibility shim for Werkzeug version detection in Flask test client
try:
    import werkzeug  # type: ignore
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3"
except Exception:
    pass

# Configure logging based on settings
log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
log_file = 'app.log' if settings.LOG_TO_FILE else None
logger = setup_logger('stock_api', log_file, log_level)


def create_app():
    """Application factory with improved portability"""
    # Disable default static folder to avoid conflicts with frontend
    app = Flask(__name__, static_folder=None)

    # Validate configuration
    try:
        ConfigValidator.validate_and_raise()
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        # Continue with warning in development mode
        if not settings.is_production():
            logger.warning("Continuing with invalid configuration in development mode")
        else:
            raise

    # Configure CORS with environment variable support
    cors_origins = settings.get_cors_origins()
    CORS(app, origins=cors_origins)
    logger.info(f"CORS configured for origins: {cors_origins}")
    
    # Database setup with graceful degradation
    try:
        init_database()
        session_factory = get_session_factory()
        if db_manager.is_fallback_mode():
            logger.warning("Running in database fallback mode")
        else:
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Continue with degraded functionality rather than failing completely
        session_factory = None
    
    # Initialize Redis and middleware (optional based on configuration)
    if settings.USE_REDIS and not settings.OFFLINE_MODE:
        try:
            redis_client = get_redis_client()
            rate_limiter = RateLimiter(redis_client)
            cache_manager = CacheManager(redis_client)
            
            app.rate_limiter = rate_limiter
            app.cache_manager = cache_manager
            logger.info("Redis middleware initialized")
        except Exception as e:
            logger.warning(f"Redis unavailable, middleware disabled: {e}")
            app.rate_limiter = None
            app.cache_manager = None
    else:
        logger.info("Redis disabled by configuration or offline mode")
        app.rate_limiter = None
        app.cache_manager = None
    
    # Initialize dependency injection container
    container = init_container(
        session_factory=session_factory,
        cache_manager=getattr(app, 'cache_manager', None),
        rate_limiter=getattr(app, 'rate_limiter', None)
    )
    app.container = container
    logger.info("Dependency injection container initialized")
    
    # Request timing and metrics middleware
    @app.before_request
    def before_request():
        g.start_time = time.time()
        RequestLogger.log_request(logger, request)
        before_request_metrics()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            duration_ms = (time.time() - g.start_time) * 1000
            RequestLogger.log_response(logger, response, duration_ms)
            response.headers['X-Response-Time'] = f"{duration_ms:.2f}ms"
        
        # Record metrics
        response = after_request_metrics(response)
        return response
    
    # Initialize authentication middleware
    auth_middleware = AuthMiddleware(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register blueprints
    app.register_blueprint(stock_bp)
    app.register_blueprint(metrics_bp)

    # Frontend routes
    @app.route('/')
    def index():
        """Serve frontend index page."""
        frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
        return send_from_directory(frontend_dir, 'index.html')

    @app.route('/static/<path:path>')
    def send_static(path):
        """Serve frontend static files (CSS, JS)."""
        frontend_static_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'frontend',
            'static'
        )
        return send_from_directory(frontend_static_dir, path)

    # API info endpoint
    @app.route('/api')
    def api_info():
        return {
            'message': 'Chinese Stock Analysis System API',
            'version': '1.0.0',
            'endpoints': {
                'stocks': '/api/stocks',
                'health': '/api/stocks/health',
                'metrics': '/metrics',
                'docs': 'https://github.com/your-org/stock-analysis-system'
            }
        }
    
    # Error handlers are now registered via register_error_handlers()
    
    logger.info("Stock Analysis System started successfully")
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(
        host=settings.API_HOST,
        port=settings.API_PORT,
        debug=settings.DEBUG
    )
