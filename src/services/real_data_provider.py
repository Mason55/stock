# src/services/real_data_provider.py
import yfinance as yf
import requests
import json
import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass


@dataclass
class StockQuote:
    """标准化股票报价数据结构"""
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: Optional[float] = None
    open_price: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    previous_close: Optional[float] = None
    currency: str = 'CNY'
    timestamp: datetime = None


class YahooFinanceProvider:
    """Yahoo Finance数据提供者"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def _convert_symbol(self, symbol: str) -> str:
        """转换股票代码为Yahoo Finance格式"""
        if symbol.endswith('.SZ'):
            # 深交所：000001.SZ -> 000001.SZ
            return symbol
        elif symbol.endswith('.SH'):
            # 上交所：600000.SH -> 600000.SS
            return symbol.replace('.SH', '.SS')
        elif symbol.endswith('.HK'):
            # 港股：700.HK -> 0700.HK
            code = symbol.split('.')[0]
            return f"{code.zfill(4)}.HK"
        return symbol
    
    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        """获取股票实时报价"""
        try:
            yf_symbol = self._convert_symbol(symbol)
            stock = yf.Ticker(yf_symbol)
            
            # 获取实时数据
            info = stock.info
            hist = stock.history(period="2d")
            
            if hist.empty:
                self.logger.warning(f"No data available for {symbol}")
                return None
            
            latest = hist.iloc[-1]
            previous = hist.iloc[-2] if len(hist) > 1 else latest
            
            # 确定货币
            currency = 'CNY'
            if symbol.endswith('.HK'):
                currency = 'HKD'
            elif symbol.endswith(('.US', '.NASDAQ')):
                currency = 'USD'
            
            return StockQuote(
                symbol=symbol,
                name=info.get('longName', symbol),
                price=float(latest['Close']),
                change=float(latest['Close'] - previous['Close']),
                change_percent=float((latest['Close'] - previous['Close']) / previous['Close'] * 100),
                volume=int(latest['Volume']),
                market_cap=info.get('marketCap'),
                open_price=float(latest['Open']),
                high=float(latest['High']),
                low=float(latest['Low']),
                previous_close=float(previous['Close']),
                currency=currency,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error fetching Yahoo Finance data for {symbol}: {e}")
            return None
    
    async def get_batch_quotes(self, symbols: List[str]) -> List[StockQuote]:
        """批量获取股票报价"""
        quotes = []
        for symbol in symbols:
            quote = await self.get_quote(symbol)
            if quote:
                quotes.append(quote)
            # 避免请求过于频繁
            await asyncio.sleep(0.1)
        return quotes


class SinaFinanceProvider:
    """新浪财经数据提供者"""
    
    BASE_URL = "https://hq.sinajs.cn/list="
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def _convert_symbol(self, symbol: str) -> str:
        """转换为新浪财经格式"""
        if symbol.endswith('.SZ'):
            code = symbol.split('.')[0]
            return f"sz{code}"
        elif symbol.endswith('.SH'):
            code = symbol.split('.')[0]  
            return f"sh{code}"
        elif symbol.endswith('.HK'):
            code = symbol.split('.')[0]
            return f"rt_hk{code.zfill(5)}"
        return symbol
    
    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        """获取股票实时报价"""
        try:
            sina_symbol = self._convert_symbol(symbol)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}{sina_symbol}") as response:
                    if response.status != 200:
                        return None
                    
                    content = await response.text()
                    
            # 解析新浪返回数据
            if 'hq_str_' in content:
                data_line = content.split('"')[1]
                if not data_line:
                    return None
                
                fields = data_line.split(',')
                
                # A股数据格式
                if symbol.endswith(('.SZ', '.SH')):
                    if len(fields) < 32:
                        return None
                    
                    name = fields[0]
                    price = float(fields[3])
                    previous_close = float(fields[2])
                    open_price = float(fields[1])
                    high = float(fields[4])
                    low = float(fields[5])
                    volume = int(fields[8])
                    
                    change = price - previous_close
                    change_percent = (change / previous_close * 100) if previous_close > 0 else 0
                    
                    return StockQuote(
                        symbol=symbol,
                        name=name,
                        price=price,
                        change=change,
                        change_percent=change_percent,
                        volume=volume,
                        open_price=open_price,
                        high=high,
                        low=low,
                        previous_close=previous_close,
                        currency='CNY',
                        timestamp=datetime.now()
                    )
                
                # 港股数据格式
                elif symbol.endswith('.HK'):
                    if len(fields) < 20:
                        return None
                    
                    name = fields[1]
                    price = float(fields[6])
                    previous_close = float(fields[3])
                    open_price = float(fields[2])
                    high = float(fields[4])
                    low = float(fields[5])
                    volume = int(fields[12]) if fields[12] else 0
                    
                    change = price - previous_close
                    change_percent = (change / previous_close * 100) if previous_close > 0 else 0
                    
                    return StockQuote(
                        symbol=symbol,
                        name=name,
                        price=price,
                        change=change,
                        change_percent=change_percent,
                        volume=volume,
                        open_price=open_price,
                        high=high,
                        low=low,
                        previous_close=previous_close,
                        currency='HKD',
                        timestamp=datetime.now()
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching Sina Finance data for {symbol}: {e}")
            return None
    
    async def get_batch_quotes(self, symbols: List[str]) -> List[StockQuote]:
        """批量获取股票报价"""
        # 新浪支持批量查询
        sina_symbols = [self._convert_symbol(s) for s in symbols]
        batch_url = f"{self.BASE_URL}{'&'.join(sina_symbols)}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(batch_url) as response:
                    if response.status != 200:
                        return []
                    
                    content = await response.text()
                    
            quotes = []
            lines = content.strip().split('\n')
            
            for i, line in enumerate(lines):
                if i < len(symbols):
                    # 解析每一行数据
                    if 'hq_str_' in line and '"' in line:
                        # 模拟单个解析逻辑
                        quote = await self._parse_single_line(symbols[i], line)
                        if quote:
                            quotes.append(quote)
            
            return quotes
            
        except Exception as e:
            self.logger.error(f"Error in batch fetch: {e}")
            return []
    
    async def _parse_single_line(self, symbol: str, line: str) -> Optional[StockQuote]:
        """解析单行新浪数据"""
        # 这里重用get_quote的解析逻辑
        # 为了简化，直接调用单个查询
        return await self.get_quote(symbol)


class RealDataManager:
    """真实数据管理器，支持多数据源"""
    
    def __init__(self, primary_provider: str = 'yahoo'):
        self.logger = logging.getLogger(__name__)
        
        # 初始化数据提供者
        self.providers = {
            'yahoo': YahooFinanceProvider(),
            'sina': SinaFinanceProvider()
        }
        
        self.primary_provider = primary_provider
        self.fallback_providers = ['sina', 'yahoo'] if primary_provider == 'yahoo' else ['yahoo', 'sina']
    
    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        """获取股票报价，支持多数据源fallback"""
        # 首先尝试主要数据源
        quote = await self.providers[self.primary_provider].get_quote(symbol)
        
        if quote:
            return quote
        
        # 尝试备用数据源
        for provider_name in self.fallback_providers:
            if provider_name != self.primary_provider:
                self.logger.info(f"Trying fallback provider {provider_name} for {symbol}")
                quote = await self.providers[provider_name].get_quote(symbol)
                if quote:
                    return quote
        
        self.logger.error(f"Failed to get quote for {symbol} from all providers")
        return None
    
    async def get_batch_quotes(self, symbols: List[str]) -> List[StockQuote]:
        """批量获取股票报价"""
        return await self.providers[self.primary_provider].get_batch_quotes(symbols)