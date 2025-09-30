# src/strategies/mean_reversion.py - Mean reversion strategy using Bollinger Bands and RSI
import logging
from typing import Dict
from collections import deque
import math

from src.backtest.engine import Strategy, MarketDataEvent

logger = logging.getLogger(__name__)


class MeanReversion(Strategy):
    """Mean reversion strategy using Bollinger Bands and RSI.

    Trading Logic:
    - BUY: Price touches lower Bollinger Band AND RSI < oversold threshold
    - SELL: Price touches upper Bollinger Band OR RSI > overbought threshold

    Indicators:
    - Bollinger Bands: MA ± (std_dev × multiplier)
    - RSI: Relative Strength Index

    Parameters:
    - bb_period: Bollinger Bands period (default: 20)
    - bb_std_dev: Standard deviation multiplier (default: 2.0)
    - rsi_period: RSI period (default: 14)
    - rsi_oversold: RSI oversold threshold (default: 30)
    - rsi_overbought: RSI overbought threshold (default: 70)
    - signal_strength: Signal strength (default: 0.7)
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        super().__init__("mean_reversion", config)

        # Strategy parameters
        self.bb_period = config.get('bb_period', 20)
        self.bb_std_dev = config.get('bb_std_dev', 2.0)
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.signal_strength = config.get('signal_strength', 0.7)

        # Price history
        self.price_history: Dict[str, deque] = {}
        self.price_changes: Dict[str, deque] = {}

        logger.info(
            f"Mean Reversion Strategy initialized: BB({self.bb_period}, {self.bb_std_dev}), "
            f"RSI({self.rsi_period}, {self.rsi_oversold}/{self.rsi_overbought})"
        )

    async def handle_market_data(self, event: MarketDataEvent):
        """Process market data and generate signals."""
        symbol = event.symbol
        close_price = float(event.price_data.get('close', 0))

        if close_price <= 0:
            return

        # Initialize history
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=max(self.bb_period, self.rsi_period) + 1)
            self.price_changes[symbol] = deque(maxlen=self.rsi_period)

        # Store previous price for change calculation
        if len(self.price_history[symbol]) > 0:
            prev_price = self.price_history[symbol][-1]
            change = close_price - prev_price
            self.price_changes[symbol].append(change)

        # Update price history
        self.price_history[symbol].append(close_price)

        # Need enough data
        min_required = max(self.bb_period, self.rsi_period)
        if len(self.price_history[symbol]) < min_required:
            return

        # Calculate indicators
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(symbol)
        rsi = self._calculate_rsi(symbol)

        if bb_upper is None or rsi is None:
            return

        # Generate signals
        self._check_buy_signal(symbol, close_price, bb_lower, rsi)
        self._check_sell_signal(symbol, close_price, bb_upper, rsi)

    def _check_buy_signal(self, symbol: str, price: float, bb_lower: float, rsi: float):
        """Check for buy signal."""
        # Price at or below lower band AND RSI oversold
        if price <= bb_lower and rsi < self.rsi_oversold:
            self.generate_signal(
                symbol,
                "BUY",
                strength=self.signal_strength,
                metadata={
                    'price': price,
                    'bb_lower': bb_lower,
                    'rsi': rsi,
                    'strategy': 'mean_reversion',
                    'signal_type': 'oversold'
                }
            )
            logger.info(
                f"Mean reversion BUY: {symbol} | "
                f"Price={price:.2f} <= BB_lower={bb_lower:.2f}, RSI={rsi:.1f}"
            )

    def _check_sell_signal(self, symbol: str, price: float, bb_upper: float, rsi: float):
        """Check for sell signal."""
        # Only sell if we have position
        if symbol not in self.position or self.position[symbol] <= 0:
            return

        # Price at or above upper band OR RSI overbought
        if price >= bb_upper or rsi > self.rsi_overbought:
            self.generate_signal(
                symbol,
                "SELL",
                strength=1.0,  # Sell all
                metadata={
                    'price': price,
                    'bb_upper': bb_upper,
                    'rsi': rsi,
                    'strategy': 'mean_reversion',
                    'signal_type': 'overbought' if rsi > self.rsi_overbought else 'resistance'
                }
            )
            logger.info(
                f"Mean reversion SELL: {symbol} | "
                f"Price={price:.2f}, BB_upper={bb_upper:.2f}, RSI={rsi:.1f}"
            )

    def _calculate_bollinger_bands(self, symbol: str):
        """Calculate Bollinger Bands.

        Returns:
            (upper_band, middle_band, lower_band) or (None, None, None)
        """
        if len(self.price_history[symbol]) < self.bb_period:
            return None, None, None

        prices = list(self.price_history[symbol])[-self.bb_period:]

        # Calculate middle band (SMA)
        middle = sum(prices) / len(prices)

        # Calculate standard deviation
        variance = sum((p - middle) ** 2 for p in prices) / len(prices)
        std_dev = math.sqrt(variance)

        # Calculate bands
        upper = middle + (std_dev * self.bb_std_dev)
        lower = middle - (std_dev * self.bb_std_dev)

        return upper, middle, lower

    def _calculate_rsi(self, symbol: str):
        """Calculate RSI (Relative Strength Index).

        Returns:
            RSI value (0-100) or None
        """
        if len(self.price_changes[symbol]) < self.rsi_period:
            return None

        changes = list(self.price_changes[symbol])[-self.rsi_period:]

        # Separate gains and losses
        gains = [c if c > 0 else 0 for c in changes]
        losses = [-c if c < 0 else 0 for c in changes]

        # Calculate average gain and loss
        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)

        # Avoid division by zero
        if avg_loss == 0:
            return 100.0

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def get_indicators(self, symbol: str) -> Dict:
        """Get current indicator values for symbol."""
        if symbol not in self.price_history:
            return {}

        if len(self.price_history[symbol]) < max(self.bb_period, self.rsi_period):
            return {}

        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(symbol)
        rsi = self._calculate_rsi(symbol)

        return {
            'bb_upper': bb_upper,
            'bb_middle': bb_middle,
            'bb_lower': bb_lower,
            'rsi': rsi,
            'current_price': list(self.price_history[symbol])[-1]
        }