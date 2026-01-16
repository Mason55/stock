"""ETF Analyzer - Specialized analysis for Exchange-Traded Funds

Provides ETF-specific analysis including:
- Premium/discount calculation
- Holdings analysis
- Tracking error
- Fund flow analysis
"""
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from io import StringIO

import requests
import pandas as pd

from config.settings import settings
from src.cache.persistent_cache import get_persistent_cache

logger = logging.getLogger(__name__)


class ETFAnalyzer:
    """Analyzer for Exchange-Traded Funds"""

    def __init__(self, use_cache: bool = True):
        """Initialize ETF analyzer

        Args:
            use_cache: Whether to use persistent cache
        """
        self.use_cache = use_cache
        if self.use_cache:
            self.cache = get_persistent_cache()
        self.timeout = settings.EXTERNAL_API_TIMEOUT

        # ETF identification patterns
        self.etf_patterns = [
            r'ETF$',  # Name ends with ETF
            r'^[15]\d{5}\.(SZ|SH)$',  # ETF code pattern: 159XXX.SZ or 510XXX.SH
        ]

    def is_etf(self, stock_code: str, stock_name: str = None) -> bool:
        """Check if a stock code represents an ETF

        Args:
            stock_code: Stock code (e.g., '159920.SZ')
            stock_name: Optional stock name for additional checking

        Returns:
            True if it's an ETF
        """
        # Check code pattern
        for pattern in self.etf_patterns:
            if re.search(pattern, stock_code):
                return True

        # Check name if provided
        if stock_name and 'ETF' in stock_name.upper():
            return True

        return False

    def get_etf_info(self, etf_code: str) -> Optional[Dict[str, Any]]:
        """Get basic ETF information

        Args:
            etf_code: ETF code (e.g., '159920.SZ')

        Returns:
            Dictionary with ETF basic information
        """
        if self.use_cache:
            cache_key = f"etf_info:{etf_code}"
            cached = self.cache.get(cache_key, max_age=86400)  # 24 hours
            if cached:
                logger.debug(f"Using cached ETF info for {etf_code}")
                return cached

        try:
            # Try multiple data sources
            info = self._fetch_etf_info_from_eastmoney(etf_code)
            if not info:
                info = self._fetch_etf_info_from_jisilu(etf_code)

            if info and self.use_cache:
                cache_key = f"etf_info:{etf_code}"
                self.cache.set(
                    cache_key,
                    info,
                    ttl=86400,
                    data_type="etf_info",
                    stock_code=etf_code
                )

            return info

        except Exception as e:
            logger.error(f"Failed to get ETF info for {etf_code}: {e}")
            return None

    def _fetch_etf_info_from_eastmoney(self, etf_code: str) -> Optional[Dict[str, Any]]:
        """Fetch ETF info from EastMoney (天天基金)

        Args:
            etf_code: ETF code

        Returns:
            ETF information dictionary
        """
        try:
            # Convert code: 159920.SZ -> 159920
            code_num = etf_code.split('.')[0]

            # EastMoney fund API
            url = f"http://fund.eastmoney.com/{code_num}.html"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'http://fund.eastmoney.com/'
            }

            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return None

            response.encoding = 'utf-8'
            html = response.text

            # Parse basic information using regex
            info = {
                'etf_code': etf_code,
                'source': 'eastmoney'
            }

            # Extract fund name
            name_match = re.search(r'<title>([^<]+?)[\(（]', html)
            if name_match:
                info['etf_name'] = name_match.group(1).strip()

            # Extract fund company
            company_match = re.search(r'基金管理人：\s*<a[^>]*>([^<]+)</a>', html)
            if company_match:
                info['fund_company'] = company_match.group(1).strip()

            # Extract fund size (规模)
            size_match = re.search(r'基金规模[：:]\s*([\d.]+)\s*亿', html)
            if size_match:
                info['fund_size'] = float(size_match.group(1))

            # Extract establishment date
            date_match = re.search(r'成立日期[：:]\s*(\d{4}-\d{2}-\d{2})', html)
            if date_match:
                info['establishment_date'] = date_match.group(1)

            # Extract management fee
            fee_match = re.search(r'管理费率[：:]\s*([\d.]+)%', html)
            if fee_match:
                info['management_fee'] = float(fee_match.group(1)) / 100

            # Extract tracking index
            index_match = re.search(r'跟踪标的[：:]\s*<[^>]+>([^<]+)</[^>]+>', html)
            if index_match:
                info['tracking_index'] = index_match.group(1).strip()

            return info if len(info) > 2 else None

        except Exception as e:
            logger.debug(f"EastMoney ETF info fetch failed for {etf_code}: {e}")
            return None

    def _fetch_etf_info_from_jisilu(self, etf_code: str) -> Optional[Dict[str, Any]]:
        """Fetch ETF info from Jisilu (集思录)

        Args:
            etf_code: ETF code

        Returns:
            ETF information dictionary
        """
        try:
            # Convert code
            code_num = etf_code.split('.')[0]

            url = f"https://www.jisilu.cn/data/etf/detail/{code_num}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.jisilu.cn/'
            }

            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return None

            response.encoding = 'utf-8'
            html = response.text

            info = {
                'etf_code': etf_code,
                'source': 'jisilu'
            }

            # Parse information (simplified parsing)
            name_match = re.search(r'<h2[^>]*>([^<]+)</h2>', html)
            if name_match:
                info['etf_name'] = name_match.group(1).strip()

            return info if len(info) > 2 else None

        except Exception as e:
            logger.debug(f"Jisilu ETF info fetch failed for {etf_code}: {e}")
            return None

    def get_premium_discount(self, etf_code: str) -> Optional[Dict[str, Any]]:
        """Calculate ETF premium/discount rate

        Args:
            etf_code: ETF code

        Returns:
            Dictionary with premium/discount information
        """
        if self.use_cache:
            cache_key = f"etf_premium:{etf_code}"
            cached = self.cache.get(cache_key, max_age=300)  # 5 minutes
            if cached:
                logger.debug(f"Using cached premium data for {etf_code}")
                return cached

        try:
            result = self._calculate_premium_discount(etf_code)

            if result and self.use_cache:
                cache_key = f"etf_premium:{etf_code}"
                self.cache.set(
                    cache_key,
                    result,
                    ttl=300,
                    data_type="etf_premium",
                    stock_code=etf_code
                )

            return result

        except Exception as e:
            logger.error(f"Failed to calculate premium for {etf_code}: {e}")
            return None

    def _calculate_premium_discount(self, etf_code: str) -> Optional[Dict[str, Any]]:
        """Calculate premium/discount from various sources

        Args:
            etf_code: ETF code

        Returns:
            Premium/discount data
        """
        try:
            from src.api.stock_api import fetch_sina_realtime_sync

            # Get current market price
            quote = fetch_sina_realtime_sync(etf_code)
            if not quote:
                return None

            market_price = quote.get('current_price')
            if not market_price:
                return None

            # Try to get NAV (Net Asset Value) from multiple sources in order
            nav = None
            sources_tried = []

            # 1. Try EastMoney (天天基金 - most reliable for real-time estimated NAV)
            nav = self._fetch_nav_from_eastmoney(etf_code)
            sources_tried.append('eastmoney')
            if nav:
                logger.info(f"NAV successfully fetched from EastMoney for {etf_code}: {nav}")
            else:
                # 2. Try Sina Finance
                nav = self._fetch_nav_from_sina(etf_code)
                sources_tried.append('sina')
                if nav:
                    logger.info(f"NAV successfully fetched from Sina for {etf_code}: {nav}")
                else:
                    # 3. Try Jisilu
                    nav = self._fetch_nav_from_jisilu(etf_code)
                    sources_tried.append('jisilu')
                    if nav:
                        logger.info(f"NAV successfully fetched from Jisilu for {etf_code}: {nav}")

            if not nav:
                logger.error(f"NAV not available for {etf_code} after trying sources: {', '.join(sources_tried)}")
                return {
                    'etf_code': etf_code,
                    'market_price': market_price,
                    'nav': None,
                    'premium_rate': None,
                    'status': 'unknown',
                    'timestamp': datetime.now().isoformat(),
                    'note': f'NAV data not available (tried: {", ".join(sources_tried)})'
                }

            # Calculate premium/discount rate
            premium_rate = (market_price - nav) / nav * 100

            # Determine status
            if abs(premium_rate) < 0.5:
                status = 'fair'
            elif premium_rate > 0:
                status = 'premium'
            else:
                status = 'discount'

            return {
                'etf_code': etf_code,
                'market_price': round(market_price, 3),
                'nav': round(nav, 3),
                'premium_rate': round(premium_rate, 2),
                'status': status,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Premium calculation error for {etf_code}: {e}")
            return None

    def _fetch_nav_from_eastmoney(self, etf_code: str) -> Optional[float]:
        """Fetch NAV from EastMoney with retry mechanism

        Args:
            etf_code: ETF code

        Returns:
            NAV value (real-time estimated NAV if available, otherwise latest NAV)
        """
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                code_num = etf_code.split('.')[0]
                url = f"http://fundgz.1234567.com.cn/js/{code_num}.js"

                response = requests.get(url, timeout=10)  # Increased timeout
                if response.status_code != 200:
                    logger.warning(f"EastMoney API returned status {response.status_code} for {etf_code}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return None

                # Parse JavaScript response
                # Format: jsonpgz({"fundcode":"159920","name":"...","jzrq":"2025-11-17","dwjz":"1.612","gsz":"1.625",...});
                # Priority: gsz (估算净值, real-time estimated) > dwjz (单位净值, last closing)

                # Try to get estimated NAV first (real-time during trading hours)
                gsz_match = re.search(r'"gsz":"([\d.]+)"', response.text)
                if gsz_match:
                    nav = float(gsz_match.group(1))
                    logger.debug(f"Using estimated NAV (gsz) for {etf_code}: {nav}")
                    return nav

                # Fallback to unit NAV (last closing)
                dwjz_match = re.search(r'"dwjz":"([\d.]+)"', response.text)
                if dwjz_match:
                    nav = float(dwjz_match.group(1))
                    logger.debug(f"Using unit NAV (dwjz) for {etf_code}: {nav}")
                    return nav

                logger.warning(f"No NAV data found in EastMoney response for {etf_code}")
                return None

            except requests.Timeout as e:
                logger.warning(f"EastMoney NAV fetch timeout for {etf_code} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
            except Exception as e:
                logger.warning(f"EastMoney NAV fetch failed for {etf_code} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None

        return None

    def _fetch_nav_from_sina(self, etf_code: str) -> Optional[float]:
        """Fetch NAV from Sina Finance

        Args:
            etf_code: ETF code

        Returns:
            NAV value
        """
        try:
            code_num = etf_code.split('.')[0]
            # Sina finance fund API
            url = f"https://hq.sinajs.cn/list=fu_{code_num}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://finance.sina.com.cn/'
            }

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return None

            # Parse response format: var hq_str_fu_513090="基金名称,净值,日期,时间,累计净值,..."
            response.encoding = 'gbk'
            text = response.text

            if 'hq_str_fu_' not in text:
                return None

            # Extract data between quotes
            match = re.search(r'"([^"]+)"', text)
            if not match:
                return None

            parts = match.group(1).split(',')
            if len(parts) >= 2 and parts[1]:
                nav = float(parts[1])
                logger.debug(f"Using NAV from Sina for {etf_code}: {nav}")
                return nav

            return None

        except Exception as e:
            logger.debug(f"Sina NAV fetch failed for {etf_code}: {e}")
            return None

    def _fetch_nav_from_jisilu(self, etf_code: str) -> Optional[float]:
        """Fetch NAV from Jisilu

        Args:
            etf_code: ETF code

        Returns:
            NAV value
        """
        try:
            code_num = etf_code.split('.')[0]
            url = "https://www.jisilu.cn/data/etf/etf_list/"

            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://www.jisilu.cn/data/etf/'
            }

            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return None

            data = response.json()
            if 'rows' not in data:
                return None

            # Find ETF in list
            for row in data['rows']:
                cell = row.get('cell', {})
                if cell.get('fund_id') == code_num:
                    nav = cell.get('unit_net_value')
                    if nav:
                        logger.debug(f"Using NAV from Jisilu for {etf_code}: {nav}")
                        return float(nav)

            return None

        except Exception as e:
            logger.debug(f"Jisilu NAV fetch failed for {etf_code}: {e}")
            return None

    def get_holdings(self, etf_code: str, top_n: int = 10) -> Optional[Dict[str, Any]]:
        """Get ETF holdings composition

        Args:
            etf_code: ETF code
            top_n: Number of top holdings to return

        Returns:
            Holdings data including top holdings and sector distribution
        """
        if self.use_cache:
            cache_key = f"etf_holdings:{etf_code}"
            cached = self.cache.get(cache_key, max_age=86400)  # 24 hours
            if cached:
                logger.debug(f"Using cached holdings for {etf_code}")
                return cached

        try:
            result = self._fetch_holdings(etf_code, top_n)

            if result and self.use_cache:
                cache_key = f"etf_holdings:{etf_code}"
                self.cache.set(
                    cache_key,
                    result,
                    ttl=86400,
                    data_type="etf_holdings",
                    stock_code=etf_code
                )

            return result

        except Exception as e:
            logger.error(f"Failed to get holdings for {etf_code}: {e}")
            return None

    def _fetch_holdings(self, etf_code: str, top_n: int) -> Optional[Dict[str, Any]]:
        """Fetch holdings from data sources

        Args:
            etf_code: ETF code
            top_n: Number of top holdings

        Returns:
            Holdings data
        """
        # This would require accessing fund disclosure reports
        # For now, return a placeholder structure
        logger.info(f"Holdings data for {etf_code} requires manual integration")

        return {
            'etf_code': etf_code,
            'update_date': None,
            'total_stocks': None,
            'top_holdings': [],
            'sector_distribution': {},
            'note': 'Holdings data requires Tushare Pro or manual integration'
        }

    def get_fund_flow(self, etf_code: str, days: int = 5) -> Optional[Dict[str, Any]]:
        """Analyze ETF fund flow (inflow/outflow)

        Args:
            etf_code: ETF code
            days: Number of days to analyze

        Returns:
            Fund flow data
        """
        if self.use_cache:
            cache_key = f"etf_flow:{etf_code}:{days}"
            cached = self.cache.get(cache_key, max_age=3600)  # 1 hour
            if cached:
                logger.debug(f"Using cached fund flow for {etf_code}")
                return cached

        try:
            result = self._calculate_fund_flow(etf_code, days)

            if result and self.use_cache:
                cache_key = f"etf_flow:{etf_code}:{days}"
                self.cache.set(
                    cache_key,
                    result,
                    ttl=3600,
                    data_type="etf_flow",
                    stock_code=etf_code
                )

            return result

        except Exception as e:
            logger.error(f"Failed to get fund flow for {etf_code}: {e}")
            return None

    def _calculate_fund_flow(self, etf_code: str, days: int) -> Optional[Dict[str, Any]]:
        """Calculate fund flow based on volume and price changes

        Args:
            etf_code: ETF code
            days: Number of days

        Returns:
            Fund flow estimation
        """
        try:
            from src.api.stock_api import fetch_history_df

            # Get historical data
            df = fetch_history_df(etf_code, days=days)
            if df is None or df.empty:
                return None

            # Estimate fund flow based on volume * price
            # Positive flow when price rises with high volume
            # Negative flow when price falls with high volume

            daily_flow = []
            for _, row in df.tail(days).iterrows():
                close = float(row.get('close', 0))
                volume = int(row.get('volume', 0))
                date = row.get('date')

                # Simple estimation: volume * close
                amount = volume * close * 100  # volume is in lots (100 shares)

                daily_flow.append({
                    'date': str(date)[:10] if hasattr(date, 'strftime') else str(date)[:10],
                    'amount': amount
                })

            # Calculate net flow
            total_flow = sum(d['amount'] for d in daily_flow)

            # Determine trend
            if total_flow > 0:
                trend = 'inflow'
            elif total_flow < 0:
                trend = 'outflow'
            else:
                trend = 'neutral'

            return {
                'etf_code': etf_code,
                'period_days': days,
                'net_flow': round(total_flow, 2),
                'daily_flow': daily_flow,
                'trend': trend,
                'note': 'Estimated based on volume and price'
            }

        except Exception as e:
            logger.error(f"Fund flow calculation error for {etf_code}: {e}")
            return None


# Global instance
etf_analyzer = ETFAnalyzer()
