# src/app.py - Flask application main entry point
import logging
import time
from flask import Flask, request, g
from flask_cors import CORS
from config.settings import settings
from src.database import db_manager, get_session_factory
from src.api.stock_api import stock_bp
import src.api.stock_api as stock_api_module
from src.utils.logger import setup_logger, RequestLogger
from src.utils.error_handler import register_error_handlers
from src.middleware.rate_limiter import RateLimiter, get_redis_client
from src.middleware.cache import CacheManager
from src.middleware.auth import AuthMiddleware

logger = setup_logger('stock_api', 'app.log', logging.INFO)


def create_app():
    """Application factory"""
    app = Flask(__name__)
    
    # Enable CORS for frontend
    CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000'])
    
    # Database setup - using managed database instance with fallback
    if not db_manager.is_initialized():
        logger.error("Database initialization failed completely")
        raise RuntimeError("Database initialization failed")
    
    if db_manager.is_fallback_mode():
        logger.warning("Running in database fallback mode")
    
    session_factory = get_session_factory()
    
    # Initialize Redis and middleware
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
    
    # Inject dependencies into API module
    stock_api_module.session_factory = session_factory
    stock_api_module.cache_manager = getattr(app, 'cache_manager', None)
    stock_api_module.rate_limiter = getattr(app, 'rate_limiter', None)
    
    # Request timing middleware
    @app.before_request
    def before_request():
        g.start_time = time.time()
        RequestLogger.log_request(logger, request)
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            duration_ms = (time.time() - g.start_time) * 1000
            RequestLogger.log_response(logger, response, duration_ms)
            response.headers['X-Response-Time'] = f"{duration_ms:.2f}ms"
        return response
    
    # Initialize authentication middleware
    auth_middleware = AuthMiddleware(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register blueprints
    app.register_blueprint(stock_bp)
    
    # Root endpoint
    @app.route('/')
    def index():
        return {
            'message': 'Chinese Stock Analysis System API',
            'version': '1.0.0',
            'endpoints': {
                'stocks': '/api/stocks',
                'health': '/api/stocks/health',
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