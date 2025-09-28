# src/services/jac_analyzer.py - JAC Motors (江淮汽车) specialized analyzer
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import yfinance as yf
from .real_data_provider import RealDataManager, StockQuote
import logging

class JACAnalyzer:
    """江淮汽车专门分析器"""
    
    def __init__(self):
        self.symbol = "600418.SH"  # 江淮汽车股票代码
        self.data_manager = RealDataManager(primary_provider='yahoo')
        self.logger = logging.getLogger(__name__)
        
    async def get_real_time_data(self) -> Optional[StockQuote]:
        """获取江淮汽车实时股价数据"""
        try:
            quote = await self.data_manager.get_quote(self.symbol)
            return quote
        except Exception as e:
            self.logger.error(f"Failed to get real-time data: {e}")
            return None
    
    def get_historical_data(self, period: str = "6mo") -> pd.DataFrame:
        """获取历史股价数据"""
        try:
            ticker = yf.Ticker(self.symbol.replace('.SH', '.SS'))
            hist = ticker.history(period=period)
            return hist
        except Exception as e:
            self.logger.error(f"Failed to get historical data: {e}")
            return pd.DataFrame()
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> Dict:
        """计算技术指标"""
        if df.empty:
            return {}
        
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
        ema12 = df['Close'].ewm(span=12).mean()
        ema26 = df['Close'].ewm(span=26).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        
        # 布林带
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        
        # 成交量均线
        df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()
        df['Volume_MA10'] = df['Volume'].rolling(window=10).mean()
        
        # 当前值
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
            'macd_histogram': latest['MACD_Histogram'],
            'bb_upper': latest['BB_Upper'],
            'bb_middle': latest['BB_Middle'],
            'bb_lower': latest['BB_Lower'],
            'volume': latest['Volume'],
            'volume_ma5': latest['Volume_MA5'],
            'volume_ma10': latest['Volume_MA10']
        }
    
    def analyze_trend(self, indicators: Dict) -> Dict:
        """趋势分析"""
        signals = []
        score = 0
        
        # 移动平均线分析
        if indicators['ma5'] > indicators['ma10'] > indicators['ma20']:
            signals.append("短期均线多头排列")
            score += 2
        elif indicators['ma5'] < indicators['ma10'] < indicators['ma20']:
            signals.append("短期均线空头排列")
            score -= 2
        
        # RSI分析
        rsi = indicators['rsi']
        if rsi > 70:
            signals.append("RSI超买区域")
            score -= 1
        elif rsi < 30:
            signals.append("RSI超卖区域")
            score += 1
        elif 40 <= rsi <= 60:
            signals.append("RSI中性区域")
        
        # MACD分析
        if indicators['macd'] > indicators['macd_signal'] and indicators['macd_histogram'] > 0:
            signals.append("MACD金叉信号")
            score += 1
        elif indicators['macd'] < indicators['macd_signal'] and indicators['macd_histogram'] < 0:
            signals.append("MACD死叉信号")
            score -= 1
        
        # 布林带分析
        price = indicators['price']
        bb_upper = indicators['bb_upper']
        bb_lower = indicators['bb_lower']
        bb_middle = indicators['bb_middle']
        
        if price > bb_upper:
            signals.append("价格突破布林带上轨")
            score -= 1
        elif price < bb_lower:
            signals.append("价格跌破布林带下轨")
            score += 1
        elif price > bb_middle:
            signals.append("价格位于布林带上半部")
        else:
            signals.append("价格位于布林带下半部")
        
        # 成交量分析
        volume = indicators['volume']
        volume_ma5 = indicators['volume_ma5']
        if volume > volume_ma5 * 1.5:
            signals.append("成交量放大")
            score += 0.5
        elif volume < volume_ma5 * 0.5:
            signals.append("成交量萎缩")
            score -= 0.5
        
        # 综合评级
        if score >= 3:
            rating = "强烈买入"
        elif score >= 1:
            rating = "买入"
        elif score >= -1:
            rating = "持有"
        elif score >= -3:
            rating = "卖出"
        else:
            rating = "强烈卖出"
        
        return {
            'rating': rating,
            'score': score,
            'signals': signals
        }
    
    def calculate_support_resistance(self, df: pd.DataFrame) -> Dict:
        """计算支撑位和阻力位"""
        if df.empty:
            return {}
        
        # 使用最近20个交易日的高点和低点
        recent_highs = df['High'].tail(20).nlargest(3)
        recent_lows = df['Low'].tail(20).nsmallest(3)
        
        resistance_levels = recent_highs.mean()
        support_levels = recent_lows.mean()
        
        current_price = df['Close'].iloc[-1]
        
        return {
            'support': round(support_levels, 2),
            'resistance': round(resistance_levels, 2),
            'current_price': round(current_price, 2),
            'distance_to_support': round((current_price - support_levels) / current_price * 100, 2),
            'distance_to_resistance': round((resistance_levels - current_price) / current_price * 100, 2)
        }
    
    async def comprehensive_analysis(self) -> Dict:
        """综合分析报告"""
        try:
            # 获取实时数据
            real_time = await self.get_real_time_data()
            
            # 获取历史数据
            hist_data = self.get_historical_data()
            
            if hist_data.empty:
                return {"error": "无法获取历史数据"}
            
            # 计算技术指标
            indicators = self.calculate_technical_indicators(hist_data)
            
            # 趋势分析
            trend_analysis = self.analyze_trend(indicators)
            
            # 支撑阻力分析
            sr_analysis = self.calculate_support_resistance(hist_data)
            
            # 价格变化分析
            price_changes = {
                '1d_change': round(((hist_data['Close'].iloc[-1] - hist_data['Close'].iloc[-2]) / hist_data['Close'].iloc[-2]) * 100, 2),
                '5d_change': round(((hist_data['Close'].iloc[-1] - hist_data['Close'].iloc[-6]) / hist_data['Close'].iloc[-6]) * 100, 2) if len(hist_data) >= 6 else 0,
                '20d_change': round(((hist_data['Close'].iloc[-1] - hist_data['Close'].iloc[-21]) / hist_data['Close'].iloc[-21]) * 100, 2) if len(hist_data) >= 21 else 0
            }
            
            # 波动率分析
            volatility = hist_data['Close'].pct_change().std() * np.sqrt(252) * 100  # 年化波动率
            
            return {
                'symbol': '600418.SH',
                'company_name': '江淮汽车',
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'real_time_data': {
                    'price': real_time.price if real_time else indicators.get('price'),
                    'change': real_time.change if real_time else None,
                    'change_percent': real_time.change_percent if real_time else None,
                    'volume': real_time.volume if real_time else indicators.get('volume')
                },
                'technical_indicators': indicators,
                'trend_analysis': trend_analysis,
                'support_resistance': sr_analysis,
                'price_changes': price_changes,
                'volatility': round(volatility, 2),
                'market_status': self._get_market_status()
            }
            
        except Exception as e:
            self.logger.error(f"Comprehensive analysis failed: {e}")
            return {"error": f"分析失败: {str(e)}"}
    
    def _get_market_status(self) -> str:
        """获取市场状态"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()
        
        # 周末
        if weekday >= 5:
            return "休市"
        
        # 交易时间判断
        if (9 <= hour < 11) or (hour == 11 and minute <= 30) or (13 <= hour < 15):
            return "交易中"
        else:
            return "休市"