# src/strategies/bollinger_breakout.py - Bollinger Bands breakout strategy
import logging
from collections import deque
from typing import Dict

import numpy as np

from src.backtest.engine import MarketDataEvent, Strategy

logger = logging.getLogger(__name__)


class BollingerBreakout(Strategy):
    """Bollinger Bands breakout/mean reversion strategy.

    Trading Logic:
    - BUY: Price touches or breaks below lower band (oversold)
    - SELL: Price touches or breaks above upper band (overbought)

    Parameters:
    - period: MA period for middle band (default: 20)
    - std_dev: Standard deviation multiplier (default: 2.0)
    - mode: 'breakout' or 'reversion' (default: 'reversion')
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        super().__init__("bollinger_breakout", config)

        self.period = config.get("period", 20)
        self.std_dev = config.get("std_dev", 2.0)
        self.mode = config.get("mode", "reversion")  # or 'breakout'

        # Price history for each symbol
        self.price_history: Dict[str, deque] = {}
        self.last_signal: Dict[str, str] = {}

        logger.info(
            f"Bollinger Breakout initialized: period={self.period}, "
            f"std_dev={self.std_dev}, mode={self.mode}"
        )

    def calculate_bollinger_bands(self, prices: deque) -> Dict:
        """Calculate Bollinger Bands"""
        if len(prices) < self.period:
            return None

        prices_array = np.array(list(prices))
        middle = np.mean(prices_array[-self.period :])
        std = np.std(prices_array[-self.period :])
        upper = middle + self.std_dev * std
        lower = middle - self.std_dev * std

        return {"upper": upper, "middle": middle, "lower": lower, "std": std}

    async def handle_market_data(self, event: MarketDataEvent):
        """Process market data and generate signals"""
        symbol = event.symbol
        close_price = float(event.price_data.get("close", 0))

        if close_price <= 0:
            return

        # Initialize history
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.period + 10)
            self.last_signal[symbol] = None

        self.price_history[symbol].append(close_price)

        # Need enough data
        if len(self.price_history[symbol]) < self.period:
            return

        # Calculate Bollinger Bands
        bands = self.calculate_bollinger_bands(self.price_history[symbol])
        if not bands:
            return

        upper, middle, lower = bands["upper"], bands["middle"], bands["lower"]

        # Generate signals based on mode
        if self.mode == "reversion":
            # Mean reversion: buy at lower band, sell at upper band
            if close_price <= lower and self.last_signal[symbol] != "BUY":
                signal_strength = min(0.9, 0.6 + (lower - close_price) / lower * 5)
                self.generate_signal(symbol, "BUY", signal_strength)
                self.last_signal[symbol] = "BUY"
                logger.info(
                    f"{symbol}: Price {close_price:.2f} <= Lower band {lower:.2f} - BUY signal"
                )

            elif close_price >= upper and self.last_signal[symbol] != "SELL":
                signal_strength = min(0.9, 0.6 + (close_price - upper) / upper * 5)
                self.generate_signal(symbol, "SELL", signal_strength)
                self.last_signal[symbol] = "SELL"
                logger.info(
                    f"{symbol}: Price {close_price:.2f} >= Upper band {upper:.2f} - SELL signal"
                )

            elif lower < close_price < upper and self.last_signal[symbol] is not None:
                # Back to normal range
                self.last_signal[symbol] = None

        else:  # breakout mode
            # Breakout: buy when breaking above upper, sell when breaking below lower
            prev_price = list(self.price_history[symbol])[-2] if len(self.price_history[symbol]) > 1 else close_price

            # Upward breakout
            if prev_price <= upper < close_price and self.last_signal[symbol] != "BUY":
                signal_strength = 0.75
                self.generate_signal(symbol, "BUY", signal_strength)
                self.last_signal[symbol] = "BUY"
                logger.info(
                    f"{symbol}: Upward breakout at {close_price:.2f} through {upper:.2f} - BUY signal"
                )

            # Downward breakout
            elif prev_price >= lower > close_price and self.last_signal[symbol] != "SELL":
                signal_strength = 0.75
                self.generate_signal(symbol, "SELL", signal_strength)
                self.last_signal[symbol] = "SELL"
                logger.info(
                    f"{symbol}: Downward breakout at {close_price:.2f} through {lower:.2f} - SELL signal"
                )

    def get_state(self) -> Dict:
        """Get strategy state for persistence"""
        return {
            "name": self.name,
            "period": self.period,
            "std_dev": self.std_dev,
            "mode": self.mode,
            "symbols_tracked": len(self.price_history),
        }