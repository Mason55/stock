# src/risk/position_monitor.py - Position monitoring and rebalancing
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Monitor positions and trigger rebalancing.

    Features:
    - Real-time position tracking
    - Unrealized/realized P&L calculation
    - Position drift detection
    - Automatic rebalancing alerts
    - Large loss warnings
    """

    def __init__(self, config: Dict = None):
        config = config or {}

        # Configuration
        self.rebalance_threshold = config.get('rebalance_threshold', 0.05)  # 5%
        self.rebalance_interval = config.get('rebalance_interval', 3600)  # 1 hour
        self.alert_on_large_loss = config.get('alert_on_large_loss', True)
        self.large_loss_threshold = config.get('large_loss_threshold', 0.05)  # 5%

        # State
        self.positions: Dict[str, Dict] = {}
        self.target_weights: Dict[str, float] = {}
        self.last_rebalance_check = datetime.now()

        logger.info(
            f"Position Monitor initialized: rebalance_threshold={self.rebalance_threshold:.1%}"
        )

    def set_target_weights(self, weights: Dict[str, float]):
        """Set target portfolio weights.

        Args:
            weights: Dict of {symbol: weight} (weights should sum to ~1.0)
        """
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Target weights sum to {total:.2%}, not 100%")

        self.target_weights = weights.copy()
        logger.info(f"Target weights set for {len(weights)} positions")

    def update(
        self,
        symbol: str,
        quantity: int,
        avg_cost: float,
        current_price: float,
        last_price: Optional[float] = None
    ):
        """Update position data.

        Args:
            symbol: Stock symbol
            quantity: Current quantity
            avg_cost: Average cost basis
            current_price: Current market price
            last_price: Previous price (for realized P&L calculation)
        """
        if symbol not in self.positions:
            self.positions[symbol] = {
                'quantity': 0,
                'avg_cost': 0.0,
                'unrealized_pnl': 0.0,
                'realized_pnl': 0.0,
                'market_value': 0.0,
                'total_cost': 0.0,
                'updated_at': datetime.now()
            }

        pos = self.positions[symbol]
        old_quantity = pos['quantity']

        # Update position
        pos['quantity'] = quantity
        pos['avg_cost'] = avg_cost
        pos['market_value'] = quantity * current_price
        pos['total_cost'] = quantity * avg_cost
        pos['updated_at'] = datetime.now()

        # Calculate unrealized P&L
        pos['unrealized_pnl'] = pos['market_value'] - pos['total_cost']

        # Calculate realized P&L if position closed or reduced
        if quantity < old_quantity and last_price:
            sold_qty = old_quantity - quantity
            realized = (last_price - avg_cost) * sold_qty
            pos['realized_pnl'] += realized

        # Check for large losses
        if self.alert_on_large_loss and pos['total_cost'] > 0:
            loss_pct = pos['unrealized_pnl'] / pos['total_cost']
            if loss_pct < -self.large_loss_threshold:
                logger.warning(
                    f"Large loss alert: {symbol} down {loss_pct:.2%} "
                    f"(¥{pos['unrealized_pnl']:,.2f})"
                )

    def remove_position(self, symbol: str):
        """Remove a closed position."""
        if symbol in self.positions:
            del self.positions[symbol]
            logger.info(f"Position removed: {symbol}")

    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position data for symbol."""
        return self.positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Dict]:
        """Get all current positions."""
        return self.positions.copy()

    def get_total_value(self) -> float:
        """Get total portfolio value."""
        return sum(pos['market_value'] for pos in self.positions.values())

    def get_total_pnl(self) -> Dict:
        """Get total P&L metrics."""
        total_unrealized = sum(pos['unrealized_pnl'] for pos in self.positions.values())
        total_realized = sum(pos['realized_pnl'] for pos in self.positions.values())
        total_cost = sum(pos['total_cost'] for pos in self.positions.values())

        return {
            'unrealized_pnl': total_unrealized,
            'realized_pnl': total_realized,
            'total_pnl': total_unrealized + total_realized,
            'total_cost': total_cost,
            'return_pct': ((total_unrealized + total_realized) / total_cost) if total_cost > 0 else 0
        }

    def check_rebalance_needed(self) -> Dict:
        """Check if rebalancing is needed.

        Returns:
            Dict with rebalance status and recommendations
        """
        now = datetime.now()

        # Check interval
        elapsed = (now - self.last_rebalance_check).total_seconds()
        if elapsed < self.rebalance_interval:
            return {
                'needed': False,
                'reason': f'Last check {elapsed:.0f}s ago (interval: {self.rebalance_interval}s)'
            }

        self.last_rebalance_check = now

        if not self.target_weights:
            return {
                'needed': False,
                'reason': 'No target weights set'
            }

        # Calculate current weights
        total_value = self.get_total_value()
        if total_value == 0:
            return {
                'needed': False,
                'reason': 'No positions'
            }

        current_weights = {
            symbol: pos['market_value'] / total_value
            for symbol, pos in self.positions.items()
        }

        # Check drift for each position
        drifts = {}
        max_drift = 0

        for symbol, target_weight in self.target_weights.items():
            current_weight = current_weights.get(symbol, 0)
            drift = abs(current_weight - target_weight)
            drifts[symbol] = {
                'target': target_weight,
                'current': current_weight,
                'drift': drift,
                'drift_pct': drift / target_weight if target_weight > 0 else 0
            }

            if drift > max_drift:
                max_drift = drift

        # Check if any position exceeded threshold
        needs_rebalance = max_drift > self.rebalance_threshold

        result = {
            'needed': needs_rebalance,
            'max_drift': max_drift,
            'drifts': drifts,
            'total_value': total_value
        }

        if needs_rebalance:
            result['reason'] = f'Max drift {max_drift:.2%} > threshold {self.rebalance_threshold:.2%}'
            result['recommendations'] = self._generate_rebalance_recommendations(drifts, total_value)
        else:
            result['reason'] = f'Max drift {max_drift:.2%} within threshold'

        return result

    def _generate_rebalance_recommendations(
        self,
        drifts: Dict,
        total_value: float
    ) -> List[Dict]:
        """Generate rebalancing trade recommendations.

        Args:
            drifts: Position drift data
            total_value: Total portfolio value

        Returns:
            List of recommended trades
        """
        recommendations = []

        for symbol, drift_data in drifts.items():
            target_weight = drift_data['target']
            current_weight = drift_data['current']

            if abs(current_weight - target_weight) < self.rebalance_threshold:
                continue

            # Calculate target value and current value
            target_value = total_value * target_weight
            pos = self.positions.get(symbol)

            if not pos:
                # Need to buy
                recommendations.append({
                    'symbol': symbol,
                    'action': 'BUY',
                    'target_value': target_value,
                    'current_value': 0,
                    'adjustment': target_value
                })
            else:
                current_value = pos['market_value']
                adjustment = target_value - current_value

                if abs(adjustment) > 100:  # Min adjustment ¥100
                    action = 'BUY' if adjustment > 0 else 'SELL'
                    recommendations.append({
                        'symbol': symbol,
                        'action': action,
                        'target_value': target_value,
                        'current_value': current_value,
                        'adjustment': abs(adjustment)
                    })

        return recommendations

    def get_performance_metrics(self) -> Dict:
        """Get portfolio performance metrics."""
        pnl = self.get_total_pnl()
        total_value = self.get_total_value()

        winning_positions = [
            symbol for symbol, pos in self.positions.items()
            if pos['unrealized_pnl'] > 0
        ]

        losing_positions = [
            symbol for symbol, pos in self.positions.items()
            if pos['unrealized_pnl'] < 0
        ]

        return {
            'total_value': total_value,
            'total_positions': len(self.positions),
            'winning_positions': len(winning_positions),
            'losing_positions': len(losing_positions),
            'win_rate': len(winning_positions) / len(self.positions) if self.positions else 0,
            **pnl
        }