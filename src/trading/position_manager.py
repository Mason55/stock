# src/trading/position_manager.py - Position and risk management
"""Position sizing and risk management utilities."""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level enum."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass
class PositionSize:
    """Position size calculation result."""
    symbol: str
    shares: int
    price: float
    total_value: float
    position_pct: float
    risk_amount: float
    stop_loss_price: float


class PositionSizer:
    """Calculate optimal position sizes based on risk management rules."""

    def __init__(
        self,
        total_capital: float,
        risk_per_trade_pct: float = 0.02,  # 2% risk per trade
        max_position_pct: float = 0.20,  # 20% max per position
        max_total_exposure: float = 0.80  # 80% max total exposure
    ):
        """Initialize position sizer.

        Args:
            total_capital: Total available capital
            risk_per_trade_pct: Max risk per trade as decimal (default: 0.02 = 2%)
            max_position_pct: Max position size as decimal (default: 0.20 = 20%)
            max_total_exposure: Max total market exposure (default: 0.80 = 80%)
        """
        self.total_capital = total_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_pct = max_position_pct
        self.max_total_exposure = max_total_exposure

        self.current_positions: Dict[str, float] = {}  # {symbol: value}

    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        signal_strength: float = 1.0
    ) -> Optional[PositionSize]:
        """Calculate position size using risk-based method.

        Args:
            symbol: Stock symbol
            entry_price: Planned entry price
            stop_loss_price: Stop loss price
            signal_strength: Signal strength 0-1 (affects position size)

        Returns:
            PositionSize object or None if invalid
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            logger.error("Invalid prices for position sizing")
            return None

        if stop_loss_price >= entry_price:
            logger.error("Stop loss must be below entry price")
            return None

        # Calculate risk per share
        risk_per_share = entry_price - stop_loss_price
        risk_pct_per_share = risk_per_share / entry_price

        # Maximum risk amount in dollars
        max_risk_amount = self.total_capital * self.risk_per_trade_pct * signal_strength

        # Calculate shares based on risk
        shares_by_risk = int(max_risk_amount / risk_per_share)

        # Calculate shares based on max position size
        max_position_value = self.total_capital * self.max_position_pct
        shares_by_max = int(max_position_value / entry_price)

        # Take the smaller of the two
        shares = min(shares_by_risk, shares_by_max)

        if shares <= 0:
            logger.warning(f"Position size too small for {symbol}")
            return None

        # Calculate actual values
        total_value = shares * entry_price
        position_pct = total_value / self.total_capital
        risk_amount = shares * risk_per_share

        # Check total exposure
        current_exposure = sum(self.current_positions.values())
        if current_exposure + total_value > self.total_capital * self.max_total_exposure:
            logger.warning(
                f"Position would exceed max exposure: "
                f"current={current_exposure:.0f}, "
                f"new={total_value:.0f}, "
                f"max={self.total_capital * self.max_total_exposure:.0f}"
            )
            # Reduce position size to fit
            max_allowed = self.total_capital * self.max_total_exposure - current_exposure
            if max_allowed > 0:
                shares = int(max_allowed / entry_price)
                total_value = shares * entry_price
                position_pct = total_value / self.total_capital
                risk_amount = shares * risk_per_share
            else:
                return None

        return PositionSize(
            symbol=symbol,
            shares=shares,
            price=entry_price,
            total_value=total_value,
            position_pct=position_pct,
            risk_amount=risk_amount,
            stop_loss_price=stop_loss_price
        )

    def calculate_kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """Calculate Kelly Criterion position size.

        Args:
            win_rate: Historical win rate (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount (positive number)

        Returns:
            Optimal position size as decimal (e.g., 0.25 = 25%)
        """
        if avg_loss == 0 or win_rate >= 1 or win_rate <= 0:
            return 0.0

        b = avg_win / avg_loss  # Win/loss ratio
        p = win_rate
        q = 1 - p

        # Kelly % = (bp - q) / b
        kelly_pct = (b * p - q) / b

        # Use fractional Kelly for safety (half Kelly)
        fractional_kelly = kelly_pct * 0.5

        # Cap at reasonable maximum
        return min(max(fractional_kelly, 0.0), 0.25)

    def add_position(self, symbol: str, value: float):
        """Add or update position."""
        self.current_positions[symbol] = value

    def remove_position(self, symbol: str):
        """Remove position."""
        if symbol in self.current_positions:
            del self.current_positions[symbol]

    def get_available_capital(self) -> float:
        """Get available capital (not invested)."""
        current_exposure = sum(self.current_positions.values())
        return self.total_capital - current_exposure

    def get_exposure_pct(self) -> float:
        """Get current market exposure percentage."""
        current_exposure = sum(self.current_positions.values())
        return current_exposure / self.total_capital if self.total_capital > 0 else 0

    def update_capital(self, new_capital: float):
        """Update total capital."""
        self.total_capital = new_capital


class RiskPreset:
    """Predefined risk management presets."""

    @staticmethod
    def conservative() -> Dict:
        """Conservative risk parameters."""
        return {
            'risk_per_trade_pct': 0.01,  # 1% per trade
            'max_position_pct': 0.10,  # 10% per position
            'max_total_exposure': 0.60,  # 60% total exposure
            'stop_loss_pct': 0.03  # 3% stop loss
        }

    @staticmethod
    def moderate() -> Dict:
        """Moderate risk parameters."""
        return {
            'risk_per_trade_pct': 0.02,  # 2% per trade
            'max_position_pct': 0.20,  # 20% per position
            'max_total_exposure': 0.80,  # 80% total exposure
            'stop_loss_pct': 0.05  # 5% stop loss
        }

    @staticmethod
    def aggressive() -> Dict:
        """Aggressive risk parameters."""
        return {
            'risk_per_trade_pct': 0.03,  # 3% per trade
            'max_position_pct': 0.30,  # 30% per position
            'max_total_exposure': 0.95,  # 95% total exposure
            'stop_loss_pct': 0.08  # 8% stop loss
        }

    @staticmethod
    def get_preset(risk_level: RiskLevel) -> Dict:
        """Get preset by risk level."""
        presets = {
            RiskLevel.CONSERVATIVE: RiskPreset.conservative(),
            RiskLevel.MODERATE: RiskPreset.moderate(),
            RiskLevel.AGGRESSIVE: RiskPreset.aggressive()
        }
        return presets.get(risk_level, RiskPreset.moderate())

    @staticmethod
    def get_sizer_params(risk_level: RiskLevel) -> Dict:
        """Get only PositionSizer initialization parameters.

        Use this when creating a PositionSizer instance.
        For stop_loss_pct, use the full preset dict or calculate_stop_loss().

        Args:
            risk_level: Risk level

        Returns:
            Dict with only risk_per_trade_pct, max_position_pct, max_total_exposure
        """
        preset = RiskPreset.get_preset(risk_level)
        return {
            'risk_per_trade_pct': preset['risk_per_trade_pct'],
            'max_position_pct': preset['max_position_pct'],
            'max_total_exposure': preset['max_total_exposure']
        }


def calculate_stop_loss(entry_price: float, stop_loss_pct: float = 0.05) -> float:
    """Calculate stop loss price.

    Args:
        entry_price: Entry price
        stop_loss_pct: Stop loss as percentage (default: 0.05 = 5%)

    Returns:
        Stop loss price
    """
    return entry_price * (1 - stop_loss_pct)


def calculate_take_profit(entry_price: float, risk_reward_ratio: float = 2.0, stop_loss_price: float = None) -> float:
    """Calculate take profit price based on risk/reward ratio.

    Args:
        entry_price: Entry price
        risk_reward_ratio: Risk/reward ratio (default: 2.0 = 2:1)
        stop_loss_price: Stop loss price (optional)

    Returns:
        Take profit price
    """
    if stop_loss_price:
        risk = entry_price - stop_loss_price
        return entry_price + (risk * risk_reward_ratio)
    else:
        # Assume 5% risk
        risk = entry_price * 0.05
        return entry_price + (risk * risk_reward_ratio)


# Example usage
if __name__ == "__main__":
    # Create position sizer with $100,000 capital
    sizer = PositionSizer(total_capital=100000, risk_per_trade_pct=0.02)

    # Calculate position for a stock
    position = sizer.calculate_position_size(
        symbol="000977.SZ",
        entry_price=70.0,
        stop_loss_price=65.0,  # 5元止损 (~7%)
        signal_strength=0.8
    )

    if position:
        print(f"\nPosition Size Calculation:")
        print(f"Symbol: {position.symbol}")
        print(f"Entry Price: ¥{position.price:.2f}")
        print(f"Shares: {position.shares}")
        print(f"Total Value: ¥{position.total_value:,.2f}")
        print(f"Position %: {position.position_pct:.1%}")
        print(f"Risk Amount: ¥{position.risk_amount:,.2f}")
        print(f"Stop Loss: ¥{position.stop_loss_price:.2f}")
