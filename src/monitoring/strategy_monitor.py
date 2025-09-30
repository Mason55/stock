# src/monitoring/strategy_monitor.py - Strategy performance monitoring
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StrategyMetrics:
    """Strategy performance metrics."""
    strategy_name: str

    # Returns
    total_return: float = 0.0
    daily_return: float = 0.0
    annualized_return: float = 0.0

    # Risk metrics
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0

    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # P&L
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0  # total_wins / total_losses

    # Execution
    avg_fill_time: float = 0.0  # seconds
    fill_rate: float = 1.0  # percentage of orders filled

    # Health score (0-100)
    health_score: int = 100

    # Timestamps
    last_trade_time: Optional[datetime] = None
    last_signal_time: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.now)


class StrategyMonitor:
    """Monitor strategy performance and health.

    Features:
    - Real-time return tracking
    - Signal quality statistics (win rate, profit factor)
    - Strategy health scoring
    - Performance degradation detection
    - Prometheus metrics export
    """

    def __init__(self, config: Dict = None):
        config = config or {}

        # Configuration
        self.min_trades_for_stats = config.get('min_trades_for_stats', 10)
        self.health_check_interval = config.get('health_check_interval', 300)  # 5 min
        self.performance_window = config.get('performance_window', 30)  # 30 days

        # State
        self.strategies: Dict[str, StrategyMetrics] = {}
        self.trade_history: Dict[str, List[Dict]] = defaultdict(list)
        self.equity_curves: Dict[str, List[Dict]] = defaultdict(list)

        logger.info("Strategy Monitor initialized")

    def register_strategy(self, strategy_name: str):
        """Register a strategy for monitoring."""
        if strategy_name not in self.strategies:
            self.strategies[strategy_name] = StrategyMetrics(strategy_name=strategy_name)
            logger.info(f"Strategy registered: {strategy_name}")

    def record_trade(
        self,
        strategy_name: str,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
        exit_price: float,
        pnl: float,
        entry_time: datetime,
        exit_time: datetime
    ):
        """Record completed trade."""
        if strategy_name not in self.strategies:
            self.register_strategy(strategy_name)

        trade = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'duration': (exit_time - entry_time).total_seconds()
        }

        self.trade_history[strategy_name].append(trade)

        # Update metrics
        metrics = self.strategies[strategy_name]
        metrics.total_trades += 1
        metrics.total_pnl += pnl
        metrics.last_trade_time = exit_time

        if pnl > 0:
            metrics.winning_trades += 1
        elif pnl < 0:
            metrics.losing_trades += 1

        # Recalculate statistics
        self._update_trade_statistics(strategy_name)

        logger.debug(
            f"Trade recorded: {strategy_name} | {symbol} {side} | "
            f"PnL: {pnl:,.2f}"
        )

    def record_signal(
        self,
        strategy_name: str,
        symbol: str,
        signal_type: str,
        strength: float
    ):
        """Record strategy signal generation."""
        if strategy_name not in self.strategies:
            self.register_strategy(strategy_name)

        metrics = self.strategies[strategy_name]
        metrics.last_signal_time = datetime.now()

    def update_equity(
        self,
        strategy_name: str,
        equity: float,
        timestamp: datetime = None
    ):
        """Update strategy equity curve."""
        timestamp = timestamp or datetime.now()

        if strategy_name not in self.strategies:
            self.register_strategy(strategy_name)

        self.equity_curves[strategy_name].append({
            'timestamp': timestamp,
            'equity': equity
        })

        # Keep only recent data
        cutoff = datetime.now() - timedelta(days=self.performance_window)
        self.equity_curves[strategy_name] = [
            e for e in self.equity_curves[strategy_name]
            if e['timestamp'] > cutoff
        ]

        # Update return metrics
        self._update_return_metrics(strategy_name)

    def _update_trade_statistics(self, strategy_name: str):
        """Update trade statistics from history."""
        metrics = self.strategies[strategy_name]
        trades = self.trade_history[strategy_name]

        if not trades:
            return

        # Win rate
        if metrics.total_trades > 0:
            metrics.win_rate = metrics.winning_trades / metrics.total_trades

        # Average win/loss
        winning_pnls = [t['pnl'] for t in trades if t['pnl'] > 0]
        losing_pnls = [t['pnl'] for t in trades if t['pnl'] < 0]

        if winning_pnls:
            metrics.avg_win = sum(winning_pnls) / len(winning_pnls)
        if losing_pnls:
            metrics.avg_loss = abs(sum(losing_pnls) / len(losing_pnls))

        # Profit factor
        total_wins = sum(winning_pnls) if winning_pnls else 0
        total_losses = abs(sum(losing_pnls)) if losing_pnls else 0

        if total_losses > 0:
            metrics.profit_factor = total_wins / total_losses
        elif total_wins > 0:
            metrics.profit_factor = float('inf')

        # Average fill time (estimate from trade duration)
        if len(trades) >= self.min_trades_for_stats:
            metrics.avg_fill_time = sum(t['duration'] for t in trades[-10:]) / 10

        metrics.updated_at = datetime.now()

    def _update_return_metrics(self, strategy_name: str):
        """Update return and risk metrics from equity curve."""
        metrics = self.strategies[strategy_name]
        equity_curve = self.equity_curves[strategy_name]

        if len(equity_curve) < 2:
            return

        equities = [e['equity'] for e in equity_curve]

        # Total return
        initial_equity = equities[0]
        current_equity = equities[-1]

        if initial_equity > 0:
            metrics.total_return = (current_equity - initial_equity) / initial_equity

        # Daily return
        if len(equities) >= 2:
            metrics.daily_return = (equities[-1] - equities[-2]) / equities[-2]

        # Calculate returns series
        returns = []
        for i in range(1, len(equities)):
            if equities[i-1] > 0:
                ret = (equities[i] - equities[i-1]) / equities[i-1]
                returns.append(ret)

        if not returns:
            return

        # Volatility (standard deviation of returns)
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        metrics.volatility = variance ** 0.5

        # Annualized return (assuming daily data)
        if len(equity_curve) > 1:
            days = (equity_curve[-1]['timestamp'] - equity_curve[0]['timestamp']).days
            if days > 0:
                metrics.annualized_return = ((current_equity / initial_equity) ** (365 / days)) - 1

        # Sharpe ratio (assuming risk-free rate = 0)
        if metrics.volatility > 0:
            metrics.sharpe_ratio = mean_return / metrics.volatility * (252 ** 0.5)

        # Maximum drawdown
        peak = equities[0]
        max_dd = 0

        for equity in equities:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        metrics.max_drawdown = max_dd

        metrics.updated_at = datetime.now()

    def calculate_health_score(self, strategy_name: str) -> int:
        """Calculate strategy health score (0-100).

        Factors:
        - Win rate (20 points)
        - Profit factor (20 points)
        - Sharpe ratio (20 points)
        - Drawdown (20 points)
        - Recent activity (20 points)
        """
        if strategy_name not in self.strategies:
            return 0

        metrics = self.strategies[strategy_name]

        # Need minimum trades for meaningful score
        if metrics.total_trades < self.min_trades_for_stats:
            return 50  # Neutral score

        score = 0

        # Win rate (20 points)
        # 50% = 10 pts, 60% = 15 pts, 70%+ = 20 pts
        if metrics.win_rate >= 0.70:
            score += 20
        elif metrics.win_rate >= 0.60:
            score += 15
        elif metrics.win_rate >= 0.50:
            score += 10
        else:
            score += max(0, int(metrics.win_rate * 20))

        # Profit factor (20 points)
        # >2.0 = 20 pts, >1.5 = 15 pts, >1.0 = 10 pts
        if metrics.profit_factor >= 2.0:
            score += 20
        elif metrics.profit_factor >= 1.5:
            score += 15
        elif metrics.profit_factor >= 1.0:
            score += 10
        else:
            score += max(0, int(metrics.profit_factor * 10))

        # Sharpe ratio (20 points)
        # >2.0 = 20 pts, >1.0 = 15 pts, >0.5 = 10 pts
        if metrics.sharpe_ratio >= 2.0:
            score += 20
        elif metrics.sharpe_ratio >= 1.0:
            score += 15
        elif metrics.sharpe_ratio >= 0.5:
            score += 10
        else:
            score += max(0, int(metrics.sharpe_ratio * 10))

        # Drawdown (20 points)
        # <5% = 20 pts, <10% = 15 pts, <20% = 10 pts
        if metrics.max_drawdown < 0.05:
            score += 20
        elif metrics.max_drawdown < 0.10:
            score += 15
        elif metrics.max_drawdown < 0.20:
            score += 10
        else:
            score += max(0, 20 - int(metrics.max_drawdown * 100))

        # Recent activity (20 points)
        if metrics.last_trade_time:
            hours_since_trade = (datetime.now() - metrics.last_trade_time).total_seconds() / 3600
            if hours_since_trade < 24:
                score += 20
            elif hours_since_trade < 72:
                score += 15
            elif hours_since_trade < 168:  # 1 week
                score += 10
            else:
                score += 5
        else:
            score += 10  # Neutral

        metrics.health_score = min(100, score)
        return metrics.health_score

    def get_metrics(self, strategy_name: str) -> Optional[StrategyMetrics]:
        """Get metrics for a strategy."""
        return self.strategies.get(strategy_name)

    def get_all_metrics(self) -> Dict[str, StrategyMetrics]:
        """Get metrics for all strategies."""
        # Update health scores
        for name in self.strategies:
            self.calculate_health_score(name)

        return self.strategies.copy()

    def get_summary(self) -> Dict:
        """Get summary statistics across all strategies."""
        if not self.strategies:
            return {}

        total_trades = sum(m.total_trades for m in self.strategies.values())
        total_pnl = sum(m.total_pnl for m in self.strategies.values())

        active_strategies = [
            name for name, m in self.strategies.items()
            if m.last_trade_time and
            (datetime.now() - m.last_trade_time).total_seconds() < 86400  # 24h
        ]

        avg_health = (
            sum(m.health_score for m in self.strategies.values()) / len(self.strategies)
            if self.strategies else 0
        )

        return {
            'total_strategies': len(self.strategies),
            'active_strategies': len(active_strategies),
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'avg_health_score': avg_health,
            'updated_at': datetime.now()
        }

    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        for name, metrics in self.strategies.items():
            prefix = f'strategy_{name.lower().replace(" ", "_")}'

            lines.append(f'# HELP {prefix}_total_return Total return percentage')
            lines.append(f'# TYPE {prefix}_total_return gauge')
            lines.append(f'{prefix}_total_return {metrics.total_return:.6f}')

            lines.append(f'# HELP {prefix}_sharpe_ratio Sharpe ratio')
            lines.append(f'# TYPE {prefix}_sharpe_ratio gauge')
            lines.append(f'{prefix}_sharpe_ratio {metrics.sharpe_ratio:.6f}')

            lines.append(f'# HELP {prefix}_win_rate Win rate')
            lines.append(f'# TYPE {prefix}_win_rate gauge')
            lines.append(f'{prefix}_win_rate {metrics.win_rate:.6f}')

            lines.append(f'# HELP {prefix}_health_score Health score (0-100)')
            lines.append(f'# TYPE {prefix}_health_score gauge')
            lines.append(f'{prefix}_health_score {metrics.health_score}')

            lines.append(f'# HELP {prefix}_total_trades Total number of trades')
            lines.append(f'# TYPE {prefix}_total_trades counter')
            lines.append(f'{prefix}_total_trades {metrics.total_trades}')

            lines.append('')

        return '\n'.join(lines)