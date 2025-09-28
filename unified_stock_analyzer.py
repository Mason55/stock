# unified_stock_analyzer.py - 使用新架构的统一股票分析器
import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.analyzer_factory import StockAnalyzerFactory, analyze_stock, batch_analyze_stocks
from core.stock_config import search_stocks, get_supported_symbols


class UnifiedStockAnalyzer:
    """统一股票分析器 - 使用新架构"""
    
    def __init__(self):
        self.factory = StockAnalyzerFactory()
        
    async def analyze_single_stock(self, symbol: str) -> Dict[str, Any]:
        """分析单只股票"""
        print(f"🔍 开始分析 {symbol}...")
        
        result = await analyze_stock(symbol)
        if not result:
            return {'error': f'不支持的股票代码: {symbol}'}
        
        return result
    
    async def analyze_multiple_stocks(self, symbols: List[str]) -> Dict[str, Any]:
        """批量分析股票"""
        print(f"📊 批量分析 {len(symbols)} 只股票...")
        
        return await batch_analyze_stocks(symbols)
    
    def search_stock_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """根据关键词搜索股票"""
        stocks = search_stocks(keyword)
        return [stock.to_dict() for stock in stocks]
    
    def get_supported_stocks(self) -> List[str]:
        """获取所有支持的股票代码"""
        return get_supported_symbols()
    
    def format_analysis_report(self, result: Dict[str, Any]) -> str:
        """格式化分析报告"""
        if 'error' in result:
            return f"❌ 分析失败: {result['error']}"
        
        report = []
        report.append("=" * 60)
        report.append(f"📈 {result['company_name']} ({result['symbol']}) 分析报告")
        report.append("=" * 60)
        report.append(f"📅 分析时间: {result['analysis_time'][:19]}")
        
        # 实时行情
        if result.get('quote'):
            quote = result['quote']
            change_symbol = "+" if quote['change'] >= 0 else ""
            color_indicator = "🔴" if quote['change'] < 0 else "🟢"
            
            report.append(f"\n📈 实时行情:")
            report.append(f"  {color_indicator} 现价: {quote['currency']}{quote['current_price']:.2f}")
            report.append(f"  📊 涨跌: {change_symbol}{quote['change']:.2f} ({change_symbol}{quote['change_pct']:.2f}%)")
            report.append(f"  🌅 今开: {quote['currency']}{quote['open_price']:.2f}")
            report.append(f"  ⬆️  最高: {quote['currency']}{quote['high_price']:.2f}")
            report.append(f"  ⬇️  最低: {quote['currency']}{quote['low_price']:.2f}")
            report.append(f"  📦 成交量: {quote['volume']:,}")
            report.append(f"  💰 成交额: {quote['currency']}{quote['turnover']/100000000:.2f}亿")
        
        # 技术分析
        rec_emoji = {'BUY': '🚀', 'SELL': '📉', 'HOLD': '🤝'}
        rec_text = {'BUY': '买入', 'SELL': '卖出', 'HOLD': '持有'}
        
        recommendation = result['recommendation']
        report.append(f"\n🎯 投资建议:")
        report.append(f"  建议: {rec_emoji.get(recommendation, '🤝')} {rec_text.get(recommendation, '持有')}")
        report.append(f"  置信度: {result['confidence']*100:.1f}%")
        report.append(f"  综合评分: {result['overall_score']:.2f}")
        report.append(f"  风险等级: {result['risk_level']}")
        
        # 关键因子
        if result.get('key_factors'):
            report.append(f"\n🔍 关键因子:")
            for factor in result['key_factors']:
                report.append(f"  • {factor}")
        
        # 技术信号
        if result.get('signals'):
            tech_signals = [s for s in result['signals'] if s['type'] == 'technical']
            if tech_signals:
                report.append(f"\n📊 技术信号:")
                for signal in tech_signals:
                    signal_emoji = {'buy': '🟢', 'sell': '🔴', 'neutral': '🟡'}.get(signal['signal'], '⚪')
                    report.append(f"  {signal_emoji} {signal['description']} (强度: {signal['strength']:.1f})")
        
        # 市场环境
        if result.get('market_context'):
            context = result['market_context']
            report.append(f"\n📊 市场环境:")
            report.append(f"  交易状态: {context.get('trading_status', 'Unknown')}")
            report.append(f"  所属行业: {context.get('industry', 'Unknown')}")
        
        report.append("\n" + "=" * 60)
        report.append("⚠️  风险提示: 股票投资有风险，本分析仅供参考，请谨慎决策")
        report.append("=" * 60)
        
        return "\n".join(report)


async def main():
    """主函数"""
    print("🚀 统一股票分析系统启动...")
    
    analyzer = UnifiedStockAnalyzer()
    
    # 获取命令行参数
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
        
        # 检查是否是搜索请求
        if symbol.startswith('SEARCH:'):
            keyword = symbol[7:]  # 移除 'SEARCH:' 前缀
            print(f"🔍 搜索关键词: {keyword}")
            results = analyzer.search_stock_by_keyword(keyword)
            if results:
                print(f"找到 {len(results)} 只相关股票:")
                for stock in results:
                    print(f"  {stock['symbol']} - {stock['name']} ({stock['industry']})")
            else:
                print("未找到相关股票")
            return
        
        # 检查是否是批量分析请求
        if ',' in symbol:
            symbols = [s.strip().upper() for s in symbol.split(',')]
            print(f"📊 批量分析: {symbols}")
            
            results = await analyzer.analyze_multiple_stocks(symbols)
            
            for sym, result in results.items():
                print(f"\n{'='*20} {sym} {'='*20}")
                if 'error' not in result:
                    quote = result.get('quote', {})
                    print(f"建议: {result['recommendation']} | 置信度: {result['confidence']*100:.1f}%")
                    if quote:
                        print(f"价格: {quote.get('currency', '')}{quote.get('current_price', 0):.2f} ({quote.get('change_pct', 0):+.2f}%)")
                else:
                    print(f"错误: {result['error']}")
            return
        
        # 单股分析
        result = await analyzer.analyze_single_stock(symbol)
        
        if 'error' not in result:
            # 生成详细报告
            report = analyzer.format_analysis_report(result)
            print(report)
            
            # 保存分析结果
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"analysis_{symbol}_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 分析结果已保存至: {filename}")
        else:
            print(f"❌ {result['error']}")
    
    else:
        # 展示支持的股票列表
        supported = analyzer.get_supported_stocks()
        print(f"📋 系统支持 {len(supported)} 只股票:")
        print("使用方法:")
        print("  python unified_stock_analyzer.py 601127.SH          # 分析单只股票")
        print("  python unified_stock_analyzer.py 601127.SH,2015.HK  # 批量分析")
        print("  python unified_stock_analyzer.py SEARCH:汽车        # 搜索股票")
        print(f"\n支持的股票代码: {', '.join(supported[:10])}{'...' if len(supported) > 10 else ''}")


if __name__ == "__main__":
    asyncio.run(main())