# src/core/data_sources.py - 数据源管理
import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime
from .base_analyzer import StockQuote


class DataSourceException(Exception):
    """数据源异常"""
    pass


class RateLimitException(DataSourceException):
    """限流异常"""
    pass


class BaseDataSource(ABC):
    """数据源基类"""
    
    def __init__(self, name: str):
        self.name = name
        self.base_url = ""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    @abstractmethod
    async def fetch_quote(self, symbol: str, config: Dict[str, Any]) -> Optional[StockQuote]:
        """获取股票行情"""
        pass
    
    async def _make_request(self, url: str, timeout: int = 10) -> str:
        """发起HTTP请求"""
        try:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_config, headers=self.headers) as session:
                async with session.get(url) as response:
                    if response.status == 429:
                        raise RateLimitException(f"{self.name} 请求频率限制")
                    elif response.status != 200:
                        raise DataSourceException(f"{self.name} 返回状态码 {response.status}")
                    
                    return await response.text()
        except asyncio.TimeoutError:
            raise DataSourceException(f"{self.name} 请求超时")
        except Exception as e:
            raise DataSourceException(f"{self.name} 请求失败: {str(e)}")


class SinaDataSource(BaseDataSource):
    """新浪财经数据源"""
    
    def __init__(self):
        super().__init__("新浪财经")
        self.base_url = "https://hq.sinajs.cn/list="
        self.headers.update({
            'Referer': 'https://finance.sina.com.cn/'
        })
    
    async def fetch_quote(self, symbol: str, config: Dict[str, Any]) -> Optional[StockQuote]:
        """获取新浪财经股票数据"""
        sina_code = config.get('sina_code', '')
        if not sina_code:
            return None
            
        try:
            url = f"{self.base_url}{sina_code}"
            content = await self._make_request(url)
            
            if 'hq_str_' not in content or '"' not in content:
                return None
            
            data_line = content.split('"')[1]
            if not data_line.strip():
                return None
            
            parts = data_line.split(',')
            
            # 根据市场类型解析数据
            market = config.get('market', 'A')
            
            if market == 'HK':
                return self._parse_hk_data(symbol, config, parts)
            else:
                return self._parse_a_share_data(symbol, config, parts)
                
        except Exception as e:
            raise DataSourceException(f"新浪财经数据解析失败: {str(e)}")
    
    def _parse_a_share_data(self, symbol: str, config: Dict[str, Any], parts: list) -> StockQuote:
        """解析A股数据"""
        if len(parts) < 32:
            raise DataSourceException("A股数据格式不完整")
        
        name = parts[0]
        open_price = float(parts[1]) if parts[1] else 0
        yesterday_close = float(parts[2]) if parts[2] else 0
        current_price = float(parts[3]) if parts[3] else 0
        high_price = float(parts[4]) if parts[4] else 0
        low_price = float(parts[5]) if parts[5] else 0
        volume = int(parts[8]) if parts[8] else 0
        turnover = float(parts[9]) if parts[9] else 0
        
        change = current_price - yesterday_close
        change_pct = (change / yesterday_close * 100) if yesterday_close > 0 else 0
        
        return StockQuote(
            symbol=symbol,
            name=name,
            current_price=current_price,
            change=change,
            change_pct=change_pct,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            yesterday_close=yesterday_close,
            volume=volume,
            turnover=turnover,
            currency=config.get('currency', 'CNY'),
            market=config.get('market', 'A')
        )
    
    def _parse_hk_data(self, symbol: str, config: Dict[str, Any], parts: list) -> StockQuote:
        """解析港股数据"""
        if len(parts) < 15:
            raise DataSourceException("港股数据格式不完整")
        
        name = parts[1]
        open_price = float(parts[2]) if parts[2] else 0
        yesterday_close = float(parts[3]) if parts[3] else 0
        current_price = float(parts[6]) if parts[6] else 0
        high_price = float(parts[4]) if parts[4] else 0
        low_price = float(parts[5]) if parts[5] else 0
        turnover = float(parts[10]) if len(parts) > 10 and parts[10] else 0
        
        # 港股成交量需要特殊处理
        volume = int(turnover / current_price) if current_price > 0 and turnover > 0 else 0
        
        change = current_price - yesterday_close
        change_pct = (change / yesterday_close * 100) if yesterday_close > 0 else 0
        
        return StockQuote(
            symbol=symbol,
            name=name,
            current_price=current_price,
            change=change,
            change_pct=change_pct,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            yesterday_close=yesterday_close,
            volume=volume,
            turnover=turnover,
            currency=config.get('currency', 'HKD'),
            market=config.get('market', 'HK')
        )


class EastMoneyDataSource(BaseDataSource):
    """东方财富数据源"""
    
    def __init__(self):
        super().__init__("东方财富")
        self.base_url = "https://push2.eastmoney.com/api/qt/stock/get"
    
    async def fetch_quote(self, symbol: str, config: Dict[str, Any]) -> Optional[StockQuote]:
        """获取东方财富股票数据"""
        # 转换股票代码格式
        em_code = self._convert_to_em_code(symbol)
        if not em_code:
            return None
        
        try:
            params = {
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                'invt': '2',
                'fltt': '2',
                'fields': 'f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f53,f54,f55,f56,f57,f58',
                'secid': em_code
            }
            
            url = f"{self.base_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
            content = await self._make_request(url)
            
            import json
            data = json.loads(content)
            
            if not data.get('data'):
                return None
            
            return self._parse_em_data(symbol, config, data['data'])
            
        except Exception as e:
            raise DataSourceException(f"东方财富数据解析失败: {str(e)}")
    
    def _convert_to_em_code(self, symbol: str) -> Optional[str]:
        """转换为东方财富代码格式"""
        if symbol.endswith('.SH'):
            return f"1.{symbol[:-3]}"
        elif symbol.endswith('.SZ'):
            return f"0.{symbol[:-3]}"
        elif symbol.endswith('.HK'):
            return f"116.{symbol[:-3]}"
        return None
    
    def _parse_em_data(self, symbol: str, config: Dict[str, Any], data: dict) -> StockQuote:
        """解析东方财富数据"""
        name = data.get('f58', '')
        current_price = float(data.get('f43', 0)) / 100
        change = float(data.get('f44', 0)) / 100
        change_pct = float(data.get('f45', 0)) / 100
        open_price = float(data.get('f46', 0)) / 100
        high_price = float(data.get('f47', 0)) / 100
        low_price = float(data.get('f48', 0)) / 100
        volume = int(data.get('f49', 0))
        turnover = float(data.get('f50', 0))
        yesterday_close = current_price - change
        
        return StockQuote(
            symbol=symbol,
            name=name,
            current_price=current_price,
            change=change,
            change_pct=change_pct,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            yesterday_close=yesterday_close,
            volume=volume,
            turnover=turnover,
            currency=config.get('currency', 'CNY'),
            market=config.get('market', 'A')
        )


class TencentDataSource(BaseDataSource):
    """腾讯财经数据源"""
    
    def __init__(self):
        super().__init__("腾讯财经")
        self.base_url = "https://qt.gtimg.cn/q="
    
    async def fetch_quote(self, symbol: str, config: Dict[str, Any]) -> Optional[StockQuote]:
        """获取腾讯财经股票数据"""
        qq_code = self._convert_to_qq_code(symbol)
        if not qq_code:
            return None
            
        try:
            url = f"{self.base_url}{qq_code}"
            content = await self._make_request(url)
            
            # 腾讯数据格式: v_股票代码="51~股票名称~代码~当前价格~昨收~今开~成交量~..."
            if f'v_{qq_code}=' not in content:
                return None
            
            data_line = content.split(f'v_{qq_code}="')[1].split('"')[0]
            parts = data_line.split('~')
            
            if len(parts) < 20:
                return None
                
            return self._parse_qq_data(symbol, config, parts)
            
        except Exception as e:
            raise DataSourceException(f"腾讯财经数据解析失败: {str(e)}")
    
    def _convert_to_qq_code(self, symbol: str) -> Optional[str]:
        """转换为腾讯代码格式"""
        if symbol.endswith('.SH'):
            return f"sh{symbol[:-3]}"
        elif symbol.endswith('.SZ'):
            return f"sz{symbol[:-3]}"
        elif symbol.endswith('.HK'):
            return f"hk{symbol[:-3].zfill(5)}"
        return None
    
    def _parse_qq_data(self, symbol: str, config: Dict[str, Any], parts: list) -> StockQuote:
        """解析腾讯数据"""
        name = parts[1]
        current_price = float(parts[3]) if parts[3] else 0
        yesterday_close = float(parts[4]) if parts[4] else 0
        open_price = float(parts[5]) if parts[5] else 0
        volume = int(parts[6]) if parts[6] else 0
        
        # 腾讯数据中高低价位置可能不同，需要特殊处理
        high_price = float(parts[33]) if len(parts) > 33 and parts[33] else current_price
        low_price = float(parts[34]) if len(parts) > 34 and parts[34] else current_price
        turnover = float(parts[37]) if len(parts) > 37 and parts[37] else 0
        
        change = current_price - yesterday_close
        change_pct = (change / yesterday_close * 100) if yesterday_close > 0 else 0
        
        return StockQuote(
            symbol=symbol,
            name=name,
            current_price=current_price,
            change=change,
            change_pct=change_pct,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            yesterday_close=yesterday_close,
            volume=volume,
            turnover=turnover,
            currency=config.get('currency', 'CNY'),
            market=config.get('market', 'A')
        )


class TongHuaShunDataSource(BaseDataSource):
    """同花顺数据源"""
    
    def __init__(self):
        super().__init__("同花顺")
        self.base_url = "https://d.10jqka.com.cn/v6/line/hs_"
        self.headers.update({
            'Referer': 'https://www.10jqka.com.cn/'
        })
    
    async def fetch_quote(self, symbol: str, config: Dict[str, Any]) -> Optional[StockQuote]:
        """获取同花顺股票数据"""
        ths_code = self._convert_to_ths_code(symbol)
        if not ths_code:
            return None
            
        try:
            # 同花顺API相对复杂，这里使用简化版本
            url = f"https://basic.10jqka.com.cn/api/stock/export.php?code={ths_code}"
            content = await self._make_request(url)
            
            # 同花顺返回JSON格式
            import json
            data = json.loads(content)
            
            if 'data' not in data:
                return None
                
            return self._parse_ths_data(symbol, config, data['data'])
            
        except Exception as e:
            # 如果同花顺API失败，返回None让系统尝试其他数据源
            return None
    
    def _convert_to_ths_code(self, symbol: str) -> Optional[str]:
        """转换为同花顺代码格式"""
        if symbol.endswith('.SH') or symbol.endswith('.SZ'):
            return symbol[:-3]
        elif symbol.endswith('.HK'):
            return f"hk{symbol[:-3]}"
        return None
    
    def _parse_ths_data(self, symbol: str, config: Dict[str, Any], data: dict) -> StockQuote:
        """解析同花顺数据"""
        current_price = float(data.get('7', 0))
        yesterday_close = float(data.get('6', current_price))
        open_price = float(data.get('5', current_price))
        high_price = float(data.get('8', current_price))
        low_price = float(data.get('9', current_price))
        volume = int(data.get('13', 0))
        turnover = float(data.get('19', 0))
        
        change = current_price - yesterday_close
        change_pct = (change / yesterday_close * 100) if yesterday_close > 0 else 0
        
        return StockQuote(
            symbol=symbol,
            name=data.get('1', symbol),
            current_price=current_price,
            change=change,
            change_pct=change_pct,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            yesterday_close=yesterday_close,
            volume=volume,
            turnover=turnover,
            currency=config.get('currency', 'CNY'),
            market=config.get('market', 'A')
        )


class DataSourceManager:
    """数据源管理器"""
    
    def __init__(self):
        self.sources = {
            'sina': SinaDataSource(),
            'eastmoney': EastMoneyDataSource(),
            'tencent': TencentDataSource(),
            'tonghuashun': TongHuaShunDataSource()
        }
        self.retry_count = 3
        self.retry_delay = 1  # 秒
    
    async def fetch_quote_with_fallback(self, symbol: str, config: Dict[str, Any]) -> Optional[StockQuote]:
        """使用故障转移获取股票数据"""
        data_sources = config.get('data_sources', ['sina'])
        
        for source_name in data_sources:
            if source_name not in self.sources:
                continue
                
            source = self.sources[source_name]
            
            # 重试机制
            for attempt in range(self.retry_count):
                try:
                    quote = await source.fetch_quote(symbol, config)
                    if quote:
                        return quote
                except RateLimitException:
                    if attempt < self.retry_count - 1:
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    continue
                except DataSourceException as e:
                    print(f"数据源 {source_name} 失败: {e}")
                    break
                except Exception as e:
                    print(f"数据源 {source_name} 未知错误: {e}")
                    break
        
        return None


# 全局数据源管理器
data_source_manager = DataSourceManager()