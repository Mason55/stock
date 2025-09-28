# enhanced_analyzer_demo.py - 增强版分析器演示
import asyncio
import sys
import os
from datetime import datetime

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.analyzer_factory import StockAnalyzerFactory
from core.stock_config import StockConfigManager
from core.data_sources import DataSourceManager


async def demo_enhanced_features():
    """演示增强功能"""
    print("🚀 增强版股票分析系统演示")
    print("=" * 60)
    
    # 1. 展示支持的股票
    config_manager = StockConfigManager()
    print(f"📊 系统概况:")
    print(f"  支持股票总数: {len(config_manager.get_all_symbols())}")
    print(f"  市场分布: {config_manager.get_market_summary()}")
    print(f"  行业分布: {config_manager.get_industry_summary()}")
    
    # 2. 搜索功能演示
    print(f"\n🔍 搜索功能演示:")
    search_results = config_manager.search_stocks("新能源")
    print(f"搜索'新能源'相关股票:")
    for stock in search_results[:5]:  # 显示前5个结果
        print(f"  {stock.symbol} - {stock.name} ({', '.join(stock.special_features)})")
    
    # 3. 多数据源对比
    print(f"\n📡 多数据源对比:")
    test_symbols = ["601127.SH", "2015.HK"]
    
    for symbol in test_symbols:
        print(f"\n--- {symbol} 数据源对比 ---")
        analyzer = StockAnalyzerFactory.create_analyzer(symbol)
        if analyzer:
            try:
                result = await analyzer.run_analysis()
                quote = result.quote
                if quote:
                    print(f"✅ 成功获取数据")
                    print(f"   价格: {quote.currency}{quote.current_price:.2f}")
                    print(f"   涨跌: {quote.change_pct:+.2f}%")
                    print(f"   成交额: {quote.turnover/100000000:.2f}亿")
                else:
                    print(f"❌ 数据获取失败")
            except Exception as e:
                print(f"❌ 分析失败: {e}")
    
    # 4. 技术指标演示
    print(f"\n📈 技术指标分析演示:")
    analyzer = StockAnalyzerFactory.create_analyzer("601127.SH")
    if analyzer:
        result = await analyzer.run_analysis()
        indicators = result.technical_indicators
        
        if indicators:
            print(f"技术指标 (赛力斯):")
            if indicators.ma5:
                print(f"  MA5:  ¥{indicators.ma5:.2f}")
            if indicators.rsi:
                print(f"  RSI:  {indicators.rsi:.1f}")
            if indicators.macd:
                print(f"  MACD: {indicators.macd:.3f}")
        
        # 信号分析
        print(f"\n技术信号:")
        for signal in result.signals:
            signal_emoji = {'buy': '🟢', 'sell': '🔴', 'neutral': '🟡'}.get(signal.signal, '⚪')
            print(f"  {signal_emoji} {signal.description} (强度: {signal.strength:.1f}, 置信度: {signal.confidence:.1f})")
    
    # 5. 风险评级演示
    print(f"\n⚠️  风险评级演示:")
    test_symbols = ["601127.SH", "600519.SH", "2015.HK"]  # 赛力斯、茅台、理想
    
    for symbol in test_symbols:
        analyzer = StockAnalyzerFactory.create_analyzer(symbol)
        if analyzer:
            try:
                result = await analyzer.run_analysis()
                risk_color = {'LOW': '🟢', 'MEDIUM': '🟡', 'HIGH': '🔴'}.get(result.risk_level, '⚪')
                print(f"  {symbol} ({result.company_name}): {risk_color} {result.risk_level}")
                print(f"    综合评分: {result.overall_score:.2f}")
                print(f"    建议: {result.recommendation}")
            except Exception as e:
                print(f"  {symbol}: ❌ 分析失败")
    
    # 6. 行业对比
    print(f"\n🏭 行业对比 - 汽车制造:")
    auto_stocks = config_manager.get_symbols_by_industry(config_manager._configs['601127.SH'].industry)
    
    auto_results = []
    for symbol in auto_stocks[:3]:  # 取前3个
        analyzer = StockAnalyzerFactory.create_analyzer(symbol)
        if analyzer:
            try:
                result = await analyzer.run_analysis()
                auto_results.append((symbol, result))
            except:
                continue
    
    # 排序并显示
    auto_results.sort(key=lambda x: x[1].overall_score, reverse=True)
    for i, (symbol, result) in enumerate(auto_results):
        print(f"  {i+1}. {result.company_name} ({symbol})")
        print(f"     评分: {result.overall_score:.2f} | 建议: {result.recommendation}")
        if result.quote:
            print(f"     涨跌: {result.quote.change_pct:+.2f}%")
    
    print(f"\n✅ 演示完成!")


async def interactive_analysis():
    """交互式分析"""
    print("\n" + "="*60)
    print("🎯 交互式股票分析")
    print("输入股票代码进行分析，输入 'quit' 退出")
    print("="*60)
    
    while True:
        try:
            user_input = input("\n请输入股票代码 (或 'search:关键词' 搜索): ").strip()
            
            if user_input.lower() == 'quit':
                print("👋 再见!")
                break
            
            if user_input.startswith('search:'):
                keyword = user_input[7:]
                config_manager = StockConfigManager()
                results = config_manager.search_stocks(keyword)
                
                if results:
                    print(f"🔍 找到 {len(results)} 只相关股票:")
                    for stock in results:
                        print(f"  {stock.symbol} - {stock.name}")
                else:
                    print("❌ 未找到相关股票")
                continue
            
            # 股票分析
            symbol = user_input.upper()
            analyzer = StockAnalyzerFactory.create_analyzer(symbol)
            
            if not analyzer:
                print(f"❌ 不支持的股票代码: {symbol}")
                continue
            
            print(f"🔍 正在分析 {symbol}...")
            result = await analyzer.run_analysis()
            
            # 显示简化结果
            print(f"\n📊 {result.company_name} ({result.symbol})")
            if result.quote:
                quote = result.quote
                change_symbol = "+" if quote.change >= 0 else ""
                color = "🟢" if quote.change >= 0 else "🔴"
                print(f"  {color} 价格: {quote.currency}{quote.current_price:.2f} ({change_symbol}{quote.change_pct:.2f}%)")
            
            rec_emoji = {'BUY': '🚀', 'SELL': '📉', 'HOLD': '🤝'}
            print(f"  🎯 建议: {rec_emoji.get(result.recommendation, '🤝')} {result.recommendation}")
            print(f"  📊 置信度: {result.confidence*100:.1f}%")
            print(f"  ⚠️  风险: {result.risk_level}")
            
        except KeyboardInterrupt:
            print(f"\n👋 用户中断，再见!")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")


async def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == '--demo':
        await demo_enhanced_features()
    elif len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        await interactive_analysis()
    else:
        print("🚀 增强版股票分析系统")
        print("使用方法:")
        print("  python enhanced_analyzer_demo.py --demo         # 功能演示")
        print("  python enhanced_analyzer_demo.py --interactive  # 交互模式")
        print()
        await demo_enhanced_features()


if __name__ == "__main__":
    asyncio.run(main())