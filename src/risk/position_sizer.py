# src/risk/position_sizer.py - Position sizing algorithms
import logging
import math
from enum import Enum
from typing import Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class PositionSizeMethod(Enum):
    """Position sizing methods."""
    FIXED_RATIO = "fixed_ratio"  # Fixed percentage per position
    KELLY = "kelly"  # Kelly criterion
    VOLATILITY_ADJUSTED = "volatility_adjusted"  # ATR-based sizing
    EQUAL_WEIGHT = "equal_weight"  # 1/N allocation


class PositionSizer:
    """Calculate optimal position sizes.

    Supports multiple sizing methods:
    - Fixed ratio: Simple percentage-based
    - Kelly criterion: Optimal bet sizing
    - Volatility-adjusted: ATR/volatility-based
    - Equal weight: 1/N portfolio
    """

    def __init__(self, config: Dict = None):
        config = config or {}

        # Default parameters
        self.method = PositionSizeMethod(config.get('method', 'fixed_ratio'))
        self.default_ratio = config.get('default_ratio', 0.10)  # 10%
        self.kelly_fraction = config.get('kelly_fraction', 0.5)  # Half Kelly
        self.max_position_size = config.get('max_position_size', 0.20)  # 20% max
        self.min_position_size = config.get('min_position_size', 0.02)  # 2% min

        logger.info(f"Position Sizer initialized: method={self.method.value}")

    def calculate(
        self,
        available_capital: float,
        current_price: float,
        method: PositionSizeMethod = None,
        **kwargs
    ) -> int:
        """Calculate position size in shares.

        Args:
            available_capital: Available cash for trading
            current_price: Current stock price
            method: Position sizing method (uses default if None)
            **kwargs: Method-specific parameters

        Returns:
            Number of shares to buy (rounded to lot size)
        """
        if available_capital <= 0 or current_price <= 0:
            return 0

        method = method or self.method

        # Calculate position value
        if method == PositionSizeMethod.FIXED_RATIO:
            position_value = self._fixed_ratio(available_capital, **kwargs)
        elif method == PositionSizeMethod.KELLY:
            position_value = self._kelly_criterion(available_capital, **kwargs)
        elif method == PositionSizeMethod.VOLATILITY_ADJUSTED:
            position_value = self._volatility_adjusted(available_capital, current_price, **kwargs)
        elif method == PositionSizeMethod.EQUAL_WEIGHT:
            position_value = self._equal_weight(available_capital, **kwargs)
        else:
            logger.warning(f"Unknown method: {method}, using fixed ratio")
            position_value = self._fixed_ratio(available_capital, **kwargs)

        # Apply limits
        position_value = min(position_value, available_capital * self.max_position_size)
        position_value = max(position_value, available_capital * self.min_position_size)

        # Convert to shares
        shares = int(position_value / current_price / 100) * 100  # Round to 100 shares (lot size)

        logger.debug(
            f"Position calculated: {shares} shares @ ¥{current_price:.2f} "
            f"= ¥{shares * current_price:,.2f} ({method.value})"
        )

        return shares

    def _fixed_ratio(self, available_capital: float, ratio: float = None, **kwargs) -> float:
        """Fixed percentage of capital.

        Args:
            available_capital: Available cash
            ratio: Position ratio (default: self.default_ratio)
            **kwargs: Ignored extra parameters

        Returns:
            Position value in currency
        """
        ratio = ratio if ratio is not None else self.default_ratio
        return available_capital * ratio

    def _kelly_criterion(
        self,
        available_capital: float,
        win_rate: float = None,
        avg_win: float = None,
        avg_loss: float = None,
        **kwargs
    ) -> float:
        """Kelly criterion for optimal bet sizing.

        Formula: f = (p * b - q) / b
        where:
            f = fraction to bet
            p = probability of winning (win_rate)
            q = probability of losing (1 - win_rate)
            b = ratio of average win to average loss

        Args:
            available_capital: Available cash
            win_rate: Win probability (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount

        Returns:
            Position value in currency
        """
        # Use defaults if not provided
        if win_rate is None or avg_win is None or avg_loss is None:
            logger.warning("Kelly parameters missing, using default ratio")
            return self._fixed_ratio(available_capital)

        if not (0 < win_rate < 1) or avg_loss <= 0:
            logger.warning("Invalid Kelly parameters, using default ratio")
            return self._fixed_ratio(available_capital)

        # Calculate Kelly fraction
        b = avg_win / avg_loss
        q = 1 - win_rate
        kelly_f = (win_rate * b - q) / b

        # Apply Kelly fraction (typically use half-Kelly for safety)
        kelly_f = kelly_f * self.kelly_fraction

        # Ensure non-negative
        if kelly_f <= 0:
            return available_capital * self.min_position_size

        return available_capital * min(kelly_f, self.max_position_size)

    def _volatility_adjusted(
        self,
        available_capital: float,
        current_price: float,
        atr: float = None,
        volatility: float = None,
        risk_per_trade: float = None,
        **kwargs
    ) -> float:
        """Volatility-adjusted position sizing.

        Position size inversely proportional to volatility.
        Lower volatility -> Larger position
        Higher volatility -> Smaller position

        Args:
            available_capital: Available cash
            current_price: Current price
            atr: Average True Range (price)
            volatility: Historical volatility (std dev)
            risk_per_trade: Maximum risk percentage per trade

        Returns:
            Position value in currency
        """
        if atr is None and volatility is None:
            logger.warning("No volatility data, using default ratio")
            return self._fixed_ratio(available_capital)

        # Use ATR if available, otherwise volatility
        if atr is not None:
            risk_per_share = atr
        elif volatility is not None:
            risk_per_share = current_price * volatility
        else:
            risk_per_share = current_price * 0.02  # Default 2%

        if risk_per_share <= 0:
            return self._fixed_ratio(available_capital)

        # Use config value if not provided
        if risk_per_trade is None:
            risk_per_trade = 0.01  # 1% default

        # Calculate position size based on risk
        risk_amount = available_capital * risk_per_trade
        shares = risk_amount / risk_per_share
        position_value = shares * current_price

        return min(position_value, available_capital * self.max_position_size)

    def _equal_weight(self, available_capital: float, num_positions: int = None, **kwargs) -> float:
        """Equal weight allocation (1/N).

        Args:
            available_capital: Available cash
            num_positions: Number of positions in portfolio

        Returns:
            Position value in currency
        """
        if num_positions is None or num_positions <= 0:
            # Default to 1/10 if not specified
            num_positions = 10

        return available_capital / num_positions

    def calculate_batch(
        self,
        available_capital: float,
        symbols: Dict[str, Dict],
        method: PositionSizeMethod = None
    ) -> Dict[str, int]:
        """Calculate position sizes for multiple symbols.

        Args:
            available_capital: Available cash
            symbols: Dict of {symbol: {'price': float, 'atr': float, ...}}
            method: Position sizing method

        Returns:
            Dict of {symbol: shares}
        """
        if not symbols:
            return {}

        method = method or self.method
        position_sizes = {}

        # For equal weight, adjust per symbol
        if method == PositionSizeMethod.EQUAL_WEIGHT:
            for symbol, data in symbols.items():
                shares = self.calculate(
                    available_capital,
                    data['price'],
                    method=method,
                    num_positions=len(symbols)
                )
                position_sizes[symbol] = shares
        else:
            # Other methods
            for symbol, data in symbols.items():
                shares = self.calculate(
                    available_capital,
                    data['price'],
                    method=method,
                    **data  # Pass all data as kwargs
                )
                position_sizes[symbol] = shares

        return position_sizes

    def calculate_kelly_parameters(self, trades: list) -> Dict:
        """Calculate Kelly parameters from trade history.

        Args:
            trades: List of trade dicts with 'pnl' key

        Returns:
            Dict with win_rate, avg_win, avg_loss
        """
        if not trades:
            return {}

        winning_trades = [t['pnl'] for t in trades if t['pnl'] > 0]
        losing_trades = [t['pnl'] for t in trades if t['pnl'] < 0]

        if not winning_trades or not losing_trades:
            return {}

        win_rate = len(winning_trades) / len(trades)
        avg_win = sum(winning_trades) / len(winning_trades)
        avg_loss = abs(sum(losing_trades) / len(losing_trades))

        return {
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_trades': len(trades),
            'win_count': len(winning_trades),
            'loss_count': len(losing_trades)
        }