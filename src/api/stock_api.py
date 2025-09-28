# src/api/stock_api.py - Stock query API endpoints
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from flask import Blueprint, jsonify, request
from sqlalchemy.orm import sessionmaker
from src.models.stock import Stock, StockPrice
from src.services.data_collector import DataCollector
from src.services.recommendation_engine import RecommendationEngine
from src.middleware.validator import require_stock_code, InputValidator
from config.settings import settings

stock_bp = Blueprint('stocks', __name__, url_prefix='/api/stocks')

# Database session (to be injected)
db_session = None


@stock_bp.route('/<stock_code>', methods=['GET'])
@require_stock_code
def get_stock_info(stock_code: str):
    """Get comprehensive stock information"""
    try:
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
def scan_stocks():
    """Multi-condition stock screening"""
    try:
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
        
        results = []
        rec_engine = RecommendationEngine(db_session)
        
        for stock in stocks:
            # Get latest price
            latest_price = db_session.query(StockPrice).filter_by(
                stock_code=stock.code
            ).order_by(StockPrice.timestamp.desc()).first()
            
            if not latest_price:
                continue
            
            # Apply price filters
            if min_price and latest_price.close_price < min_price:
                continue
            if max_price and latest_price.close_price > max_price:
                continue
            if min_volume and latest_price.volume < min_volume:
                continue
            
            # Get recommendation
            recommendation = rec_engine.get_latest_recommendation(stock.code)
            if recommendation:
                # Apply recommendation filters
                if action_filter and recommendation['action'] != action_filter:
                    continue
                if recommendation['confidence'] < min_confidence:
                    continue
            
            results.append({
                'code': stock.code,
                'name': stock.name,
                'industry': stock.industry,
                'current_price': latest_price.close_price,
                'change_pct': latest_price.change_pct,
                'volume': latest_price.volume,
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
def list_stocks():
    """Get list of all available stocks"""
    try:
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
        rec_engine = RecommendationEngine(db_session)
        recommendation = rec_engine.predict_recommendation(stock_code)
        
        if not recommendation:
            return jsonify({'error': 'Unable to generate recommendation'}), 404
        
        return jsonify(recommendation)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Health check endpoint
@stock_bp.route('/health', methods=['GET'])
def health_check():
    """API health check"""
    try:
        # Test database connection
        stock_count = db_session.query(Stock).count()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'stock_count': stock_count
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500