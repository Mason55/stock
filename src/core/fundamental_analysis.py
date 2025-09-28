# src/core/fundamental_analysis.py - 基本面分析模块
import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class FundamentalData:
    """基本面数据"""
    # 估值指标
    pe_ratio: Optional[float] = None      # 市盈率
    pb_ratio: Optional[float] = None      # 市净率
    ps_ratio: Optional[float] = None      # 市销率
    market_cap: Optional[float] = None    # 市值(亿元)
    
    # 盈利能力
    roe: Optional[float] = None           # 净资产收益率
    roa: Optional[float] = None           # 总资产收益率
    gross_margin: Optional[float] = None  # 毛利率
    net_margin: Optional[float] = None    # 净利率
    
    # 成长性
    revenue_growth: Optional[float] = None     # 营收增长率
    profit_growth: Optional[float] = None      # 净利润增长率
    eps_growth: Optional[float] = None         # 每股收益增长率
    
    # 财务健康
    debt_ratio: Optional[float] = None         # 资产负债率
    current_ratio: Optional[float] = None      # 流动比率
    quick_ratio: Optional[float] = None        # 速动比率
    
    # 分红情况
    dividend_yield: Optional[float] = None     # 股息率
    payout_ratio: Optional[float] = None       # 分红比率
    
    # 业务数据
    revenue: Optional[float] = None            # 营业收入(亿元)
    net_profit: Optional[float] = None         # 净利润(亿元)
    total_assets: Optional[float] = None       # 总资产(亿元)
    
    # 行业对比
    industry_pe_percentile: Optional[float] = None  # 行业PE百分位
    industry_pb_percentile: Optional[float] = None  # 行业PB百分位
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class FundamentalAnalyzer:
    """基本面分析器"""
    
    def __init__(self):
        self.data_sources = {
            'eastmoney': self._fetch_eastmoney_fundamental,
            'sina': self._fetch_sina_fundamental,
            'mock': self._fetch_mock_fundamental  # 模拟数据源
        }
    
    async def fetch_fundamental_data(self, symbol: str, config: Dict[str, Any]) -> Optional[FundamentalData]:
        """获取基本面数据"""
        # 按优先级尝试不同数据源
        for source_name in ['eastmoney', 'sina', 'mock']:
            try:
                if source_name in self.data_sources:
                    data = await self.data_sources[source_name](symbol, config)
                    if data:
                        return data
            except Exception as e:
                print(f"数据源 {source_name} 获取基本面数据失败: {e}")
                continue
        
        return None
    
    async def _fetch_eastmoney_fundamental(self, symbol: str, config: Dict[str, Any]) -> Optional[FundamentalData]:
        """从东方财富获取基本面数据"""
        try:
            # 转换股票代码
            if symbol.endswith('.SH'):
                em_code = f"1.{symbol[:-3]}"
            elif symbol.endswith('.SZ'):
                em_code = f"0.{symbol[:-3]}"
            else:
                return None
            
            # 获取财务数据
            financial_url = f"https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax"
            params = {
                'code': em_code
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(financial_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_eastmoney_data(data, symbol)
            
        except Exception as e:
            raise Exception(f"东方财富基本面数据获取失败: {e}")
        
        return None
    
    async def _fetch_sina_fundamental(self, symbol: str, config: Dict[str, Any]) -> Optional[FundamentalData]:
        """从新浪财经获取基本面数据"""
        try:
            # 新浪财经基本面数据API
            sina_code = config.get('sina_code', '')
            if not sina_code:
                return None
            
            # 获取基本财务数据
            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=40&sort=symbol&asc=1&node=hs_a&symbol={sina_code}"
            
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://finance.sina.com.cn/'
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        # 新浪返回的是JSON格式
                        data = json.loads(content)
                        return self._parse_sina_data(data, symbol)
            
        except Exception as e:
            raise Exception(f"新浪财经基本面数据获取失败: {e}")
        
        return None
    
    async def _fetch_mock_fundamental(self, symbol: str, config: Dict[str, Any]) -> Optional[FundamentalData]:
        """模拟基本面数据（用于测试和演示）"""
        try:
            # 根据股票类型生成模拟数据
            special_features = config.get('special_features', [])
            industry = config.get('industry', '未知')
            
            # 基础数据
            fundamental = FundamentalData()
            
            # 根据行业和特性生成不同的估值水平
            if '汽车制造' in industry:
                if '华为概念' in special_features:
                    # 华为概念股通常估值较高
                    fundamental.pe_ratio = 25.5
                    fundamental.pb_ratio = 3.2
                    fundamental.ps_ratio = 2.1
                    fundamental.market_cap = 1250.8
                elif '新能源汽车' in special_features:
                    # 新能源汽车估值中等偏高
                    fundamental.pe_ratio = 32.1
                    fundamental.pb_ratio = 4.5
                    fundamental.ps_ratio = 3.2
                    fundamental.market_cap = 856.4
                else:
                    # 传统汽车估值较低
                    fundamental.pe_ratio = 15.8
                    fundamental.pb_ratio = 1.8
                    fundamental.ps_ratio = 1.2
                    fundamental.market_cap = 450.2
            elif '科技' in industry or '互联网' in industry:
                # 科技股估值通常较高
                fundamental.pe_ratio = 45.6
                fundamental.pb_ratio = 5.8
                fundamental.ps_ratio = 8.2
                fundamental.market_cap = 2800.5
            elif '金融' in industry:
                # 金融股估值较低
                fundamental.pe_ratio = 8.5
                fundamental.pb_ratio = 0.9
                fundamental.ps_ratio = 2.1
                fundamental.market_cap = 3200.1
            elif '消费' in industry:
                # 消费股估值中等
                fundamental.pe_ratio = 28.9
                fundamental.pb_ratio = 6.2
                fundamental.ps_ratio = 4.5
                fundamental.market_cap = 8500.7
            else:
                # 默认数据
                fundamental.pe_ratio = 20.0
                fundamental.pb_ratio = 2.5
                fundamental.ps_ratio = 2.0
                fundamental.market_cap = 800.0
            
            # 盈利能力（根据行业调整）
            if '汽车制造' in industry:
                fundamental.roe = 12.5
                fundamental.roa = 4.8
                fundamental.gross_margin = 18.5
                fundamental.net_margin = 6.2
            elif '科技' in industry:
                fundamental.roe = 18.9
                fundamental.roa = 8.5
                fundamental.gross_margin = 45.8
                fundamental.net_margin = 15.2
            else:
                fundamental.roe = 15.2
                fundamental.roa = 6.8
                fundamental.gross_margin = 25.6
                fundamental.net_margin = 8.9
            
            # 成长性
            if '新能源汽车' in special_features or '华为概念' in special_features:
                fundamental.revenue_growth = 35.8
                fundamental.profit_growth = 42.1
                fundamental.eps_growth = 38.5
            elif '科技' in industry:
                fundamental.revenue_growth = 28.5
                fundamental.profit_growth = 31.2
                fundamental.eps_growth = 29.8
            else:
                fundamental.revenue_growth = 12.3
                fundamental.profit_growth = 15.6
                fundamental.eps_growth = 14.2
            
            # 财务健康
            fundamental.debt_ratio = 45.2
            fundamental.current_ratio = 2.1
            fundamental.quick_ratio = 1.5
            
            # 分红
            if '金融' in industry:
                fundamental.dividend_yield = 4.5
                fundamental.payout_ratio = 35.8
            else:
                fundamental.dividend_yield = 1.8
                fundamental.payout_ratio = 25.2
            
            # 业务数据（基于市值推算）
            fundamental.revenue = fundamental.market_cap * 1.2
            fundamental.net_profit = fundamental.revenue * (fundamental.net_margin / 100)
            fundamental.total_assets = fundamental.revenue * 1.8
            
            # 行业百分位（模拟）
            fundamental.industry_pe_percentile = 65.5
            fundamental.industry_pb_percentile = 72.3
            
            return fundamental
            
        except Exception as e:
            raise Exception(f"模拟基本面数据生成失败: {e}")
    
    def _parse_eastmoney_data(self, data: Dict, symbol: str) -> FundamentalData:
        """解析东方财富数据"""
        fundamental = FundamentalData()
        
        try:
            # 从东方财富API响应中提取数据
            if 'data' in data and data['data']:
                info = data['data']
                
                # 基础估值数据
                fundamental.pe_ratio = float(info.get('pe', 0)) if info.get('pe') else None
                fundamental.pb_ratio = float(info.get('pb', 0)) if info.get('pb') else None
                fundamental.market_cap = float(info.get('market_cap', 0)) if info.get('market_cap') else None
                
                # 财务指标
                fundamental.roe = float(info.get('roe', 0)) if info.get('roe') else None
                fundamental.revenue_growth = float(info.get('revenue_growth', 0)) if info.get('revenue_growth') else None
        
        except Exception as e:
            print(f"解析东方财富数据失败: {e}")
        
        return fundamental
    
    def _parse_sina_data(self, data: List, symbol: str) -> FundamentalData:
        """解析新浪财经数据"""
        fundamental = FundamentalData()
        
        try:
            # 从新浪API响应中查找对应股票数据
            for item in data:
                if item.get('symbol') == symbol:
                    fundamental.pe_ratio = float(item.get('pe', 0)) if item.get('pe') else None
                    fundamental.pb_ratio = float(item.get('pb', 0)) if item.get('pb') else None
                    break
        
        except Exception as e:
            print(f"解析新浪数据失败: {e}")
        
        return fundamental
    
    def analyze_fundamental_strength(self, fundamental: FundamentalData, industry: str) -> Dict[str, Any]:
        """分析基本面强弱"""
        scores = []
        signals = []
        
        # 1. 估值分析
        if fundamental.pe_ratio:
            if fundamental.pe_ratio < 15:
                scores.append(2)
                signals.append("PE估值偏低")
            elif fundamental.pe_ratio < 25:
                scores.append(1)
                signals.append("PE估值合理")
            elif fundamental.pe_ratio > 40:
                scores.append(-2)
                signals.append("PE估值偏高")
            else:
                scores.append(-1)
                signals.append("PE估值略高")
        
        if fundamental.pb_ratio:
            if fundamental.pb_ratio < 1.5:
                scores.append(2)
                signals.append("PB估值偏低")
            elif fundamental.pb_ratio < 3:
                scores.append(1)
                signals.append("PB估值合理")
            elif fundamental.pb_ratio > 5:
                scores.append(-2)
                signals.append("PB估值偏高")
            else:
                scores.append(-1)
                signals.append("PB估值略高")
        
        # 2. 盈利能力分析
        if fundamental.roe:
            if fundamental.roe > 20:
                scores.append(2)
                signals.append("ROE优秀")
            elif fundamental.roe > 15:
                scores.append(1)
                signals.append("ROE良好")
            elif fundamental.roe < 8:
                scores.append(-1)
                signals.append("ROE偏低")
        
        if fundamental.net_margin:
            if fundamental.net_margin > 15:
                scores.append(2)
                signals.append("净利率优秀")
            elif fundamental.net_margin > 10:
                scores.append(1)
                signals.append("净利率良好")
            elif fundamental.net_margin < 5:
                scores.append(-1)
                signals.append("净利率偏低")
        
        # 3. 成长性分析
        if fundamental.revenue_growth:
            if fundamental.revenue_growth > 30:
                scores.append(2)
                signals.append("营收高增长")
            elif fundamental.revenue_growth > 15:
                scores.append(1)
                signals.append("营收稳定增长")
            elif fundamental.revenue_growth < 0:
                scores.append(-2)
                signals.append("营收负增长")
        
        if fundamental.profit_growth:
            if fundamental.profit_growth > 30:
                scores.append(2)
                signals.append("利润高增长")
            elif fundamental.profit_growth > 15:
                scores.append(1)
                signals.append("利润稳定增长")
            elif fundamental.profit_growth < 0:
                scores.append(-2)
                signals.append("利润负增长")
        
        # 4. 财务健康分析
        if fundamental.debt_ratio:
            if fundamental.debt_ratio < 30:
                scores.append(1)
                signals.append("负债率健康")
            elif fundamental.debt_ratio > 70:
                scores.append(-2)
                signals.append("负债率偏高")
        
        if fundamental.current_ratio:
            if fundamental.current_ratio > 2:
                scores.append(1)
                signals.append("流动性充足")
            elif fundamental.current_ratio < 1:
                scores.append(-1)
                signals.append("流动性紧张")
        
        # 计算综合评分
        if scores:
            avg_score = sum(scores) / len(scores)
            strength_percentage = (avg_score + 2) / 4 * 100  # 转换为0-100的百分比
        else:
            strength_percentage = 50  # 默认中性
        
        # 判断基本面强弱
        if strength_percentage >= 75:
            overall_strength = "优秀"
        elif strength_percentage >= 60:
            overall_strength = "良好"
        elif strength_percentage >= 40:
            overall_strength = "一般"
        else:
            overall_strength = "较弱"
        
        return {
            'signals': signals,
            'scores': scores,
            'strength_percentage': strength_percentage,
            'overall_strength': overall_strength,
            'fundamental_summary': f"基本面{overall_strength}，评分{strength_percentage:.1f}%"
        }


# 全局基本面分析器
fundamental_analyzer = FundamentalAnalyzer()


async def get_fundamental_data(symbol: str, config: Dict[str, Any]) -> Optional[FundamentalData]:
    """便捷函数：获取基本面数据"""
    return await fundamental_analyzer.fetch_fundamental_data(symbol, config)


def analyze_fundamental_strength(fundamental: FundamentalData, industry: str) -> Dict[str, Any]:
    """便捷函数：分析基本面强度"""
    return fundamental_analyzer.analyze_fundamental_strength(fundamental, industry)


if __name__ == "__main__":
    # 测试基本面分析
    async def test_fundamental():
        print("=== 基本面分析测试 ===")
        
        # 模拟配置
        test_config = {
            'special_features': ['华为概念', '新能源汽车'],
            'industry': '汽车制造'
        }
        
        # 获取基本面数据
        fundamental = await get_fundamental_data("601127.SH", test_config)
        
        if fundamental:
            print("基本面数据:")
            for key, value in fundamental.to_dict().items():
                print(f"  {key}: {value}")
            
            # 分析基本面强度
            strength = analyze_fundamental_strength(fundamental, '汽车制造')
            print(f"\n基本面分析:")
            print(f"  强度: {strength['overall_strength']} ({strength['strength_percentage']:.1f}%)")
            print(f"  信号: {', '.join(strength['signals'])}")
        else:
            print("获取基本面数据失败")
    
    asyncio.run(test_fundamental())