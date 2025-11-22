"""
Broker adapters for real trading integration

Available adapters:
- HuataiAdapter: 华泰证券 OpenAPI
- EasytraderAdapter: 通用券商（基于easytrader）
- GuojinXTPAdapter: 国金证券 XTP (TODO)
"""

from .huatai_adapter import HuataiAdapter
from .easytrader_adapter import EasytraderAdapter

__all__ = ['HuataiAdapter', 'EasytraderAdapter']
