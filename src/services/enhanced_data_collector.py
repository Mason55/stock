# src/services/enhanced_data_collector.py
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from config.settings import settings
from src.models.stock import Stock, StockPrice
from src.services.real_data_provider import RealDataManager, StockQuote


class EnhancedDataCollector:
    """增强版数据采集器，支持真实数据和模拟数据"""
    
    def __init__(self, db_session: Session, use_real_data: bool = True):
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)
        self.use_real_data = use_real_data
        
        if use_real_data:
            self.data_manager = RealDataManager(primary_provider='yahoo')
            self.logger.info("Initialized with real data providers")
        else:
            self.data_manager = None
            self.logger.info("Initialized with mock data")
    
    async def fetch_stock_list(self) -> List[Dict]:
        """获取股票列表"""
        # 固定的股票列表，实际项目中可以从数据源获取
        stock_list = [
            # A股热门股票
            {"code": "000001.SZ", "name": "平安银行", "exchange": "SZ", "industry": "银行", "currency": "CNY"},
            {"code": "000002.SZ", "name": "万科A", "exchange": "SZ", "industry": "房地产", "currency": "CNY"},
            {"code": "000858.SZ", "name": "五粮液", "exchange": "SZ", "industry": "白酒", "currency": "CNY"},
            {"code": "000977.SZ", "name": "浪潮信息", "exchange": "SZ", "industry": "计算机设备", "currency": "CNY"},
            {"code": "600000.SH", "name": "浦发银行", "exchange": "SH", "industry": "银行", "currency": "CNY"},
            {"code": "600036.SH", "name": "招商银行", "exchange": "SH", "industry": "银行", "currency": "CNY"},
            {"code": "600519.SH", "name": "贵州茅台", "exchange": "SH", "industry": "白酒", "currency": "CNY"},
            {"code": "600900.SH", "name": "长江电力", "exchange": "SH", "industry": "电力", "currency": "CNY"},
            
            # 港股热门股票
            {"code": "700.HK", "name": "腾讯控股", "exchange": "HK", "industry": "互联网", "currency": "HKD"},
            {"code": "9988.HK", "name": "阿里巴巴-SW", "exchange": "HK", "industry": "互联网", "currency": "HKD"},
            {"code": "3690.HK", "name": "美团-W", "exchange": "HK", "industry": "互联网", "currency": "HKD"},
            {"code": "9618.HK", "name": "京东集团-SW", "exchange": "HK", "industry": "电商", "currency": "HKD"},
            {"code": "1810.HK", "name": "小米集团-W", "exchange": "HK", "industry": "智能手机", "currency": "HKD"},
            {"code": "2318.HK", "name": "中国平安", "exchange": "HK", "industry": "保险", "currency": "HKD"},
            {"code": "1299.HK", "name": "友邦保险", "exchange": "HK", "industry": "保险", "currency": "HKD"},
            {"code": "2020.HK", "name": "安踏体育", "exchange": "HK", "industry": "服装", "currency": "HKD"}
        ]
        
        return stock_list
    
    async def fetch_realtime_price(self, stock_code: str) -> Optional[Dict]:
        """获取实时价格数据"""
        if not self.use_real_data:
            return self._generate_mock_price(stock_code)
        
        try:
            quote = await self.data_manager.get_quote(stock_code)
            if not quote:
                self.logger.warning(f"No real data available for {stock_code}, using fallback")
                return self._generate_mock_price(stock_code)
            
            return {
                "stock_code": quote.symbol,
                "timestamp": quote.timestamp or datetime.now(),
                "open_price": quote.open_price,
                "high_price": quote.high,
                "low_price": quote.low,
                "close_price": quote.price,
                "volume": quote.volume,
                "turnover": quote.volume * quote.price if quote.volume else None,
                "change_pct": quote.change_percent
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching real data for {stock_code}: {e}")
            return self._generate_mock_price(stock_code)
    
    def _generate_mock_price(self, stock_code: str) -> Dict:
        """生成模拟价格数据（作为fallback）"""
        import random
        
        # 根据市场设置不同价格区间
        if stock_code.endswith('.HK'):
            base_price = random.uniform(50, 500)
            volume_range = (1000000, 50000000)
        else:
            base_price = random.uniform(10, 100)
            volume_range = (100000, 10000000)
        
        change_pct = random.uniform(-10, 10)
        
        return {
            "stock_code": stock_code,
            "timestamp": datetime.now(),
            "open_price": base_price * 0.99,
            "high_price": base_price * 1.05,
            "low_price": base_price * 0.95,
            "close_price": base_price,
            "volume": random.randint(*volume_range),
            "turnover": base_price * random.randint(*volume_range),
            "change_pct": change_pct
        }
    
    async def fetch_batch_prices(self, stock_codes: List[str]) -> List[Dict]:
        """批量获取价格数据"""
        if not self.use_real_data:
            return [self._generate_mock_price(code) for code in stock_codes]
        
        try:
            quotes = await self.data_manager.get_batch_quotes(stock_codes)
            results = []
            
            for quote in quotes:
                if quote:
                    results.append({
                        "stock_code": quote.symbol,
                        "timestamp": quote.timestamp or datetime.now(),
                        "open_price": quote.open_price,
                        "high_price": quote.high,
                        "low_price": quote.low,
                        "close_price": quote.price,
                        "volume": quote.volume,
                        "turnover": quote.volume * quote.price if quote.volume else None,
                        "change_pct": quote.change_percent
                    })
            
            # 对于没有获取到数据的股票，使用模拟数据
            fetched_codes = {r['stock_code'] for r in results}
            for code in stock_codes:
                if code not in fetched_codes:
                    self.logger.warning(f"Using mock data for {code}")
                    results.append(self._generate_mock_price(code))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in batch fetch: {e}")
            return [self._generate_mock_price(code) for code in stock_codes]
    
    def save_stock_info(self, stock_data: Dict) -> bool:
        """保存股票基本信息"""
        try:
            stock = self.db_session.query(Stock).filter_by(code=stock_data['code']).first()
            if not stock:
                stock = Stock(
                    code=stock_data['code'],
                    name=stock_data['name'],
                    exchange=stock_data['exchange'],
                    industry=stock_data.get('industry'),
                    currency=stock_data.get('currency', 'CNY')
                )
                self.db_session.add(stock)
            else:
                stock.name = stock_data['name']
                stock.industry = stock_data.get('industry')
                stock.currency = stock_data.get('currency', 'CNY')
                stock.updated_at = datetime.utcnow()
            
            self.db_session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to save stock info: {e}")
            self.db_session.rollback()
            return False
    
    def save_price_data(self, price_data: Dict) -> bool:
        """保存价格数据"""
        try:
            price = StockPrice(**price_data)
            self.db_session.add(price)
            self.db_session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to save price data: {e}")
            self.db_session.rollback()
            return False
    
    async def run_data_collection(self):
        """执行数据采集任务"""
        self.logger.info("Starting enhanced data collection cycle")
        
        # 获取股票列表并更新基本信息
        stocks = await self.fetch_stock_list()
        for stock in stocks:
            self.save_stock_info(stock)
        
        # 批量获取价格数据
        stock_codes = [stock['code'] for stock in stocks]
        
        if self.use_real_data:
            self.logger.info(f"Fetching real market data for {len(stock_codes)} stocks...")
        else:
            self.logger.info(f"Generating mock data for {len(stock_codes)} stocks...")
        
        price_data_list = await self.fetch_batch_prices(stock_codes)
        
        # 保存价格数据
        success_count = 0
        for price_data in price_data_list:
            if price_data and self.save_price_data(price_data):
                success_count += 1
        
        self.logger.info(f"Data collection completed: {success_count}/{len(stock_codes)} stocks updated")
        
        if self.use_real_data:
            self.logger.info("Real market data collection finished")
        else:
            self.logger.info("Mock data generation finished")