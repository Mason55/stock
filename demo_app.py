# demo_app.py - Simplified demo version for stock query
import json
import random
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np

app = Flask(__name__)
CORS(app)

# Mock stock database (A-share + HK stocks)
MOCK_STOCKS = {
    # A-share stocks
    "601127.SH": {
        "code": "601127.SH", 
        "name": "赛力斯",
        "exchange": "SH",
        "industry": "汽车制造",
        "market_cap": 1250.5,
        "base_price": 85.32,
        "currency": "CNY"
    },
    "000977.SZ": {
        "code": "000977.SZ",
        "name": "浪潮信息",
        "exchange": "SZ", 
        "industry": "计算机设备",
        "market_cap": 856.8,
        "base_price": 38.45,
        "currency": "CNY"
    },
    "600900.SH": {
        "code": "600900.SH",
        "name": "长江电力",
        "exchange": "SH",
        "industry": "电力行业", 
        "market_cap": 5420.3,
        "base_price": 24.18,
        "currency": "CNY"
    },
    "000001.SZ": {
        "code": "000001.SZ",
        "name": "平安银行", 
        "exchange": "SZ",
        "industry": "银行",
        "market_cap": 2856.7,
        "base_price": 14.58,
        "currency": "CNY"
    },
    # Hong Kong stocks
    "700.HK": {
        "code": "700.HK",
        "name": "腾讯控股",
        "exchange": "HK",
        "industry": "互联网",
        "market_cap": 28500.0,
        "base_price": 335.0,
        "currency": "HKD"
    },
    "9988.HK": {
        "code": "9988.HK",
        "name": "阿里巴巴-SW",
        "exchange": "HK", 
        "industry": "互联网",
        "market_cap": 15800.0,
        "base_price": 78.5,
        "currency": "HKD"
    },
    "3690.HK": {
        "code": "3690.HK",
        "name": "美团-W",
        "exchange": "HK",
        "industry": "互联网",
        "market_cap": 8900.0,
        "base_price": 148.0,
        "currency": "HKD"
    },
    "1810.HK": {
        "code": "1810.HK",
        "name": "小米集团-W",
        "exchange": "HK",
        "industry": "智能手机",
        "market_cap": 4200.0,
        "base_price": 17.2,
        "currency": "HKD"
    }
}

def generate_mock_price_data(stock_code, days=30):
    """Generate mock historical price data"""
    if stock_code not in MOCK_STOCKS:
        return []
    
    base_price = MOCK_STOCKS[stock_code]["base_price"]
    data = []
    
    for i in range(days):
        date = datetime.now() - timedelta(days=days-i-1)
        
        # Generate realistic price movements
        change_pct = random.uniform(-5, 5)
        price = base_price * (1 + change_pct/100)
        
        data.append({
            'timestamp': date.isoformat(),
            'open': price * 0.998,
            'high': price * 1.025, 
            'low': price * 0.975,
            'close': price,
            'volume': random.randint(1000000, 50000000),
            'change_pct': change_pct
        })
        
        base_price = price  # Carry forward for next day
    
    return data

def calculate_technical_indicators(stock_code):
    """Calculate mock technical indicators"""
    # Generate mock technical indicators for demo
    return {
        'price_momentum_5d': random.uniform(-10, 10),
        'price_momentum_20d': random.uniform(-15, 15), 
        'ma_5_ratio': random.uniform(0.95, 1.05),
        'ma_20_ratio': random.uniform(0.90, 1.10),
        'rsi': random.uniform(20, 80),
        'macd': random.uniform(-2, 2),
        'bb_position': random.uniform(0, 1),
        'volume_ratio': random.uniform(0.5, 2.0),
        'volatility': random.uniform(2, 8),
        'avg_volume': random.randint(5000000, 30000000)
    }

def generate_recommendation(stock_code):
    """Generate mock investment recommendation"""
    if stock_code not in MOCK_STOCKS:
        return None
    
    # Mock ML recommendation based on stock characteristics
    if "赛力斯" in MOCK_STOCKS[stock_code]["name"]:
        # Specific analysis for SERES
        action = "buy"  
        confidence = 0.72
        reasoning = """技术分析显示：1) 新能源汽车行业景气度高，政策支持持续; 2) 公司与华为深度合作，智能化优势明显; 3) 近期成交量放大，资金关注度提升; 4) RSI指标显示超跌反弹机会; 5) 20日均线支撑有效，技术形态良好。建议关注新车型交付情况及华为合作进展。"""
    elif "浪潮信息" in MOCK_STOCKS[stock_code]["name"]:
        # Specific analysis for Inspur
        action = "hold"
        confidence = 0.68
        reasoning = """综合分析显示：1) AI服务器龙头地位稳固，受益于人工智能产业发展; 2) 与OpenAI、百度等头部AI公司深度合作，订单饱满; 3) 但估值相对偏高，短期调整压力较大; 4) 技术指标显示震荡整理，突破方向待定; 5) 建议等待更好买入时机。重点关注AI算力需求变化及新产品发布。"""
    elif "长江电力" in MOCK_STOCKS[stock_code]["name"]:
        # Specific analysis for Yangtze Power
        action = "buy"
        confidence = 0.75
        reasoning = """价值分析显示：1) 水电龙头企业，拥有三峡、葛洲坝等优质水电资产，现金流稳定; 2) 股息率约4.5%，分红政策稳定，适合价值投资; 3) 受益于碳中和政策，清洁能源地位突出; 4) 技术面显示长期上升趋势完好，回调提供买入机会; 5) 防御性强，在市场波动中表现稳健。建议长期持有，关注来水情况及电价政策。"""
    else:
        actions = ['buy', 'hold', 'sell']
        action = random.choice(actions)
        confidence = random.uniform(0.5, 0.9)
        reasoning = f"基于多因子模型分析，当前技术指标偏向{action}，置信度{confidence:.2f}"
    
    return {
        'stock_code': stock_code,
        'action': action,
        'confidence': confidence,
        'reasoning': reasoning,
        'timestamp': datetime.now().isoformat()
    }

# API Routes
@app.route('/api/stocks/<stock_code>')
def get_stock_info(stock_code):
    """Get stock information"""
    if stock_code not in MOCK_STOCKS:
        return jsonify({'error': '股票代码不存在'}), 404
    
    stock = MOCK_STOCKS[stock_code]
    latest_prices = generate_mock_price_data(stock_code, 1)
    latest_price = latest_prices[0] if latest_prices else None
    
    recommendation = generate_recommendation(stock_code)
    
    return jsonify({
        'code': stock['code'],
        'name': stock['name'], 
        'exchange': stock['exchange'],
        'industry': stock['industry'],
        'market_cap': stock['market_cap'],
        'current_price': latest_price['close'] if latest_price else None,
        'change_pct': latest_price['change_pct'] if latest_price else None,
        'volume': latest_price['volume'] if latest_price else None,
        'last_updated': latest_price['timestamp'] if latest_price else None,
        'recommendation': recommendation
    })

@app.route('/api/stocks/<stock_code>/timeline')  
def get_stock_timeline(stock_code):
    """Get historical price data"""
    if stock_code not in MOCK_STOCKS:
        return jsonify({'error': '股票代码不存在'}), 404
        
    range_param = request.args.get('range', '1M')
    
    # Map range to days
    range_days = {
        '1D': 1,
        '1W': 7, 
        '1M': 30,
        '3M': 90,
        '1Y': 365
    }
    
    days = range_days.get(range_param, 30)
    price_data = generate_mock_price_data(stock_code, days)
    
    return jsonify({
        'stock_code': stock_code,
        'range': range_param,
        'data': price_data
    })

@app.route('/api/stocks/<stock_code>/factors')
def get_stock_factors(stock_code):
    """Get factor analysis"""
    if stock_code not in MOCK_STOCKS:
        return jsonify({'error': '股票代码不存在'}), 404
        
    features = calculate_technical_indicators(stock_code)
    recommendation = generate_recommendation(stock_code)
    
    return jsonify({
        'stock_code': stock_code,
        'features': features,
        'recommendation': recommendation,
        'analysis_timestamp': datetime.now().isoformat()
    })

@app.route('/api/stocks/scan')
def scan_stocks():
    """Stock screening"""
    industry = request.args.get('industry')
    action_filter = request.args.get('action')
    
    results = []
    for code, stock in MOCK_STOCKS.items():
        if industry and stock['industry'] != industry:
            continue
            
        latest_prices = generate_mock_price_data(code, 1)
        latest_price = latest_prices[0] if latest_prices else {}
        
        recommendation = generate_recommendation(code)
        if action_filter and recommendation['action'] != action_filter:
            continue
            
        results.append({
            'code': stock['code'],
            'name': stock['name'],
            'industry': stock['industry'], 
            'current_price': latest_price.get('close'),
            'change_pct': latest_price.get('change_pct'),
            'volume': latest_price.get('volume'),
            'recommendation': recommendation
        })
    
    return jsonify({
        'total_found': len(results),
        'stocks': results
    })

@app.route('/api/stocks/recommend/<stock_code>', methods=['POST'])
def generate_fresh_recommendation(stock_code):
    """Generate fresh recommendation"""
    if stock_code not in MOCK_STOCKS:
        return jsonify({'error': '股票代码不存在'}), 404
        
    recommendation = generate_recommendation(stock_code)
    return jsonify(recommendation)

@app.route('/api/stocks/health')
def health_check():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'available_stocks': len(MOCK_STOCKS)
    })

@app.route('/')
def index():
    return jsonify({
        'message': '中国股市分析系统 Demo',
        'available_stocks': list(MOCK_STOCKS.keys()),
        'endpoints': [
            '/api/stocks/{code}',
            '/api/stocks/{code}/timeline', 
            '/api/stocks/{code}/factors',
            '/api/stocks/scan',
            '/api/stocks/health'
        ]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)