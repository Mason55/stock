# src/core/base_analyzer.py - 统一股票分析器基类
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio
import logging


@dataclass
class StockQuote:
    """标准化股票行情数据"""
    symbol: str
    name: str
    current_price: float
    change: float
    change_pct: float
    open_price: float
    high_price: float
    low_price: float
    yesterday_close: float
    volume: int
    turnover: float
    timestamp: datetime = field(default_factory=datetime.now)
    currency: str = "CNY"
    market: str = "A"  # A股、HK、US等


@dataclass 
class TechnicalIndicators:
    """技术指标数据"""
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    volume_ma: Optional[float] = None


@dataclass
class AnalysisSignal:
    """分析信号"""
    type: str  # technical, fundamental, sentiment
    signal: str  # buy, sell, hold
    strength: float  # 信号强度 0-1
    description: str
    confidence: float  # 置信度 0-1


@dataclass
class AnalysisResult:
    """标准化分析结果"""
    symbol: str
    company_name: str
    analysis_time: datetime
    quote: Optional[StockQuote]
    technical_indicators: Optional[TechnicalIndicators]
    fundamental_data: Optional[Any] = None  # 基本面数据
    sentiment_data: Optional[Any] = None  # 情绪数据
    signals: List[AnalysisSignal] = field(default_factory=list)
    recommendation: str = "HOLD"  # BUY, SELL, HOLD
    confidence: float = 0.5
    overall_score: float = 0.5
    risk_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    key_factors: List[str] = field(default_factory=list)
    market_context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        quote_dict = None
        if self.quote:
            quote_dict = dict(self.quote.__dict__)
            # 转换datetime为字符串
            if 'timestamp' in quote_dict and hasattr(quote_dict['timestamp'], 'isoformat'):
                quote_dict['timestamp'] = quote_dict['timestamp'].isoformat()
        
        # 处理基本面数据
        fundamental_dict = None
        if self.fundamental_data and hasattr(self.fundamental_data, 'to_dict'):
            fundamental_dict = self.fundamental_data.to_dict()
        
        # 处理情绪数据
        sentiment_dict = None
        if self.sentiment_data and hasattr(self.sentiment_data, 'to_dict'):
            sentiment_dict = self.sentiment_data.to_dict()
        
        return {
            'symbol': self.symbol,
            'company_name': self.company_name,
            'analysis_time': self.analysis_time.isoformat(),
            'quote': quote_dict,
            'technical_indicators': self.technical_indicators.__dict__ if self.technical_indicators else None,
            'fundamental_data': fundamental_dict,
            'sentiment_data': sentiment_dict,
            'signals': [signal.__dict__ for signal in self.signals],
            'recommendation': self.recommendation,
            'confidence': self.confidence,
            'overall_score': self.overall_score,
            'risk_level': self.risk_level,
            'key_factors': self.key_factors,
            'market_context': self.market_context
        }


class BaseStockAnalyzer(ABC):
    """股票分析器基类"""
    
    def __init__(self, symbol: str, config: Dict[str, Any]):
        self.symbol = symbol
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{symbol}")
        
        # 从配置中提取基本信息
        self.company_name = config.get('name', symbol)
        self.market = config.get('market', 'A')
        self.currency = config.get('currency', 'CNY')
        self.industry = config.get('industry', 'Unknown')
        self.sina_code = config.get('sina_code', '')
        
    @abstractmethod
    async def fetch_real_time_data(self) -> Optional[StockQuote]:
        """获取实时行情数据"""
        pass
    
    @abstractmethod
    def calculate_technical_indicators(self, quote: StockQuote, historical_data: Optional[List] = None) -> TechnicalIndicators:
        """计算技术指标"""
        pass
    
    @abstractmethod
    def analyze_technical_signals(self, quote: StockQuote, indicators: TechnicalIndicators) -> List[AnalysisSignal]:
        """分析技术信号"""
        pass
    
    async def analyze_fundamental_signals(self, quote: StockQuote) -> List[AnalysisSignal]:
        """分析基本面信号（默认实现）"""
        signals = []
        
        # 简单的基本面分析
        if quote.turnover > 100000000:  # 成交额超过1亿
            signals.append(AnalysisSignal(
                type="fundamental",
                signal="neutral",
                strength=0.6,
                description="成交活跃",
                confidence=0.7
            ))
            
        return signals
    
    async def analyze_sentiment_signals(self, quote: StockQuote) -> List[AnalysisSignal]:
        """分析情绪信号（默认实现）"""
        signals = []
        
        # 简单的情绪分析
        # 基于成交量判断市场关注度
        if quote.volume > 50000000:  # 大成交量
            signals.append(AnalysisSignal(
                type="sentiment",
                signal="neutral",
                strength=0.5,
                description="市场关注度高",
                confidence=0.6
            ))
            
        return signals
    
    def analyze_market_context(self) -> Dict[str, Any]:
        """分析市场环境"""
        now = datetime.now()
        hour = now.hour
        
        # 判断交易状态
        if self.market == "A":
            trading = (9 <= hour < 12) or (13 <= hour < 15)
        elif self.market == "HK":
            trading = (9 <= hour < 12) or (13 <= hour < 16)
        elif self.market == "US":
            # 简化处理，不考虑时区
            trading = (21 <= hour) or (hour < 5)
        else:
            trading = False
            
        return {
            'market': self.market,
            'trading_status': 'TRADING' if trading else 'CLOSED',
            'industry': self.industry,
            'analysis_session': f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
        }
    
    def calculate_overall_recommendation(self, signals: List[AnalysisSignal]) -> tuple[str, float, float]:
        """计算综合建议"""
        if not signals:
            return "HOLD", 0.5, 0.5
            
        # 计算加权评分
        total_weight = 0
        weighted_score = 0
        confidence_sum = 0
        
        signal_weights = {
            'technical': 0.6,
            'fundamental': 0.3,
            'sentiment': 0.1
        }
        
        for signal in signals:
            weight = signal_weights.get(signal.type, 0.5) * signal.strength
            if signal.signal == 'buy':
                score = 1.0
            elif signal.signal == 'sell':
                score = 0.0
            else:  # hold
                score = 0.5
                
            weighted_score += score * weight
            total_weight += weight
            confidence_sum += signal.confidence
            
        if total_weight == 0:
            return "HOLD", 0.5, 0.5
            
        overall_score = weighted_score / total_weight
        avg_confidence = confidence_sum / len(signals)
        
        # 确定建议
        if overall_score >= 0.7:
            recommendation = "BUY"
        elif overall_score <= 0.3:
            recommendation = "SELL"
        else:
            recommendation = "HOLD"
            
        return recommendation, overall_score, avg_confidence
    
    def calculate_risk_level(self, quote: StockQuote, indicators: TechnicalIndicators) -> str:
        """计算风险等级"""
        risk_score = 0
        
        # 价格波动风险
        if quote.high_price > 0 and quote.low_price > 0:
            daily_volatility = (quote.high_price - quote.low_price) / quote.low_price
            if daily_volatility > 0.10:  # 日内波动超过10%
                risk_score += 2
            elif daily_volatility > 0.05:  # 日内波动超过5%
                risk_score += 1
                
        # 涨跌幅风险
        if abs(quote.change_pct) > 8:  # 涨跌幅超过8%
            risk_score += 2
        elif abs(quote.change_pct) > 5:  # 涨跌幅超过5%
            risk_score += 1
            
        # 成交量风险（流动性）
        if quote.volume < 1000000:  # 成交量过小
            risk_score += 1
            
        # RSI风险
        if indicators.rsi:
            if indicators.rsi > 80 or indicators.rsi < 20:  # RSI极值
                risk_score += 1
                
        # 风险等级判定
        if risk_score >= 4:
            return "HIGH"
        elif risk_score >= 2:
            return "MEDIUM"
        else:
            return "LOW"
    
    async def run_analysis(self) -> AnalysisResult:
        """运行完整分析流程"""
        try:
            # 1. 获取实时数据
            quote = await self.fetch_real_time_data()
            if not quote:
                raise ValueError(f"无法获取 {self.symbol} 的实时数据")
                
            # 2. 计算技术指标
            indicators = self.calculate_technical_indicators(quote)
            
            # 3. 分析各类信号
            technical_signals = self.analyze_technical_signals(quote, indicators)
            fundamental_signals = await self.analyze_fundamental_signals(quote)
            sentiment_signals = await self.analyze_sentiment_signals(quote)
            
            all_signals = technical_signals + fundamental_signals + sentiment_signals
            
            # 4. 计算综合建议
            recommendation, overall_score, confidence = self.calculate_overall_recommendation(all_signals)
            
            # 5. 计算风险等级
            risk_level = self.calculate_risk_level(quote, indicators)
            
            # 6. 提取关键因子
            key_factors = [signal.description for signal in all_signals if signal.strength > 0.7]
            
            # 7. 市场环境分析
            market_context = self.analyze_market_context()
            
            # 获取基本面和情绪数据（如果analyzer有的话）
            fundamental_data = getattr(self, '_fundamental_data', None)
            sentiment_data = getattr(self, '_sentiment_data', None)
            
            return AnalysisResult(
                symbol=self.symbol,
                company_name=self.company_name,
                analysis_time=datetime.now(),
                quote=quote,
                technical_indicators=indicators,
                fundamental_data=fundamental_data,
                sentiment_data=sentiment_data,
                signals=all_signals,
                recommendation=recommendation,
                confidence=confidence,
                overall_score=overall_score,
                risk_level=risk_level,
                key_factors=key_factors,
                market_context=market_context
            )
            
        except Exception as e:
            self.logger.error(f"分析失败: {e}")
            # 返回错误结果
            return AnalysisResult(
                symbol=self.symbol,
                company_name=self.company_name,
                analysis_time=datetime.now(),
                quote=None,
                technical_indicators=None,
                signals=[],
                recommendation="HOLD",
                confidence=0.0,
                overall_score=0.5,
                risk_level="HIGH",
                key_factors=[f"分析错误: {str(e)}"],
                market_context=self.analyze_market_context()
            )