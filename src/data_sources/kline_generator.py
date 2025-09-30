# src/data_sources/kline_generator.py - Real-time K-line generation from ticks
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Tick:
    """Tick data point."""
    symbol: str
    price: float
    volume: int
    timestamp: datetime


@dataclass
class KLine:
    """K-line (candlestick) data."""
    symbol: str
    interval: str  # "1m", "5m", "15m", "30m", "1h", "1d"
    timestamp: datetime
    open: float = 0.0
    high: float = 0.0
    low: float = float('inf')
    close: float = 0.0
    volume: int = 0
    turnover: float = 0.0
    tick_count: int = 0

    def update(self, tick: Tick):
        """Update K-line with new tick."""
        if self.tick_count == 0:
            self.open = tick.price

        self.high = max(self.high, tick.price)
        self.low = min(self.low, tick.price)
        self.close = tick.price
        self.volume += tick.volume
        self.turnover += tick.price * tick.volume
        self.tick_count += 1

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'interval': self.interval,
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low if self.low != float('inf') else self.open,
            'close': self.close,
            'volume': self.volume,
            'turnover': self.turnover
        }


class KLineGenerator:
    """Generate K-lines from tick data.

    Features:
    - Multiple timeframes (1m/5m/15m/30m/1h)
    - Real-time aggregation
    - K-line completion callbacks
    - Historical data persistence
    """

    INTERVALS = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600
    }

    def __init__(self, intervals: List[str] = None, config: Dict = None):
        config = config or {}

        # Configuration
        self.intervals = intervals or ['1m', '5m', '15m']
        self.save_to_db = config.get('save_to_db', True)
        self.max_history = config.get('max_history', 1000)  # Per symbol per interval

        # Validate intervals
        for interval in self.intervals:
            if interval not in self.INTERVALS:
                raise ValueError(f"Invalid interval: {interval}")

        # State
        self.current_klines: Dict[str, Dict[str, KLine]] = defaultdict(dict)
        self.kline_history: Dict[str, Dict[str, List[KLine]]] = defaultdict(lambda: defaultdict(list))
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)

        logger.info(f"KLine Generator initialized with intervals: {self.intervals}")

    def process_tick(self, symbol: str, price: float, volume: int, timestamp: datetime = None):
        """Process incoming tick data.

        Args:
            symbol: Stock symbol
            price: Tick price
            volume: Tick volume
            timestamp: Tick timestamp (default: now)
        """
        timestamp = timestamp or datetime.now()
        tick = Tick(symbol, price, volume, timestamp)

        for interval in self.intervals:
            self._update_kline(tick, interval)

    def _update_kline(self, tick: Tick, interval: str):
        """Update K-line for specific interval."""
        symbol = tick.symbol

        # Get or create current K-line
        if interval not in self.current_klines[symbol]:
            kline = self._create_kline(tick, interval)
            self.current_klines[symbol][interval] = kline
        else:
            kline = self.current_klines[symbol][interval]

            # Check if K-line period expired
            interval_seconds = self.INTERVALS[interval]
            if (tick.timestamp - kline.timestamp).total_seconds() >= interval_seconds:
                # Complete current K-line
                self._complete_kline(symbol, interval, kline)

                # Start new K-line
                kline = self._create_kline(tick, interval)
                self.current_klines[symbol][interval] = kline

        # Update with tick
        kline.update(tick)

    def _create_kline(self, tick: Tick, interval: str) -> KLine:
        """Create new K-line aligned to interval."""
        interval_seconds = self.INTERVALS[interval]

        # Align timestamp to interval boundary
        ts = tick.timestamp.replace(second=0, microsecond=0)
        minutes = (ts.minute // (interval_seconds // 60)) * (interval_seconds // 60)
        aligned_ts = ts.replace(minute=minutes)

        return KLine(
            symbol=tick.symbol,
            interval=interval,
            timestamp=aligned_ts
        )

    def _complete_kline(self, symbol: str, interval: str, kline: KLine):
        """Mark K-line as complete and trigger callbacks."""
        # Add to history
        self.kline_history[symbol][interval].append(kline)

        # Trim history
        if len(self.kline_history[symbol][interval]) > self.max_history:
            self.kline_history[symbol][interval] = \
                self.kline_history[symbol][interval][-self.max_history:]

        # Save to database
        if self.save_to_db:
            self._save_kline(kline)

        # Trigger callbacks
        for callback in self.callbacks[interval]:
            try:
                callback(kline)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        logger.debug(
            f"K-line completed: {symbol} {interval} | "
            f"O:{kline.open:.2f} H:{kline.high:.2f} "
            f"L:{kline.low:.2f} C:{kline.close:.2f} V:{kline.volume}"
        )

    def _save_kline(self, kline: KLine):
        """Save K-line to database (placeholder)."""
        # TODO: Implement database persistence
        # from src.database.session import DatabaseManager
        # db = DatabaseManager()
        # db.save_kline(kline)
        pass

    def register_callback(self, interval: str, callback: Callable):
        """Register callback for K-line completion.

        Args:
            interval: K-line interval
            callback: Function to call with completed KLine

        Callback signature: callback(kline: KLine)
        """
        if interval not in self.INTERVALS:
            raise ValueError(f"Invalid interval: {interval}")

        self.callbacks[interval].append(callback)
        logger.info(f"Callback registered for {interval}: {callback.__name__}")

    def get_current_kline(self, symbol: str, interval: str) -> Optional[KLine]:
        """Get current (incomplete) K-line."""
        return self.current_klines[symbol].get(interval)

    def get_history(
        self,
        symbol: str,
        interval: str,
        count: int = 100
    ) -> List[KLine]:
        """Get historical K-lines.

        Args:
            symbol: Stock symbol
            interval: K-line interval
            count: Number of K-lines to return

        Returns:
            List of K-lines (most recent last)
        """
        history = self.kline_history[symbol][interval]
        return history[-count:] if history else []

    def get_latest_kline(self, symbol: str, interval: str) -> Optional[KLine]:
        """Get most recent completed K-line."""
        history = self.kline_history[symbol][interval]
        return history[-1] if history else None

    def calculate_indicators(
        self,
        symbol: str,
        interval: str,
        period: int = 20
    ) -> Dict:
        """Calculate technical indicators from K-line history.

        Args:
            symbol: Stock symbol
            interval: K-line interval
            period: Indicator period

        Returns:
            Dict with MA, EMA, volume_ma
        """
        history = self.get_history(symbol, interval, period)

        if len(history) < period:
            return {}

        closes = [k.close for k in history]
        volumes = [k.volume for k in history]

        # Simple Moving Average
        ma = sum(closes[-period:]) / period

        # Exponential Moving Average
        multiplier = 2 / (period + 1)
        ema = closes[0]
        for price in closes[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        # Volume MA
        volume_ma = sum(volumes[-period:]) / period

        return {
            'ma': ma,
            'ema': ema,
            'volume_ma': volume_ma,
            'period': period
        }

    def get_statistics(self) -> Dict:
        """Get generator statistics."""
        total_symbols = len(self.current_klines)
        total_klines = sum(
            len(intervals)
            for intervals in self.current_klines.values()
        )

        total_history = sum(
            sum(len(klines) for klines in symbol_history.values())
            for symbol_history in self.kline_history.values()
        )

        return {
            'active_symbols': total_symbols,
            'active_klines': total_klines,
            'historical_klines': total_history,
            'intervals': self.intervals
        }