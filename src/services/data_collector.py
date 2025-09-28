# src/services/data_collector.py - Data collection service
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
import aiohttp
import pandas as pd
from sqlalchemy.orm import Session
from config.settings import settings
from src.models.stock import Stock, StockPrice


class DataCollector:
    """Handles data collection from multiple sources"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=settings.API_TIMEOUT)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_stock_list(self) -> List[Dict]:
        """Fetch list of all available stocks (A-share + HK)"""
        try:
            # Mock implementation - replace with real data source
            mock_stocks = [
                # A-share stocks
                {"code": "000001.SZ", "name": "平安银行", "exchange": "SZ", "industry": "银行", "currency": "CNY"},
                {"code": "000002.SZ", "name": "万科A", "exchange": "SZ", "industry": "房地产", "currency": "CNY"},
                {"code": "600000.SH", "name": "浦发银行", "exchange": "SH", "industry": "银行", "currency": "CNY"},
                {"code": "600036.SH", "name": "招商银行", "exchange": "SH", "industry": "银行", "currency": "CNY"},
                {"code": "000858.SZ", "name": "五粮液", "exchange": "SZ", "industry": "白酒", "currency": "CNY"},
                {"code": "000977.SZ", "name": "浪潮信息", "exchange": "SZ", "industry": "计算机设备", "currency": "CNY"},
                # Hong Kong stocks
                {"code": "700.HK", "name": "腾讯控股", "exchange": "HK", "industry": "互联网", "currency": "HKD"},
                {"code": "9988.HK", "name": "阿里巴巴-SW", "exchange": "HK", "industry": "互联网", "currency": "HKD"},
                {"code": "3690.HK", "name": "美团-W", "exchange": "HK", "industry": "互联网", "currency": "HKD"},
                {"code": "9618.HK", "name": "京东集团-SW", "exchange": "HK", "industry": "电商", "currency": "HKD"},
                {"code": "2318.HK", "name": "中国平安", "exchange": "HK", "industry": "保险", "currency": "HKD"},
                {"code": "1299.HK", "name": "友邦保险", "exchange": "HK", "industry": "保险", "currency": "HKD"},
                {"code": "2020.HK", "name": "安踏体育", "exchange": "HK", "industry": "服装", "currency": "HKD"},
                {"code": "1810.HK", "name": "小米集团-W", "exchange": "HK", "industry": "智能手机", "currency": "HKD"},
            ]
            return mock_stocks
        except Exception as e:
            self.logger.error(f"Failed to fetch stock list: {e}")
            return []
    
    async def fetch_realtime_price(self, stock_code: str) -> Optional[Dict]:
        """Fetch real-time price data for a specific stock"""
        try:
            import random
            
            # Different price ranges for different markets
            if stock_code.endswith('.HK'):
                # HK stocks typically in HKD, higher price range
                base_price = random.uniform(50, 500)
                volume_range = (1000000, 50000000)
            else:
                # A-share stocks in CNY
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
        except Exception as e:
            self.logger.error(f"Failed to fetch price for {stock_code}: {e}")
            return None
    
    async def fetch_batch_prices(self, stock_codes: List[str]) -> List[Dict]:
        """Fetch prices for multiple stocks concurrently"""
        tasks = [self.fetch_realtime_price(code) for code in stock_codes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for result in results:
            if isinstance(result, dict):
                valid_results.append(result)
            elif isinstance(result, Exception):
                self.logger.error(f"Error in batch fetch: {result}")
        
        return valid_results
    
    def save_stock_info(self, stock_data: Dict) -> bool:
        """Save stock basic information to database"""
        try:
            stock = self.db_session.query(Stock).filter_by(code=stock_data['code']).first()
            if not stock:
                stock = Stock(
                    code=stock_data['code'],
                    name=stock_data['name'],
                    exchange=stock_data['exchange'],
                    industry=stock_data.get('industry')
                )
                self.db_session.add(stock)
            else:
                stock.name = stock_data['name']
                stock.industry = stock_data.get('industry')
                stock.updated_at = datetime.utcnow()
            
            self.db_session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to save stock info: {e}")
            self.db_session.rollback()
            return False
    
    def save_price_data(self, price_data: Dict) -> bool:
        """Save price data to database"""
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
        """Main data collection loop"""
        self.logger.info("Starting data collection cycle")
        
        # Fetch stock list and update
        stocks = await self.fetch_stock_list()
        for stock in stocks:
            self.save_stock_info(stock)
        
        # Fetch price data
        stock_codes = [stock['code'] for stock in stocks]
        price_data = await self.fetch_batch_prices(stock_codes)
        
        for price in price_data:
            if price:
                self.save_price_data(price)
        
        self.logger.info(f"Collected data for {len(price_data)} stocks")