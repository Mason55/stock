# src/risk/real_time_monitor.py - Real-time risk monitoring
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RiskAlert:
    """Risk alert data class."""
    timestamp: datetime
    level: str  # 'warning', 'limit', 'circuit_breaker'
    rule: str
    message: str
    data: Dict


class RealTimeRiskMonitor:
    """Real-time risk monitoring and circuit breaker.

    Features:
    - Daily loss circuit breaker
    - Maximum drawdown monitoring
    - Abnormal volatility detection
    - Position concentration control
    - Liquidity checks
    """

    def __init__(self, config: Dict = None):
        config = config or {}

        # Risk thresholds
        self.max_daily_loss_pct = config.get('max_daily_loss_pct', 3.0)  # -3%
        self.max_drawdown_pct = config.get('max_drawdown_pct', 10.0)  # -10%
        self.max_position_pct = config.get('max_position_pct', 15.0)  # 15% per stock
        self.max_volatility_factor = config.get('max_volatility_factor', 3.0)  # 3x normal
        self.min_liquidity_ratio = config.get('min_liquidity_ratio', 0.01)  # 1% of volume

        # State tracking
        self.daily_pnl = 0.0
        self.initial_capital = 0.0
        self.current_capital = 0.0
        self.peak_capital = 0.0
        self.daily_reset_time = None

        # Historical data for volatility calculation
        self.daily_returns: List[float] = []
        self.max_return_history = 30

        # Alert history
        self.alerts: List[RiskAlert] = []
        self.is_trading_halted = False
        self.halt_reason = None

        logger.info(
            f"Risk Monitor initialized: daily_loss={self.max_daily_loss_pct}%, "
            f"drawdown={self.max_drawdown_pct}%"
        )

    def initialize(self, initial_capital: float):
        """Initialize monitor with starting capital."""
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_capital = initial_capital
        self.daily_pnl = 0.0
        self.daily_reset_time = datetime.now()
        logger.info(f"Risk monitor initialized with capital: ¥{initial_capital:,.2f}")

    def update(self, current_capital: float, positions: Dict = None) -> Dict:
        """Update risk metrics and check violations.

        Args:
            current_capital: Current total portfolio value
            positions: Dict of {symbol: {'quantity': int, 'value': float}}

        Returns:
            Risk status dict with violations and alerts
        """
        # Reset daily P&L at day boundary
        self._check_daily_reset()

        # Update metrics
        old_capital = self.current_capital
        self.current_capital = current_capital
        self.peak_capital = max(self.peak_capital, current_capital)

        # Calculate P&L
        intraday_pnl = current_capital - old_capital
        self.daily_pnl += intraday_pnl

        # Check risk rules
        violations = []

        # 1. Daily loss check
        violation = self._check_daily_loss()
        if violation:
            violations.append(violation)

        # 2. Drawdown check
        violation = self._check_drawdown()
        if violation:
            violations.append(violation)

        # 3. Position concentration check
        if positions:
            violation = self._check_concentration(positions)
            if violation:
                violations.append(violation)

        # 4. Volatility check
        violation = self._check_volatility()
        if violation:
            violations.append(violation)

        # Generate alerts for violations
        for violation in violations:
            alert = RiskAlert(
                timestamp=datetime.now(),
                level=violation['level'],
                rule=violation['rule'],
                message=violation['message'],
                data=violation['data']
            )
            self.alerts.append(alert)
            logger.warning(f"Risk Alert [{alert.level}]: {alert.message}")

            # Circuit breaker
            if alert.level == 'circuit_breaker' and not self.is_trading_halted:
                self._halt_trading(alert)

        return {
            'is_halted': self.is_trading_halted,
            'halt_reason': self.halt_reason,
            'violations': violations,
            'metrics': self.get_metrics()
        }

    def _check_daily_reset(self):
        """Reset daily metrics at day boundary."""
        now = datetime.now()
        if self.daily_reset_time is None:
            self.daily_reset_time = now
            return

        # Reset if new day
        if now.date() > self.daily_reset_time.date():
            # Record daily return
            if self.current_capital > 0:
                daily_return = (self.current_capital - (self.current_capital - self.daily_pnl)) / (self.current_capital - self.daily_pnl)
                self.daily_returns.append(daily_return)
                if len(self.daily_returns) > self.max_return_history:
                    self.daily_returns.pop(0)

            # Reset
            self.daily_pnl = 0.0
            self.daily_reset_time = now
            logger.info("Daily risk metrics reset")

    def _check_daily_loss(self) -> Optional[Dict]:
        """Check daily loss threshold."""
        if self.current_capital == 0:
            return None

        start_capital = self.current_capital - self.daily_pnl
        if start_capital == 0:
            return None

        loss_pct = (self.daily_pnl / start_capital) * 100

        if loss_pct <= -self.max_daily_loss_pct:
            return {
                'rule': 'daily_loss',
                'level': 'circuit_breaker',
                'message': f"Daily loss limit exceeded: {loss_pct:.2f}% (limit: -{self.max_daily_loss_pct}%)",
                'data': {
                    'daily_pnl': self.daily_pnl,
                    'loss_pct': loss_pct,
                    'threshold': -self.max_daily_loss_pct
                }
            }
        elif loss_pct <= -(self.max_daily_loss_pct * 0.7):
            return {
                'rule': 'daily_loss',
                'level': 'warning',
                'message': f"Daily loss approaching limit: {loss_pct:.2f}%",
                'data': {
                    'daily_pnl': self.daily_pnl,
                    'loss_pct': loss_pct
                }
            }

        return None

    def _check_drawdown(self) -> Optional[Dict]:
        """Check maximum drawdown."""
        if self.peak_capital == 0:
            return None

        drawdown_pct = ((self.current_capital - self.peak_capital) / self.peak_capital) * 100

        if drawdown_pct <= -self.max_drawdown_pct:
            return {
                'rule': 'max_drawdown',
                'level': 'circuit_breaker',
                'message': f"Max drawdown exceeded: {drawdown_pct:.2f}% (limit: -{self.max_drawdown_pct}%)",
                'data': {
                    'drawdown_pct': drawdown_pct,
                    'peak_capital': self.peak_capital,
                    'current_capital': self.current_capital,
                    'threshold': -self.max_drawdown_pct
                }
            }
        elif drawdown_pct <= -(self.max_drawdown_pct * 0.7):
            return {
                'rule': 'max_drawdown',
                'level': 'warning',
                'message': f"Drawdown approaching limit: {drawdown_pct:.2f}%",
                'data': {
                    'drawdown_pct': drawdown_pct
                }
            }

        return None

    def _check_concentration(self, positions: Dict) -> Optional[Dict]:
        """Check position concentration."""
        if not positions or self.current_capital == 0:
            return None

        max_position_value = 0
        max_position_symbol = None

        for symbol, pos_data in positions.items():
            value = pos_data.get('value', 0)
            if value > max_position_value:
                max_position_value = value
                max_position_symbol = symbol

        concentration_pct = (max_position_value / self.current_capital) * 100

        if concentration_pct > self.max_position_pct:
            return {
                'rule': 'position_concentration',
                'level': 'limit',
                'message': f"Position concentration too high: {max_position_symbol} {concentration_pct:.2f}% (limit: {self.max_position_pct}%)",
                'data': {
                    'symbol': max_position_symbol,
                    'concentration_pct': concentration_pct,
                    'threshold': self.max_position_pct
                }
            }

        return None

    def _check_volatility(self) -> Optional[Dict]:
        """Check abnormal volatility."""
        if len(self.daily_returns) < 5:
            return None

        # Calculate volatility
        import math
        mean_return = sum(self.daily_returns) / len(self.daily_returns)
        variance = sum((r - mean_return) ** 2 for r in self.daily_returns) / len(self.daily_returns)
        std_dev = math.sqrt(variance)

        # Check today's move vs normal volatility
        if self.current_capital > 0 and std_dev > 0:
            start_capital = self.current_capital - self.daily_pnl
            if start_capital > 0:
                today_move_pct = abs(self.daily_pnl / start_capital)
                normal_move = std_dev * self.max_volatility_factor

                if today_move_pct > normal_move:
                    return {
                        'rule': 'abnormal_volatility',
                        'level': 'warning',
                        'message': f"Abnormal volatility detected: {today_move_pct:.2%} vs normal {normal_move:.2%}",
                        'data': {
                            'today_volatility': today_move_pct,
                            'normal_volatility': std_dev,
                            'factor': self.max_volatility_factor
                        }
                    }

        return None

    def _halt_trading(self, alert: RiskAlert):
        """Halt all trading due to risk violation."""
        self.is_trading_halted = True
        self.halt_reason = alert.message
        logger.critical(f"TRADING HALTED: {alert.message}")

    def resume_trading(self):
        """Manually resume trading after halt."""
        self.is_trading_halted = False
        self.halt_reason = None
        logger.info("Trading resumed manually")

    def get_metrics(self) -> Dict:
        """Get current risk metrics."""
        if self.current_capital == 0:
            return {}

        start_capital = self.current_capital - self.daily_pnl
        daily_return_pct = (self.daily_pnl / start_capital * 100) if start_capital > 0 else 0
        total_return_pct = ((self.current_capital - self.initial_capital) / self.initial_capital * 100) if self.initial_capital > 0 else 0
        drawdown_pct = ((self.current_capital - self.peak_capital) / self.peak_capital * 100) if self.peak_capital > 0 else 0

        return {
            'current_capital': self.current_capital,
            'daily_pnl': self.daily_pnl,
            'daily_return_pct': daily_return_pct,
            'total_return_pct': total_return_pct,
            'drawdown_pct': drawdown_pct,
            'peak_capital': self.peak_capital,
            'is_halted': self.is_trading_halted
        }

    def get_alerts(self, level: str = None, last_n: int = None) -> List[RiskAlert]:
        """Get risk alerts.

        Args:
            level: Filter by level ('warning', 'limit', 'circuit_breaker')
            last_n: Get last N alerts

        Returns:
            List of RiskAlert objects
        """
        alerts = self.alerts

        if level:
            alerts = [a for a in alerts if a.level == level]

        if last_n:
            alerts = alerts[-last_n:]

        return alerts