# test_real_data.py - Test real data fetching
import asyncio
import sys
import logging
sys.path.append('.')

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_yahoo_finance():
    """Test Yahoo Finance data provider"""
    from src.services.real_data_provider import YahooFinanceProvider
    
    provider = YahooFinanceProvider()
    
    test_symbols = ['000001.SZ', '700.HK', '9988.HK', '600036.SH']
    
    print("🔍 Testing Yahoo Finance Provider...")
    print("-" * 50)
    
    for symbol in test_symbols:
        try:
            print(f"\nTesting {symbol}...")
            quote = await provider.get_quote(symbol)
            
            if quote:
                print(f"✅ {symbol} - {quote.name}")
                print(f"   Price: {quote.price} {quote.currency}")
                print(f"   Change: {quote.change_percent:.2f}%")
                print(f"   Volume: {quote.volume:,}")
            else:
                print(f"❌ No data for {symbol}")
                
        except Exception as e:
            print(f"❌ Error fetching {symbol}: {e}")
    
    # Test batch fetching
    print(f"\n🚀 Testing batch fetch...")
    try:
        quotes = await provider.get_batch_quotes(test_symbols)
        print(f"✅ Batch fetch successful: {len(quotes)} quotes")
        for quote in quotes:
            print(f"   {quote.symbol}: {quote.price} {quote.currency}")
    except Exception as e:
        print(f"❌ Batch fetch error: {e}")


async def test_sina_finance():
    """Test Sina Finance data provider"""
    from src.services.real_data_provider import SinaFinanceProvider
    
    provider = SinaFinanceProvider()
    
    test_symbols = ['000001.SZ', '600036.SH', '700.HK']
    
    print("\n📈 Testing Sina Finance Provider...")
    print("-" * 50)
    
    for symbol in test_symbols:
        try:
            print(f"\nTesting {symbol}...")
            quote = await provider.get_quote(symbol)
            
            if quote:
                print(f"✅ {symbol} - {quote.name}")
                print(f"   Price: {quote.price} {quote.currency}")
                print(f"   Change: {quote.change_percent:.2f}%")
                print(f"   Volume: {quote.volume:,}")
            else:
                print(f"❌ No data for {symbol}")
                
        except Exception as e:
            print(f"❌ Error fetching {symbol}: {e}")


async def test_real_data_manager():
    """Test Real Data Manager with fallback"""
    from src.services.real_data_provider import RealDataManager
    
    manager = RealDataManager(primary_provider='yahoo')
    
    test_symbols = ['700.HK', '000001.SZ', '9988.HK']
    
    print("\n🎯 Testing Real Data Manager (with fallback)...")
    print("-" * 50)
    
    for symbol in test_symbols:
        try:
            print(f"\nTesting {symbol}...")
            quote = await manager.get_quote(symbol)
            
            if quote:
                print(f"✅ {symbol} - {quote.name}")
                print(f"   Price: {quote.price} {quote.currency}")
                print(f"   Change: {quote.change_percent:.2f}%")
                print(f"   Market Cap: {quote.market_cap}")
            else:
                print(f"❌ No data for {symbol}")
                
        except Exception as e:
            print(f"❌ Error fetching {symbol}: {e}")


async def main():
    print("🚀 Real Stock Data Testing")
    print("=" * 50)
    
    # Test individual providers
    await test_yahoo_finance()
    await test_sina_finance()
    
    # Test manager with fallback
    await test_real_data_manager()
    
    print("\n✨ Testing completed!")


if __name__ == '__main__':
    asyncio.run(main())