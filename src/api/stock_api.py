# src/api/stock_api.py - Stock query API endpoints with offline mode support
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import Blueprint, jsonify, g
from flask import request as flask_request
from sqlalchemy.orm import sessionmaker
from src.models.stock import Stock, StockPrice
try:
    from src.services.recommendation_engine import RecommendationEngine
except ImportError:
    from src.services.simple_recommendation import SimpleRecommendationEngine as RecommendationEngine
from src.services.mock_data import mock_data_service
from src.services.fundamental_provider import fundamental_data_provider
from src.services.sentiment_provider import sentiment_data_provider
import requests
from src.middleware.validator import require_stock_code, InputValidator
from src.database import get_db_session
from src.utils.exceptions import DatabaseError, ValidationError
from src.utils.sql_security import sql_injection_protection, SafeQueryBuilder
from src.cache import initialize_cache, get_cache_manager, cached
from src.monitoring import monitor_performance, monitor_db_operation
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class _RequestShim:
    """Patch-friendly shim for flask.request to avoid context errors in tests.
    For real requests, forwards attribute access lazily to flask.request.
    """
    def __getattr__(self, name):
        try:
            return getattr(flask_request, name)
        except Exception:
            if name == 'args':
                class _Args:
                    def get(self, *a, **k):
                        return None
                return _Args()
            return None


# Expose shim as module attribute so tests can patch it safely
request = _RequestShim()

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


def _convert_to_sina_code(stock_code: str) -> str:
    """Convert standard code like 600580.SH to sh600580 for Sina."""
    try:
        code, market = stock_code.split('.')
        market = market.upper()
        prefix = 'sh' if market == 'SH' else 'sz'
        return f"{prefix}{code}"
    except Exception:
        return stock_code


def fetch_sina_realtime_sync(stock_code: str) -> Optional[dict]:
    """Fetch realtime quote from Sina synchronously using requests with proper headers.
    Returns a normalized dict or None on failure.
    """
    try:
        sina_code = _convert_to_sina_code(stock_code)
        url = f"https://hq.sinajs.cn/list={sina_code}"
        headers = {
            'Referer': 'https://finance.sina.com.cn',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=settings.EXTERNAL_API_TIMEOUT)
        if resp.status_code != 200:
            return None
        resp.encoding = 'gbk'
        text = resp.text
        start = text.find('"') + 1
        end = text.rfind('"')
        if start <= 0 or end <= start:
            return None
        data_str = text[start:end]
        if not data_str:
            return None
        parts = data_str.split(',')
        if len(parts) < 32:
            return None
        name = parts[0]
        open_price = float(parts[1] or 0)
        prev_close = float(parts[2] or 0)
        price = float(parts[3] or 0)
        high = float(parts[4] or 0)
        low = float(parts[5] or 0)
        volume = int(parts[8] or 0)
        turnover = float(parts[9] or 0)
        return {
            'stock_code': stock_code,
            'company_name': name,
            'open_price': open_price,
            'previous_close': prev_close,
            'current_price': price,
            'high_price': high,
            'low_price': low,
            'volume': volume,
            'turnover': turnover,
            'timestamp': datetime.now().isoformat(),
            'source': 'sina'
        }
    except Exception as e:
        logger.warning(f"Sina realtime fetch failed for {stock_code}: {e}")
        return None


# ---- Historical data and indicators (Tushare/Yahoo) ----
def _try_fetch_history_tushare(stock_code: str, days: int = 120) -> Optional['pd.DataFrame']:
    try:
        import os
        import pandas as pd
        import tushare as ts
        token = os.getenv('TUSHARE_TOKEN')
        if not token:
            return None
        pro = ts.pro_api(token)
        # Tushare expects ts_code like 600580.SH
        end = datetime.now().strftime('%Y%m%d')
        start = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')
        df = pro.daily(ts_code=stock_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        df = df[['trade_date','open','high','low','close','vol']].copy()
        df.rename(columns={'trade_date':'date','vol':'volume'}, inplace=True)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        # Keep last N days (trading days)
        return df.tail(days)
    except Exception as e:
        logger.warning(f"Tushare history fetch failed for {stock_code}: {e}")
        return None


def _try_fetch_history_yahoo(stock_code: str, days: int = 120) -> Optional['pd.DataFrame']:
    try:
        import pandas as pd
        import yfinance as yf
        # Convert to Yahoo code: SH->SS, SZ stays SZ
        yf_symbol = stock_code.replace('.SH', '.SS')
        period_days = max(60, days+10)
        data = yf.download(yf_symbol, period=f"{period_days}d", interval='1d', progress=False, auto_adjust=False)
        if data is None or data.empty:
            return None
        data = data.reset_index()
        data.rename(columns={
            'Date':'date','Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'
        }, inplace=True)
        return data.tail(days)
    except Exception as e:
        logger.warning(f"Yahoo history fetch failed for {stock_code}: {e}")
        return None


def _try_fetch_history_sina_kline(stock_code: str, days: int = 120) -> Optional['pd.DataFrame']:
    """Fetch daily K-line from Sina openapi (real data)"""
    try:
        import pandas as pd
        import requests
        # Convert to sina code
        sina_code = _convert_to_sina_code(stock_code)
        url = 'https://quotes.sina.cn/cn/api/openapi.php/CN_MarketDataService.getKLineData'
        params = {
            'symbol': sina_code,
            'scale': '240',  # daily bar
            'ma': '5',
            'datalen': str(max(60, days + 20))
        }
        headers = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, params=params, headers=headers, timeout=settings.EXTERNAL_API_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data or 'result' not in data or 'data' not in data['result'] or not data['result']['data']:
            return None
        rows = data['result']['data']
        df = pd.DataFrame(rows)
        # Normalize columns
        df.rename(columns={'day':'date'}, inplace=True)
        for col in ['open','high','low','close','volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        return df.tail(days)
    except Exception as e:
        logger.warning(f"Sina kline history fetch failed for {stock_code}: {e}")
        return None


def fetch_history_df(stock_code: str, days: int = 120) -> Optional['pd.DataFrame']:
    """Fetch real historical OHLCV with priority: Tushare -> Yahoo. Returns ascending by date."""
    df = _try_fetch_history_tushare(stock_code, days)
    if df is not None and not df.empty:
        return df
    df = _try_fetch_history_yahoo(stock_code, days)
    if df is not None and not df.empty:
        return df
    df = _try_fetch_history_sina_kline(stock_code, days)
    return df


def _ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def compute_indicators(df: 'pd.DataFrame') -> dict:
    """Compute MA/RSI/MACD from historical close series.
    df columns: date, open, high, low, close, volume
    """
    import pandas as pd
    s = df['close'].astype(float).copy()
    out = {}
    # MA
    out['ma5'] = float(s.rolling(5).mean().iloc[-1]) if len(s) >= 5 else None
    out['ma20'] = float(s.rolling(20).mean().iloc[-1]) if len(s) >= 20 else None
    out['ma60'] = float(s.rolling(60).mean().iloc[-1]) if len(s) >= 60 else None
    # RSI(14)
    if len(s) >= 15:
        delta = s.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        roll_up = gain.rolling(14).mean()
        roll_down = loss.rolling(14).mean()
        rs = roll_up / (roll_down.replace(0, pd.NA))
        rsi = 100 - (100 / (1 + rs))
        out['rsi14'] = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None
    else:
        out['rsi14'] = None
    # MACD (12,26,9)
    if len(s) >= 26:
        ema12 = _ema(s, 12)
        ema26 = _ema(s, 26)
        macd_line = ema12 - ema26
        signal = _ema(macd_line, 9)
        hist = macd_line - signal
        out['macd'] = float(macd_line.iloc[-1]) if pd.notna(macd_line.iloc[-1]) else None
        out['macd_signal'] = float(signal.iloc[-1]) if pd.notna(signal.iloc[-1]) else None
        out['macd_hist'] = float(hist.iloc[-1]) if pd.notna(hist.iloc[-1]) else None
    else:
        out['macd'] = out['macd_signal'] = out['macd_hist'] = None
    return out
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
        
        # Prefer real historical K-line for technical part when not offline
        if not is_offline_mode():
            import pandas as pd
            hist = fetch_history_df(stock_code, days=120)
            sina = fetch_sina_realtime_sync(stock_code)
            if hist is not None and not hist.empty:
                inds = compute_indicators(hist)
                price = float(hist['close'].iloc[-1]) if 'close' in hist.columns else (sina.get('current_price') if sina else None)
                result = {
                    'stock_code': stock_code,
                    'company_name': (sina.get('company_name') if sina else stock_code),
                    'current_price': price,
                    'analysis_timestamp': datetime.now().isoformat(),
                }
                if analysis_type in ['technical', 'all']:
                    # Derive trend based on MA alignment and MACD sign
                    ma20 = inds.get('ma20')
                    macd = inds.get('macd')
                    trend = 'neutral'
                    if price and ma20 and macd is not None:
                        if price > ma20 and macd > 0:
                            trend = 'bullish'
                        elif price < ma20 and macd < 0:
                            trend = 'bearish'
                    strength = 0.0
                    if price and ma20:
                        strength = min(1.0, abs(price - ma20) / (ma20 * 0.05))  # 距离MA20的相对偏离
                    tech = {
                        'overall_trend': trend,
                        'trend_strength': round(strength, 2),
                        'support_levels': [round(price * 0.95, 2), round(price * 0.9, 2)] if price else [],
                        'resistance_levels': [round(price * 1.05, 2), round(price * 1.1, 2)] if price else [],
                        'indicators': {
                            'ma5': inds.get('ma5'),
                            'ma20': inds.get('ma20'),
                            'ma60': inds.get('ma60'),
                            'rsi14': inds.get('rsi14'),
                            'macd': inds.get('macd'),
                            'macd_signal': inds.get('macd_signal'),
                            'macd_hist': inds.get('macd_hist')
                        },
                        'source': 'tushare/yahoo'
                    }
                    result['technical_analysis'] = tech
                if analysis_type in ['fundamental', 'all']:
                    fundamentals = fundamental_data_provider.get_fundamental_analysis(
                        stock_code, price_hint=price
                    )
                    if fundamentals:
                        fundamentals = {**fundamentals, 'degraded': False}
                        valuation = fundamentals.get('valuation') or {}
                        if price:
                            eps = valuation.get('eps')
                            bvps = valuation.get('book_value_per_share')
                            if eps not in (None, 0):
                                valuation['pe_ratio'] = round(price / eps, 2)
                            if bvps not in (None, 0):
                                valuation['pb_ratio'] = round(price / bvps, 2)
                        fundamentals['valuation'] = valuation
                    else:
                        fundamentals = {
                            'degraded': True,
                            'note': '未接入真实基本面数据',
                            'source': 'fallback'
                        }
                    result['fundamental_analysis'] = fundamentals

                if analysis_type in ['sentiment', 'all']:
                    sentiment = sentiment_data_provider.get_sentiment_analysis(stock_code)
                    if sentiment:
                        sentiment = {**sentiment, 'degraded': False}
                    else:
                        sentiment = {
                            'degraded': True,
                            'note': '未接入真实情绪数据',
                            'source': 'fallback'
                        }
                    result['sentiment_analysis'] = sentiment

                if analysis_type == 'all':
                    # 综合技术 / 基本面 / 情绪得分
                    tech_score = 0.0
                    trend = result['technical_analysis']['overall_trend']
                    if trend == 'bullish':
                        tech_score = 7.5 if (inds.get('rsi14') and inds['rsi14'] < 70) else 6.0
                    elif trend == 'neutral':
                        tech_score = 5.0
                    else:
                        tech_score = 3.5 if (inds.get('rsi14') and inds['rsi14'] < 30) else 2.5

                    def _fundamental_score(data: Dict) -> Optional[float]:
                        if not data or data.get('degraded'):
                            return None
                        valuation = data.get('valuation', {})
                        profitability = data.get('profitability', {})
                        growth = data.get('growth', {})
                        score = 5.0
                        pe = valuation.get('pe_ratio')
                        if isinstance(pe, (int, float)):
                            if pe <= 15:
                                score += 1.0
                            elif pe >= 40:
                                score -= 1.0
                        roe = profitability.get('roe')
                        if isinstance(roe, (int, float)):
                            score += max(-1.5, min(1.5, (roe - 0.1) * 30))
                        revenue_growth = growth.get('revenue_growth')
                        if isinstance(revenue_growth, (int, float)):
                            score += max(-1.0, min(1.5, revenue_growth * 10))
                        return round(min(max(score, 0.0), 10.0), 2)

                    def _sentiment_score(data: Dict) -> Optional[float]:
                        if not data or data.get('degraded'):
                            return None
                        overall = data.get('overall_sentiment')
                        if isinstance(overall, (int, float)):
                            return round(min(max(overall * 10, 0.0), 10.0), 2)
                        return None

                    scores = [tech_score]
                    fund_score = _fundamental_score(result.get('fundamental_analysis'))
                    if fund_score is not None:
                        scores.append(fund_score)
                    sent_score = _sentiment_score(result.get('sentiment_analysis'))
                    if sent_score is not None:
                        scores.append(sent_score)

                    final_score = sum(scores) / len(scores)
                    action = '买入' if final_score >= 7 else '持有' if final_score >= 5 else '观望'
                    risk = '低风险' if final_score >= 7 else '中等风险' if final_score >= 5 else '高风险'
                    result['recommendation'] = {
                        'action': action,
                        'confidence': round(min(1.0, final_score / 10.0), 2),
                        'score': round(final_score, 1),
                        'risk_level': risk,
                        'source': 'multi-factor'
                    }
                return jsonify(result)
        
        # Offline or realtime failed → try mock to keep API usable
        if is_offline_mode():
            logger.info(f"Using mock data for analysis: {stock_code}")
            result = mock_data_service.get_stock_analysis(stock_code, analysis_type)
            if not result:
                return jsonify({'error': 'Stock not found in mock data'}), 404
            return jsonify(result)
        
        # Fallback: database info with neutral technicals
        db_session = get_current_session()
        stock = db_session.query(Stock).filter_by(code=stock_code).first()
        if not stock:
            return jsonify({'error': 'Stock not found'}), 404
        latest_price = db_session.query(StockPrice).filter_by(
            stock_code=stock_code
        ).order_by(StockPrice.timestamp.desc()).first()
        price = latest_price.close_price if latest_price else None
        result = {
            'stock_code': stock_code,
            'company_name': stock.name,
            'current_price': price,
            'analysis_timestamp': datetime.now().isoformat(),
            'technical_analysis': {
                'overall_trend': 'neutral',
                'trend_strength': 0.5,
                'support_levels': [round(price * 0.95, 2), round(price * 0.9, 2)] if price else [],
                'resistance_levels': [round(price * 1.05, 2), round(price * 1.1, 2)] if price else [],
                'indicators': {}
            }
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
        # Prefer real-time external source when not offline
        if not is_offline_mode():
            sina = fetch_sina_realtime_sync(stock_code)
            if sina:
                # Derive intraday change pct if possible
                change_pct = 0.0
                if sina.get('previous_close'):
                    change_pct = (sina['current_price'] - sina['previous_close']) / sina['previous_close'] * 100
                result = {
                    'stock_code': stock_code,
                    'current_price': sina['current_price'],
                    'price_change': round(change_pct, 2),
                    'volume': sina['volume'],
                    'timestamp': sina['timestamp'],
                    'market_status': 'unknown',
                    'source': 'sina'
                }
                return jsonify(result)
        
        # Fallbacks
        if is_offline_mode():
            logger.info(f"Using mock data for realtime (offline): {stock_code}")
            result = mock_data_service.get_realtime_data(stock_code)
            if result:
                return jsonify(result)
        
        db_session = get_current_session()
        if db_session:
            latest_price = db_session.query(StockPrice).filter_by(
                stock_code=stock_code
            ).order_by(StockPrice.timestamp.desc()).first()
            if latest_price:
                result = {
                    'stock_code': stock_code,
                    'current_price': latest_price.close_price,
                    'price_change': latest_price.change_pct,
                    'volume': latest_price.volume,
                    'timestamp': latest_price.timestamp.isoformat(),
                    'market_status': 'closed',
                    'source': 'database'
                }
                return jsonify(result)
        
        return jsonify({'error': 'No price data available'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/<stock_code>/history', methods=['GET'])
@require_stock_code
@cached(ttl=3600, tags=['historical_data'], key_func=lambda stock_code: f"history:{stock_code}")
def get_historical_data(stock_code: str):
    """Get historical price data"""
    try:
        db_session = get_current_session()
        
        # Parse query parameters
        days = min(365, max(1, request.args.get('days', 30, type=int)))
        start_date = datetime.now() - timedelta(days=days)
        
        data: list = []
        source = 'database'
        
        # Try database first if session is available
        if db_session:
            prices = db_session.query(StockPrice).filter(
                StockPrice.stock_code == stock_code,
                StockPrice.timestamp >= start_date
            ).order_by(StockPrice.timestamp.desc()).limit(max(100, days)).all()
            for price in prices:
                data.append({
                    'date': price.timestamp.strftime('%Y-%m-%d'),
                    'open': float(price.open_price),
                    'high': float(price.high_price),
                    'low': float(price.low_price),
                    'close': float(price.close_price),
                    'volume': int(price.volume) if price.volume is not None else 0
                })
        
        # If no DB data (or no session), and not offline → fetch from network
        if (not data) and (not is_offline_mode()):
            import pandas as pd  # noqa: F401
            df = fetch_history_df(stock_code, days=days)
            if df is not None and not df.empty:
                source = 'tushare/yahoo/sina'
                # Ensure required columns
                for _, row in df.iterrows():
                    dt = row['date']
                    # Accept datetime or string
                    date_str = dt.strftime('%Y-%m-%d') if hasattr(dt, 'strftime') else str(dt)[:10]
                    data.append({
                        'date': date_str,
                        'open': float(row.get('open', 0) or 0),
                        'high': float(row.get('high', 0) or 0),
                        'low': float(row.get('low', 0) or 0),
                        'close': float(row.get('close', 0) or 0),
                        'volume': int(row.get('volume', 0) or 0)
                    })
        
        result = {
            'stock_code': stock_code,
            'period': f"{days}d",
            'data_count': len(data),
            'data': data,
            'source': source
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/batch_analysis', methods=['POST'])
@monitor_performance(operation_type='batch_analysis', component='api')
def batch_analysis():
    """Batch analysis for multiple stocks"""
    try:
        try:
            data = request.get_json()
        except Exception as e:
            raise ValidationError(f"Invalid JSON format: {str(e)}")
            
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
        return jsonify({'error': 'validation_error', 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Health check endpoint
@stock_bp.route('/health', methods=['GET'])
def health_check():
    """API health check with detailed status"""
    from src.database import db_manager
    
    # Get database health status
    try:
        db_health = db_manager.health_check()
        if not isinstance(db_health, dict):
            # Fallback for older implementation that might return bool
            db_health = {
                'status': 'healthy' if db_health else 'unavailable',
                'initialized': bool(db_health),
                'fallback_mode': False
            }
    except Exception as e:
        db_health = {
            'status': 'unavailable',
            'initialized': False,
            'fallback_mode': False,
            'error': str(e)
        }
    
    # Overall system status
    overall_status = 'healthy'
    if db_health.get('status') == 'degraded':
        overall_status = 'degraded'
    elif db_health.get('status') in ['unhealthy', 'unavailable']:
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
    
    # Backward compatible summary field for tests/dashboards
    response_data['services'] = {
        'database': db_health.get('status', 'unknown'),
        'api': 'running',
        'cache': response_data['middleware']['cache'],
        'rate_limiter': response_data['middleware']['rate_limiter'],
    }
    
    status_code = 200 if overall_status in ['healthy', 'degraded'] else 503
    return jsonify(response_data), status_code
