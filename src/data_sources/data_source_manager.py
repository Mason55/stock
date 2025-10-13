# src/data_sources/data_source_manager.py - Unified data source management
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from enum import Enum
import pandas as pd

logger = logging.getLogger(__name__)


class DataQuality(Enum):
    """Data quality levels"""
    HIGH = "high"       # Professional/paid data
    MEDIUM = "medium"   # Free but reliable
    LOW = "low"         # Basic/unstable


@dataclass
class DataSource:
    """Data source configuration"""
    name: str
    provider: str
    quality: DataQuality
    cost: str
    frequency_support: List[str]
    markets: List[str]
    rate_limit: int  # requests per minute
    requires_auth: bool
    description: str


class BaseDataProvider(ABC):
    """Abstract base class for data providers"""
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.config = config
        self.rate_limit = config.get('rate_limit', 60)
        self.rate_limit_safety_margin = config.get('rate_limit_safety_margin', 2.0)
        self._min_safety_margin = config.get('rate_limit_safety_margin_min', 0.0)
        self._max_safety_margin = config.get('rate_limit_safety_margin_max', 5.0)
        self.adaptive_rate_limit = config.get('adaptive_rate_limit', True)
        self.last_request_time: Optional[float] = None
        self._last_execution_time: Optional[float] = None
        
    @abstractmethod
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date, 
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data"""
        pass
    
    @abstractmethod
    async def get_realtime_data(self, symbols: List[str]) -> Dict:
        """Fetch real-time quotes"""
        pass
    
    @abstractmethod
    async def get_company_info(self, symbol: str) -> Dict:
        """Fetch company basic information"""
        pass
    
    async def rate_limit_check(self):
        """Check and enforce rate limits"""
        current_time = time.monotonic()
        min_interval = 60.0 / self.rate_limit if self.rate_limit > 0 else 0

        if self.last_request_time is None:
            self.last_request_time = current_time - min_interval if min_interval > 0 else current_time

        actual_sleep = 0.0
        if min_interval > 0:
            next_allowed_time = self.last_request_time + min_interval
            wait_time = max(0.0, next_allowed_time - current_time)
            if wait_time > 0:
                logger.debug(
                    "%s rate limit sleep %.2fs (limit=%s/min)",
                    self.name,
                    wait_time,
                    self.rate_limit,
                )
                await asyncio.sleep(wait_time)
                actual_sleep += wait_time
                current_time = next_allowed_time

        if self.rate_limit_safety_margin > 0:
            await asyncio.sleep(self.rate_limit_safety_margin)
            actual_sleep += self.rate_limit_safety_margin
            current_time += self.rate_limit_safety_margin

        self.last_request_time = current_time

        now = time.monotonic()
        if self._last_execution_time is not None:
            actual_interval = now - self._last_execution_time
            self._adjust_rate_limit_margin(actual_interval, min_interval)
        self._last_execution_time = now

    def _adjust_rate_limit_margin(self, actual_interval: float, min_interval: float) -> None:
        """Adapt safety margin based on observed interval to balance throughput & safety."""
        if not self.adaptive_rate_limit or min_interval <= 0:
            return

        target_interval = min_interval + max(self.rate_limit_safety_margin, 0)

        if actual_interval + 1e-3 < min_interval:
            increment = max(0.2, (min_interval - actual_interval) * 1.2)
            new_margin = min(self._max_safety_margin, self.rate_limit_safety_margin + increment)
            if new_margin > self.rate_limit_safety_margin:
                logger.warning(
                    "%s rate limit tightened: margin %.2fs -> %.2fs",
                    self.name,
                    self.rate_limit_safety_margin,
                    new_margin,
                )
                self.rate_limit_safety_margin = new_margin
        elif actual_interval > target_interval + 2:
            decrement = min(0.5, (actual_interval - target_interval) / 2)
            new_margin = max(self._min_safety_margin, self.rate_limit_safety_margin - decrement)
            if new_margin < self.rate_limit_safety_margin:
                logger.debug(
                    "%s rate limit relaxed: margin %.2fs -> %.2fs",
                    self.name,
                    self.rate_limit_safety_margin,
                    new_margin,
                )
                self.rate_limit_safety_margin = new_margin


class SinaFinanceProvider(BaseDataProvider):
    """Sina Finance data provider (Free, Medium quality)"""
    
    def __init__(self, config: Dict):
        super().__init__("sina_finance", config)
        self.base_url = "https://finance.sina.com.cn"
    
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date, 
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """
        Fetch historical data from Sina Finance
        
        Args:
            symbol: Stock code (e.g., "600036.SH")
            start_date: Start date
            end_date: End date
            frequency: Data frequency ("1d", "1w", "1M")
            
        Returns:
            DataFrame with OHLCV data
        """
        await self.rate_limit_check()
        
        # Implementation would use requests/aiohttp to fetch data
        # For now, return mock data structure
        logger.info(f"Fetching {symbol} data from Sina Finance: {start_date} to {end_date}")
        
        # Mock implementation
        dates = pd.date_range(start_date, end_date, freq='D')
        return pd.DataFrame({
            'date': dates,
            'open': 41.8,
            'high': 42.5,
            'low': 41.2,
            'close': 42.0,
            'volume': 8500000,
            'amount': 357000000
        })
    
    async def get_realtime_data(self, symbols: List[str]) -> Dict:
        """Fetch real-time data from Sina Finance"""
        await self.rate_limit_check()
        
        logger.info(f"Fetching real-time data for {len(symbols)} symbols from Sina")
        
        # Mock implementation
        result = {}
        for symbol in symbols:
            result[symbol] = {
                'price': 42.0,
                'change': 0.2,
                'change_pct': 0.48,
                'volume': 8500000,
                'timestamp': datetime.now()
            }
        return result
    
    async def get_company_info(self, symbol: str) -> Dict:
        """Fetch company information"""
        await self.rate_limit_check()
        
        return {
            'symbol': symbol,
            'name': '招商银行',
            'industry': '银行',
            'market_cap': 1200000000000,
            'pe_ratio': 5.8,
            'pb_ratio': 0.7
        }


class TushareProvider(BaseDataProvider):
    """Tushare data provider (Requires token, High quality)"""
    
    def __init__(self, config: Dict):
        super().__init__("tushare", config)
        self.token = config.get('token')
        if not self.token:
            raise ValueError("Tushare token is required")
    
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date, 
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """Fetch historical data from Tushare"""
        await self.rate_limit_check()
        
        logger.info(f"Fetching {symbol} data from Tushare: {start_date} to {end_date}")
        
        # Convert symbol format for Tushare (600036.SH -> 600036.SH)
        ts_symbol = symbol
        
        # Mock implementation - in real use, would call Tushare API
        dates = pd.date_range(start_date, end_date, freq='D')
        return pd.DataFrame({
            'trade_date': dates,
            'open': 41.8,
            'high': 42.5,
            'low': 41.2,
            'close': 42.0,
            'volume': 8500000,
            'amount': 357000000,
            'pre_close': 41.6,
            'change': 0.4,
            'pct_chg': 0.96
        })
    
    async def get_realtime_data(self, symbols: List[str]) -> Dict:
        """Fetch real-time data from Tushare"""
        await self.rate_limit_check()
        
        # Tushare has limited real-time data, may need other sources
        result = {}
        for symbol in symbols:
            result[symbol] = {
                'price': 42.0,
                'change': 0.2,
                'change_pct': 0.48,
                'volume': 8500000,
                'timestamp': datetime.now()
            }
        return result
    
    async def get_company_info(self, symbol: str) -> Dict:
        """Fetch company information from Tushare"""
        await self.rate_limit_check()
        
        return {
            'symbol': symbol,
            'name': '招商银行',
            'industry': '银行',
            'list_date': '2002-04-09',
            'market': 'SH',
            'exchange': '上交所'
        }


class YahooFinanceProvider(BaseDataProvider):
    """Yahoo Finance data provider (Free, Medium quality, Global markets)"""
    
    def __init__(self, config: Dict):
        super().__init__("yahoo_finance", config)
    
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date, 
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """Fetch historical data from Yahoo Finance"""
        await self.rate_limit_check()
        
        # Convert symbol format (600036.SH -> 600036.SS for Yahoo)
        yahoo_symbol = symbol.replace('.SH', '.SS').replace('.SZ', '.SZ')
        
        logger.info(f"Fetching {yahoo_symbol} data from Yahoo Finance")
        
        # Mock implementation
        dates = pd.date_range(start_date, end_date, freq='D')
        return pd.DataFrame({
            'Date': dates,
            'Open': 41.8,
            'High': 42.5,
            'Low': 41.2,
            'Close': 42.0,
            'Adj Close': 42.0,
            'Volume': 8500000
        })
    
    async def get_realtime_data(self, symbols: List[str]) -> Dict:
        """Fetch real-time data from Yahoo Finance"""
        await self.rate_limit_check()
        
        result = {}
        for symbol in symbols:
            yahoo_symbol = symbol.replace('.SH', '.SS').replace('.SZ', '.SZ')
            result[symbol] = {
                'price': 42.0,
                'change': 0.2,
                'change_pct': 0.48,
                'volume': 8500000,
                'timestamp': datetime.now()
            }
        return result
    
    async def get_company_info(self, symbol: str) -> Dict:
        """Fetch company information from Yahoo Finance"""
        await self.rate_limit_check()
        
        return {
            'symbol': symbol,
            'name': 'China Merchants Bank',
            'sector': 'Financial Services',
            'industry': 'Banks',
            'market_cap': 1200000000000
        }


class DataSourceManager:
    """Unified data source manager with fallback support"""
    
    def __init__(self):
        self.providers = {}
        self.provider_priority = []
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available data providers"""
        
        # Sina Finance (Free, always available)
        sina_config = {'rate_limit': 120}
        self.providers['sina'] = SinaFinanceProvider(sina_config)
        
        # Tushare (Requires token)
        try:
            import os
            tushare_token = os.getenv('TUSHARE_TOKEN')
            if tushare_token:
                tushare_config = {'token': tushare_token, 'rate_limit': 200}
                self.providers['tushare'] = TushareProvider(tushare_config)
                logger.info("Tushare provider initialized")
        except Exception as e:
            logger.warning(f"Tushare provider not available: {e}")
        
        # Yahoo Finance (Free, global)
        yahoo_config = {'rate_limit': 100}
        self.providers['yahoo'] = YahooFinanceProvider(yahoo_config)
        
        # Set priority order (high quality first)
        self.provider_priority = ['tushare', 'sina', 'yahoo']
        
        logger.info(f"Initialized {len(self.providers)} data providers")
    
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date, 
        frequency: str = "1d",
        preferred_provider: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch historical data with automatic fallback
        
        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            frequency: Data frequency
            preferred_provider: Preferred provider name
            
        Returns:
            DataFrame with historical data
        """
        
        providers_to_try = []
        
        # Use preferred provider first if specified
        if preferred_provider and preferred_provider in self.providers:
            providers_to_try.append(preferred_provider)
        
        # Add other providers by priority
        for provider_name in self.provider_priority:
            if provider_name in self.providers and provider_name not in providers_to_try:
                providers_to_try.append(provider_name)
        
        last_error = None
        
        for provider_name in providers_to_try:
            try:
                provider = self.providers[provider_name]
                logger.info(f"Trying to fetch data from {provider_name}")
                
                data = await provider.get_historical_data(symbol, start_date, end_date, frequency)
                
                if not data.empty:
                    logger.info(f"Successfully fetched data from {provider_name}")
                    # Add metadata
                    data.attrs['source'] = provider_name
                    data.attrs['symbol'] = symbol
                    data.attrs['frequency'] = frequency
                    return data
                
            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {e}")
                last_error = e
                continue
        
        # All providers failed
        raise Exception(f"All data providers failed. Last error: {last_error}")
    
    async def get_realtime_data(
        self, 
        symbols: List[str], 
        preferred_provider: Optional[str] = None
    ) -> Dict:
        """Fetch real-time data with fallback"""
        
        providers_to_try = []
        
        if preferred_provider and preferred_provider in self.providers:
            providers_to_try.append(preferred_provider)
        
        for provider_name in self.provider_priority:
            if provider_name in self.providers and provider_name not in providers_to_try:
                providers_to_try.append(provider_name)
        
        for provider_name in providers_to_try:
            try:
                provider = self.providers[provider_name]
                data = await provider.get_realtime_data(symbols)
                
                if data:
                    logger.info(f"Successfully fetched real-time data from {provider_name}")
                    return data
                    
            except Exception as e:
                logger.warning(f"Real-time provider {provider_name} failed: {e}")
                continue
        
        raise Exception("All real-time data providers failed")
    
    def get_provider_info(self) -> List[DataSource]:
        """Get information about available data providers"""
        
        sources = [
            DataSource(
                name="sina_finance",
                provider="新浪财经",
                quality=DataQuality.MEDIUM,
                cost="免费",
                frequency_support=["1d", "1w", "1M"],
                markets=["CN"],
                rate_limit=120,
                requires_auth=False,
                description="新浪财经免费数据，稳定性较好，适合回测和基础分析"
            ),
            DataSource(
                name="tushare",
                provider="Tushare",
                quality=DataQuality.HIGH,
                cost="需要积分/付费",
                frequency_support=["1d", "1w", "1M", "1m", "5m"],
                markets=["CN"],
                rate_limit=200,
                requires_auth=True,
                description="专业级中国股票数据，数据质量高，支持多频率"
            ),
            DataSource(
                name="yahoo_finance",
                provider="Yahoo Finance",
                quality=DataQuality.MEDIUM,
                cost="免费",
                frequency_support=["1d", "1w", "1M"],
                markets=["CN", "US", "HK"],
                rate_limit=100,
                requires_auth=False,
                description="雅虎财经全球市场数据，免费但可能有延迟"
            )
        ]
        
        return sources


# Global instance
data_source_manager = DataSourceManager()
