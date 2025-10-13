# src/strategies/grid_trading.py - Grid trading strategy for range-bound markets
import logging
from collections import deque
from typing import Dict, List

import numpy as np

from src.backtest.engine import MarketDataEvent, Strategy

logger = logging.getLogger(__name__)


class GridTrading(Strategy):
    """Grid trading strategy for range-bound markets.

    Trading Logic:
    - Divide price range into N grids
    - BUY when price drops to a grid level (if not already bought)
    - SELL when price rises to a grid level (if holding position)

    Parameters:
    - grid_count: Number of grid levels (default: 10)
    - price_range_pct: Price range as percentage (default: 20%)
    - base_price: Center price for grid (auto-calculated if not provided)
    - profit_per_grid: Profit target per grid level (default: 2%)
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        super().__init__("grid_trading", config)

        self.grid_count = config.get("grid_count", 10)
        self.price_range_pct = config.get("price_range_pct", 0.20)  # 20%
        self.profit_per_grid = config.get("profit_per_grid", 0.02)  # 2%
        self.base_price = config.get("base_price", None)

        # Track grid levels and positions
        self.grid_levels: Dict[str, List[float]] = {}
        self.buy_prices: Dict[str, List[float]] = {}  # Active buy positions
        self.last_grid_action: Dict[str, int] = {}  # Last grid level traded
        self.price_history: Dict[str, deque] = {}

        # Initialization status
        self.initialized: Dict[str, bool] = {}

        logger.info(
            f"Grid Trading initialized: grid_count={self.grid_count}, "
            f"range={self.price_range_pct*100}%, profit_per_grid={self.profit_per_grid*100}%"
        )

    def initialize_grids(self, symbol: str, current_price: float):
        """Initialize grid levels based on current price"""
        if self.base_price:
            base = self.base_price
        else:
            # Use historical average if available, otherwise current price
            if symbol in self.price_history and len(self.price_history[symbol]) > 20:
                base = np.mean(list(self.price_history[symbol]))
            else:
                base = current_price

        # Calculate grid levels
        range_half = base * self.price_range_pct / 2
        min_price = base - range_half
        max_price = base + range_half

        step = (max_price - min_price) / (self.grid_count - 1)
        self.grid_levels[symbol] = [min_price + i * step for i in range(self.grid_count)]

        self.buy_prices[symbol] = []
        self.last_grid_action[symbol] = -1
        self.initialized[symbol] = True

        logger.info(
            f"{symbol}: Grids initialized - Base: {base:.2f}, "
            f"Range: [{min_price:.2f}, {max_price:.2f}], "
            f"Step: {step:.2f}"
        )

    def find_nearest_grid(self, symbol: str, price: float) -> int:
        """Find nearest grid level index"""
        if symbol not in self.grid_levels:
            return -1

        grids = self.grid_levels[symbol]
        distances = [abs(price - grid) for grid in grids]
        return distances.index(min(distances))

    async def handle_market_data(self, event: MarketDataEvent):
        """Process market data and generate grid signals"""
        symbol = event.symbol
        close_price = float(event.price_data.get("close", 0))

        if close_price <= 0:
            return

        # Initialize price history
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=50)

        self.price_history[symbol].append(close_price)

        # Initialize grids after collecting some price history
        if not self.initialized.get(symbol, False):
            if len(self.price_history[symbol]) >= 20:
                self.initialize_grids(symbol, close_price)
            return

        grids = self.grid_levels[symbol]
        min_grid = grids[0]
        max_grid = grids[-1]

        # Check if price is out of range - may need rebalancing
        if close_price < min_grid * 0.95 or close_price > max_grid * 1.05:
            logger.warning(
                f"{symbol}: Price {close_price:.2f} outside grid range "
                f"[{min_grid:.2f}, {max_grid:.2f}] - Consider rebalancing"
            )
            return

        # Find current grid level
        current_grid_idx = self.find_nearest_grid(symbol, close_price)
        if current_grid_idx < 0:
            return

        current_grid_price = grids[current_grid_idx]
        last_action_grid = self.last_grid_action[symbol]

        # BUY signal: price dropped to a lower grid level
        if current_grid_idx < last_action_grid or last_action_grid == -1:
            # Only buy if not at the bottom grid (need room to fall more)
            if current_grid_idx > 0:
                # Check if we're close enough to the grid line (within 0.5%)
                if abs(close_price - current_grid_price) / current_grid_price < 0.005:
                    # Calculate signal strength based on grid position
                    # Stronger signals at lower grids
                    signal_strength = 0.6 + (1 - current_grid_idx / self.grid_count) * 0.3

                    self.generate_signal(symbol, "BUY", signal_strength)
                    self.buy_prices[symbol].append(close_price)
                    self.last_grid_action[symbol] = current_grid_idx

                    logger.info(
                        f"{symbol}: BUY at grid {current_grid_idx}/{self.grid_count-1} - "
                        f"Price: {close_price:.2f}, Grid: {current_grid_price:.2f}, "
                        f"Strength: {signal_strength:.2f}"
                    )

        # SELL signal: price rose to a higher grid level
        elif current_grid_idx > last_action_grid and self.buy_prices[symbol]:
            # Check if we have profitable positions to sell
            avg_buy_price = np.mean(self.buy_prices[symbol]) if self.buy_prices[symbol] else 0
            profit_pct = (close_price - avg_buy_price) / avg_buy_price if avg_buy_price > 0 else 0

            # Sell if we're at a grid line and profitable
            if (
                abs(close_price - current_grid_price) / current_grid_price < 0.005
                and profit_pct >= self.profit_per_grid
            ):
                # Stronger signals at higher grids
                signal_strength = 0.6 + (current_grid_idx / self.grid_count) * 0.3

                self.generate_signal(symbol, "SELL", signal_strength)

                # Remove one buy position (FIFO)
                if self.buy_prices[symbol]:
                    sold_price = self.buy_prices[symbol].pop(0)
                    actual_profit = (close_price - sold_price) / sold_price

                    logger.info(
                        f"{symbol}: SELL at grid {current_grid_idx}/{self.grid_count-1} - "
                        f"Price: {close_price:.2f}, Grid: {current_grid_price:.2f}, "
                        f"Bought: {sold_price:.2f}, Profit: {actual_profit*100:.2f}%, "
                        f"Strength: {signal_strength:.2f}"
                    )

                self.last_grid_action[symbol] = current_grid_idx

    def get_state(self) -> Dict:
        """Get strategy state"""
        return {
            "name": self.name,
            "grid_count": self.grid_count,
            "symbols_tracked": len(self.grid_levels),
            "active_positions": {
                symbol: {
                    "buy_count": len(self.buy_prices.get(symbol, [])),
                    "avg_price": (
                        float(np.mean(self.buy_prices[symbol])) if self.buy_prices.get(symbol) else 0
                    ),
                    "grid_range": (
                        [self.grid_levels[symbol][0], self.grid_levels[symbol][-1]]
                        if symbol in self.grid_levels
                        else None
                    ),
                }
                for symbol in self.grid_levels
            },
        }