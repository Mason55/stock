# src/services/indicators_calculator.py - Calculate and store technical indicators
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from src.models.indicators import IndicatorSignals, TechnicalIndicators
from src.models.market_data import HistoricalPrice

logger = logging.getLogger(__name__)


class IndicatorsCalculator:
    """Calculate technical indicators from historical price data"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def calculate_ma(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average"""
        return prices.rolling(window=period, min_periods=period).mean()

    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False, min_periods=period).mean()

    def calculate_macd(
        self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Dict[str, pd.Series]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False, min_periods=signal).mean()
        histogram = dif - dea

        return {"dif": dif, "dea": dea, "histogram": histogram}

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=period).mean()

        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_bollinger_bands(
        self, prices: pd.Series, period: int = 20, std_dev: float = 2.0
    ) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands"""
        middle = self.calculate_ma(prices, period)
        std = prices.rolling(window=period, min_periods=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        width = (upper - lower) / middle

        return {"upper": upper, "middle": middle, "lower": lower, "width": width}

    def calculate_kdj(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9
    ) -> Dict[str, pd.Series]:
        """Calculate KDJ indicator"""
        low_min = low.rolling(window=period, min_periods=period).min()
        high_max = high.rolling(window=period, min_periods=period).max()

        rsv = 100 * (close - low_min) / (high_max - low_min).replace(0, np.nan)

        k = rsv.ewm(com=2, adjust=False, min_periods=period).mean()
        d = k.ewm(com=2, adjust=False, min_periods=period).mean()
        j = 3 * k - 2 * d

        return {"k": k, "d": d, "j": j}

    def calculate_atr(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Calculate Average True Range"""
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period, min_periods=period).mean()

        return atr

    def fetch_historical_data(
        self, symbol: str, start_date: date, end_date: date
    ) -> Optional[pd.DataFrame]:
        """Fetch historical price data from database"""
        try:
            query = (
                self.db.query(HistoricalPrice)
                .filter(
                    HistoricalPrice.symbol == symbol,
                    HistoricalPrice.trade_date >= start_date,
                    HistoricalPrice.trade_date <= end_date,
                )
                .order_by(HistoricalPrice.trade_date)
            )

            data = []
            for row in query:
                data.append(
                    {
                        "date": row.trade_date,
                        "open": float(row.open_price),
                        "high": float(row.high_price),
                        "low": float(row.low_price),
                        "close": float(row.close_price),
                        "volume": int(row.volume),
                    }
                )

            if not data:
                return None

            df = pd.DataFrame(data)
            df.set_index("date", inplace=True)
            return df

        except Exception as e:
            logger.error(f"Failed to fetch historical data for {symbol}: {e}")
            return None

    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators for a dataframe"""
        if df is None or df.empty:
            return pd.DataFrame()

        result = pd.DataFrame(index=df.index)

        # Moving Averages
        result["ma_5"] = self.calculate_ma(df["close"], 5)
        result["ma_10"] = self.calculate_ma(df["close"], 10)
        result["ma_20"] = self.calculate_ma(df["close"], 20)
        result["ma_60"] = self.calculate_ma(df["close"], 60)
        result["ema_12"] = self.calculate_ema(df["close"], 12)
        result["ema_26"] = self.calculate_ema(df["close"], 26)

        # MACD
        macd = self.calculate_macd(df["close"])
        result["macd_dif"] = macd["dif"]
        result["macd_dea"] = macd["dea"]
        result["macd_histogram"] = macd["histogram"]

        # RSI
        result["rsi_6"] = self.calculate_rsi(df["close"], 6)
        result["rsi_12"] = self.calculate_rsi(df["close"], 12)
        result["rsi_24"] = self.calculate_rsi(df["close"], 24)

        # Bollinger Bands
        boll = self.calculate_bollinger_bands(df["close"])
        result["boll_upper"] = boll["upper"]
        result["boll_middle"] = boll["middle"]
        result["boll_lower"] = boll["lower"]
        result["boll_width"] = boll["width"]

        # KDJ
        kdj = self.calculate_kdj(df["high"], df["low"], df["close"])
        result["kdj_k"] = kdj["k"]
        result["kdj_d"] = kdj["d"]
        result["kdj_j"] = kdj["j"]

        # ATR
        result["atr_14"] = self.calculate_atr(df["high"], df["low"], df["close"])
        result["atr_normalized"] = result["atr_14"] / df["close"] * 100

        # Volume indicators
        result["volume_ma_5"] = df["volume"].rolling(window=5, min_periods=5).mean()
        result["volume_ma_10"] = df["volume"].rolling(window=10, min_periods=10).mean()
        result["volume_ratio"] = df["volume"] / result["volume_ma_5"]

        return result

    def generate_signals(self, symbol: str, indicators: pd.Series, calc_date: date) -> Dict:
        """Generate trading signals from indicators"""
        signals = {}
        interpretations = []

        # MA signals
        if indicators.get("ma_5") and indicators.get("ma_20"):
            if indicators["ma_5"] > indicators["ma_20"]:
                signals["ma_signal"] = "BUY"
                interpretations.append("Short-term MA above long-term MA (bullish)")
            else:
                signals["ma_signal"] = "SELL"
                interpretations.append("Short-term MA below long-term MA (bearish)")

        # MACD signals
        if indicators.get("macd_dif") and indicators.get("macd_dea"):
            if indicators["macd_dif"] > indicators["macd_dea"] and indicators["macd_histogram"] > 0:
                signals["macd_signal"] = "BUY"
                interpretations.append("MACD golden cross (bullish)")
            elif (
                indicators["macd_dif"] < indicators["macd_dea"] and indicators["macd_histogram"] < 0
            ):
                signals["macd_signal"] = "SELL"
                interpretations.append("MACD death cross (bearish)")

        # RSI signals
        if indicators.get("rsi_12"):
            if indicators["rsi_12"] < 30:
                signals["rsi_signal"] = "BUY"
                interpretations.append(f"RSI oversold ({indicators['rsi_12']:.1f})")
            elif indicators["rsi_12"] > 70:
                signals["rsi_signal"] = "SELL"
                interpretations.append(f"RSI overbought ({indicators['rsi_12']:.1f})")

        # Bollinger Bands signals
        if (
            indicators.get("boll_lower")
            and indicators.get("boll_upper")
            and indicators.get("close")
        ):
            close = indicators["close"]
            if close < indicators["boll_lower"]:
                signals["boll_signal"] = "BUY"
                interpretations.append("Price below lower Bollinger band")
            elif close > indicators["boll_upper"]:
                signals["boll_signal"] = "SELL"
                interpretations.append("Price above upper Bollinger band")

        # KDJ signals
        if indicators.get("kdj_k") and indicators.get("kdj_d"):
            if indicators["kdj_k"] < 20 and indicators["kdj_d"] < 20:
                signals["kdj_signal"] = "BUY"
                interpretations.append("KDJ in oversold zone")
            elif indicators["kdj_k"] > 80 and indicators["kdj_d"] > 80:
                signals["kdj_signal"] = "SELL"
                interpretations.append("KDJ in overbought zone")

        # Calculate overall signal
        buy_count = sum(1 for s in signals.values() if s == "BUY")
        sell_count = sum(1 for s in signals.values() if s == "SELL")
        total_signals = buy_count + sell_count

        if total_signals == 0:
            signal_type = "HOLD"
            signal_strength = 0.5
        elif buy_count > sell_count:
            signal_type = "BUY"
            signal_strength = buy_count / total_signals
        else:
            signal_type = "SELL"
            signal_strength = sell_count / total_signals

        return {
            "signal_type": signal_type,
            "signal_strength": signal_strength,
            "interpretation": "; ".join(interpretations),
            **signals,
        }

    def store_indicators(self, symbol: str, indicators_df: pd.DataFrame) -> int:
        """Store calculated indicators to database"""
        stored_count = 0

        for calc_date, row in indicators_df.iterrows():
            if pd.isna(row["ma_20"]):  # Skip rows without enough data
                continue

            try:
                indicator = (
                    self.db.query(TechnicalIndicators)
                    .filter_by(symbol=symbol, calc_date=calc_date)
                    .first()
                )

                if indicator is None:
                    indicator = TechnicalIndicators(symbol=symbol, calc_date=calc_date)
                    self.db.add(indicator)

                # Update all fields
                for col in row.index:
                    if pd.notna(row[col]):
                        value = row[col]
                        # Convert to proper type
                        if col.startswith("volume"):
                            setattr(indicator, col, int(value) if not pd.isna(value) else None)
                        else:
                            setattr(
                                indicator, col, Decimal(str(value)) if not pd.isna(value) else None
                            )

                stored_count += 1

            except Exception as e:
                logger.error(f"Failed to store indicator for {symbol} on {calc_date}: {e}")
                continue

        self.db.commit()
        return stored_count

    def process_stock(self, symbol: str, lookback_days: int = 120) -> bool:
        """Process a single stock: fetch data, calculate indicators, store results"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)

            logger.info(f"Processing {symbol} from {start_date} to {end_date}")

            # Fetch historical data
            df = self.fetch_historical_data(symbol, start_date, end_date)
            if df is None or df.empty:
                logger.warning(f"No historical data found for {symbol}")
                return False

            # Calculate indicators
            indicators_df = self.calculate_all_indicators(df)
            if indicators_df.empty:
                logger.warning(f"No indicators calculated for {symbol}")
                return False

            # Store indicators
            stored_count = self.store_indicators(symbol, indicators_df)
            logger.info(f"Stored {stored_count} indicator records for {symbol}")

            return stored_count > 0

        except Exception as e:
            logger.error(f"Failed to process {symbol}: {e}")
            return False