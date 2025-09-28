# comprehensive_demo.py - 全面功能演示
import asyncio
import sys
import os
from datetime import datetime

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.analyzer_factory import StockAnalyzerFactory
from core.stock_config import StockConfigManager
from core.data_sources import DataSourceManager


async def comprehensive_analysis_demo():
    """全面分析演示"""
    print("🚀 股票分析系统 - 全面功能演示")
    print("=" * 80)
    print(f"演示时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 1. 系统概览
    print("\n📊 系统概览")
    print("-" * 40)
    config_manager = StockConfigManager()
    print(f"支持股票总数: {len(config_manager.get_all_symbols())}")
    print(f"市场分布: {config_manager.get_market_summary()}")
    print(f"行业分布: {config_manager.get_industry_summary()}")
    
    # 2. 多层次分析演示
    test_stocks = ["601127.SH", "2015.HK"]  # 赛力斯、理想汽车
    
    for symbol in test_stocks:
        print(f"\n🔍 深度分析: {symbol}")
        print("-" * 60)
        
        analyzer = StockAnalyzerFactory.create_analyzer(symbol)
        if not analyzer:
            print(f"❌ 不支持的股票: {symbol}")
            continue
        
        try:
            result = await analyzer.run_analysis()
            
            # 基本信息
            print(f"📈 {result.company_name} ({result.symbol})")
            
            # 实时行情
            if result.quote:
                quote = result.quote
                change_symbol = "📈" if quote.change >= 0 else "📉"
                print(f"  {change_symbol} 价格: {quote.currency}{quote.current_price:.2f} ({quote.change_pct:+.2f}%)")
                print(f"  💰 成交额: {quote.turnover/100000000:.2f}亿")
                print(f"  📊 成交量: {quote.volume:,}")
            
            # 技术分析
            print(f"\n🔧 技术分析:")
            indicators = result.technical_indicators
            if indicators:
                if indicators.ma5:
                    print(f"  MA5:  {indicators.ma5:.2f}")
                if indicators.ma20:
                    print(f"  MA20: {indicators.ma20:.2f}")
                if indicators.rsi:
                    print(f"  RSI:  {indicators.rsi:.1f}")
                if indicators.macd:
                    print(f"  MACD: {indicators.macd:.4f}")
            
            # 基本面分析
            print(f"\n💼 基本面分析:")
            if result.fundamental_data:
                # 如果是字典格式
                if isinstance(result.fundamental_data, dict):
                    fundamental = result.fundamental_data
                    pe_ratio = fundamental.get('pe_ratio')
                    pb_ratio = fundamental.get('pb_ratio') 
                    roe = fundamental.get('roe')
                    revenue_growth = fundamental.get('revenue_growth')
                else:
                    # 如果是对象格式
                    fundamental = result.fundamental_data
                    pe_ratio = getattr(fundamental, 'pe_ratio', None)
                    pb_ratio = getattr(fundamental, 'pb_ratio', None)
                    roe = getattr(fundamental, 'roe', None)
                    revenue_growth = getattr(fundamental, 'revenue_growth', None)
                
                if pe_ratio:
                    print(f"  PE比率: {pe_ratio:.1f}")
                if pb_ratio:
                    print(f"  PB比率: {pb_ratio:.1f}")
                if roe:
                    print(f"  ROE: {roe:.1f}%")
                if revenue_growth:
                    print(f"  营收增长: {revenue_growth:.1f}%")
            else:
                print("  基本面数据获取中...")
            
            # 情绪分析
            print(f"\n😊 情绪分析:")
            if result.sentiment_data:
                # 如果是字典格式
                if isinstance(result.sentiment_data, dict):
                    sentiment = result.sentiment_data
                    news_score = sentiment.get('news_sentiment_score')
                    social_score = sentiment.get('social_sentiment_score')
                    analyst_sentiment = sentiment.get('analyst_sentiment')
                    overall_score = sentiment.get('overall_sentiment_score')
                else:
                    # 如果是对象格式
                    sentiment = result.sentiment_data
                    news_score = getattr(sentiment, 'news_sentiment_score', None)
                    social_score = getattr(sentiment, 'social_sentiment_score', None)
                    analyst_sentiment = getattr(sentiment, 'analyst_sentiment', None)
                    overall_score = getattr(sentiment, 'overall_sentiment_score', None)
                
                if news_score is not None:
                    print(f"  新闻情绪: {news_score:.2f}")
                if social_score is not None:
                    print(f"  社交情绪: {social_score:.2f}")
                if analyst_sentiment:
                    print(f"  分析师态度: {analyst_sentiment}")
                if overall_score is not None:
                    print(f"  综合情绪: {overall_score:.2f}")
            else:
                print("  情绪数据获取中...")
            
            # 信号分析
            print(f"\n📡 信号分析:")
            signals = result.signals
            technical_signals = [s for s in signals if s.type == 'technical']
            fundamental_signals = [s for s in signals if s.type == 'fundamental']
            sentiment_signals = [s for s in signals if s.type == 'sentiment']
            
            print(f"  技术信号: {len(technical_signals)}个")
            print(f"  基本面信号: {len(fundamental_signals)}个")
            print(f"  情绪信号: {len(sentiment_signals)}个")
            
            # 显示重要信号
            important_signals = [s for s in signals if s.strength > 0.6]
            if important_signals:
                print(f"  ⭐ 重要信号:")
                for signal in important_signals[:3]:
                    signal_emoji = {'buy': '🟢', 'sell': '🔴', 'neutral': '🟡'}.get(signal.signal, '⚪')
                    print(f"    {signal_emoji} {signal.description}")
            
            # 综合建议
            print(f"\n🎯 投资建议:")
            rec_emoji = {'BUY': '🚀', 'SELL': '📉', 'HOLD': '🤝'}.get(result.recommendation, '🤝')
            print(f"  {rec_emoji} {result.recommendation}")
            print(f"  📊 置信度: {result.confidence*100:.1f}%")
            print(f"  📈 综合评分: {result.overall_score:.2f}")
            print(f"  ⚠️  风险等级: {result.risk_level}")
            
            # 市场环境
            print(f"\n🌍 市场环境:")
            context = result.market_context
            print(f"  市场: {context.get('market', 'N/A')}")
            print(f"  交易状态: {context.get('trading_status', 'N/A')}")
            print(f"  行业: {context.get('industry', 'N/A')}")
            
        except Exception as e:
            print(f"❌ 分析失败: {e}")
    
    # 3. 行业对比分析
    print(f"\n🏭 行业对比分析")
    print("-" * 60)
    
    # 获取汽车制造行业股票
    auto_stocks = []
    for symbol in config_manager.get_all_symbols():
        config = config_manager.get_config(symbol)
        if config and '汽车' in str(config.industry):
            auto_stocks.append(symbol)
    
    print(f"汽车制造行业股票 (共{len(auto_stocks)}只):")
    
    # 分析前3只股票
    industry_results = []
    for symbol in auto_stocks[:3]:
        try:
            result = await StockAnalyzerFactory.analyze_stock(symbol)
            if result and 'error' not in result:
                industry_results.append((symbol, result))
        except:
            continue
    
    # 按综合评分排序
    industry_results.sort(key=lambda x: x[1]['overall_score'], reverse=True)
    
    for i, (symbol, result) in enumerate(industry_results):
        print(f"  {i+1}. {result['company_name']} ({symbol})")
        print(f"     评分: {result['overall_score']:.2f} | {result['recommendation']} | {result['risk_level']}")
        if result.get('quote'):
            print(f"     涨跌: {result['quote']['change_pct']:+.2f}%")
    
    # 4. 数据源可靠性测试
    print(f"\n📡 数据源可靠性测试")
    print("-" * 60)
    
    test_symbol = "601127.SH"
    config = config_manager.get_config(test_symbol)
    if config:
        data_manager = DataSourceManager()
        print(f"测试股票: {config.name} ({test_symbol})")
        
        # 尝试不同数据源
        for source_name in ['sina', 'eastmoney', 'tencent']:
            try:
                # 临时修改配置只使用单一数据源
                test_config = config.to_dict()
                test_config['data_sources'] = [source_name]
                
                quote = await data_manager.fetch_quote_with_fallback(test_symbol, test_config)
                if quote:
                    print(f"  ✅ {source_name}: 成功 (价格: {quote.current_price:.2f})")
                else:
                    print(f"  ❌ {source_name}: 失败")
            except Exception as e:
                print(f"  ❌ {source_name}: 错误 - {str(e)[:50]}")
    
    # 5. 性能统计
    print(f"\n⚡ 性能统计")
    print("-" * 60)
    
    start_time = datetime.now()
    
    # 批量分析测试
    batch_symbols = ["601127.SH", "2015.HK", "600418.SH"]
    tasks = [StockAnalyzerFactory.analyze_stock(symbol) for symbol in batch_symbols]
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    successful_analyses = sum(1 for r in batch_results if isinstance(r, dict) and 'error' not in r)
    
    print(f"  批量分析 {len(batch_symbols)} 只股票:")
    print(f"  ⏱️  总耗时: {duration:.2f}秒")
    print(f"  📊 成功率: {successful_analyses}/{len(batch_symbols)} ({successful_analyses/len(batch_symbols)*100:.1f}%)")
    print(f"  🚀 平均速度: {duration/len(batch_symbols):.2f}秒/只")
    
    print(f"\n✅ 演示完成!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(comprehensive_analysis_demo())
    except KeyboardInterrupt:
        print("\n👋 用户中断，演示结束")
    except Exception as e:
        print(f"\n❌ 演示过程中发生错误: {e}")