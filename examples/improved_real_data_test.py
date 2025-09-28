# improved_real_data_test.py - Improved real data test with better handling
import asyncio
import aiohttp
import yfinance as yf
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_yahoo_with_delay():
    """Test Yahoo Finance with delays and better error handling"""
    print("🔍 Testing Yahoo Finance (with delays)...")
    print("-" * 50)
    
    test_symbols = [
        ('000001.SZ', '000001.SZ', '平安银行'),
        ('600036.SH', '600036.SS', '招商银行'),
        ('700.HK', '0700.HK', '腾讯控股')
    ]
    
    success_count = 0
    
    for original, yf_symbol, name in test_symbols:
        try:
            print(f"\nTesting {original} ({name})...")
            
            # Add delay to avoid rate limiting
            await asyncio.sleep(2)
            
            stock = yf.Ticker(yf_symbol)
            
            # Try to get basic info first
            info = stock.info
            if info and 'symbol' in info:
                print(f"✅ Basic info available for {original}")
                print(f"   Symbol: {info.get('symbol', 'N/A')}")
                print(f"   Name: {info.get('longName', name)}")
                print(f"   Currency: {info.get('currency', 'N/A')}")
                print(f"   Market Cap: {info.get('marketCap', 'N/A')}")
                success_count += 1
            else:
                print(f"❌ No info data for {original}")
                
            # Try to get price data  
            hist = stock.history(period="1d")
            if not hist.empty:
                latest = hist.iloc[-1]
                print(f"   Latest Price: {latest['Close']:.2f}")
                print(f"   Volume: {int(latest['Volume']):,}")
            else:
                print(f"   No price history available")
                
        except Exception as e:
            print(f"❌ Error fetching {original}: {e}")
            
        # Longer delay between requests
        await asyncio.sleep(3)
    
    return success_count


async def test_sina_with_headers():
    """Test Sina Finance with proper headers"""
    print("\n📈 Testing Sina Finance (with headers)...")
    print("-" * 50)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://finance.sina.com.cn/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    test_symbols = [
        ('000001.SZ', 'sz000001', '平安银行'),
        ('600036.SH', 'sh600036', '招商银行')
    ]
    
    base_url = "https://hq.sinajs.cn/list="
    success_count = 0
    
    for original, sina_symbol, expected_name in test_symbols:
        try:
            print(f"\nTesting {original} ({expected_name})...")
            await asyncio.sleep(1)
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(f"{base_url}{sina_symbol}") as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        if 'hq_str_' in content and '"' in content:
                            data_line = content.split('"')[1]
                            if data_line.strip():
                                fields = data_line.split(',')
                                
                                if len(fields) >= 10:
                                    name = fields[0]
                                    price = float(fields[3]) if fields[3] else 0
                                    previous_close = float(fields[2]) if fields[2] else 0
                                    volume = int(fields[8]) if fields[8] else 0
                                    
                                    change_pct = ((price - previous_close) / previous_close * 100) if previous_close > 0 else 0
                                    
                                    print(f"✅ {original} - {name}")
                                    print(f"   Price: {price:.2f} CNY")
                                    print(f"   Change: {change_pct:+.2f}%")
                                    print(f"   Volume: {volume:,}")
                                    success_count += 1
                                else:
                                    print(f"❌ Insufficient data fields: {len(fields)}")
                            else:
                                print(f"❌ Empty data response for {original}")
                        else:
                            print(f"❌ Invalid response format for {original}")
                    else:
                        print(f"❌ HTTP {response.status} for {original}")
                        
        except Exception as e:
            print(f"❌ Error fetching {original}: {e}")
    
    return success_count


async def test_alternative_apis():
    """Test alternative free APIs"""
    print("\n🔄 Testing Alternative APIs...")
    print("-" * 50)
    
    # Test Alpha Vantage (requires free API key)
    # Test Financial Modeling Prep (requires free API key)
    # Test IEX Cloud (has free tier)
    
    print("💡 Alternative data sources to consider:")
    print("   1. Alpha Vantage - Free tier: 5 calls/min, 500 calls/day")
    print("   2. IEX Cloud - Free tier available")  
    print("   3. Financial Modeling Prep - Free tier available")
    print("   4. Polygon.io - Free tier for delayed data")
    print("   5. Quandl (now part of Nasdaq) - Some free datasets")
    print("\n   For production use, consider getting API keys from above providers.")


async def test_mock_data_fallback():
    """Test mock data generation as fallback"""
    print("\n🎭 Testing Mock Data Fallback...")
    print("-" * 50)
    
    import random
    
    test_symbols = ['000001.SZ', '600036.SH', '700.HK', '9988.HK']
    
    for symbol in test_symbols:
        # Generate realistic mock data
        if symbol.endswith('.HK'):
            base_price = random.uniform(50, 500)
            currency = 'HKD'
            volume_range = (1000000, 50000000)
        else:
            base_price = random.uniform(10, 100)
            currency = 'CNY'
            volume_range = (100000, 10000000)
        
        change_pct = random.uniform(-10, 10)
        volume = random.randint(*volume_range)
        
        print(f"✅ {symbol} (Mock Data)")
        print(f"   Price: {base_price:.2f} {currency}")
        print(f"   Change: {change_pct:+.2f}%")
        print(f"   Volume: {volume:,}")
        print(f"   Timestamp: {datetime.now().isoformat()}")
    
    print("\n💡 Mock data provides consistent fallback when real APIs are unavailable")


async def main():
    print("🚀 Improved Real Stock Data Testing")
    print("=" * 60)
    
    yahoo_success = await test_yahoo_with_delay()
    sina_success = await test_sina_with_headers()
    
    await test_alternative_apis()
    await test_mock_data_fallback()
    
    print(f"\n📊 Results Summary:")
    print(f"   Yahoo Finance: {yahoo_success} successful")
    print(f"   Sina Finance: {sina_success} successful") 
    
    print(f"\n💭 Recommendations:")
    if yahoo_success == 0 and sina_success == 0:
        print("   ⚠️  Both APIs are blocked/limited. Consider:")
        print("   1. Using proxy/VPN")
        print("   2. Getting official API keys")
        print("   3. Using mock data for development")
        print("   4. Implementing retry logic with exponential backoff")
    elif yahoo_success > sina_success:
        print("   ✅ Yahoo Finance is working better - use as primary")
    elif sina_success > yahoo_success:
        print("   ✅ Sina Finance is working better - use as primary")
    else:
        print("   ✅ Both APIs working - implement with fallback")
    
    print("\n✨ Testing completed!")


if __name__ == '__main__':
    asyncio.run(main())