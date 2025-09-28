# src/data_sources/sina_finance.py - Sina Finance data source
import asyncio
import aiohttp
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from src.utils.exceptions import DataSourceError

logger = logging.getLogger(__name__)


class SinaFinanceDataSource:
    """Sina Finance data source for real-time and historical stock data"""
    
    BASE_URL = "https://hq.sinajs.cn"
    HISTORY_URL = "https://finance.sina.com.cn/realstock/company"
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def get_realtime_data(self, stock_code: str) -> Dict:
        """Get real-time stock data"""
        try:
            # Convert stock code format (000001.SZ -> sz000001)
            sina_code = self._convert_stock_code(stock_code)
            
            url = f"{self.BASE_URL}/list={sina_code}"
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise DataSourceError(f"HTTP {response.status} from Sina Finance")
                
                content = await response.text(encoding='gbk')
                return self._parse_realtime_data(content, stock_code)
                
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching data for {stock_code}: {e}")
            raise DataSourceError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Error fetching realtime data for {stock_code}: {e}")
            raise DataSourceError(f"Data parsing error: {e}")
    
    async def get_historical_data(self, stock_code: str, days: int = 30) -> List[Dict]:
        """Get historical stock data"""
        try:
            # For demo purposes, using simplified approach
            # In production, you would integrate with proper historical data API
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Generate sample historical data based on current price
            current_data = await self.get_realtime_data(stock_code)
            base_price = current_data.get('current_price', 10.0)
            
            historical_data = []
            for i in range(days):
                date = start_date + timedelta(days=i)
                # Simulate price variation
                price_variation = (i % 10 - 5) * 0.02  # ±10% variation
                price = base_price * (1 + price_variation)
                
                historical_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'open': round(price * 0.99, 2),
                    'high': round(price * 1.03, 2),
                    'low': round(price * 0.97, 2),
                    'close': round(price, 2),
                    'volume': int(1000000 + (i % 100) * 10000),
                    'turnover': round(price * (1000000 + (i % 100) * 10000), 2)
                })
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {stock_code}: {e}")
            raise DataSourceError(f"Historical data error: {e}")
    
    def _convert_stock_code(self, stock_code: str) -> str:
        """Convert standard stock code to Sina format"""
        if '.' not in stock_code:
            return stock_code
        
        code, market = stock_code.split('.')
        if market.upper() == 'SZ':
            return f"sz{code}"
        elif market.upper() == 'SH':
            return f"sh{code}"
        else:
            return code
    
    def _parse_realtime_data(self, content: str, stock_code: str) -> Dict:
        """Parse Sina Finance real-time data response"""
        try:
            # Extract data from JavaScript response
            if 'var hq_str_' not in content:
                raise DataSourceError("Invalid response format")
            
            # Find the data string
            start = content.find('"') + 1
            end = content.rfind('"')
            
            if start == 0 or end == -1:
                raise DataSourceError("No data found in response")
            
            data_str = content[start:end]
            
            if not data_str or data_str == "":
                raise DataSourceError("Empty data string")
            
            # Split the data string
            data_parts = data_str.split(',')
            
            if len(data_parts) < 32:
                raise DataSourceError("Insufficient data fields")
            
            # Parse the data fields
            return {
                'stock_code': stock_code,
                'company_name': data_parts[0],
                'open_price': float(data_parts[1]) if data_parts[1] else 0.0,
                'yesterday_close': float(data_parts[2]) if data_parts[2] else 0.0,
                'current_price': float(data_parts[3]) if data_parts[3] else 0.0,
                'high_price': float(data_parts[4]) if data_parts[4] else 0.0,
                'low_price': float(data_parts[5]) if data_parts[5] else 0.0,
                'bid_price': float(data_parts[6]) if data_parts[6] else 0.0,
                'ask_price': float(data_parts[7]) if data_parts[7] else 0.0,
                'volume': int(data_parts[8]) if data_parts[8] else 0,
                'turnover': float(data_parts[9]) if data_parts[9] else 0.0,
                'bid1_volume': int(data_parts[10]) if data_parts[10] else 0,
                'bid1_price': float(data_parts[11]) if data_parts[11] else 0.0,
                'bid2_volume': int(data_parts[12]) if data_parts[12] else 0,
                'bid2_price': float(data_parts[13]) if data_parts[13] else 0.0,
                'ask1_volume': int(data_parts[20]) if data_parts[20] else 0,
                'ask1_price': float(data_parts[21]) if data_parts[21] else 0.0,
                'ask2_volume': int(data_parts[22]) if data_parts[22] else 0,
                'ask2_price': float(data_parts[23]) if data_parts[23] else 0.0,
                'date': data_parts[30],
                'time': data_parts[31],
                'timestamp': datetime.now().isoformat()
            }
            
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing data: {e}")
            raise DataSourceError(f"Data parsing error: {e}")
    
    async def health_check(self) -> bool:
        """Check if data source is available"""
        try:
            test_url = f"{self.BASE_URL}/list=sh000001"
            async with self.session.get(test_url) as response:
                return response.status == 200
        except Exception:
            return False