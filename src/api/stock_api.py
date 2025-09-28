# src/api/stock_api.py - Stock query API endpoints with offline mode support
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from flask import Blueprint, jsonify, request, g
from sqlalchemy.orm import sessionmaker
from src.models.stock import Stock, StockPrice
try:
    from src.services.recommendation_engine import RecommendationEngine
except ImportError:
    from src.services.simple_recommendation import SimpleRecommendationEngine as RecommendationEngine
from src.services.mock_data import mock_data_service
from src.middleware.validator import require_stock_code, InputValidator
from src.database import get_db_session
from src.utils.exceptions import DatabaseError, ValidationError
from src.utils.sql_security import sql_injection_protection, SafeQueryBuilder
from src.cache import initialize_cache, get_cache_manager, cached
from src.monitoring import monitor_performance, monitor_db_operation
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

stock_bp = Blueprint('stocks', __name__, url_prefix='/api/stocks')

# Session factory (to be injected)
session_factory = None
cache_manager = None
rate_limiter = None

# Initialize cache on module load
def init_api_cache():
    """Initialize cache for API endpoints"""
    global cache_manager
    try:
        import redis
        redis_client = redis.Redis(host='localhost', port=6379, db=0)
        cache_manager = initialize_cache(redis_client=redis_client, memory_limit_mb=128)
        logger.info("API cache initialized with Redis")
    except Exception as e:
        logger.warning(f"Redis unavailable, using memory-only cache: {e}")
        cache_manager = initialize_cache(redis_client=None, memory_limit_mb=128)


def is_offline_mode() -> bool:
    """Check if running in offline mode"""
    return settings.is_offline_mode()


def get_data_source(prefer_mock: bool = False):
    """Get appropriate data source based on mode"""
    if is_offline_mode() or prefer_mock:
        return mock_data_service
    return None  # Use database/external APIs


def get_current_session():
    """Get database session for current request"""
    if not hasattr(g, 'db_session'):
        if session_factory:
            try:
                g.db_session = session_factory()
            except Exception as e:
                logger.warning(f"Failed to create database session: {e}")
                g.db_session = None
        else:
            g.db_session = None
    return g.db_session


@stock_bp.before_request
def before_request():
    """Initialize database session for each request"""
    # Create session on demand to improve compatibility
    if session_factory:
        try:
            g.db_session = session_factory()
        except Exception as e:
            logger.warning(f"Failed to create database session: {e}")
            g.db_session = None


@stock_bp.teardown_request
def teardown_request(exception=None):
    """Clean up database session after each request"""
    db_session = g.pop('db_session', None)
    if db_session:
        try:
            if exception:
                db_session.rollback()
            else:
                db_session.commit()
        except Exception as e:
            logger.warning(f"Session cleanup error: {e}")
            try:
                db_session.rollback()
            except:
                pass
        finally:
            try:
                db_session.close()
            except:
                pass


@stock_bp.route('/<stock_code>', methods=['GET'])
@require_stock_code
def get_stock_info(stock_code: str):
    """Get comprehensive stock information"""
    try:
        db_session = get_current_session()
        
        # Fallback to mock data if database unavailable
        if not db_session or is_offline_mode():
            mock_data = mock_data_service.get_stock_info(stock_code)
            if not mock_data:
                return jsonify({'error': 'Stock not found'}), 404
            return jsonify(mock_data)
        
        # Get basic stock info
        stock = db_session.query(Stock).filter_by(code=stock_code).first()
        if not stock:
            return jsonify({'error': 'Stock not found'}), 404
        
        # Get latest price
        latest_price = db_session.query(StockPrice).filter_by(
            stock_code=stock_code
        ).order_by(StockPrice.timestamp.desc()).first()
        
        # Get recommendation
        rec_engine = RecommendationEngine(db_session)
        recommendation = rec_engine.get_latest_recommendation(stock_code)
        
        response = {
            'code': stock.code,
            'name': stock.name,
            'exchange': stock.exchange,
            'industry': stock.industry,
            'market_cap': stock.market_cap,
            'current_price': latest_price.close_price if latest_price else None,
            'change_pct': latest_price.change_pct if latest_price else None,
            'volume': latest_price.volume if latest_price else None,
            'last_updated': latest_price.timestamp.isoformat() if latest_price else None,
            'recommendation': recommendation
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/<stock_code>/timeline', methods=['GET'])
@require_stock_code
def get_stock_timeline(stock_code: str):
    """Get historical price timeline"""
    try:
        db_session = get_current_session()
        
        # Parse query parameters
        range_param = InputValidator.validate_time_range(
            request.args.get('range', '1M')
        )
        
        # Calculate date range
        end_date = datetime.now()
        if range_param == '1D':
            start_date = end_date - timedelta(days=1)
        elif range_param == '1W':
            start_date = end_date - timedelta(weeks=1)
        elif range_param == '1M':
            start_date = end_date - timedelta(days=30)
        elif range_param == '3M':
            start_date = end_date - timedelta(days=90)
        elif range_param == 'YTD':
            start_date = datetime(end_date.year, 1, 1)
        elif range_param == '1Y':
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Get price data
        prices = db_session.query(StockPrice).filter(
            StockPrice.stock_code == stock_code,
            StockPrice.timestamp >= start_date
        ).order_by(StockPrice.timestamp).all()
        
        timeline_data = []
        for price in prices:
            timeline_data.append({
                'timestamp': price.timestamp.isoformat(),
                'open': price.open_price,
                'high': price.high_price,
                'low': price.low_price,
                'close': price.close_price,
                'volume': price.volume,
                'change_pct': price.change_pct
            })
        
        return jsonify({
            'stock_code': stock_code,
            'range': range_param,
            'data': timeline_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/<stock_code>/factors', methods=['GET'])
@require_stock_code
def get_stock_factors(stock_code: str):
    """Get detailed factor analysis"""
    try:
        db_session = get_current_session()
        rec_engine = RecommendationEngine(db_session)
        
        # Get features
        features = rec_engine.extract_features(stock_code)
        if not features:
            return jsonify({'error': 'Insufficient data for analysis'}), 404
        
        # Get latest recommendation for factor explanation
        recommendation = rec_engine.get_latest_recommendation(stock_code)
        
        response = {
            'stock_code': stock_code,
            'features': features,
            'recommendation': recommendation,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/scan', methods=['GET'])
@sql_injection_protection
@monitor_performance(operation_type='stock_scan', component='api')
def scan_stocks():
    """Multi-condition stock screening"""
    try:
        db_session = get_current_session()
        
        # Parse query parameters
        industry = InputValidator.sanitize_string(request.args.get('industry', ''))
        min_price = InputValidator.validate_numeric_range(request.args.get('min_price', type=float), 0, 10000)
        max_price = InputValidator.validate_numeric_range(request.args.get('max_price', type=float), 0, 10000)
        min_volume = InputValidator.validate_numeric_range(request.args.get('min_volume', type=float), 0)
        action_filter = request.args.get('action')
        min_confidence = InputValidator.validate_numeric_range(request.args.get('min_confidence', type=float, default=0.0), 0, 1) or 0.0
        limit = min(request.args.get('limit', type=int, default=50), 100)
        
        # Build query
        query = db_session.query(Stock)
        
        if industry:
            query = query.filter(Stock.industry == industry)
        
        stocks = query.limit(1000).all()  # Get base stocks
        
        if not stocks:
            return jsonify({
                'total_found': 0,
                'stocks': []
            })
        
        # 优化: 批量查询最新价格数据，避免N+1查询问题
        stock_codes = [stock.code for stock in stocks]
        
        # 使用子查询获取每个股票的最新价格
        from sqlalchemy import func
        latest_price_subquery = db_session.query(
            StockPrice.stock_code,
            func.max(StockPrice.timestamp).label('max_timestamp')
        ).filter(
            StockPrice.stock_code.in_(stock_codes)
        ).group_by(StockPrice.stock_code).subquery()
        
        # 连接查询获取最新价格详细信息
        latest_prices = db_session.query(
            StockPrice
        ).join(
            latest_price_subquery,
            (StockPrice.stock_code == latest_price_subquery.c.stock_code) &
            (StockPrice.timestamp == latest_price_subquery.c.max_timestamp)
        ).all()
        
        # 创建价格查找字典，提高查找效率
        price_dict = {price.stock_code: price for price in latest_prices}
        
        # 批量获取推荐数据（如果有推荐引擎）
        recommendations_dict = {}
        try:
            rec_engine = RecommendationEngine(db_session)
            # 尝试批量获取推荐（如果RecommendationEngine支持）
            if hasattr(rec_engine, 'get_batch_recommendations'):
                recommendations_dict = rec_engine.get_batch_recommendations(stock_codes)
            else:
                # 如果不支持批量，至少缓存引擎实例
                pass
        except Exception as e:
            logger.warning(f"Recommendation engine initialization failed: {e}")
            rec_engine = None
        
        results = []
        
        for stock in stocks:
            # 从缓存字典中获取价格数据
            latest_price = price_dict.get(stock.code)
            
            if not latest_price:
                continue
            
            # Apply price filters
            if min_price and latest_price.close_price < min_price:
                continue
            if max_price and latest_price.close_price > max_price:
                continue
            if min_volume and latest_price.volume < min_volume:
                continue
            
            # Get recommendation (优化后)
            recommendation = None
            if rec_engine:
                if stock.code in recommendations_dict:
                    recommendation = recommendations_dict[stock.code]
                else:
                    # Fallback to individual query if batch not available
                    try:
                        recommendation = rec_engine.get_latest_recommendation(stock.code)
                    except Exception as e:
                        logger.warning(f"Failed to get recommendation for {stock.code}: {e}")
                
                if recommendation:
                    # Apply recommendation filters
                    if action_filter and recommendation.get('action') != action_filter:
                        continue
                    if recommendation.get('confidence', 0) < min_confidence:
                        continue
            
            results.append({
                'code': stock.code,
                'name': stock.name,
                'industry': stock.industry,
                'current_price': float(latest_price.close_price),
                'change_pct': float(latest_price.change_pct) if latest_price.change_pct else 0.0,
                'volume': int(latest_price.volume) if latest_price.volume else 0,
                'recommendation': recommendation
            })
            
            if len(results) >= limit:
                break
        
        return jsonify({
            'total_found': len(results),
            'stocks': results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/list', methods=['GET'])
@sql_injection_protection
def list_stocks():
    """Get list of all available stocks"""
    try:
        db_session = get_current_session()
        
        page, per_page = InputValidator.validate_pagination(
            request.args.get('page', type=int),
            request.args.get('per_page', type=int)
        )
        
        stocks = db_session.query(Stock).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        stock_list = []
        for stock in stocks:
            stock_list.append({
                'code': stock.code,
                'name': stock.name,
                'exchange': stock.exchange,
                'industry': stock.industry
            })
        
        total_count = db_session.query(Stock).count()
        
        return jsonify({
            'stocks': stock_list,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': (total_count + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/recommend/<stock_code>', methods=['POST'])
@require_stock_code
def generate_recommendation(stock_code: str):
    """Generate fresh recommendation for a stock"""
    try:
        db_session = get_current_session()
        rec_engine = RecommendationEngine(db_session)
        recommendation = rec_engine.predict_recommendation(stock_code)
        
        if not recommendation:
            return jsonify({'error': 'Unable to generate recommendation'}), 404
        
        return jsonify(recommendation)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# New API endpoints to match documentation
@stock_bp.route('/<stock_code>/analysis', methods=['GET'])
@require_stock_code
@cached(ttl=300, tags=['stock_analysis'], key_func=lambda stock_code: f"analysis:{stock_code}")
def get_stock_analysis(stock_code: str):
    """Get comprehensive stock analysis"""
    try:
        analysis_type = request.args.get('analysis_type', 'all')
        
        # Check if offline mode
        if is_offline_mode():
            logger.info(f"Using mock data for analysis: {stock_code}")
            result = mock_data_service.get_stock_analysis(stock_code, analysis_type)
            if not result:
                return jsonify({'error': 'Stock not found in mock data'}), 404
            return jsonify(result)
        
        # Normal database mode
        db_session = get_current_session()
        
        # Get basic stock info
        stock = db_session.query(Stock).filter_by(code=stock_code).first()
        if not stock:
            return jsonify({'error': 'Stock not found'}), 404
        
        # Get latest price data
        latest_price = db_session.query(StockPrice).filter_by(
            stock_code=stock_code
        ).order_by(StockPrice.timestamp.desc()).first()
        
        result = {
            'stock_code': stock_code,
            'company_name': stock.name,
            'current_price': latest_price.close_price if latest_price else None,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        # Add analysis based on type
        if analysis_type in ['technical', 'all']:
            result['technical_analysis'] = {
                'overall_trend': 'neutral',
                'trend_strength': 0.5,
                'support_levels': [],
                'resistance_levels': [],
                'indicators': {}
            }
        
        if analysis_type in ['fundamental', 'all']:
            result['fundamental_analysis'] = {
                'valuation': {'pe_ratio': None, 'pb_ratio': None},
                'profitability': {'roe': None, 'roa': None},
                'growth': {'revenue_growth': None},
                'financial_health': {'debt_ratio': None}
            }
        
        if analysis_type in ['sentiment', 'all']:
            result['sentiment_analysis'] = {
                'overall_sentiment': 0.5,
                'sentiment_level': 'neutral',
                'news_sentiment': {'score': 0.5, 'article_count': 0},
                'social_sentiment': {'score': 0.5, 'mention_count': 0}
            }
        
        if analysis_type == 'all':
            result['recommendation'] = {
                'action': '持有',
                'confidence': 0.5,
                'score': 5.0,
                'risk_level': '中等'
            }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/<stock_code>/realtime', methods=['GET'])
@require_stock_code
@cached(ttl=30, tags=['realtime_data'], key_func=lambda stock_code: f"realtime:{stock_code}")
def get_realtime_data(stock_code: str):
    """Get real-time stock data"""
    try:
        # Check if offline mode
        if is_offline_mode():
            logger.info(f"Using mock data for realtime: {stock_code}")
            result = mock_data_service.get_realtime_data(stock_code)
            if not result:
                return jsonify({'error': 'Stock not found in mock data'}), 404
            return jsonify(result)
        
        # Normal database mode
        db_session = get_current_session()
        
        # Get latest price data (in real implementation, this would come from live feed)
        latest_price = db_session.query(StockPrice).filter_by(
            stock_code=stock_code
        ).order_by(StockPrice.timestamp.desc()).first()
        
        if not latest_price:
            return jsonify({'error': 'No price data available'}), 404
        
        result = {
            'stock_code': stock_code,
            'current_price': latest_price.close_price,
            'price_change': latest_price.change_pct,
            'volume': latest_price.volume,
            'timestamp': latest_price.timestamp.isoformat(),
            'market_status': 'closed'  # This would be determined by market hours
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/<stock_code>/history', methods=['GET'])
@require_stock_code
@cached(ttl=3600, tags=['historical_data'], key_func=lambda stock_code: f"history:{stock_code}:{request.args.get('days', 30)}")
def get_historical_data(stock_code: str):
    """Get historical price data"""
    try:
        db_session = get_current_session()
        
        # Parse query parameters
        days = min(365, max(1, request.args.get('days', 30, type=int)))
        start_date = datetime.now() - timedelta(days=days)
        
        # Get historical price data
        prices = db_session.query(StockPrice).filter(
            StockPrice.stock_code == stock_code,
            StockPrice.timestamp >= start_date
        ).order_by(StockPrice.timestamp.desc()).limit(100).all()
        
        data = []
        for price in prices:
            data.append({
                'date': price.timestamp.strftime('%Y-%m-%d'),
                'open': price.open_price,
                'high': price.high_price,
                'low': price.low_price,
                'close': price.close_price,
                'volume': price.volume
            })
        
        result = {
            'stock_code': stock_code,
            'period': f"{days}d",
            'data_count': len(data),
            'data': data
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/batch_analysis', methods=['POST'])
@monitor_performance(operation_type='batch_analysis', component='api')
def batch_analysis():
    """Batch analysis for multiple stocks"""
    try:
        data = request.get_json()
        if not data or 'stock_codes' not in data:
            raise ValidationError("Missing stock_codes in request")
        
        stock_codes = data['stock_codes']
        if not isinstance(stock_codes, list) or len(stock_codes) == 0:
            raise ValidationError("stock_codes must be a non-empty list")
        
        if len(stock_codes) > 50:
            raise ValidationError("Maximum 50 stocks per batch request")
        
        analysis_types = data.get('analysis_types', ['technical'])
        
        # Check if offline mode
        if is_offline_mode():
            logger.info(f"Using mock data for batch analysis: {len(stock_codes)} stocks")
            result = mock_data_service.batch_analysis(stock_codes, analysis_types)
            return jsonify(result)
        
        # Normal database mode
        db_session = get_current_session()
        
        results = []
        for stock_code in stock_codes:
            try:
                # Basic validation
                if not stock_code or len(stock_code) < 6:
                    results.append({
                        'stock_code': stock_code,
                        'status': 'error',
                        'error': 'Invalid stock code format'
                    })
                    continue
                
                # Get basic analysis (simplified)
                stock = db_session.query(Stock).filter_by(code=stock_code).first()
                if not stock:
                    results.append({
                        'stock_code': stock_code,
                        'status': 'error',
                        'error': 'Stock not found'
                    })
                    continue
                
                analysis = {
                    'stock_code': stock_code,
                    'company_name': stock.name,
                    'status': 'success'
                }
                
                # Add requested analysis types
                if 'technical' in analysis_types:
                    analysis['technical_score'] = 5.0
                if 'fundamental' in analysis_types:
                    analysis['fundamental_score'] = 5.0
                
                results.append(analysis)
                
            except Exception as e:
                results.append({
                    'stock_code': stock_code,
                    'status': 'error',
                    'error': str(e)
                })
        
        # Summary statistics
        successful = [r for r in results if r.get('status') == 'success']
        failed = [r for r in results if r.get('status') == 'error']
        
        response = {
            'batch_id': f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'total_stocks': len(stock_codes),
            'completed': len(successful),
            'failed': len(failed),
            'results': results,
            'summary': {
                'success_rate': len(successful) / len(stock_codes) if stock_codes else 0
            }
        }
        
        return jsonify(response)
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Health check endpoint
@stock_bp.route('/health', methods=['GET'])
def health_check():
    """API health check with detailed status"""
    from src.database import db_manager
    
    # Get database health status
    db_health = db_manager.health_check()
    
    # Overall system status
    overall_status = 'healthy'
    if db_health['status'] == 'degraded':
        overall_status = 'degraded'
    elif db_health['status'] in ['unhealthy', 'unavailable']:
        overall_status = 'unhealthy'
    
    response_data = {
        'status': overall_status,
        'timestamp': datetime.now().isoformat(),
        'database': db_health,
        'api': 'running'
    }
    
    # Add stock count if database is available
    if db_health['status'] in ['healthy', 'degraded']:
        try:
            db_session = get_current_session()
            if db_session:
                stock_count = db_session.query(Stock).count()
                response_data['stock_count'] = stock_count
        except Exception as e:
            response_data['stock_count_error'] = str(e)
    
    # Add middleware status
    response_data['middleware'] = {
        'cache': 'available' if cache_manager else 'unavailable',
        'rate_limiter': 'available' if rate_limiter else 'unavailable'
    }
    
    # Add mode information
    response_data['mode'] = {
        'offline_mode': settings.OFFLINE_MODE,
        'mock_data_enabled': settings.MOCK_DATA_ENABLED,
        'use_redis': settings.USE_REDIS,
        'deployment_mode': settings.DEPLOYMENT_MODE
    }
    
    # Add available stocks count for offline mode
    if is_offline_mode():
        response_data['mock_stocks_available'] = len(mock_data_service.stocks)
    
    status_code = 200 if overall_status in ['healthy', 'degraded'] else 503
    return jsonify(response_data), status_code