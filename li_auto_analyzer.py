# li_auto_analyzer.py - 理想汽车(Li Auto)专门分析器
import asyncio
import aiohttp
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import yfinance as yf
import logging
import sys
import os

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from services.real_data_provider import RealDataManager, StockQuote
except ImportError:
    # 如果导入失败，创建简单的StockQuote类
    class StockQuote:
        def __init__(self, symbol: str, price: float, change: float = 0, change_pct: float = 0, volume: int = 0):
            self.symbol = symbol
            self.price = price
            self.change = change
            self.change_pct = change_pct
            self.volume = volume

class LiAutoAnalyzer:
    """理想汽车专门分析器"""
    
    def __init__(self):
        # 理想汽车股票代码
        self.hk_symbol = "2015.HK"  # 港股
        self.us_symbol = "LI"       # 美股NASDAQ
        self.sina_code = "rt_hk02015"  # 新浪财经港股代码
        self.logger = logging.getLogger(__name__)
        
        # 配置日志
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        
    async def get_sina_real_time_data(self) -> Optional[StockQuote]:
        """从新浪财经获取理想汽车实时港股数据"""
        sina_url = f"https://hq.sinajs.cn/list={self.sina_code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(sina_url) as response:
                    if response.status != 200:
                        self.logger.error(f"Sina API returned status {response.status}")
                        return None
                    
                    content = await response.text()
                    self.logger.info(f"Sina response: {content[:200]}...")
                    
                    if 'hq_str_' not in content or '"' not in content:
                        self.logger.warning("Invalid response format from Sina")
                        return None
                    
                    # 解析新浪港股数据格式
                    data_line = content.split('"')[1]
                    if not data_line.strip():
                        self.logger.warning("Empty data from Sina")
                        return None
                    
                    parts = data_line.split(',')
                    if len(parts) < 10:
                        self.logger.warning(f"Insufficient data parts: {len(parts)}")
                        return None
                    
                    # 港股数据格式: 名称,今开,昨收,现价,最高,最低,买入,卖出,成交量,成交金额,买1量,买1价,...
                    current_price = float(parts[3]) if parts[3] else 0
                    yesterday_close = float(parts[2]) if parts[2] else current_price
                    volume = int(float(parts[8])) if parts[8] else 0
                    
                    change = current_price - yesterday_close
                    change_pct = (change / yesterday_close * 100) if yesterday_close > 0 else 0
                    
                    return StockQuote(
                        symbol=self.hk_symbol,
                        price=current_price,
                        change=change,
                        change_pct=change_pct,
                        volume=volume
                    )
                    
        except Exception as e:
            self.logger.error(f"Failed to get Sina data: {e}")
            return None
    
    def get_yfinance_data(self, period: str = "6mo") -> pd.DataFrame:
        """使用yfinance获取理想汽车历史数据"""
        try:
            # 优先使用美股数据，因为数据更完整
            ticker = yf.Ticker(self.us_symbol)
            hist = ticker.history(period=period)
            
            if hist.empty:
                self.logger.warning("US data empty, trying HK data")
                # 如果美股数据获取失败，尝试港股
                ticker_hk = yf.Ticker("2015.HK")
                hist = ticker_hk.history(period=period)
            
            return hist
        except Exception as e:
            self.logger.error(f"Failed to get historical data: {e}")
            return pd.DataFrame()
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> Dict:
        """计算技术指标"""
        if df.empty:
            return {}
        
        try:
            # 移动平均线
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA10'] = df['Close'].rolling(window=10).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            
            # RSI相对强弱指标
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # MACD指标
            exp1 = df['Close'].ewm(span=12).mean()
            exp2 = df['Close'].ewm(span=26).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
            df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
            
            # 布林带
            df['BB_Middle'] = df['Close'].rolling(window=20).mean()
            bb_std = df['Close'].rolling(window=20).std()
            df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
            df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
            
            # 获取最新指标值
            latest = df.iloc[-1]
            
            return {
                'price': latest['Close'],
                'ma5': latest['MA5'],
                'ma10': latest['MA10'], 
                'ma20': latest['MA20'],
                'ma60': latest['MA60'],
                'rsi': latest['RSI'],
                'macd': latest['MACD'],
                'macd_signal': latest['MACD_Signal'],
                'bb_upper': latest['BB_Upper'],
                'bb_middle': latest['BB_Middle'],
                'bb_lower': latest['BB_Lower'],
                'volume': latest['Volume']
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate indicators: {e}")
            return {}
    
    def analyze_trend(self, indicators: Dict) -> Dict:
        """分析趋势和建议"""
        if not indicators:
            return {'recommendation': 'HOLD', 'confidence': 0, 'reasons': ['数据不足']}
        
        signals = []
        score = 0
        
        try:
            price = indicators['price']
            ma5 = indicators.get('ma5', price)
            ma20 = indicators.get('ma20', price)
            ma60 = indicators.get('ma60', price)
            rsi = indicators.get('rsi', 50)
            macd = indicators.get('macd', 0)
            
            # 均线分析
            if price > ma5 > ma20 > ma60:
                signals.append('多头排列')
                score += 2
            elif price > ma20:
                signals.append('价格在20日均线上方')
                score += 1
            elif price < ma20:
                signals.append('价格在20日均线下方')
                score -= 1
                
            # RSI分析
            if rsi < 30:
                signals.append('RSI超卖')
                score += 1
            elif rsi > 70:
                signals.append('RSI超买')
                score -= 1
            else:
                signals.append('RSI中性')
                
            # MACD分析
            if macd > 0:
                signals.append('MACD金叉')
                score += 1
            else:
                signals.append('MACD死叉')
                score -= 1
                
            # 生成建议
            if score >= 2:
                recommendation = 'BUY'
                confidence = min(80, 50 + score * 10)
            elif score <= -2:
                recommendation = 'SELL'
                confidence = min(80, 50 + abs(score) * 10)
            else:
                recommendation = 'HOLD'
                confidence = 60
                
            return {
                'recommendation': recommendation,
                'confidence': confidence,
                'score': score,
                'signals': signals
            }
            
        except Exception as e:
            self.logger.error(f"Failed to analyze trend: {e}")
            return {'recommendation': 'HOLD', 'confidence': 0, 'reasons': ['分析错误']}
    
    async def run_full_analysis(self) -> Dict:
        """运行完整分析"""
        analysis_result = {
            'company': '理想汽车',
            'symbol_hk': self.hk_symbol,
            'symbol_us': self.us_symbol,
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'market_status': 'OPEN' if datetime.now().hour in range(9, 16) else 'CLOSED'
        }
        
        try:
            # 获取实时数据
            real_time_data = await self.get_sina_real_time_data()
            if real_time_data:
                analysis_result['real_time_data'] = {
                    'price': real_time_data.price,
                    'change': real_time_data.change,
                    'change_pct': real_time_data.change_pct,
                    'volume': real_time_data.volume
                }
            else:
                analysis_result['real_time_data'] = {
                    'price': 0,
                    'change': None,
                    'change_pct': None,
                    'volume': 0,
                    'note': '实时数据获取失败，使用历史数据'
                }
            
            # 获取历史数据并计算技术指标
            hist_data = self.get_yfinance_data()
            if not hist_data.empty:
                indicators = self.calculate_technical_indicators(hist_data)
                analysis_result['technical_indicators'] = indicators
                
                # 如果实时数据获取失败，使用最新历史数据
                if not real_time_data and indicators:
                    analysis_result['real_time_data']['price'] = indicators['price']
                
                # 趋势分析
                trend_analysis = self.analyze_trend(indicators)
                analysis_result['trend_analysis'] = trend_analysis
                
                # 价格表现统计
                if len(hist_data) > 0:
                    analysis_result['performance'] = {
                        'period_high': hist_data['High'].max(),
                        'period_low': hist_data['Low'].min(),
                        'period_return': ((hist_data['Close'].iloc[-1] - hist_data['Close'].iloc[0]) / hist_data['Close'].iloc[0] * 100),
                        'volatility': hist_data['Close'].pct_change().std() * np.sqrt(252) * 100  # 年化波动率
                    }
            else:
                analysis_result['error'] = '无法获取历史数据'
                
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            analysis_result['error'] = str(e)
            
        return analysis_result


def format_analysis_report(analysis_data: Dict) -> str:
    """格式化分析报告为可读文本"""
    if 'error' in analysis_data:
        return f"❌ 分析失败: {analysis_data['error']}"
    
    report = []
    report.append("=" * 60)
    report.append("🚗 理想汽车 (Li Auto) 技术分析报告")
    report.append("=" * 60)
    report.append(f"📅 分析时间: {analysis_data['analysis_time']}")
    report.append(f"📊 市场状态: {analysis_data['market_status']}")
    report.append(f"📈 港股代码: {analysis_data['symbol_hk']}")
    report.append(f"📈 美股代码: {analysis_data['symbol_us']}")
    report.append("")
    
    # 实时数据
    real_time = analysis_data['real_time_data']
    report.append("📈 实时行情:")
    if real_time['price'] > 0:
        report.append(f"  当前价格: ${real_time['price']:.2f}")
        if real_time['change'] is not None:
            change_sign = "+" if real_time['change'] >= 0 else ""
            report.append(f"  涨跌额: {change_sign}{real_time['change']:.2f}")
            report.append(f"  涨跌幅: {change_sign}{real_time['change_pct']:.2f}%")
        report.append(f"  成交量: {real_time['volume']:,}")
    else:
        report.append("  ⚠️ 实时数据暂时无法获取")
    report.append("")
    
    # 技术指标
    if 'technical_indicators' in analysis_data:
        indicators = analysis_data['technical_indicators']
        report.append("📊 技术指标:")
        report.append(f"  MA5:  ${indicators.get('ma5', 0):.2f}")
        report.append(f"  MA20: ${indicators.get('ma20', 0):.2f}")
        report.append(f"  MA60: ${indicators.get('ma60', 0):.2f}")
        report.append(f"  RSI:  {indicators.get('rsi', 0):.1f}")
        report.append(f"  MACD: {indicators.get('macd', 0):.3f}")
        report.append("")
    
    # 趋势分析
    if 'trend_analysis' in analysis_data:
        trend = analysis_data['trend_analysis']
        recommendation = trend['recommendation']
        confidence = trend['confidence']
        
        emoji_map = {'BUY': '🚀', 'SELL': '📉', 'HOLD': '🤝'}
        action_map = {'BUY': '买入', 'SELL': '卖出', 'HOLD': '持有'}
        
        report.append("🎯 投资建议:")
        report.append(f"  建议: {emoji_map.get(recommendation, '🤝')} {action_map.get(recommendation, '持有')}")
        report.append(f"  置信度: {confidence}%")
        report.append(f"  信号: {', '.join(trend.get('signals', []))}")
        report.append("")
    
    # 表现统计
    if 'performance' in analysis_data:
        perf = analysis_data['performance']
        report.append("📈 区间表现:")
        report.append(f"  区间最高: ${perf['period_high']:.2f}")
        report.append(f"  区间最低: ${perf['period_low']:.2f}")
        report.append(f"  区间收益: {perf['period_return']:.2f}%")
        report.append(f"  年化波动率: {perf['volatility']:.2f}%")
        report.append("")
    
    report.append("=" * 60)
    report.append("⚠️  投资有风险，建议仅供参考，请结合自身情况决策")
    report.append("=" * 60)
    
    return "\n".join(report)


async def main():
    """主函数"""
    print("🚀 启动理想汽车分析...")
    
    analyzer = LiAutoAnalyzer()
    analysis_result = await analyzer.run_full_analysis()
    
    # 生成报告
    report = format_analysis_report(analysis_result)
    print(report)
    
    # 保存分析结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"li_auto_analysis_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(analysis_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 分析结果已保存至: {filename}")
    

if __name__ == "__main__":
    asyncio.run(main())