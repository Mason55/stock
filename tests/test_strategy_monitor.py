# tests/test_strategy_monitor.py - Strategy monitor tests
import pytest
from datetime import datetime, timedelta

from src.monitoring.strategy_monitor import StrategyMonitor, StrategyMetrics


class TestStrategyMonitor:
    """Test StrategyMonitor functionality."""

    def test_initialization(self):
        """Test monitor initialization."""
        monitor = StrategyMonitor(config={
            'min_trades_for_stats': 10,
            'health_check_interval': 300,
            'performance_window': 30
        })

        assert monitor.min_trades_for_stats == 10
        assert monitor.health_check_interval == 300
        assert monitor.performance_window == 30
        assert len(monitor.strategies) == 0

    def test_register_strategy(self):
        """Test strategy registration."""
        monitor = StrategyMonitor()

        monitor.register_strategy('test_strategy')

        assert 'test_strategy' in monitor.strategies
        assert monitor.strategies['test_strategy'].strategy_name == 'test_strategy'
        assert monitor.strategies['test_strategy'].total_trades == 0

    def test_record_trade_winning(self):
        """Test recording winning trade."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        monitor.record_trade(
            strategy_name='test_strategy',
            symbol='000001.SZ',
            side='BUY',
            quantity=1000,
            entry_price=10.0,
            exit_price=10.5,
            pnl=500,
            entry_time=datetime(2025, 1, 1, 9, 30),
            exit_time=datetime(2025, 1, 1, 15, 0)
        )

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.total_trades == 1
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 0
        assert metrics.total_pnl == 500

    def test_record_trade_losing(self):
        """Test recording losing trade."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        monitor.record_trade(
            strategy_name='test_strategy',
            symbol='000001.SZ',
            side='BUY',
            quantity=1000,
            entry_price=10.0,
            exit_price=9.5,
            pnl=-500,
            entry_time=datetime(2025, 1, 1, 9, 30),
            exit_time=datetime(2025, 1, 1, 15, 0)
        )

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.total_trades == 1
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 1
        assert metrics.total_pnl == -500

    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        # Record 3 wins, 2 losses
        trades = [
            (10.5, 500),   # Win
            (9.5, -500),   # Loss
            (10.8, 800),   # Win
            (9.2, -800),   # Loss
            (11.0, 1000)   # Win
        ]

        for exit_price, pnl in trades:
            monitor.record_trade(
                strategy_name='test_strategy',
                symbol='000001.SZ',
                side='BUY',
                quantity=1000,
                entry_price=10.0,
                exit_price=exit_price,
                pnl=pnl,
                entry_time=datetime.now() - timedelta(hours=1),
                exit_time=datetime.now()
            )

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.total_trades == 5
        assert metrics.winning_trades == 3
        assert metrics.losing_trades == 2
        assert metrics.win_rate == 0.6

    def test_profit_factor_calculation(self):
        """Test profit factor calculation."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        # Total wins: 1500, Total losses: 1000
        trades = [
            (10.5, 500),
            (10.8, 800),
            (11.0, 200),
            (9.5, -400),
            (9.2, -600)
        ]

        for exit_price, pnl in trades:
            monitor.record_trade(
                strategy_name='test_strategy',
                symbol='000001.SZ',
                side='BUY',
                quantity=1000,
                entry_price=10.0,
                exit_price=exit_price,
                pnl=pnl,
                entry_time=datetime.now() - timedelta(hours=1),
                exit_time=datetime.now()
            )

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.profit_factor == pytest.approx(1.5, rel=0.01)

    def test_avg_win_loss_calculation(self):
        """Test average win/loss calculation."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        trades = [
            (10.5, 500),
            (10.8, 600),
            (9.5, -400),
            (9.2, -200)
        ]

        for exit_price, pnl in trades:
            monitor.record_trade(
                strategy_name='test_strategy',
                symbol='000001.SZ',
                side='BUY',
                quantity=1000,
                entry_price=10.0,
                exit_price=exit_price,
                pnl=pnl,
                entry_time=datetime.now() - timedelta(hours=1),
                exit_time=datetime.now()
            )

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.avg_win == pytest.approx(550, rel=0.01)  # (500+600)/2
        assert metrics.avg_loss == pytest.approx(300, rel=0.01)  # (400+200)/2

    def test_equity_curve_update(self):
        """Test equity curve update."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        # Update equity
        monitor.update_equity('test_strategy', 1000000)
        monitor.update_equity('test_strategy', 1050000)
        monitor.update_equity('test_strategy', 1030000)

        assert len(monitor.equity_curves['test_strategy']) == 3

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.total_return == pytest.approx(0.03, rel=0.01)  # 3% gain

    def test_daily_return_calculation(self):
        """Test daily return calculation."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        monitor.update_equity('test_strategy', 1000000)
        monitor.update_equity('test_strategy', 1020000)

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.daily_return == pytest.approx(0.02, rel=0.01)

    def test_volatility_calculation(self):
        """Test volatility calculation."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        # Add equity points with some volatility
        equities = [1000000, 1020000, 1010000, 1030000, 1015000]
        for equity in equities:
            monitor.update_equity('test_strategy', equity)

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.volatility > 0

    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        # Peak at 1100000, drop to 990000 = 10% drawdown
        equities = [1000000, 1100000, 1050000, 990000, 1020000]
        for equity in equities:
            monitor.update_equity('test_strategy', equity)

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.max_drawdown == pytest.approx(0.10, rel=0.01)

    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        # Steady growth
        equities = [1000000, 1010000, 1020000, 1030000, 1040000]
        for equity in equities:
            monitor.update_equity('test_strategy', equity)

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.sharpe_ratio > 0

    def test_health_score_high_performance(self):
        """Test health score for high-performance strategy."""
        monitor = StrategyMonitor(config={'min_trades_for_stats': 5})
        monitor.register_strategy('test_strategy')

        # High win rate (80%), good profit factor
        for i in range(10):
            pnl = 500 if i < 8 else -200
            exit_price = 10.5 if i < 8 else 9.8
            monitor.record_trade(
                strategy_name='test_strategy',
                symbol='000001.SZ',
                side='BUY',
                quantity=1000,
                entry_price=10.0,
                exit_price=exit_price,
                pnl=pnl,
                entry_time=datetime.now() - timedelta(hours=1),
                exit_time=datetime.now()
            )

        # Good equity curve (low drawdown)
        equities = [1000000, 1020000, 1040000, 1060000, 1080000]
        for equity in equities:
            monitor.update_equity('test_strategy', equity)

        health_score = monitor.calculate_health_score('test_strategy')
        assert health_score >= 80

    def test_health_score_low_performance(self):
        """Test health score for low-performance strategy."""
        monitor = StrategyMonitor(config={'min_trades_for_stats': 5})
        monitor.register_strategy('test_strategy')

        # Low win rate (30%)
        for i in range(10):
            pnl = 300 if i < 3 else -500
            exit_price = 10.3 if i < 3 else 9.5
            monitor.record_trade(
                strategy_name='test_strategy',
                symbol='000001.SZ',
                side='BUY',
                quantity=1000,
                entry_price=10.0,
                exit_price=exit_price,
                pnl=pnl,
                entry_time=datetime.now() - timedelta(hours=1),
                exit_time=datetime.now()
            )

        # Poor equity curve (high drawdown)
        equities = [1000000, 980000, 950000, 960000, 940000]
        for equity in equities:
            monitor.update_equity('test_strategy', equity)

        health_score = monitor.calculate_health_score('test_strategy')
        assert health_score < 50

    def test_health_score_insufficient_trades(self):
        """Test health score with insufficient trades."""
        monitor = StrategyMonitor(config={'min_trades_for_stats': 10})
        monitor.register_strategy('test_strategy')

        # Only 5 trades (< min_trades_for_stats)
        for i in range(5):
            monitor.record_trade(
                strategy_name='test_strategy',
                symbol='000001.SZ',
                side='BUY',
                quantity=1000,
                entry_price=10.0,
                exit_price=10.5,
                pnl=500,
                entry_time=datetime.now() - timedelta(hours=1),
                exit_time=datetime.now()
            )

        health_score = monitor.calculate_health_score('test_strategy')
        assert health_score == 50  # Neutral score

    def test_record_signal(self):
        """Test signal recording."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        monitor.record_signal(
            strategy_name='test_strategy',
            symbol='000001.SZ',
            signal_type='BUY',
            strength=0.8
        )

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.last_signal_time is not None

    def test_get_all_metrics(self):
        """Test getting all metrics."""
        monitor = StrategyMonitor()
        monitor.register_strategy('strategy1')
        monitor.register_strategy('strategy2')

        all_metrics = monitor.get_all_metrics()

        assert len(all_metrics) == 2
        assert 'strategy1' in all_metrics
        assert 'strategy2' in all_metrics

    def test_get_summary(self):
        """Test summary statistics."""
        monitor = StrategyMonitor()

        # Register and add trades to multiple strategies
        for strategy in ['strategy1', 'strategy2']:
            monitor.register_strategy(strategy)
            monitor.record_trade(
                strategy_name=strategy,
                symbol='000001.SZ',
                side='BUY',
                quantity=1000,
                entry_price=10.0,
                exit_price=10.5,
                pnl=500,
                entry_time=datetime.now() - timedelta(hours=1),
                exit_time=datetime.now()
            )

        summary = monitor.get_summary()

        assert summary['total_strategies'] == 2
        assert summary['total_trades'] == 2
        assert summary['total_pnl'] == 1000
        assert summary['active_strategies'] == 2

    def test_prometheus_metrics_export(self):
        """Test Prometheus metrics export."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        # Add some data
        monitor.record_trade(
            strategy_name='test_strategy',
            symbol='000001.SZ',
            side='BUY',
            quantity=1000,
            entry_price=10.0,
            exit_price=10.5,
            pnl=500,
            entry_time=datetime.now() - timedelta(hours=1),
            exit_time=datetime.now()
        )

        monitor.update_equity('test_strategy', 1050000)

        # Export metrics
        metrics_text = monitor.export_prometheus_metrics()

        assert 'strategy_test_strategy_total_return' in metrics_text
        assert 'strategy_test_strategy_sharpe_ratio' in metrics_text
        assert 'strategy_test_strategy_win_rate' in metrics_text
        assert 'strategy_test_strategy_health_score' in metrics_text
        assert 'strategy_test_strategy_total_trades' in metrics_text

    def test_performance_window_trimming(self):
        """Test that old equity data is trimmed."""
        monitor = StrategyMonitor(config={'performance_window': 1})  # 1 day
        monitor.register_strategy('test_strategy')

        # Add old equity point
        old_timestamp = datetime.now() - timedelta(days=2)
        monitor.equity_curves['test_strategy'].append({
            'timestamp': old_timestamp,
            'equity': 1000000
        })

        # Add recent equity point
        monitor.update_equity('test_strategy', 1050000)

        # Old data should be trimmed
        assert len(monitor.equity_curves['test_strategy']) == 1
        assert monitor.equity_curves['test_strategy'][0]['equity'] == 1050000

    def test_annualized_return_calculation(self):
        """Test annualized return calculation."""
        monitor = StrategyMonitor()
        monitor.register_strategy('test_strategy')

        # Add equity points spanning multiple days
        base_time = datetime.now() - timedelta(days=30)
        monitor.equity_curves['test_strategy'].append({
            'timestamp': base_time,
            'equity': 1000000
        })
        monitor.update_equity('test_strategy', 1100000)

        metrics = monitor.get_metrics('test_strategy')
        assert metrics.annualized_return > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])