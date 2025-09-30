# src/strategies/moving_average.py - Double moving average crossover strategy
import logging
from typing import Dict, List
from collections import deque

from src.backtest.engine import Strategy, MarketDataEvent

logger = logging.getLogger(__name__)


class MovingAverageCrossover(Strategy):
    """Double moving average crossover strategy.

    Trading Logic:
    - BUY: Fast MA crosses above Slow MA (golden cross)
    - SELL: Fast MA crosses below Slow MA (death cross)

    Parameters:
    - fast_period: Fast MA period (default: 5)
    - slow_period: Slow MA period (default: 20)
    - signal_strength: Signal strength when crossover occurs (default: 0.8)
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        super().__init__("moving_average_crossover", config)

        # Strategy parameters
        self.fast_period = config.get('fast_period', 5)
        self.slow_period = config.get('slow_period', 20)
        self.signal_strength = config.get('signal_strength', 0.8)

        # Price history for each symbol
        self.price_history: Dict[str, deque] = {}

        # Track last crossover direction to avoid repeated signals
        self.last_crossover: Dict[str, str] = {}  # 'up' or 'down'

        logger.info(
            f"MA Strategy initialized: fast={self.fast_period}, "
            f"slow={self.slow_period}, strength={self.signal_strength}"
        )

    async def handle_market_data(self, event: MarketDataEvent):
        """Process market data and generate signals."""
        symbol = event.symbol
        close_price = float(event.price_data.get('close', 0))

        if close_price <= 0:
            return

        # Initialize price history for new symbol
        if symbol not in self.price_history:
            # Need slow_period + 1 to detect crossover
            self.price_history[symbol] = deque(maxlen=self.slow_period + 1)
            self.last_crossover[symbol] = None

        # Update price history
        self.price_history[symbol].append(close_price)

        # Need enough data to calculate both MAs
        if len(self.price_history[symbol]) < self.slow_period:
            return

        # Calculate moving averages
        prices = list(self.price_history[symbol])
        fast_ma = sum(prices[-self.fast_period:]) / self.fast_period
        slow_ma = sum(prices[-self.slow_period:]) / self.slow_period

        # Detect crossover
        crossover = self._detect_crossover(symbol, fast_ma, slow_ma)

        if crossover == 'golden':
            # Fast MA crosses above Slow MA -> BUY signal
            if self.last_crossover[symbol] != 'up':
                self.generate_signal(
                    symbol,
                    "BUY",
                    strength=self.signal_strength,
                    metadata={
                        'fast_ma': fast_ma,
                        'slow_ma': slow_ma,
                        'price': close_price,
                        'strategy': 'ma_crossover',
                        'crossover_type': 'golden'
                    }
                )
                self.last_crossover[symbol] = 'up'
                logger.info(
                    f"Golden cross detected: {symbol} | "
                    f"MA({self.fast_period})={fast_ma:.2f} > "
                    f"MA({self.slow_period})={slow_ma:.2f}"
                )

        elif crossover == 'death':
            # Fast MA crosses below Slow MA -> SELL signal
            if self.last_crossover[symbol] != 'down':
                # Only sell if we have a position
                if symbol in self.position and self.position[symbol] > 0:
                    self.generate_signal(
                        symbol,
                        "SELL",
                        strength=1.0,  # Sell all
                        metadata={
                            'fast_ma': fast_ma,
                            'slow_ma': slow_ma,
                            'price': close_price,
                            'strategy': 'ma_crossover',
                            'crossover_type': 'death'
                        }
                    )
                self.last_crossover[symbol] = 'down'
                logger.info(
                    f"Death cross detected: {symbol} | "
                    f"MA({self.fast_period})={fast_ma:.2f} < "
                    f"MA({self.slow_period})={slow_ma:.2f}"
                )

    def _detect_crossover(self, symbol: str, fast_ma: float, slow_ma: float) -> str:
        """Detect MA crossover.

        Returns:
            'golden': Fast MA crosses above Slow MA
            'death': Fast MA crosses below Slow MA
            None: No crossover
        """
        # Need at least 2 data points to detect crossover
        if len(self.price_history[symbol]) < self.slow_period:
            return None

        # Calculate previous MAs
        prices = list(self.price_history[symbol])
        prev_prices = prices[:-1]

        if len(prev_prices) < self.slow_period:
            return None

        prev_fast_ma = sum(prev_prices[-self.fast_period:]) / self.fast_period
        prev_slow_ma = sum(prev_prices[-self.slow_period:]) / self.slow_period

        # Golden cross: fast was below, now above
        if prev_fast_ma <= prev_slow_ma and fast_ma > slow_ma:
            return 'golden'

        # Death cross: fast was above, now below
        if prev_fast_ma >= prev_slow_ma and fast_ma < slow_ma:
            return 'death'

        return None

    def get_indicators(self, symbol: str) -> Dict:
        """Get current indicator values for symbol."""
        if symbol not in self.price_history:
            return {}

        if len(self.price_history[symbol]) < self.slow_period:
            return {}

        prices = list(self.price_history[symbol])
        fast_ma = sum(prices[-self.fast_period:]) / self.fast_period
        slow_ma = sum(prices[-self.slow_period:]) / self.slow_period

        return {
            'fast_ma': fast_ma,
            'slow_ma': slow_ma,
            'current_price': prices[-1],
            'crossover_state': self.last_crossover.get(symbol)
        }