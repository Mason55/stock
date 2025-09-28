# simple_real_app.py - Simple stock app with real Sina Finance data
import asyncio
import aiohttp
import json
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Sina Finance API configuration
SINA_BASE_URL = "https://hq.sinajs.cn/list="
SINA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://finance.sina.com.cn/',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Stock database
STOCK_DATABASE = {
    # A-share stocks
    '000001.SZ': {'name': '平安银行', 'sina_code': 'sz000001', 'currency': 'CNY', 'industry': '银行'},
    '000002.SZ': {'name': '万科A', 'sina_code': 'sz000002', 'currency': 'CNY', 'industry': '房地产'},
    '000858.SZ': {'name': '五粮液', 'sina_code': 'sz000858', 'currency': 'CNY', 'industry': '白酒'},
    '000977.SZ': {'name': '浪潮信息', 'sina_code': 'sz000977', 'currency': 'CNY', 'industry': '计算机'},
    '600000.SH': {'name': '浦发银行', 'sina_code': 'sh600000', 'currency': 'CNY', 'industry': '银行'},
    '600036.SH': {'name': '招商银行', 'sina_code': 'sh600036', 'currency': 'CNY', 'industry': '银行'},
    '600519.SH': {'name': '贵州茅台', 'sina_code': 'sh600519', 'currency': 'CNY', 'industry': '白酒'},
    '600900.SH': {'name': '长江电力', 'sina_code': 'sh600900', 'currency': 'CNY', 'industry': '电力'},
    '601127.SH': {'name': '赛力斯', 'sina_code': 'sh601127', 'currency': 'CNY', 'industry': '汽车制造'},
    '600418.SH': {'name': '江淮汽车', 'sina_code': 'sh600418', 'currency': 'CNY', 'industry': '汽车制造'},
    
    # Hong Kong stocks  
    '700.HK': {'name': '腾讯控股', 'sina_code': 'rt_hk00700', 'currency': 'HKD', 'industry': '互联网'},
    '9988.HK': {'name': '阿里巴巴-SW', 'sina_code': 'rt_hk09988', 'currency': 'HKD', 'industry': '互联网'},
    '3690.HK': {'name': '美团-W', 'sina_code': 'rt_hk03690', 'currency': 'HKD', 'industry': '互联网'},
    '1810.HK': {'name': '小米集团-W', 'sina_code': 'rt_hk01810', 'currency': 'HKD', 'industry': '科技'},
}


async def fetch_sina_data(stock_code: str):
    """Fetch real data from Sina Finance"""
    if stock_code not in STOCK_DATABASE:
        return None
    
    stock_info = STOCK_DATABASE[stock_code]
    sina_code = stock_info['sina_code']
    
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout, headers=SINA_HEADERS) as session:
            async with session.get(f"{SINA_BASE_URL}{sina_code}") as response:
                if response.status != 200:
                    return None
                
                content = await response.text()
                
                if 'hq_str_' not in content or '"' not in content:
                    return None
                
                data_line = content.split('"')[1]
                if not data_line.strip():
                    return None
                
                fields = data_line.split(',')
                
                if stock_code.endswith(('.SZ', '.SH')):
                    # A-share format
                    if len(fields) < 32:
                        return None
                    
                    return {
                        'code': stock_code,
                        'name': fields[0],
                        'current_price': float(fields[3]) if fields[3] else 0,
                        'previous_close': float(fields[2]) if fields[2] else 0,
                        'open_price': float(fields[1]) if fields[1] else 0,
                        'high_price': float(fields[4]) if fields[4] else 0,
                        'low_price': float(fields[5]) if fields[5] else 0,
                        'volume': int(fields[8]) if fields[8] else 0,
                        'currency': stock_info['currency'],
                        'industry': stock_info['industry'],
                        'timestamp': datetime.now().isoformat()
                    }
                
                elif stock_code.endswith('.HK'):
                    # HK stock format
                    if len(fields) < 15:
                        return None
                    
                    return {
                        'code': stock_code,
                        'name': fields[1],
                        'current_price': float(fields[6]) if fields[6] else 0,
                        'previous_close': float(fields[3]) if fields[3] else 0,
                        'open_price': float(fields[2]) if fields[2] else 0,
                        'high_price': float(fields[4]) if fields[4] else 0,
                        'low_price': float(fields[5]) if fields[5] else 0,
                        'volume': int(fields[12]) if fields[12] else 0,
                        'currency': stock_info['currency'],
                        'industry': stock_info['industry'],
                        'timestamp': datetime.now().isoformat()
                    }
                
                return None
                
    except Exception as e:
        print(f"Error fetching {stock_code}: {e}")
        return None


def generate_recommendation(stock_data):
    """Generate simple investment recommendation"""
    if not stock_data or stock_data['current_price'] == 0:
        return None
    
    change_pct = ((stock_data['current_price'] - stock_data['previous_close']) / 
                  stock_data['previous_close'] * 100) if stock_data['previous_close'] > 0 else 0
    
    if change_pct > 3:
        action = "hold"
        reasoning = f"股价上涨{change_pct:.2f}%，建议持有观察"
    elif change_pct < -3:
        action = "buy"
        reasoning = f"股价下跌{abs(change_pct):.2f}%，可能是买入机会"
    else:
        action = "hold"
        reasoning = f"股价变动{change_pct:.2f}%，建议持有"
    
    return {
        'action': action,
        'confidence': min(0.9, max(0.5, abs(change_pct) / 10 + 0.6)),
        'reasoning': reasoning,
        'change_pct': change_pct,
        'timestamp': datetime.now().isoformat()
    }


@app.route('/')
def index():
    return {
        'message': 'Real Stock Data API (Sina Finance)',
        'version': '1.0.0',
        'supported_markets': ['A-share', 'Hong Kong'],
        'data_source': 'Sina Finance (Real-time)',
        'endpoints': {
            'stock_info': '/api/stocks/{code}',
            'stock_list': '/api/stocks/list',
            'health': '/api/stocks/health'
        }
    }


@app.route('/api/stocks/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'data_source': 'Sina Finance',
        'supported_stocks': len(STOCK_DATABASE)
    })


@app.route('/api/stocks/<stock_code>')
def get_stock_info(stock_code):
    """Get real-time stock information"""
    stock_code = stock_code.upper()
    
    if stock_code not in STOCK_DATABASE:
        return jsonify({'error': f'Stock {stock_code} not supported'}), 404
    
    # Create async loop for the request
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stock_data = loop.run_until_complete(fetch_sina_data(stock_code))
        loop.close()
    except Exception as e:
        return jsonify({'error': f'Failed to fetch data: {str(e)}'}), 500
    
    if not stock_data:
        return jsonify({'error': f'No data available for {stock_code}'}), 404
    
    # Generate recommendation
    recommendation = generate_recommendation(stock_data)
    
    # Calculate additional metrics
    change_pct = ((stock_data['current_price'] - stock_data['previous_close']) / 
                  stock_data['previous_close'] * 100) if stock_data['previous_close'] > 0 else 0
    
    response = {
        **stock_data,
        'change_pct': change_pct,
        'change_amount': stock_data['current_price'] - stock_data['previous_close'],
        'recommendation': recommendation,
        'market_status': 'REAL_TIME',
        'data_source': 'Sina Finance'
    }
    
    return jsonify(response)


@app.route('/api/stocks/list')
def list_stocks():
    """Get list of supported stocks"""
    stock_list = []
    
    for code, info in STOCK_DATABASE.items():
        stock_list.append({
            'code': code,
            'name': info['name'],
            'currency': info['currency'],
            'industry': info['industry'],
            'exchange': code.split('.')[1]
        })
    
    return jsonify({
        'stocks': stock_list,
        'total': len(stock_list),
        'data_source': 'Sina Finance'
    })


@app.route('/api/stocks/batch')
def get_batch_stocks():
    """Get multiple stocks at once"""
    codes = request.args.get('codes', '').split(',')
    codes = [code.strip().upper() for code in codes if code.strip()]
    
    if not codes:
        return jsonify({'error': 'No stock codes provided'}), 400
    
    results = []
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for code in codes[:10]:  # Limit to 10 stocks
            if code in STOCK_DATABASE:
                stock_data = loop.run_until_complete(fetch_sina_data(code))
                if stock_data:
                    change_pct = ((stock_data['current_price'] - stock_data['previous_close']) / 
                                  stock_data['previous_close'] * 100) if stock_data['previous_close'] > 0 else 0
                    
                    results.append({
                        'code': code,
                        'name': stock_data['name'],
                        'current_price': stock_data['current_price'],
                        'change_pct': change_pct,
                        'volume': stock_data['volume'],
                        'currency': stock_data['currency']
                    })
        
        loop.close()
        
    except Exception as e:
        return jsonify({'error': f'Batch fetch failed: {str(e)}'}), 500
    
    return jsonify({
        'stocks': results,
        'total': len(results),
        'data_source': 'Sina Finance'
    })


if __name__ == '__main__':
    print("🚀 Starting Real Stock Data API Server...")
    print("📊 Data Source: Sina Finance (Real-time)")
    print(f"📈 Supported Stocks: {len(STOCK_DATABASE)}")
    print("🌐 Server: http://localhost:5002")
    print("-" * 50)
    
    app.run(host='0.0.0.0', port=5002, debug=False)