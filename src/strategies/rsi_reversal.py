# src/strategies/rsi_reversal.py - RSI reversal strategy
import logging
from collections import deque
from typing import Dict

import numpy as np

from src.backtest.engine import MarketDataEvent, Strategy

logger = logging.getLogger(__name__)


class RSIReversal(Strategy):
    """RSI-based mean reversion strategy.

    Trading Logic:
    - BUY: RSI drops below oversold threshold (default 30)
    - SELL: RSI rises above overbought threshold (default 70)
    - EXIT: RSI returns to neutral zone (40-60)

    Parameters:
    - rsi_period: RSI calculation period (default: 14)
    - oversold_threshold: Buy threshold (default: 30)
    - overbought_threshold: Sell threshold (default: 70)
    - extreme_oversold: Strong buy threshold (default: 20)
    - extreme_overbought: Strong sell threshold (default: 80)
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        super().__init__("rsi_reversal", config)

        self.rsi_period = config.get("rsi_period", 14)
        self.oversold = config.get("oversold_threshold", 30)
        self.overbought = config.get("overbought_threshold", 70)
        self.extreme_oversold = config.get("extreme_oversold", 20)
        self.extreme_overbought = config.get("extreme_overbought", 80)

        # Price history
        self.price_history: Dict[str, deque] = {}
        self.rsi_values: Dict[str, deque] = {}
        self.last_signal: Dict[str, str] = {}

        logger.info(
            f"RSI Reversal initialized: period={self.rsi_period}, "
            f"oversold={self.oversold}, overbought={self.overbought}"
        )

    def calculate_rsi(self, prices: deque) -> float:
        """Calculate RSI indicator"""
        if len(prices) < self.rsi_period + 1:
            return None

        prices_array = np.array(list(prices))
        deltas = np.diff(prices_array)

        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Calculate average gains and losses
        avg_gain = np.mean(gains[-self.rsi_period :])
        avg_loss = np.mean(losses[-self.rsi_period :])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    async def handle_market_data(self, event: MarketDataEvent):
        """Process market data and generate signals"""
        symbol = event.symbol
        close_price = float(event.price_data.get("close", 0))

        if close_price <= 0:
            return

        # Initialize history
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.rsi_period * 2)
            self.rsi_values[symbol] = deque(maxlen=50)
            self.last_signal[symbol] = None

        self.price_history[symbol].append(close_price)

        # Calculate RSI
        rsi = self.calculate_rsi(self.price_history[symbol])
        if rsi is None:
            return

        self.rsi_values[symbol].append(rsi)

        # Generate signals
        if rsi <= self.extreme_oversold and self.last_signal[symbol] != "STRONG_BUY":
            # Extreme oversold - strong buy signal
            signal_strength = 0.95
            await self.generate_signal(symbol, "BUY", signal_strength)
            self.last_signal[symbol] = "STRONG_BUY"
            logger.info(
                f"{symbol}: Extreme oversold RSI={rsi:.2f} at price {close_price:.2f} - STRONG BUY"
            )

        elif (
            self.extreme_oversold < rsi <= self.oversold
            and self.last_signal[symbol] not in ["BUY", "STRONG_BUY"]
        ):
            # Oversold - regular buy signal
            signal_strength = 0.7 + (self.oversold - rsi) / self.oversold * 0.2
            await self.generate_signal(symbol, "BUY", signal_strength)
            self.last_signal[symbol] = "BUY"
            logger.info(f"{symbol}: Oversold RSI={rsi:.2f} at price {close_price:.2f} - BUY")

        elif rsi >= self.extreme_overbought and self.last_signal[symbol] != "STRONG_SELL":
            # Extreme overbought - strong sell signal
            signal_strength = 0.95
            await self.generate_signal(symbol, "SELL", signal_strength)
            self.last_signal[symbol] = "STRONG_SELL"
            logger.info(
                f"{symbol}: Extreme overbought RSI={rsi:.2f} at price {close_price:.2f} - STRONG SELL"
            )

        elif (
            self.overbought <= rsi < self.extreme_overbought
            and self.last_signal[symbol] not in ["SELL", "STRONG_SELL"]
        ):
            # Overbought - regular sell signal
            signal_strength = 0.7 + (rsi - self.overbought) / (100 - self.overbought) * 0.2
            await self.generate_signal(symbol, "SELL", signal_strength)
            self.last_signal[symbol] = "SELL"
            logger.info(f"{symbol}: Overbought RSI={rsi:.2f} at price {close_price:.2f} - SELL")

        elif 40 <= rsi <= 60 and self.last_signal[symbol] is not None:
            # Back to neutral zone - reset
            self.last_signal[symbol] = None

    def get_state(self) -> Dict:
        """Get strategy state"""
        return {
            "name": self.name,
            "rsi_period": self.rsi_period,
            "oversold": self.oversold,
            "overbought": self.overbought,
            "symbols_tracked": len(self.price_history),
            "current_rsi": {
                symbol: self.rsi_values[symbol][-1] if self.rsi_values[symbol] else None
                for symbol in self.rsi_values
            },
        }