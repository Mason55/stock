# src/services/market_data_fetcher.py
"""Unified market data fetching service with multiple provider support"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp
import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)

# Constants for Sina API response parsing
SINA_MIN_RESPONSE_FIELDS = 32
SINA_FIELD_NAME = 0
SINA_FIELD_OPEN = 1
SINA_FIELD_PREV_CLOSE = 2
SINA_FIELD_CURRENT = 3
SINA_FIELD_HIGH = 4
SINA_FIELD_LOW = 5
SINA_FIELD_VOLUME = 8
SINA_FIELD_TURNOVER = 9


class MarketDataFetchError(Exception):
    """Base exception for market data fetching errors"""

    pass


class DataProviderUnavailableError(MarketDataFetchError):
    """Raised when a data provider is unavailable"""

    pass


def convert_to_sina_code(stock_code: str) -> str:
    """Convert standard code like 600580.SH to sh600580 for Sina"""
    try:
        code, market = stock_code.split(".")
        market = market.upper()
        prefix = "sh" if market == "SH" else "sz"
        return f"{prefix}{code}"
    except ValueError as e:
        logger.warning(f"Invalid stock code format: {stock_code}")
        raise MarketDataFetchError(f"Invalid stock code format: {stock_code}") from e


class RealtimeDataFetcher:
    """Async realtime market data fetcher"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=settings.EXTERNAL_API_TIMEOUT)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_sina_realtime(self, stock_code: str) -> Optional[Dict]:
        """Fetch realtime quote from Sina Finance API

        Args:
            stock_code: Standard stock code (e.g., 600580.SH)

        Returns:
            Normalized quote dict or None if failed

        Raises:
            DataProviderUnavailableError: If Sina API is unavailable
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        try:
            sina_code = convert_to_sina_code(stock_code)
            url = f"https://hq.sinajs.cn/list={sina_code}"
            headers = {
                "Referer": "https://finance.sina.com.cn",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            async with self.session.get(url, headers=headers, ssl=True) as resp:
                if resp.status != 200:
                    logger.warning(f"Sina API returned status {resp.status} for {stock_code}")
                    raise DataProviderUnavailableError(f"Sina API returned {resp.status}")

                text = await resp.text(encoding="gbk")
                return self._parse_sina_response(text, stock_code)

        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching Sina data for {stock_code}: {e}", exc_info=True)
            raise DataProviderUnavailableError(f"Network error: {e}") from e
        except Exception as e:
            logger.error(
                f"Unexpected error fetching Sina data for {stock_code}: {e}", exc_info=True
            )
            raise MarketDataFetchError(f"Unexpected error: {e}") from e

    def _parse_sina_response(self, text: str, stock_code: str) -> Optional[Dict]:
        """Parse Sina Finance API response text"""
        try:
            start = text.find('"') + 1
            end = text.rfind('"')
            if start <= 0 or end <= start:
                logger.warning(f"Invalid Sina response format for {stock_code}")
                return None

            data_str = text[start:end]
            if not data_str:
                return None

            parts = data_str.split(",")
            if len(parts) < SINA_MIN_RESPONSE_FIELDS:
                logger.warning(
                    f"Insufficient fields in Sina response for {stock_code}: {len(parts)}"
                )
                return None

            return {
                "stock_code": stock_code,
                "company_name": parts[SINA_FIELD_NAME],
                "open_price": float(parts[SINA_FIELD_OPEN] or 0),
                "previous_close": float(parts[SINA_FIELD_PREV_CLOSE] or 0),
                "current_price": float(parts[SINA_FIELD_CURRENT] or 0),
                "high_price": float(parts[SINA_FIELD_HIGH] or 0),
                "low_price": float(parts[SINA_FIELD_LOW] or 0),
                "volume": int(parts[SINA_FIELD_VOLUME] or 0),
                "turnover": float(parts[SINA_FIELD_TURNOVER] or 0),
                "timestamp": datetime.now().isoformat(),
                "source": "sina",
            }
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing Sina response for {stock_code}: {e}", exc_info=True)
            return None


class HistoricalDataFetcher:
    """Historical OHLCV data fetcher with multiple provider fallback"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=settings.EXTERNAL_API_TIMEOUT * 2)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_history(self, stock_code: str, days: int = 120) -> Optional[pd.DataFrame]:
        """Fetch historical data with fallback chain: Tushare -> Yahoo -> Sina

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        # Try Tushare first (requires token)
        df = await self._try_tushare(stock_code, days)
        if df is not None and not df.empty:
            logger.info(f"Fetched history for {stock_code} from Tushare")
            return df

        # Fallback to Yahoo Finance
        df = await self._try_yahoo(stock_code, days)
        if df is not None and not df.empty:
            logger.info(f"Fetched history for {stock_code} from Yahoo")
            return df

        # Final fallback to Sina K-line
        df = await self._try_sina_kline(stock_code, days)
        if df is not None and not df.empty:
            logger.info(f"Fetched history for {stock_code} from Sina")
            return df

        logger.warning(f"All historical data providers failed for {stock_code}")
        return None

    async def _try_tushare(self, stock_code: str, days: int) -> Optional[pd.DataFrame]:
        """Fetch from Tushare Pro API"""
        try:
            import os

            import tushare as ts

            token = os.getenv("TUSHARE_TOKEN")
            if not token:
                return None

            pro = ts.pro_api(token)
            end = datetime.now().strftime("%Y%m%d")
            start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

            df = pro.daily(ts_code=stock_code, start_date=start, end_date=end)
            if df is None or df.empty:
                return None

            df = df[["trade_date", "open", "high", "low", "close", "vol"]].copy()
            df.rename(columns={"trade_date": "date", "vol": "volume"}, inplace=True)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            return df.tail(days)

        except Exception as e:
            logger.warning(f"Tushare fetch failed for {stock_code}: {e}")
            return None

    async def _try_yahoo(self, stock_code: str, days: int) -> Optional[pd.DataFrame]:
        """Fetch from Yahoo Finance"""
        try:
            import yfinance as yf

            yf_symbol = stock_code.replace(".SH", ".SS")
            period_days = max(60, days + 10)
            data = yf.download(
                yf_symbol,
                period=f"{period_days}d",
                interval="1d",
                progress=False,
                auto_adjust=False,
            )

            if data is None or data.empty:
                return None

            data = data.reset_index()
            data.rename(
                columns={
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                },
                inplace=True,
            )
            return data.tail(days)

        except Exception as e:
            logger.warning(f"Yahoo fetch failed for {stock_code}: {e}")
            return None

    async def _try_sina_kline(self, stock_code: str, days: int) -> Optional[pd.DataFrame]:
        """Fetch daily K-line from Sina openapi"""
        if not self.session:
            return None

        try:
            sina_code = convert_to_sina_code(stock_code)
            url = "https://quotes.sina.cn/cn/api/openapi.php/CN_MarketDataService.getKLineData"
            params = {
                "symbol": sina_code,
                "scale": "240",  # daily
                "ma": "5",
                "datalen": str(max(60, days + 20)),
            }
            headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}

            async with self.session.get(url, params=params, headers=headers, ssl=True) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                if not data or "result" not in data or "data" not in data["result"]:
                    return None

                rows = data["result"]["data"]
                if not rows:
                    return None

                df = pd.DataFrame(rows)
                df.rename(columns={"day": "date"}, inplace=True)

                for col in ["open", "high", "low", "close", "volume"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date").reset_index(drop=True)
                return df.tail(days)

        except Exception as e:
            logger.warning(f"Sina K-line fetch failed for {stock_code}: {e}")
            return None


class TechnicalIndicatorCalculator:
    """Calculate technical indicators from historical data"""

    @staticmethod
    def calculate_ma(series: pd.Series, periods: List[int]) -> Dict[str, Optional[float]]:
        """Calculate moving averages"""
        result = {}
        for period in periods:
            if len(series) >= period:
                result[f"ma{period}"] = float(series.rolling(period).mean().iloc[-1])
            else:
                result[f"ma{period}"] = None
        return result

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> Optional[float]:
        """Calculate RSI indicator"""
        if len(series) < period + 1:
            return None

        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    @staticmethod
    def calculate_macd(
        series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Dict[str, Optional[float]]:
        """Calculate MACD indicator"""
        if len(series) < slow + signal:
            return {"macd": None, "signal": None, "histogram": None}

        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line

        return {
            "macd": float(macd.iloc[-1]),
            "signal": float(signal_line.iloc[-1]),
            "histogram": float(histogram.iloc[-1]),
        }

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> Dict:
        """Calculate comprehensive technical indicators"""
        if df is None or df.empty:
            return {}

        close_series = df["close"].astype(float)
        result = {}

        # Moving averages
        result.update(TechnicalIndicatorCalculator.calculate_ma(close_series, [5, 20, 60]))

        # RSI
        result["rsi"] = TechnicalIndicatorCalculator.calculate_rsi(close_series)

        # MACD
        macd_data = TechnicalIndicatorCalculator.calculate_macd(close_series)
        result["macd"] = macd_data["macd"]
        result["macd_signal"] = macd_data["signal"]
        result["macd_histogram"] = macd_data["histogram"]

        return result
