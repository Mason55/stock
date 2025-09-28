# src/app.py - Flask application main entry point
import logging
import time
from flask import Flask, request, g
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from src.models.stock import Base
from src.api.stock_api import stock_bp
import src.api.stock_api as stock_api_module
from src.utils.logger import setup_logger, RequestLogger
from src.middleware.rate_limiter import RateLimiter, get_redis_client
from src.middleware.cache import CacheManager

logger = setup_logger('stock_api', 'app.log', logging.INFO)


def create_app():
    """Application factory"""
    app = Flask(__name__)
    
    # Enable CORS for frontend
    CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000'])
    
    # Database setup
    engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
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
    stock_api_module.db_session = db_session
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
    
    # Error handlers
    @app.errorhandler(400)
    def bad_request(error):
        logger.warning(f"Bad request: {error}")
        return {'error': 'Bad request', 'message': str(error)}, 400
    
    @app.errorhandler(404)
    def not_found(error):
        logger.warning(f"Not found: {request.path}")
        return {'error': 'Resource not found'}, 404
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        logger.warning(f"Rate limit exceeded: {request.remote_addr}")
        return {'error': 'Rate limit exceeded'}, 429
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}", exc_info=True)
        return {'error': 'Internal server error'}, 500
    
    logger.info("Stock Analysis System started successfully")
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(
        host=settings.API_HOST,
        port=settings.API_PORT,
        debug=settings.DEBUG
    )