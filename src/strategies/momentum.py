# src/strategies/momentum.py - Momentum strategy based on price trends
import logging
from typing import Dict, List
from collections import deque

from src.backtest.engine import Strategy, MarketDataEvent

logger = logging.getLogger(__name__)


class Momentum(Strategy):
    """Momentum strategy based on price rate of change.

    Trading Logic:
    - BUY: Strong positive momentum (price rising consistently)
    - SELL: Momentum weakens or turns negative

    Calculates momentum as percentage change over lookback period.

    Parameters:
    - lookback_period: Period to calculate momentum (default: 20)
    - momentum_threshold: Minimum momentum % to trigger buy (default: 5.0)
    - exit_threshold: Momentum % to trigger sell (default: -2.0)
    - signal_strength: Base signal strength (default: 0.75)
    - max_positions: Maximum number of positions (default: 5)
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        super().__init__("momentum", config)

        # Strategy parameters
        self.lookback_period = config.get('lookback_period', 20)
        self.momentum_threshold = config.get('momentum_threshold', 5.0)  # 5%
        self.exit_threshold = config.get('exit_threshold', -2.0)  # -2%
        self.signal_strength = config.get('signal_strength', 0.75)
        self.max_positions = config.get('max_positions', 5)

        # Price history for momentum calculation
        self.price_history: Dict[str, deque] = {}

        # Track momentum scores for ranking
        self.momentum_scores: Dict[str, float] = {}

        logger.info(
            f"Momentum Strategy initialized: lookback={self.lookback_period}, "
            f"threshold={self.momentum_threshold}%, exit={self.exit_threshold}%"
        )

    async def handle_market_data(self, event: MarketDataEvent):
        """Process market data and generate signals."""
        symbol = event.symbol
        close_price = float(event.price_data.get('close', 0))

        if close_price <= 0:
            return

        # Initialize price history
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.lookback_period + 1)

        # Update price history
        self.price_history[symbol].append(close_price)

        # Need enough data
        if len(self.price_history[symbol]) < self.lookback_period:
            return

        # Calculate momentum
        momentum = self._calculate_momentum(symbol)
        self.momentum_scores[symbol] = momentum

        # Generate signals
        await self._check_buy_signal(symbol, close_price, momentum)
        await self._check_sell_signal(symbol, close_price, momentum)

    async def _check_buy_signal(self, symbol: str, price: float, momentum: float):
        """Check for buy signal based on momentum."""
        # Don't buy if already at max positions
        current_positions = len([s for s, qty in self.position.items() if qty > 0])
        if current_positions >= self.max_positions:
            return

        # Don't buy if already have position in this symbol
        if symbol in self.position and self.position[symbol] > 0:
            return

        # Strong positive momentum -> BUY
        if momentum >= self.momentum_threshold:
            # Adjust strength based on momentum strength
            strength = min(self.signal_strength * (momentum / self.momentum_threshold), 1.0)

            self.generate_signal(
                symbol,
                "BUY",
                strength=strength,
                metadata={
                    'price': price,
                    'momentum': momentum,
                    'strategy': 'momentum',
                    'signal_type': 'strong_momentum'
                }
            )
            logger.info(
                f"Momentum BUY: {symbol} | "
                f"Price={price:.2f}, Momentum={momentum:.2f}%"
            )

    async def _check_sell_signal(self, symbol: str, price: float, momentum: float):
        """Check for sell signal based on momentum."""
        # Only sell if we have position
        if symbol not in self.position or self.position[symbol] <= 0:
            return

        # Momentum weakens or turns negative -> SELL
        if momentum <= self.exit_threshold:
            self.generate_signal(
                symbol,
                "SELL",
                strength=1.0,  # Sell all
                metadata={
                    'price': price,
                    'momentum': momentum,
                    'strategy': 'momentum',
                    'signal_type': 'momentum_weakening'
                }
            )
            logger.info(
                f"Momentum SELL: {symbol} | "
                f"Price={price:.2f}, Momentum={momentum:.2f}%"
            )

    def _calculate_momentum(self, symbol: str) -> float:
        """Calculate momentum as percentage change.

        Returns:
            Momentum percentage (e.g., 5.0 means 5% increase)
        """
        if len(self.price_history[symbol]) < self.lookback_period:
            return 0.0

        prices = list(self.price_history[symbol])
        start_price = prices[-self.lookback_period]
        current_price = prices[-1]

        if start_price == 0:
            return 0.0

        momentum_pct = ((current_price - start_price) / start_price) * 100

        return momentum_pct

    def get_top_momentum_stocks(self, n: int = 5) -> List[tuple]:
        """Get top N stocks by momentum score.

        Returns:
            List of (symbol, momentum) tuples, sorted descending
        """
        ranked = sorted(
            self.momentum_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return ranked[:n]

    def get_indicators(self, symbol: str) -> Dict:
        """Get current indicator values for symbol."""
        if symbol not in self.price_history:
            return {}

        if len(self.price_history[symbol]) < self.lookback_period:
            return {}

        momentum = self._calculate_momentum(symbol)

        return {
            'momentum': momentum,
            'momentum_threshold': self.momentum_threshold,
            'exit_threshold': self.exit_threshold,
            'current_price': list(self.price_history[symbol])[-1],
            'lookback_price': list(self.price_history[symbol])[-self.lookback_period]
        }