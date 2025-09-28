# real_data_app.py - Stock analysis app with real market data
import json
import asyncio
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.stock import Base, Stock, StockPrice
from src.services.enhanced_data_collector import EnhancedDataCollector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Database setup
engine = create_engine('sqlite:///real_stock_data.db', echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Global data collector
data_collector = None


def init_data_collector():
    """Initialize data collector with real data"""
    global data_collector
    session = Session()
    data_collector = EnhancedDataCollector(session, use_real_data=True)
    return session


@app.route('/')
def index():
    return {
        'message': 'Real Stock Analysis System API',
        'version': '2.0.0',
        'data_source': 'Yahoo Finance + Sina Finance',
        'endpoints': {
            'stocks': '/api/stocks',
            'health': '/api/stocks/health',
            'refresh': '/api/stocks/refresh'
        }
    }


@app.route('/api/stocks/health', methods=['GET'])
def health_check():
    """API health check"""
    try:
        session = Session()
        stock_count = session.query(Stock).count()
        latest_price = session.query(StockPrice).order_by(StockPrice.timestamp.desc()).first()
        
        session.close()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'stock_count': stock_count,
            'latest_update': latest_price.timestamp.isoformat() if latest_price else None,
            'data_source': 'Real Market Data'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@app.route('/api/stocks/refresh', methods=['POST'])
def refresh_data():
    """手动刷新市场数据"""
    try:
        session = init_data_collector()
        
        # 运行数据采集
        async def collect_data():
            await data_collector.run_data_collection()
        
        # 在新的事件循环中运行异步函数
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(collect_data())
        session.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Market data refreshed successfully',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/stocks/<stock_code>', methods=['GET'])
def get_stock_info(stock_code):
    """获取股票详细信息"""
    try:
        session = Session()
        
        # 获取股票基本信息
        stock = session.query(Stock).filter_by(code=stock_code.upper()).first()
        if not stock:
            session.close()
            return jsonify({'error': f'Stock {stock_code} not found'}), 404
        
        # 获取最新价格
        latest_price = session.query(StockPrice).filter_by(
            stock_code=stock_code.upper()
        ).order_by(StockPrice.timestamp.desc()).first()
        
        if not latest_price:
            session.close()
            return jsonify({'error': f'No price data for {stock_code}'}), 404
        
        # 生成简单的投资建议
        change_pct = latest_price.change_pct or 0
        if change_pct > 3:
            action = "hold"
            reasoning = f"股价上涨{change_pct:.2f}%，建议持有观察"
        elif change_pct < -3:
            action = "buy"
            reasoning = f"股价下跌{abs(change_pct):.2f}%，可能是买入机会"
        else:
            action = "hold" 
            reasoning = f"股价变动{change_pct:.2f}%，建议持有"
        
        recommendation = {
            'action': action,
            'confidence': min(0.9, max(0.5, abs(change_pct) / 10 + 0.5)),
            'reasoning': reasoning,
            'stock_code': stock_code.upper(),
            'timestamp': latest_price.timestamp.isoformat()
        }
        
        response = {
            'code': stock.code,
            'name': stock.name,
            'exchange': stock.exchange,
            'industry': stock.industry,
            'currency': stock.currency,
            'current_price': latest_price.close_price,
            'change_pct': latest_price.change_pct,
            'volume': latest_price.volume,
            'open_price': latest_price.open_price,
            'high_price': latest_price.high_price,
            'low_price': latest_price.low_price,
            'last_updated': latest_price.timestamp.isoformat(),
            'recommendation': recommendation,
            'data_source': 'Real Market Data'
        }
        
        session.close()
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting stock info: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocks/list', methods=['GET'])
def list_stocks():
    """获取股票列表"""
    try:
        session = Session()
        
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        stocks = session.query(Stock).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        stock_list = []
        for stock in stocks:
            # 获取最新价格
            latest_price = session.query(StockPrice).filter_by(
                stock_code=stock.code
            ).order_by(StockPrice.timestamp.desc()).first()
            
            stock_data = {
                'code': stock.code,
                'name': stock.name,
                'exchange': stock.exchange,
                'industry': stock.industry,
                'currency': stock.currency
            }
            
            if latest_price:
                stock_data.update({
                    'current_price': latest_price.close_price,
                    'change_pct': latest_price.change_pct,
                    'volume': latest_price.volume,
                    'last_updated': latest_price.timestamp.isoformat()
                })
            
            stock_list.append(stock_data)
        
        total_count = session.query(Stock).count()
        session.close()
        
        return jsonify({
            'stocks': stock_list,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': (total_count + per_page - 1) // per_page
            },
            'data_source': 'Real Market Data'
        })
        
    except Exception as e:
        logger.error(f"Error listing stocks: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocks/scan', methods=['GET'])
def scan_stocks():
    """股票扫描筛选"""
    try:
        session = Session()
        
        # 解析查询参数
        industry = request.args.get('industry', '').strip()
        exchange = request.args.get('exchange', '').strip()
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        min_change = request.args.get('min_change', type=float)
        max_change = request.args.get('max_change', type=float)
        limit = min(request.args.get('limit', 50, type=int), 100)
        
        # 构建查询
        query = session.query(Stock)
        
        if industry:
            query = query.filter(Stock.industry.like(f'%{industry}%'))
        if exchange:
            query = query.filter(Stock.exchange == exchange.upper())
        
        stocks = query.limit(1000).all()  # 先获取基础股票
        
        results = []
        for stock in stocks:
            # 获取最新价格
            latest_price = session.query(StockPrice).filter_by(
                stock_code=stock.code
            ).order_by(StockPrice.timestamp.desc()).first()
            
            if not latest_price:
                continue
            
            # 应用价格筛选
            if min_price and latest_price.close_price < min_price:
                continue
            if max_price and latest_price.close_price > max_price:
                continue
            if min_change and (latest_price.change_pct or 0) < min_change:
                continue  
            if max_change and (latest_price.change_pct or 0) > max_change:
                continue
            
            results.append({
                'code': stock.code,
                'name': stock.name,
                'exchange': stock.exchange,
                'industry': stock.industry,
                'currency': stock.currency,
                'current_price': latest_price.close_price,
                'change_pct': latest_price.change_pct,
                'volume': latest_price.volume,
                'last_updated': latest_price.timestamp.isoformat()
            })
            
            if len(results) >= limit:
                break
        
        session.close()
        
        return jsonify({
            'total_found': len(results),
            'stocks': results,
            'filters_applied': {
                'industry': industry if industry else None,
                'exchange': exchange if exchange else None,
                'min_price': min_price,
                'max_price': max_price,
                'min_change': min_change,
                'max_change': max_change
            },
            'data_source': 'Real Market Data'
        })
        
    except Exception as e:
        logger.error(f"Error scanning stocks: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # 初始化数据
    logger.info("Initializing real stock data application...")
    
    try:
        session = init_data_collector()
        
        # 检查是否需要初始化数据
        stock_count = session.query(Stock).count()
        if stock_count == 0:
            logger.info("No stocks found, initializing with market data...")
            
            # 运行初始数据采集
            async def init_data():
                await data_collector.run_data_collection()
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            loop.run_until_complete(init_data())
            logger.info("Initial data collection completed")
        else:
            logger.info(f"Found {stock_count} stocks in database")
        
        session.close()
        
    except Exception as e:
        logger.error(f"Error during initialization: {e}")
    
    # 启动应用
    logger.info("Starting Real Stock Analysis System on http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)