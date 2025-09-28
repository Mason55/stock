# simple_real_data_test.py - Simple real data test without complex dependencies
import asyncio
import yfinance as yf
import aiohttp
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_yahoo_finance_direct():
    """Direct test of Yahoo Finance using yfinance"""
    print("🔍 Testing Yahoo Finance (direct yfinance)...")
    print("-" * 50)
    
    test_symbols = {
        '000001.SZ': '000001.SZ',  # 平安银行 - 深交所
        '600036.SH': '600036.SS',  # 招商银行 - 上交所改为.SS
        '700.HK': '0700.HK',       # 腾讯控股 - 港股
        '9988.HK': '9988.HK'       # 阿里巴巴 - 港股
    }
    
    for original, yf_symbol in test_symbols.items():
        try:
            print(f"\nTesting {original} (Yahoo: {yf_symbol})...")
            
            # Get stock info
            stock = yf.Ticker(yf_symbol)
            info = stock.info
            hist = stock.history(period="2d")
            
            if not hist.empty:
                latest = hist.iloc[-1]
                previous = hist.iloc[-2] if len(hist) > 1 else latest
                
                change_pct = (latest['Close'] - previous['Close']) / previous['Close'] * 100
                
                print(f"✅ {original} - {info.get('longName', 'N/A')}")
                print(f"   Price: {latest['Close']:.2f}")
                print(f"   Change: {change_pct:.2f}%")
                print(f"   Volume: {int(latest['Volume']):,}")
                print(f"   Market Cap: {info.get('marketCap', 'N/A')}")
            else:
                print(f"❌ No historical data for {original}")
                
        except Exception as e:
            print(f"❌ Error fetching {original}: {e}")


async def test_sina_finance_direct():
    """Direct test of Sina Finance API"""
    print("\n📈 Testing Sina Finance (direct HTTP)...")
    print("-" * 50)
    
    test_symbols = {
        '000001.SZ': 'sz000001',    # 平安银行
        '600036.SH': 'sh600036',    # 招商银行  
        '700.HK': 'rt_hk00700'      # 腾讯控股
    }
    
    base_url = "https://hq.sinajs.cn/list="
    
    for original, sina_symbol in test_symbols.items():
        try:
            print(f"\nTesting {original} (Sina: {sina_symbol})...")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}{sina_symbol}") as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        if 'hq_str_' in content and '"' in content:
                            data_line = content.split('"')[1]
                            fields = data_line.split(',')
                            
                            if len(fields) >= 10:
                                if original.endswith(('.SZ', '.SH')):
                                    # A股数据格式
                                    name = fields[0]
                                    price = float(fields[3]) if fields[3] else 0
                                    previous_close = float(fields[2]) if fields[2] else 0
                                    volume = int(fields[8]) if fields[8] else 0
                                    
                                elif original.endswith('.HK'):
                                    # 港股数据格式  
                                    name = fields[1]
                                    price = float(fields[6]) if fields[6] else 0
                                    previous_close = float(fields[3]) if fields[3] else 0
                                    volume = int(fields[12]) if fields[12] else 0
                                
                                change_pct = ((price - previous_close) / previous_close * 100) if previous_close > 0 else 0
                                
                                print(f"✅ {original} - {name}")
                                print(f"   Price: {price:.2f}")
                                print(f"   Change: {change_pct:.2f}%") 
                                print(f"   Volume: {volume:,}")
                            else:
                                print(f"❌ Insufficient data fields for {original}")
                        else:
                            print(f"❌ No valid data in response for {original}")
                    else:
                        print(f"❌ HTTP {response.status} for {original}")
                        
        except Exception as e:
            print(f"❌ Error fetching {original}: {e}")


async def test_batch_yfinance():
    """Test batch fetching with yfinance"""
    print("\n🚀 Testing Batch Fetch (yfinance)...")
    print("-" * 50)
    
    symbols = ['0700.HK', '9988.HK', '000001.SZ']
    
    try:
        # yfinance supports batch download
        data = yf.download(symbols, period="2d", progress=False)
        
        if not data.empty:
            print(f"✅ Batch fetch successful for {len(symbols)} symbols")
            
            for symbol in symbols:
                try:
                    if len(symbols) > 1:
                        # Multi-symbol data has symbol in columns
                        close_prices = data['Close'][symbol].dropna()
                    else:
                        close_prices = data['Close'].dropna()
                    
                    if len(close_prices) >= 2:
                        latest_price = close_prices.iloc[-1]
                        prev_price = close_prices.iloc[-2]
                        change_pct = (latest_price - prev_price) / prev_price * 100
                        
                        print(f"   {symbol}: {latest_price:.2f} ({change_pct:+.2f}%)")
                    else:
                        print(f"   {symbol}: Insufficient price data")
                        
                except Exception as e:
                    print(f"   {symbol}: Error processing - {e}")
        else:
            print("❌ No batch data retrieved")
            
    except Exception as e:
        print(f"❌ Batch fetch error: {e}")


async def main():
    print("🚀 Simple Real Stock Data Testing")
    print("=" * 60)
    
    await test_yahoo_finance_direct()
    await test_sina_finance_direct() 
    await test_batch_yfinance()
    
    print("\n✨ Testing completed!")
    print("\n💡 Summary:")
    print("   - Yahoo Finance: Global stocks, stable API") 
    print("   - Sina Finance: A-share + HK, free but unofficial")
    print("   - Both support real-time data with good coverage")


if __name__ == '__main__':
    asyncio.run(main())