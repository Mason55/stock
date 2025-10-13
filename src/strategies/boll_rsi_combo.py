# src/strategies/boll_rsi_combo.py - Bollinger Bands + RSI combined strategy
import logging
from collections import deque
from typing import Dict

import numpy as np

from src.backtest.engine import MarketDataEvent, Strategy

logger = logging.getLogger(__name__)


class BollingerRSICombo(Strategy):
    """Combined Bollinger Bands and RSI strategy for confirmation signals.

    Trading Logic:
    - BUY: Price at lower Bollinger band AND RSI oversold
    - SELL: Price at upper Bollinger band AND RSI overbought
    - Requires confirmation from both indicators for stronger signals

    Parameters:
    - boll_period: Bollinger Bands MA period (default: 20)
    - boll_std: Bollinger Bands std dev (default: 2.0)
    - rsi_period: RSI period (default: 14)
    - rsi_oversold: RSI oversold level (default: 30)
    - rsi_overbought: RSI overbought level (default: 70)
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        super().__init__("boll_rsi_combo", config)

        # Bollinger parameters
        self.boll_period = config.get("boll_period", 20)
        self.boll_std = config.get("boll_std", 2.0)

        # RSI parameters
        self.rsi_period = config.get("rsi_period", 14)
        self.rsi_oversold = config.get("rsi_oversold", 30)
        self.rsi_overbought = config.get("rsi_overbought", 70)

        # Data tracking
        self.price_history: Dict[str, deque] = {}
        self.last_signal: Dict[str, str] = {}

        logger.info(
            f"Bollinger+RSI Combo initialized: boll_period={self.boll_period}, "
            f"rsi_period={self.rsi_period}"
        )

    def calculate_bollinger(self, prices: deque) -> Dict:
        """Calculate Bollinger Bands"""
        if len(prices) < self.boll_period:
            return None

        prices_array = np.array(list(prices))
        middle = np.mean(prices_array[-self.boll_period :])
        std = np.std(prices_array[-self.boll_period :])
        upper = middle + self.boll_std * std
        lower = middle - self.boll_std * std

        return {"upper": upper, "middle": middle, "lower": lower}

    def calculate_rsi(self, prices: deque) -> float:
        """Calculate RSI"""
        if len(prices) < self.rsi_period + 1:
            return None

        prices_array = np.array(list(prices))
        deltas = np.diff(prices_array)

        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

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
            max_period = max(self.boll_period, self.rsi_period)
            self.price_history[symbol] = deque(maxlen=max_period * 2)
            self.last_signal[symbol] = None

        self.price_history[symbol].append(close_price)

        # Need enough data
        min_data = max(self.boll_period, self.rsi_period + 1)
        if len(self.price_history[symbol]) < min_data:
            return

        # Calculate indicators
        boll = self.calculate_bollinger(self.price_history[symbol])
        rsi = self.calculate_rsi(self.price_history[symbol])

        if boll is None or rsi is None:
            return

        upper, middle, lower = boll["upper"], boll["middle"], boll["lower"]

        # Bollinger Band position
        boll_position = (close_price - lower) / (upper - lower) if (upper - lower) > 0 else 0.5

        # Generate combined signals
        # BUY: Price near/below lower band AND RSI oversold
        if close_price <= lower * 1.02 and rsi <= self.rsi_oversold:
            if self.last_signal[symbol] != "BUY":
                # Strong signal - both indicators confirm
                rsi_strength = (self.rsi_oversold - rsi) / self.rsi_oversold
                boll_strength = max(0, (lower - close_price) / lower * 5)
                signal_strength = min(0.95, 0.75 + (rsi_strength + boll_strength) / 2 * 0.2)

                self.generate_signal(symbol, "BUY", signal_strength)
                self.last_signal[symbol] = "BUY"
                logger.info(
                    f"{symbol}: Confirmed BUY - Price {close_price:.2f} at lower band {lower:.2f}, "
                    f"RSI {rsi:.2f} oversold (strength={signal_strength:.2f})"
                )

        # SELL: Price near/above upper band AND RSI overbought
        elif close_price >= upper * 0.98 and rsi >= self.rsi_overbought:
            if self.last_signal[symbol] != "SELL":
                # Strong signal - both indicators confirm
                rsi_strength = (rsi - self.rsi_overbought) / (100 - self.rsi_overbought)
                boll_strength = max(0, (close_price - upper) / upper * 5)
                signal_strength = min(0.95, 0.75 + (rsi_strength + boll_strength) / 2 * 0.2)

                self.generate_signal(symbol, "SELL", signal_strength)
                self.last_signal[symbol] = "SELL"
                logger.info(
                    f"{symbol}: Confirmed SELL - Price {close_price:.2f} at upper band {upper:.2f}, "
                    f"RSI {rsi:.2f} overbought (strength={signal_strength:.2f})"
                )

        # Weaker single-indicator signals
        # Only Bollinger extreme
        elif close_price < lower and self.last_signal[symbol] != "WEAK_BUY":
            if 30 < rsi < 50:  # RSI not overbought
                self.generate_signal(symbol, "BUY", 0.6)
                self.last_signal[symbol] = "WEAK_BUY"
                logger.info(
                    f"{symbol}: Weak BUY - Price {close_price:.2f} below band, RSI {rsi:.2f} neutral"
                )

        # Only RSI extreme
        elif rsi < self.rsi_oversold and self.last_signal[symbol] != "WEAK_BUY":
            if lower < close_price < middle:  # Price in lower half but not extreme
                self.generate_signal(symbol, "BUY", 0.6)
                self.last_signal[symbol] = "WEAK_BUY"
                logger.info(
                    f"{symbol}: Weak BUY - RSI {rsi:.2f} oversold, price {close_price:.2f} in range"
                )

        # Reset signal when back to normal
        elif (
            lower < close_price < upper
            and 40 < rsi < 60
            and self.last_signal[symbol] is not None
        ):
            self.last_signal[symbol] = None

    def get_state(self) -> Dict:
        """Get strategy state"""
        return {
            "name": self.name,
            "boll_period": self.boll_period,
            "rsi_period": self.rsi_period,
            "symbols_tracked": len(self.price_history),
        }