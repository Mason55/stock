# config/stock_symbols.py
"""Stock symbols configuration - centralized stock list management"""
from typing import Dict, List

# A-share hot stocks
A_SHARE_STOCKS: List[Dict[str, str]] = [
    {
        "code": "000001.SZ",
        "name": "平安银行",
        "exchange": "SZ",
        "industry": "银行",
        "currency": "CNY",
    },
    {
        "code": "000002.SZ",
        "name": "万科A",
        "exchange": "SZ",
        "industry": "房地产",
        "currency": "CNY",
    },
    {
        "code": "000858.SZ",
        "name": "五粮液",
        "exchange": "SZ",
        "industry": "白酒",
        "currency": "CNY",
    },
    {
        "code": "000977.SZ",
        "name": "浪潮信息",
        "exchange": "SZ",
        "industry": "计算机设备",
        "currency": "CNY",
    },
    {
        "code": "600000.SH",
        "name": "浦发银行",
        "exchange": "SH",
        "industry": "银行",
        "currency": "CNY",
    },
    {
        "code": "600036.SH",
        "name": "招商银行",
        "exchange": "SH",
        "industry": "银行",
        "currency": "CNY",
    },
    {
        "code": "600519.SH",
        "name": "贵州茅台",
        "exchange": "SH",
        "industry": "白酒",
        "currency": "CNY",
    },
    {
        "code": "600900.SH",
        "name": "长江电力",
        "exchange": "SH",
        "industry": "电力",
        "currency": "CNY",
    },
]

# Hong Kong hot stocks
HK_STOCKS: List[Dict[str, str]] = [
    {
        "code": "700.HK",
        "name": "腾讯控股",
        "exchange": "HK",
        "industry": "互联网",
        "currency": "HKD",
    },
    {
        "code": "9988.HK",
        "name": "阿里巴巴-SW",
        "exchange": "HK",
        "industry": "互联网",
        "currency": "HKD",
    },
    {
        "code": "3690.HK",
        "name": "美团-W",
        "exchange": "HK",
        "industry": "互联网",
        "currency": "HKD",
    },
    {
        "code": "9618.HK",
        "name": "京东集团-SW",
        "exchange": "HK",
        "industry": "电商",
        "currency": "HKD",
    },
    {
        "code": "1810.HK",
        "name": "小米集团-W",
        "exchange": "HK",
        "industry": "智能手机",
        "currency": "HKD",
    },
    {
        "code": "2318.HK",
        "name": "中国平安",
        "exchange": "HK",
        "industry": "保险",
        "currency": "HKD",
    },
    {
        "code": "1299.HK",
        "name": "友邦保险",
        "exchange": "HK",
        "industry": "保险",
        "currency": "HKD",
    },
    {
        "code": "2020.HK",
        "name": "安踏体育",
        "exchange": "HK",
        "industry": "服装",
        "currency": "HKD",
    },
]

# All stocks
ALL_STOCKS: List[Dict[str, str]] = A_SHARE_STOCKS + HK_STOCKS


def get_stock_by_code(code: str) -> Dict[str, str]:
    """Get stock info by code"""
    for stock in ALL_STOCKS:
        if stock["code"] == code:
            return stock
    return None


def get_stocks_by_exchange(exchange: str) -> List[Dict[str, str]]:
    """Get stocks by exchange"""
    return [s for s in ALL_STOCKS if s["exchange"] == exchange]


def get_stocks_by_industry(industry: str) -> List[Dict[str, str]]:
    """Get stocks by industry"""
    return [s for s in ALL_STOCKS if s["industry"] == industry]

# Backward compatibility: simple dict mapping
STOCK_SYMBOLS = {stock["code"]: stock["name"] for stock in A_SHARE_STOCKS}
