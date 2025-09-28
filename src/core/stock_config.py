# src/core/stock_config.py - 股票配置统一管理
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class MarketType(Enum):
    """市场类型"""
    A_SHARE = "A"      # A股
    HONG_KONG = "HK"   # 港股  
    US = "US"          # 美股
    

class IndustryType(Enum):
    """行业类型"""
    AUTO = "汽车制造"
    TECH = "科技"
    FINANCE = "金融"
    HEALTHCARE = "医疗"
    CONSUMER = "消费"
    ENERGY = "能源"
    REAL_ESTATE = "房地产"
    INTERNET = "互联网"
    UNKNOWN = "未知"


@dataclass
class StockConfig:
    """股票配置信息"""
    symbol: str                    # 股票代码
    name: str                     # 股票名称
    market: MarketType            # 市场类型
    industry: IndustryType        # 行业类型
    currency: str                 # 货币类型
    sina_code: str               # 新浪财经代码
    data_sources: List[str]      # 支持的数据源
    special_features: List[str]   # 特殊特性（如华为概念等）
    is_active: bool = True       # 是否活跃交易
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'name': self.name,
            'market': self.market.value,
            'industry': self.industry.value,
            'currency': self.currency,
            'sina_code': self.sina_code,
            'data_sources': self.data_sources,
            'special_features': self.special_features,
            'is_active': self.is_active
        }


class StockConfigManager:
    """股票配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "stock_configs.json"
        self._configs: Dict[str, StockConfig] = {}
        self._load_default_configs()
        self._load_from_file()
    
    def _load_default_configs(self):
        """加载默认配置"""
        default_configs = [
            # A股新能源汽车
            StockConfig(
                symbol="601127.SH",
                name="赛力斯",
                market=MarketType.A_SHARE,
                industry=IndustryType.AUTO,
                currency="CNY",
                sina_code="sh601127",
                data_sources=["sina", "eastmoney", "tencent"],
                special_features=["华为概念", "增程式电动车", "问界品牌"]
            ),
            StockConfig(
                symbol="600418.SH", 
                name="江淮汽车",
                market=MarketType.A_SHARE,
                industry=IndustryType.AUTO,
                currency="CNY",
                sina_code="sh600418",
                data_sources=["sina", "eastmoney"],
                special_features=["新能源汽车", "商用车"]
            ),
            
            # 港股新能源汽车
            StockConfig(
                symbol="2015.HK",
                name="理想汽车",
                market=MarketType.HONG_KONG,
                industry=IndustryType.AUTO,
                currency="HKD",
                sina_code="rt_hk02015",
                data_sources=["sina", "yahoo"],
                special_features=["增程式电动车", "智能驾驶", "美港双重上市"]
            ),
            StockConfig(
                symbol="9868.HK",
                name="小鹏汽车",
                market=MarketType.HONG_KONG,
                industry=IndustryType.AUTO,
                currency="HKD",
                sina_code="rt_hk09868",
                data_sources=["sina", "yahoo"],
                special_features=["纯电动车", "智能驾驶", "飞行汽车"]
            ),
            StockConfig(
                symbol="9866.HK",
                name="蔚来",
                market=MarketType.HONG_KONG,
                industry=IndustryType.AUTO,
                currency="HKD",
                sina_code="rt_hk09866",
                data_sources=["sina", "yahoo"],
                special_features=["纯电动车", "换电模式", "高端品牌"]
            ),
            
            # 港股科技
            StockConfig(
                symbol="700.HK",
                name="腾讯控股",
                market=MarketType.HONG_KONG,
                industry=IndustryType.INTERNET,
                currency="HKD",
                sina_code="rt_hk00700",
                data_sources=["sina", "yahoo"],
                special_features=["社交平台", "游戏", "云服务", "金融科技"]
            ),
            StockConfig(
                symbol="9988.HK",
                name="阿里巴巴",
                market=MarketType.HONG_KONG,
                industry=IndustryType.INTERNET,
                currency="HKD", 
                sina_code="rt_hk09988",
                data_sources=["sina", "yahoo"],
                special_features=["电商", "云计算", "数字支付"]
            ),
            
            # A股科技
            StockConfig(
                symbol="000977.SZ",
                name="浪潮信息",
                market=MarketType.A_SHARE,
                industry=IndustryType.TECH,
                currency="CNY",
                sina_code="sz000977",
                data_sources=["sina", "eastmoney"],
                special_features=["服务器", "云计算", "AI算力"]
            ),
            
            # A股金融
            StockConfig(
                symbol="600036.SH",
                name="招商银行",
                market=MarketType.A_SHARE,
                industry=IndustryType.FINANCE,
                currency="CNY",
                sina_code="sh600036",
                data_sources=["sina", "eastmoney"],
                special_features=["零售银行", "财富管理", "金融科技"]
            ),
            StockConfig(
                symbol="000001.SZ",
                name="平安银行",
                market=MarketType.A_SHARE,
                industry=IndustryType.FINANCE,
                currency="CNY",
                sina_code="sz000001",
                data_sources=["sina", "eastmoney"],
                special_features=["零售银行", "综合金融"]
            ),
            
            # A股消费
            StockConfig(
                symbol="600519.SH",
                name="贵州茅台",
                market=MarketType.A_SHARE,
                industry=IndustryType.CONSUMER,
                currency="CNY",
                sina_code="sh600519",
                data_sources=["sina", "eastmoney"],
                special_features=["白酒龙头", "高端消费", "价值投资"]
            ),
            StockConfig(
                symbol="000858.SZ",
                name="五粮液",
                market=MarketType.A_SHARE,
                industry=IndustryType.CONSUMER,
                currency="CNY",
                sina_code="sz000858",
                data_sources=["sina", "eastmoney"],
                special_features=["白酒", "高端消费"]
            )
        ]
        
        for config in default_configs:
            self._configs[config.symbol] = config
    
    def _load_from_file(self):
        """从文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for symbol, config_data in data.items():
                        config = StockConfig(
                            symbol=config_data['symbol'],
                            name=config_data['name'],
                            market=MarketType(config_data['market']),
                            industry=IndustryType(config_data['industry']),
                            currency=config_data['currency'],
                            sina_code=config_data['sina_code'],
                            data_sources=config_data['data_sources'],
                            special_features=config_data['special_features'],
                            is_active=config_data.get('is_active', True)
                        )
                        self._configs[symbol] = config
            except Exception as e:
                print(f"加载配置文件失败: {e}")
    
    def save_to_file(self):
        """保存配置到文件"""
        try:
            data = {symbol: config.to_dict() for symbol, config in self._configs.items()}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def get_config(self, symbol: str) -> Optional[StockConfig]:
        """获取股票配置"""
        return self._configs.get(symbol.upper())
    
    def add_config(self, config: StockConfig):
        """添加股票配置"""
        self._configs[config.symbol.upper()] = config
        self.save_to_file()
    
    def remove_config(self, symbol: str):
        """删除股票配置"""
        symbol = symbol.upper()
        if symbol in self._configs:
            del self._configs[symbol]
            self.save_to_file()
    
    def get_all_symbols(self) -> List[str]:
        """获取所有股票代码"""
        return list(self._configs.keys())
    
    def get_symbols_by_market(self, market: MarketType) -> List[str]:
        """按市场获取股票代码"""
        return [symbol for symbol, config in self._configs.items() 
                if config.market == market and config.is_active]
    
    def get_symbols_by_industry(self, industry: IndustryType) -> List[str]:
        """按行业获取股票代码"""
        return [symbol for symbol, config in self._configs.items() 
                if config.industry == industry and config.is_active]
    
    def search_stocks(self, keyword: str) -> List[StockConfig]:
        """搜索股票"""
        keyword = keyword.lower()
        results = []
        
        for config in self._configs.values():
            if not config.is_active:
                continue
                
            # 按股票代码、名称、特殊特性搜索
            if (keyword in config.symbol.lower() or 
                keyword in config.name.lower() or
                any(keyword in feature.lower() for feature in config.special_features)):
                results.append(config)
        
        return results
    
    def get_market_summary(self) -> Dict[str, int]:
        """获取市场分布摘要"""
        summary = {}
        for config in self._configs.values():
            if config.is_active:
                market = config.market.value
                summary[market] = summary.get(market, 0) + 1
        return summary
    
    def get_industry_summary(self) -> Dict[str, int]:
        """获取行业分布摘要"""
        summary = {}
        for config in self._configs.values():
            if config.is_active:
                industry = config.industry.value
                summary[industry] = summary.get(industry, 0) + 1
        return summary


# 全局配置管理器实例
stock_config_manager = StockConfigManager()


# 便捷函数
def get_stock_config(symbol: str) -> Optional[StockConfig]:
    """获取股票配置"""
    return stock_config_manager.get_config(symbol)


def search_stocks(keyword: str) -> List[StockConfig]:
    """搜索股票"""
    return stock_config_manager.search_stocks(keyword)


def get_supported_symbols() -> List[str]:
    """获取所有支持的股票代码"""
    return stock_config_manager.get_all_symbols()


if __name__ == "__main__":
    # 测试配置管理器
    manager = StockConfigManager()
    
    print("=== 股票配置管理器测试 ===")
    print(f"支持的股票数量: {len(manager.get_all_symbols())}")
    print(f"市场分布: {manager.get_market_summary()}")
    print(f"行业分布: {manager.get_industry_summary()}")
    
    print("\n=== 搜索测试 ===")
    results = manager.search_stocks("汽车")
    for stock in results:
        print(f"{stock.symbol} - {stock.name} ({stock.industry.value})")
    
    print("\n=== 理想汽车配置 ===")
    li_config = manager.get_config("2015.HK")
    if li_config:
        print(f"名称: {li_config.name}")
        print(f"市场: {li_config.market.value}")
        print(f"特性: {', '.join(li_config.special_features)}")