# src/core/analyzer_factory.py - 分析器工厂
import asyncio
import numpy as np
from typing import Optional, List, Dict, Any
from .base_analyzer import BaseStockAnalyzer, StockQuote, TechnicalIndicators, AnalysisSignal
from .stock_config import get_stock_config, StockConfig
from .data_sources import data_source_manager
from .technical_analysis import AdvancedTechnicalAnalyzer, AdvancedTechnicalIndicators, calculate_advanced_indicators, analyze_technical_strength
from .fundamental_analysis import FundamentalAnalyzer, FundamentalData, get_fundamental_data, analyze_fundamental_strength
from .sentiment_analysis import SentimentAnalyzer, SentimentData, get_sentiment_data, analyze_sentiment_strength


class StandardStockAnalyzer(BaseStockAnalyzer):
    """标准股票分析器实现"""
    
    def __init__(self, symbol: str, config: Dict[str, Any]):
        super().__init__(symbol, config)
        self.fundamental_analyzer = FundamentalAnalyzer()
        self.sentiment_analyzer = SentimentAnalyzer()
    
    async def fetch_real_time_data(self) -> Optional[StockQuote]:
        """获取实时行情数据"""
        try:
            return await data_source_manager.fetch_quote_with_fallback(
                self.symbol, 
                self.config
            )
        except Exception as e:
            self.logger.error(f"获取实时数据失败: {e}")
            return None
    
    def calculate_technical_indicators(self, quote: StockQuote, historical_data: Optional[List] = None) -> TechnicalIndicators:
        """计算技术指标"""
        # 基于当前数据计算简化技术指标
        indicators = TechnicalIndicators()
        
        try:
            # 如果有历史数据，使用高级技术分析
            if historical_data and len(historical_data) > 10:
                prices = [float(d.get('close', quote.current_price)) for d in historical_data]
                volumes = [float(d.get('volume', quote.volume)) for d in historical_data]
                highs = [float(d.get('high', quote.high_price)) for d in historical_data]
                lows = [float(d.get('low', quote.low_price)) for d in historical_data]
                
                # 添加当前数据
                prices.append(quote.current_price)
                volumes.append(quote.volume)
                highs.append(quote.high_price)
                lows.append(quote.low_price)
                
                # 使用高级技术分析模块
                advanced_indicators = calculate_advanced_indicators(
                    prices=prices,
                    volumes=volumes,
                    highs=highs,
                    lows=lows,
                    current_price=quote.current_price
                )
                
                # 将高级指标转换为基础指标格式
                indicators.ma5 = advanced_indicators.ma5
                indicators.ma10 = advanced_indicators.ma10
                indicators.ma20 = advanced_indicators.ma20
                indicators.ma60 = advanced_indicators.ma60
                indicators.rsi = advanced_indicators.rsi
                indicators.macd = advanced_indicators.macd
                indicators.macd_signal = advanced_indicators.macd_signal
                indicators.bb_upper = advanced_indicators.bb_upper
                indicators.bb_middle = advanced_indicators.bb_middle
                indicators.bb_lower = advanced_indicators.bb_lower
                indicators.volume_ma = advanced_indicators.volume_ma
                
                # 保存高级指标到属性中供后续使用
                self._advanced_indicators = advanced_indicators
                
            else:
                # 没有足够历史数据时的简化处理
                prices = [quote.yesterday_close, quote.current_price]
                
                indicators.ma5 = quote.current_price
                indicators.ma20 = quote.current_price
                indicators.rsi = 50.0  # 中性RSI
                
                # 创建简化的高级指标
                self._advanced_indicators = AdvancedTechnicalIndicators(
                    ma5=quote.current_price,
                    ma20=quote.current_price,
                    rsi=50.0
                )
            
            return indicators
            
        except Exception as e:
            self.logger.error(f"计算技术指标失败: {e}")
            return TechnicalIndicators()
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """计算RSI"""
        if len(prices) < period + 1:
            return 50.0
            
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def _calculate_macd(self, prices: List[float]) -> tuple[float, float]:
        """计算MACD"""
        if len(prices) < 26:
            return 0.0, 0.0
        
        prices_array = np.array(prices)
        
        # 计算EMA
        ema12 = self._calculate_ema(prices_array, 12)
        ema26 = self._calculate_ema(prices_array, 26)
        
        macd_line = ema12[-1] - ema26[-1]
        
        # 计算信号线（MACD的9日EMA）
        if len(prices) >= 35:  # 需要更多数据点来计算信号线
            macd_history = ema12[-9:] - ema26[-9:]
            signal_line = np.mean(macd_history)  # 简化处理
        else:
            signal_line = macd_line
        
        return float(macd_line), float(signal_line)
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """计算指数移动平均"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]
        
        return ema
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> tuple[float, float, float]:
        """计算布林带"""
        if len(prices) < period:
            current_price = prices[-1]
            return current_price, current_price, current_price
        
        recent_prices = prices[-period:]
        middle = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return float(upper), float(middle), float(lower)
    
    def analyze_technical_signals(self, quote: StockQuote, indicators: TechnicalIndicators) -> List[AnalysisSignal]:
        """分析技术信号 - 使用高级技术分析"""
        signals = []
        
        try:
            # 使用高级技术分析结果
            if hasattr(self, '_advanced_indicators') and self._advanced_indicators:
                advanced_indicators = self._advanced_indicators
                
                # 获取技术强度分析
                strength_analysis = analyze_technical_strength(advanced_indicators, quote.current_price)
                
                # 根据技术强度生成信号
                if strength_analysis['strength_percentage'] >= 70:
                    signals.append(AnalysisSignal(
                        type="technical",
                        signal="buy",
                        strength=0.8,
                        description=f"技术面强势 ({strength_analysis['strength_percentage']:.1f}%)",
                        confidence=0.8
                    ))
                elif strength_analysis['strength_percentage'] <= 30:
                    signals.append(AnalysisSignal(
                        type="technical",
                        signal="sell",
                        strength=0.8,
                        description=f"技术面弱势 ({strength_analysis['strength_percentage']:.1f}%)",
                        confidence=0.8
                    ))
                
                # 添加具体的技术信号
                for signal_desc in strength_analysis['signals']:
                    if any(keyword in signal_desc for keyword in ['金叉', '突破', '超卖', '强势']):
                        signals.append(AnalysisSignal(
                            type="technical",
                            signal="buy",
                            strength=0.6,
                            description=signal_desc,
                            confidence=0.6
                        ))
                    elif any(keyword in signal_desc for keyword in ['死叉', '跌破', '超买', '弱势']):
                        signals.append(AnalysisSignal(
                            type="technical",
                            signal="sell",
                            strength=0.6,
                            description=signal_desc,
                            confidence=0.6
                        ))
                    else:
                        signals.append(AnalysisSignal(
                            type="technical",
                            signal="neutral",
                            strength=0.4,
                            description=signal_desc,
                            confidence=0.5
                        ))
                
                # KDJ信号
                if advanced_indicators.kdj_k and advanced_indicators.kdj_d:
                    if advanced_indicators.kdj_k > advanced_indicators.kdj_d and advanced_indicators.kdj_k < 80:
                        signals.append(AnalysisSignal(
                            type="technical",
                            signal="buy",
                            strength=0.7,
                            description=f"KDJ金叉 (K:{advanced_indicators.kdj_k:.1f})",
                            confidence=0.7
                        ))
                    elif advanced_indicators.kdj_k < 20:
                        signals.append(AnalysisSignal(
                            type="technical",
                            signal="buy",
                            strength=0.6,
                            description="KDJ超卖区域",
                            confidence=0.6
                        ))
                    elif advanced_indicators.kdj_k > 80:
                        signals.append(AnalysisSignal(
                            type="technical",
                            signal="sell",
                            strength=0.6,
                            description="KDJ超买区域",
                            confidence=0.6
                        ))
                
                # 威廉指标信号
                if advanced_indicators.williams_r:
                    if advanced_indicators.williams_r < -80:
                        signals.append(AnalysisSignal(
                            type="technical",
                            signal="buy",
                            strength=0.5,
                            description="威廉指标超卖",
                            confidence=0.5
                        ))
                    elif advanced_indicators.williams_r > -20:
                        signals.append(AnalysisSignal(
                            type="technical",
                            signal="sell",
                            strength=0.5,
                            description="威廉指标超买",
                            confidence=0.5
                        ))
                
                # 布林带位置信号
                if advanced_indicators.bb_percent:
                    if advanced_indicators.bb_percent > 90:
                        signals.append(AnalysisSignal(
                            type="technical",
                            signal="sell",
                            strength=0.6,
                            description="价格接近布林带上轨",
                            confidence=0.6
                        ))
                    elif advanced_indicators.bb_percent < 10:
                        signals.append(AnalysisSignal(
                            type="technical",
                            signal="buy",
                            strength=0.6,
                            description="价格接近布林带下轨",
                            confidence=0.6
                        ))
            
            else:
                # 回退到基础分析
                self._add_basic_technical_signals(signals, quote, indicators)
            
            return signals
            
        except Exception as e:
            self.logger.error(f"分析技术信号失败: {e}")
            return []
    
    async def analyze_fundamental_signals(self, quote: StockQuote) -> List[AnalysisSignal]:
        """增强基本面分析"""
        signals = await super().analyze_fundamental_signals(quote)
        
        try:
            # 获取基本面数据
            fundamental_data = await get_fundamental_data(self.symbol, self.config)
            
            if fundamental_data:
                # 分析基本面强度
                industry = self.config.get('industry', '未知')
                strength_analysis = analyze_fundamental_strength(fundamental_data, industry)
                
                # 根据基本面强度生成信号
                if strength_analysis['strength_percentage'] >= 75:
                    signals.append(AnalysisSignal(
                        type="fundamental",
                        signal="buy",
                        strength=0.8,
                        description=f"基本面优秀 ({strength_analysis['strength_percentage']:.1f}%)",
                        confidence=0.8
                    ))
                elif strength_analysis['strength_percentage'] <= 40:
                    signals.append(AnalysisSignal(
                        type="fundamental",
                        signal="sell",
                        strength=0.7,
                        description=f"基本面较弱 ({strength_analysis['strength_percentage']:.1f}%)",
                        confidence=0.7
                    ))
                else:
                    signals.append(AnalysisSignal(
                        type="fundamental",
                        signal="neutral",
                        strength=0.5,
                        description=f"基本面{strength_analysis['overall_strength']}",
                        confidence=0.6
                    ))
                
                # 添加具体的基本面信号
                for signal_desc in strength_analysis['signals']:
                    if any(keyword in signal_desc for keyword in ['优秀', '良好', '健康', '高增长', '稳定增长']):
                        signals.append(AnalysisSignal(
                            type="fundamental",
                            signal="buy",
                            strength=0.6,
                            description=signal_desc,
                            confidence=0.6
                        ))
                    elif any(keyword in signal_desc for keyword in ['偏低', '偏高', '负增长', '紧张']):
                        signals.append(AnalysisSignal(
                            type="fundamental",
                            signal="sell",
                            strength=0.5,
                            description=signal_desc,
                            confidence=0.5
                        ))
                    else:
                        signals.append(AnalysisSignal(
                            type="fundamental",
                            signal="neutral",
                            strength=0.4,
                            description=signal_desc,
                            confidence=0.4
                        ))
                
                # 估值分析
                if fundamental_data.pe_ratio:
                    if fundamental_data.pe_ratio < 15:
                        signals.append(AnalysisSignal(
                            type="fundamental",
                            signal="buy",
                            strength=0.7,
                            description=f"PE估值偏低 ({fundamental_data.pe_ratio:.1f})",
                            confidence=0.7
                        ))
                    elif fundamental_data.pe_ratio > 40:
                        signals.append(AnalysisSignal(
                            type="fundamental",
                            signal="sell",
                            strength=0.6,
                            description=f"PE估值偏高 ({fundamental_data.pe_ratio:.1f})",
                            confidence=0.6
                        ))
                
                # 保存基本面数据供后续使用
                self._fundamental_data = fundamental_data
            
        except Exception as e:
            self.logger.error(f"基本面分析失败: {e}")
        
        return signals
    
    async def analyze_sentiment_signals(self, quote: StockQuote) -> List[AnalysisSignal]:
        """情绪分析"""
        signals = await super().analyze_sentiment_signals(quote)
        
        try:
            # 获取情绪数据
            sentiment_data = await get_sentiment_data(self.symbol, self.config)
            
            if sentiment_data:
                # 分析情绪强度
                strength_analysis = analyze_sentiment_strength(sentiment_data)
                
                # 根据情绪强度生成信号
                if strength_analysis['strength_percentage'] >= 70:
                    signals.append(AnalysisSignal(
                        type="sentiment",
                        signal="buy",
                        strength=0.7,
                        description=f"市场情绪乐观 ({strength_analysis['strength_percentage']:.1f}%)",
                        confidence=0.6
                    ))
                elif strength_analysis['strength_percentage'] <= 30:
                    signals.append(AnalysisSignal(
                        type="sentiment",
                        signal="sell",
                        strength=0.6,
                        description=f"市场情绪悲观 ({strength_analysis['strength_percentage']:.1f}%)",
                        confidence=0.6
                    ))
                else:
                    signals.append(AnalysisSignal(
                        type="sentiment",
                        signal="neutral",
                        strength=0.4,
                        description=f"市场情绪{strength_analysis['overall_mood']}",
                        confidence=0.5
                    ))
                
                # 添加具体的情绪信号
                for signal_desc in strength_analysis['signals']:
                    if any(keyword in signal_desc for keyword in ['积极', '乐观', '看好']):
                        signals.append(AnalysisSignal(
                            type="sentiment",
                            signal="buy",
                            strength=0.5,
                            description=signal_desc,
                            confidence=0.5
                        ))
                    elif any(keyword in signal_desc for keyword in ['消极', '悲观', '看空']):
                        signals.append(AnalysisSignal(
                            type="sentiment",
                            signal="sell",
                            strength=0.5,
                            description=signal_desc,
                            confidence=0.5
                        ))
                    else:
                        signals.append(AnalysisSignal(
                            type="sentiment",
                            signal="neutral",
                            strength=0.3,
                            description=signal_desc,
                            confidence=0.4
                        ))
                
                # 新闻情绪特殊处理
                if sentiment_data.news_sentiment_score:
                    if sentiment_data.news_sentiment_score > 0.4:
                        signals.append(AnalysisSignal(
                            type="sentiment",
                            signal="buy",
                            strength=0.6,
                            description=f"新闻情绪强烈积极 ({sentiment_data.news_sentiment_score:.2f})",
                            confidence=0.7
                        ))
                    elif sentiment_data.news_sentiment_score < -0.4:
                        signals.append(AnalysisSignal(
                            type="sentiment",
                            signal="sell",
                            strength=0.6,
                            description=f"新闻情绪强烈消极 ({sentiment_data.news_sentiment_score:.2f})",
                            confidence=0.7
                        ))
                
                # 保存情绪数据供后续使用
                self._sentiment_data = sentiment_data
            
        except Exception as e:
            self.logger.error(f"情绪分析失败: {e}")
        
        return signals
    
    def _add_basic_technical_signals(self, signals: List[AnalysisSignal], quote: StockQuote, indicators: TechnicalIndicators):
        """添加基础技术信号"""
        # 价格趋势信号
        if quote.change_pct > 5:
            signals.append(AnalysisSignal(
                type="technical",
                signal="buy",
                strength=0.8,
                description="强势上涨",
                confidence=0.7
            ))
        elif quote.change_pct < -5:
            signals.append(AnalysisSignal(
                type="technical",
                signal="sell",
                strength=0.8,
                description="强势下跌",
                confidence=0.7
            ))
        
        # 成交量信号
        if quote.volume > 50000000:
            signals.append(AnalysisSignal(
                type="technical",
                signal="neutral",
                strength=0.5,
                description="成交量放大",
                confidence=0.8
            ))


class SpecializedAnalyzer(StandardStockAnalyzer):
    """特殊股票分析器（如新能源汽车等）"""
    
    async def analyze_fundamental_signals(self, quote: StockQuote) -> List[AnalysisSignal]:
        """增强的基本面分析"""
        signals = await super().analyze_fundamental_signals(quote)
        
        # 基于股票特殊特性的分析
        special_features = self.config.get('special_features', [])
        
        # 华为概念股特殊分析
        if "华为概念" in special_features:
            if quote.change_pct > 3:
                signals.append(AnalysisSignal(
                    type="fundamental",
                    signal="buy",
                    strength=0.7,
                    description="华为概念利好",
                    confidence=0.6
                ))
        
        # 新能源汽车行业分析
        if "新能源汽车" in special_features or "增程式电动车" in special_features:
            # 行业景气度分析（简化）
            if quote.turnover > 500000000:  # 成交额超过5亿
                signals.append(AnalysisSignal(
                    type="fundamental",
                    signal="buy",
                    strength=0.6,
                    description="新能源汽车板块活跃",
                    confidence=0.5
                ))
        
        return signals


class StockAnalyzerFactory:
    """股票分析器工厂"""
    
    @staticmethod
    def create_analyzer(symbol: str) -> Optional[BaseStockAnalyzer]:
        """创建股票分析器"""
        # 获取股票配置
        config = get_stock_config(symbol)
        if not config:
            return None
        
        # 转换配置为字典
        config_dict = config.to_dict()
        
        # 根据股票特性选择分析器
        special_features = config.special_features
        
        # 如果有特殊特性，使用专门分析器
        if special_features and len(special_features) > 0:
            return SpecializedAnalyzer(symbol, config_dict)
        else:
            return StandardStockAnalyzer(symbol, config_dict)
    
    @staticmethod
    async def analyze_stock(symbol: str) -> Optional[Dict[str, Any]]:
        """分析股票（便捷方法）"""
        analyzer = StockAnalyzerFactory.create_analyzer(symbol)
        if not analyzer:
            return None
        
        try:
            result = await analyzer.run_analysis()
            return result.to_dict()
        except Exception as e:
            return {
                'symbol': symbol,
                'error': str(e),
                'analysis_time': None
            }


# 便捷函数
async def analyze_stock(symbol: str) -> Optional[Dict[str, Any]]:
    """分析股票"""
    return await StockAnalyzerFactory.analyze_stock(symbol)


async def batch_analyze_stocks(symbols: List[str]) -> Dict[str, Any]:
    """批量分析股票"""
    tasks = [StockAnalyzerFactory.analyze_stock(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return {
        symbol: result if not isinstance(result, Exception) else {'error': str(result)}
        for symbol, result in zip(symbols, results)
    }


if __name__ == "__main__":
    # 测试分析器工厂
    async def test_analyzer():
        print("=== 测试股票分析器工厂 ===")
        
        # 测试赛力斯
        print("\n--- 分析赛力斯 ---")
        result = await analyze_stock("601127.SH")
        if result:
            print(f"股票: {result['symbol']} - {result['company_name']}")
            print(f"建议: {result['recommendation']} (置信度: {result['confidence']:.2f})")
            print(f"风险等级: {result['risk_level']}")
            if result['quote']:
                quote = result['quote']
                print(f"价格: ¥{quote['current_price']:.2f} ({quote['change_pct']:+.2f}%)")
        
        # 测试理想汽车
        print("\n--- 分析理想汽车 ---")
        result = await analyze_stock("2015.HK")
        if result:
            print(f"股票: {result['symbol']} - {result['company_name']}")
            print(f"建议: {result['recommendation']} (置信度: {result['confidence']:.2f})")
        
        # 批量测试
        print("\n--- 批量分析测试 ---")
        batch_result = await batch_analyze_stocks(["601127.SH", "2015.HK", "600418.SH"])
        for symbol, data in batch_result.items():
            if 'error' not in data:
                print(f"{symbol}: {data['recommendation']}")
            else:
                print(f"{symbol}: 错误 - {data['error']}")
    
    asyncio.run(test_analyzer())