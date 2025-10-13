# src/services/mock_data.py - Mock data service for offline mode
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    from config.stock_symbols import ALL_STOCKS, get_stock_by_code
except Exception:  # pragma: no cover - defensive import for minimal environments
    ALL_STOCKS = []
    def get_stock_by_code(_code: str):
        return None

logger = logging.getLogger(__name__)


@dataclass
class MockStockData:
    code: str
    name: str
    current_price: float
    change_pct: float
    volume: int
    market_cap: float
    industry: str
    exchange: str


class MockDataService:
    """Provides mock stock data for offline/testing scenarios"""
    
    def __init__(self):
        self.stocks = self._initialize_mock_stocks()
        self.price_history: Dict[str, List[Dict]] = {}
        logger.info(
            "Mock data service initialized with %d sample stocks", len(self.stocks)
        )

    def _initialize_mock_stocks(self) -> Dict[str, MockStockData]:
        """Initialize sample stock data"""
        sample_stocks = {
            "600900.SH": MockStockData("600900.SH", "长江电力", 24.15, 2.85, 15680000, 580000000000, "电力", "SH"),
            "600036.SH": MockStockData("600036.SH", "招商银行", 41.80, 1.45, 8520000, 1200000000000, "银行", "SH"),
            "000001.SZ": MockStockData("000001.SZ", "平安银行", 12.50, -0.80, 12000000, 240000000000, "银行", "SZ"),
            "600519.SH": MockStockData("600519.SH", "贵州茅台", 1680.50, 0.30, 2100000, 2100000000000, "白酒", "SH"),
            "000002.SZ": MockStockData("000002.SZ", "万科A", 18.20, -1.20, 18000000, 200000000000, "房地产", "SZ"),
            "600276.SH": MockStockData("600276.SH", "恒瑞医药", 58.90, 1.80, 5600000, 380000000000, "医药", "SH"),
            "000858.SZ": MockStockData("000858.SZ", "五粮液", 158.30, 0.95, 3200000, 620000000000, "白酒", "SZ"),
            "002415.SZ": MockStockData("002415.SZ", "海康威视", 34.70, 2.15, 8900000, 320000000000, "安防", "SZ"),
            "600887.SH": MockStockData("600887.SH", "伊利股份", 32.40, -0.65, 6700000, 210000000000, "乳业", "SH"),
            "000725.SZ": MockStockData("000725.SZ", "京东方A", 4.85, 3.20, 45000000, 180000000000, "显示", "SZ"),
            "600580.SH": MockStockData("600580.SH", "卧龙电驱", 12.80, 1.10, 9200000, 26000000000, "电机", "SH"),
        }

        # Merge configured stock list with deterministic synthetic values for broader coverage
        for entry in ALL_STOCKS:
            code = entry.get("code")
            if not code or code in sample_stocks:
                continue
            sample_stocks[code] = self._create_synthetic_stock(entry)

        return sample_stocks

    def _create_synthetic_stock(self, meta: Dict[str, str]) -> MockStockData:
        """Create deterministic synthetic stock data from metadata."""
        code = meta.get("code")
        rng = random.Random(code)
        base_price = round(rng.uniform(8, 180), 2)
        change_pct = round(rng.uniform(-3, 3), 2)
        volume = rng.randint(2_000_000, 50_000_000)
        market_cap = int(base_price * volume * rng.uniform(45, 75)) * 10
        industry = meta.get("industry", "未知")
        exchange = meta.get("exchange", (code or "")[-2:])
        name = meta.get("name", code)

        return MockStockData(
            code=code,
            name=name,
            current_price=base_price,
            change_pct=change_pct,
            volume=volume,
            market_cap=market_cap,
            industry=industry,
            exchange=exchange,
        )

    def register_stock(
        self,
        code: str,
        name: str,
        industry: str = "未知",
        exchange: str = "SH",
        base_price: Optional[float] = None,
        change_pct: Optional[float] = None,
        volume: Optional[int] = None,
        market_cap: Optional[float] = None,
    ) -> None:
        """Register or override a stock in mock storage at runtime."""
        rng = random.Random(code)
        price = base_price if base_price is not None else round(rng.uniform(8, 200), 2)
        change = change_pct if change_pct is not None else round(rng.uniform(-3, 3), 2)
        vol = volume if volume is not None else rng.randint(2_000_000, 40_000_000)
        cap = market_cap if market_cap is not None else price * vol * rng.uniform(40, 70)
        self.stocks[code] = MockStockData(
            code=code,
            name=name,
            current_price=price,
            change_pct=change,
            volume=vol,
            market_cap=cap,
            industry=industry,
            exchange=exchange,
        )
        logger.info("Registered mock stock %s - %s", code, name)

    def _ensure_stock(self, stock_code: str) -> Optional[MockStockData]:
        """Ensure stock exists, auto-generating synthetic data when needed."""
        stock = self.stocks.get(stock_code)
        if stock:
            return stock

        meta = get_stock_by_code(stock_code) or {
            "code": stock_code,
            "name": stock_code,
        }
        synthetic = self._create_synthetic_stock(meta)
        self.stocks[stock_code] = synthetic
        logger.debug("Generated synthetic mock data for %s", stock_code)
        return synthetic
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """Get basic stock information"""
        stock = self._ensure_stock(stock_code)
        if not stock:
            return None

        return {
            'code': stock.code,
            'name': stock.name,
            'exchange': stock.exchange,
            'industry': stock.industry,
            'market_cap': stock.market_cap,
            'current_price': stock.current_price,
            'change_pct': stock.change_pct,
            'volume': stock.volume,
            'last_updated': datetime.now().isoformat()
        }
    
    def get_realtime_data(self, stock_code: str) -> Optional[Dict]:
        """Get mock real-time data"""
        stock = self._ensure_stock(stock_code)
        if not stock:
            return None

        # Simulate small price movements
        price_change = random.uniform(-0.02, 0.02)  # ±2%
        current_price = stock.current_price * (1 + price_change)
        change_pct = ((current_price - stock.current_price) / stock.current_price) * 100
        
        return {
            'stock_code': stock_code,
            'current_price': round(current_price, 2),
            'price_change': round(change_pct, 2),
            'volume': stock.volume + random.randint(-1000000, 1000000),
            'timestamp': datetime.now().isoformat(),
            'market_status': 'closed'  # Simplified for mock
        }
    
    def get_historical_data(self, stock_code: str, days: int = 30) -> Optional[Dict]:
        """Generate mock historical data"""
        stock = self._ensure_stock(stock_code)
        if not stock:
            return None

        data = []
        base_price = stock.current_price
        current_date = datetime.now()
        
        for i in range(days):
            date = current_date - timedelta(days=i)
            
            # Simulate price movement
            daily_change = random.uniform(-0.05, 0.05)  # ±5% daily
            price = base_price * (1 + daily_change)
            
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': round(price * 0.995, 2),
                'high': round(price * 1.02, 2),
                'low': round(price * 0.98, 2),
                'close': round(price, 2),
                'volume': stock.volume + random.randint(-5000000, 5000000)
            })
            
            base_price = price  # Use as base for next day
        
        return {
            'stock_code': stock_code,
            'period': f"{days}d",
            'data_count': len(data),
            'data': list(reversed(data))  # Chronological order
        }
    
    def get_stock_analysis(self, stock_code: str, analysis_type: str = 'all') -> Optional[Dict]:
        """Generate mock analysis data"""
        stock = self._ensure_stock(stock_code)
        if not stock:
            return None
        
        result = {
            'stock_code': stock_code,
            'company_name': stock.name,
            'current_price': stock.current_price,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        if analysis_type in ['technical', 'all']:
            trend_score = random.uniform(0.2, 0.8)
            trend = 'bullish' if trend_score > 0.6 else 'bearish' if trend_score < 0.4 else 'neutral'
            
            result['technical_analysis'] = {
                'overall_trend': trend,
                'trend_strength': round(trend_score, 2),
                'support_levels': [round(stock.current_price * 0.95, 2), round(stock.current_price * 0.90, 2)],
                'resistance_levels': [round(stock.current_price * 1.05, 2), round(stock.current_price * 1.10, 2)],
                'indicators': {
                    'rsi': round(random.uniform(30, 70), 1),
                    'macd': round(random.uniform(-1, 1), 3),
                    'volume_trend': random.choice(['increasing', 'decreasing', 'stable'])
                }
            }
        
        if analysis_type in ['fundamental', 'all']:
            result['fundamental_analysis'] = {
                'valuation': {
                    'pe_ratio': round(random.uniform(8, 25), 1),
                    'pb_ratio': round(random.uniform(0.8, 3.0), 1)
                },
                'profitability': {
                    'roe': round(random.uniform(0.08, 0.20), 3),
                    'roa': round(random.uniform(0.03, 0.15), 3)
                },
                'growth': {
                    'revenue_growth': round(random.uniform(-0.1, 0.3), 3)
                },
                'financial_health': {
                    'debt_ratio': round(random.uniform(0.2, 0.6), 2)
                }
            }
        
        if analysis_type in ['sentiment', 'all']:
            sentiment_score = random.uniform(0.3, 0.7)
            result['sentiment_analysis'] = {
                'overall_sentiment': round(sentiment_score, 2),
                'sentiment_level': 'positive' if sentiment_score > 0.6 else 'negative' if sentiment_score < 0.4 else 'neutral',
                'news_sentiment': {
                    'score': round(random.uniform(0.4, 0.6), 2),
                    'article_count': random.randint(5, 20)
                },
                'social_sentiment': {
                    'score': round(random.uniform(0.4, 0.6), 2),
                    'mention_count': random.randint(50, 200)
                }
            }
        
        if analysis_type == 'all':
            # Generate investment recommendation
            tech_score = result['technical_analysis']['trend_strength'] * 10
            fund_score = (1 - result['fundamental_analysis']['valuation']['pe_ratio'] / 25) * 10
            sentiment_score = result['sentiment_analysis']['overall_sentiment'] * 10
            
            overall_score = (tech_score + fund_score + sentiment_score) / 3
            
            if overall_score >= 7:
                action = '买入'
                risk_level = '低风险'
            elif overall_score >= 5:
                action = '持有'
                risk_level = '中等风险'
            else:
                action = '观望'
                risk_level = '高风险'
            
            result['recommendation'] = {
                'action': action,
                'confidence': round(overall_score / 10, 2),
                'score': round(overall_score, 1),
                'risk_level': risk_level
            }
        
        return result
    
    def list_available_stocks(self, limit: int = 50) -> List[Dict]:
        """List available mock stocks"""
        stocks = list(self.stocks.values())[:limit]
        return [
            {
                'code': stock.code,
                'name': stock.name,
                'exchange': stock.exchange,
                'industry': stock.industry,
                'current_price': stock.current_price,
                'change_pct': stock.change_pct
            }
            for stock in stocks
        ]
    
    def batch_analysis(self, stock_codes: List[str], analysis_types: List[str] = None) -> Dict:
        """Perform batch analysis on multiple stocks"""
        if analysis_types is None:
            analysis_types = ['technical']
        
        results = []
        for stock_code in stock_codes:
            try:
                stock = self.stocks.get(stock_code)
                if stock:
                    analysis = {
                        'stock_code': stock_code,
                        'company_name': stock.name,
                        'status': 'success'
                    }
                    
                    # Add simple scores for requested analysis types
                    if 'technical' in analysis_types:
                        analysis['technical_score'] = round(random.uniform(3.0, 8.0), 1)
                    if 'fundamental' in analysis_types:
                        analysis['fundamental_score'] = round(random.uniform(4.0, 7.5), 1)
                    
                    results.append(analysis)
                else:
                    results.append({
                        'stock_code': stock_code,
                        'status': 'error',
                        'error': 'Stock not found in mock data'
                    })
            except Exception as e:
                results.append({
                    'stock_code': stock_code,
                    'status': 'error',
                    'error': str(e)
                })
        
        successful = [r for r in results if r.get('status') == 'success']
        
        return {
            'batch_id': f"mock_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'total_stocks': len(stock_codes),
            'completed': len(successful),
            'failed': len(stock_codes) - len(successful),
            'results': results,
            'summary': {
                'success_rate': len(successful) / len(stock_codes) if stock_codes else 0
            }
        }


# Global mock data service instance
mock_data_service = MockDataService()
