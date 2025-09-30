# tests/test_risk_management.py - Risk management tests
import pytest
from datetime import datetime, timedelta

from src.risk.real_time_monitor import RealTimeRiskMonitor
from src.risk.position_sizer import PositionSizer, PositionSizeMethod
from src.risk.position_monitor import PositionMonitor
from src.risk.risk_config_loader import RiskConfigLoader


class TestRealTimeRiskMonitor:
    """Test RealTimeRiskMonitor functionality."""

    def test_initialization(self):
        """Test monitor initialization."""
        monitor = RealTimeRiskMonitor(config={
            'max_daily_loss_pct': 3.0,
            'max_drawdown_pct': 10.0
        })

        assert monitor.max_daily_loss_pct == 3.0
        assert monitor.max_drawdown_pct == 10.0
        assert monitor.is_trading_halted is False

    def test_daily_loss_warning(self):
        """Test daily loss warning."""
        monitor = RealTimeRiskMonitor(config={'max_daily_loss_pct': 3.0})
        monitor.initialize(1000000)

        # Simulate 2.5% loss (should warn but not halt)
        monitor.update(975000)  # -2.5%

        status = monitor.update(975000)
        assert status['is_halted'] is False
        assert len(status['violations']) > 0
        assert status['violations'][0]['level'] == 'warning'

    def test_daily_loss_circuit_breaker(self):
        """Test daily loss circuit breaker."""
        monitor = RealTimeRiskMonitor(config={'max_daily_loss_pct': 3.0})
        monitor.initialize(1000000)

        # Simulate 4% loss (should halt)
        status = monitor.update(960000)  # -4%

        assert status['is_halted'] is True
        assert len(status['violations']) > 0
        assert status['violations'][0]['level'] == 'circuit_breaker'

    def test_drawdown_monitoring(self):
        """Test drawdown monitoring."""
        monitor = RealTimeRiskMonitor(config={'max_drawdown_pct': 10.0})
        monitor.initialize(1000000)

        # Simulate profit then drawdown
        monitor.update(1100000)  # +10%
        monitor.update(980000)   # -11% from peak

        status = monitor.update(980000)

        assert status['is_halted'] is True
        drawdown_violation = [v for v in status['violations'] if v['rule'] == 'max_drawdown'][0]
        assert drawdown_violation['level'] == 'circuit_breaker'

    def test_position_concentration(self):
        """Test position concentration check."""
        monitor = RealTimeRiskMonitor(config={'max_position_pct': 15.0})
        monitor.initialize(1000000)

        # Simulate concentrated position (20%)
        positions = {
            'STOCK1': {'quantity': 5000, 'value': 200000},  # 20%
            'STOCK2': {'quantity': 2000, 'value': 100000}   # 10%
        }

        status = monitor.update(1000000, positions)

        violations = [v for v in status['violations'] if v['rule'] == 'position_concentration']
        assert len(violations) > 0

    def test_metrics_tracking(self):
        """Test metrics calculation."""
        monitor = RealTimeRiskMonitor()
        monitor.initialize(1000000)

        monitor.update(1050000)  # +5%

        metrics = monitor.get_metrics()

        assert metrics['current_capital'] == 1050000
        assert metrics['daily_pnl'] == 50000
        assert metrics['total_return_pct'] == 5.0

    def test_resume_trading(self):
        """Test manual trading resume."""
        monitor = RealTimeRiskMonitor(config={'max_daily_loss_pct': 3.0})
        monitor.initialize(1000000)

        # Trigger halt
        monitor.update(960000)
        assert monitor.is_trading_halted is True

        # Resume
        monitor.resume_trading()
        assert monitor.is_trading_halted is False


class TestPositionSizer:
    """Test PositionSizer functionality."""

    def test_fixed_ratio(self):
        """Test fixed ratio sizing."""
        sizer = PositionSizer(config={
            'method': 'fixed_ratio',
            'default_ratio': 0.10
        })

        shares = sizer.calculate(
            available_capital=100000,
            current_price=40.0,
            method=PositionSizeMethod.FIXED_RATIO
        )

        # 100000 * 0.10 / 40 = 250 shares -> rounded to 200 (lot size)
        assert shares == 200

    def test_kelly_criterion(self):
        """Test Kelly criterion sizing."""
        sizer = PositionSizer(config={
            'method': 'kelly',
            'kelly_fraction': 0.5
        })

        shares = sizer.calculate(
            available_capital=100000,
            current_price=40.0,
            method=PositionSizeMethod.KELLY,
            win_rate=0.6,
            avg_win=500,
            avg_loss=300
        )

        # Kelly formula: f = (0.6 * 500/300 - 0.4) / (500/300) = 0.36
        # Half-Kelly: 0.36 * 0.5 = 0.18
        # Position: 100000 * 0.18 / 40 = 450 -> 400 shares
        assert shares > 0
        assert shares % 100 == 0  # Multiple of 100

    def test_volatility_adjusted(self):
        """Test volatility-adjusted sizing."""
        sizer = PositionSizer(config={'method': 'volatility_adjusted'})

        # High volatility -> smaller position
        shares_high_vol = sizer.calculate(
            available_capital=100000,
            current_price=40.0,
            method=PositionSizeMethod.VOLATILITY_ADJUSTED,
            atr=4.0,  # High volatility
            risk_per_trade=0.01
        )

        # Low volatility -> larger position
        shares_low_vol = sizer.calculate(
            available_capital=100000,
            current_price=40.0,
            method=PositionSizeMethod.VOLATILITY_ADJUSTED,
            atr=1.0,  # Low volatility
            risk_per_trade=0.01
        )

        assert shares_low_vol > shares_high_vol

    def test_equal_weight(self):
        """Test equal weight sizing."""
        sizer = PositionSizer(config={'method': 'equal_weight'})

        shares = sizer.calculate(
            available_capital=100000,
            current_price=40.0,
            method=PositionSizeMethod.EQUAL_WEIGHT,
            num_positions=5
        )

        # 100000 / 5 / 40 = 500 shares
        assert shares == 500

    def test_position_limits(self):
        """Test position size limits."""
        sizer = PositionSizer(config={
            'max_position_size': 0.20,
            'min_position_size': 0.05
        })

        # Test max limit
        shares = sizer.calculate(
            available_capital=100000,
            current_price=10.0,
            method=PositionSizeMethod.FIXED_RATIO,
            ratio=0.50  # Try to use 50%
        )

        # Should be capped at 20%: 100000 * 0.20 / 10 = 2000
        assert shares == 2000

    def test_batch_calculation(self):
        """Test batch position sizing."""
        sizer = PositionSizer(config={'method': 'fixed_ratio', 'default_ratio': 0.10})

        symbols = {
            'STOCK1': {'price': 40.0},
            'STOCK2': {'price': 50.0},
            'STOCK3': {'price': 30.0}
        }

        position_sizes = sizer.calculate_batch(100000, symbols)

        assert len(position_sizes) == 3
        assert all(shares > 0 for shares in position_sizes.values())

    def test_kelly_parameter_calculation(self):
        """Test Kelly parameter calculation from trade history."""
        sizer = PositionSizer()

        trades = [
            {'pnl': 500},
            {'pnl': -300},
            {'pnl': 400},
            {'pnl': -200},
            {'pnl': 600},
            {'pnl': -250}
        ]

        params = sizer.calculate_kelly_parameters(trades)

        assert 'win_rate' in params
        assert 'avg_win' in params
        assert 'avg_loss' in params
        assert params['win_rate'] == 0.5  # 3 wins, 3 losses


class TestPositionMonitor:
    """Test PositionMonitor functionality."""

    def test_position_update(self):
        """Test position update."""
        monitor = PositionMonitor()

        monitor.update(
            symbol='STOCK1',
            quantity=1000,
            avg_cost=40.0,
            current_price=45.0
        )

        pos = monitor.get_position('STOCK1')

        assert pos['quantity'] == 1000
        assert pos['avg_cost'] == 40.0
        assert pos['market_value'] == 45000
        assert pos['unrealized_pnl'] == 5000  # (45-40) * 1000

    def test_pnl_calculation(self):
        """Test P&L calculation."""
        monitor = PositionMonitor()

        monitor.update('STOCK1', 1000, 40.0, 45.0)
        monitor.update('STOCK2', 500, 50.0, 48.0)

        pnl = monitor.get_total_pnl()

        assert pnl['unrealized_pnl'] == 4000  # 5000 - 1000
        assert pnl['total_cost'] == 65000

    def test_rebalance_detection(self):
        """Test rebalance detection."""
        monitor = PositionMonitor(config={
            'rebalance_threshold': 0.05,
            'rebalance_interval': 0  # No delay for test
        })

        # Set target weights
        monitor.set_target_weights({
            'STOCK1': 0.5,
            'STOCK2': 0.5
        })

        # Create imbalanced portfolio (70/30)
        monitor.update('STOCK1', 1750, 40.0, 40.0)  # 70000
        monitor.update('STOCK2', 750, 40.0, 40.0)   # 30000

        result = monitor.check_rebalance_needed()

        assert result['needed'] is True
        assert 'recommendations' in result

    def test_large_loss_alert(self):
        """Test large loss alerting."""
        monitor = PositionMonitor(config={
            'alert_on_large_loss': True,
            'large_loss_threshold': 0.05
        })

        # Create position with >5% loss
        monitor.update('STOCK1', 1000, 40.0, 37.0)  # -7.5% loss

        # Should log warning (check logs)
        pos = monitor.get_position('STOCK1')
        assert pos['unrealized_pnl'] < 0

    def test_performance_metrics(self):
        """Test performance metrics calculation."""
        monitor = PositionMonitor()

        monitor.update('STOCK1', 1000, 40.0, 45.0)  # Win
        monitor.update('STOCK2', 500, 50.0, 48.0)   # Loss

        metrics = monitor.get_performance_metrics()

        assert metrics['total_positions'] == 2
        assert metrics['winning_positions'] == 1
        assert metrics['losing_positions'] == 1
        assert metrics['win_rate'] == 0.5


class TestRiskConfigLoader:
    """Test RiskConfigLoader functionality."""

    def test_load_default_config(self):
        """Test loading default configuration."""
        loader = RiskConfigLoader()

        risk_config = loader.get_risk_monitor_config()
        sizer_config = loader.get_position_sizer_config()

        assert 'max_daily_loss_pct' in risk_config
        assert 'method' in sizer_config

    def test_load_profile(self):
        """Test loading risk profile."""
        loader = RiskConfigLoader()

        conservative = loader.get_risk_monitor_config('conservative')
        aggressive = loader.get_risk_monitor_config('aggressive')

        # Conservative should have tighter limits
        assert conservative['max_daily_loss_pct'] < aggressive['max_daily_loss_pct']

    def test_list_profiles(self):
        """Test listing available profiles."""
        loader = RiskConfigLoader()

        profiles = loader.list_profiles()

        assert 'conservative' in profiles
        assert 'moderate' in profiles
        assert 'aggressive' in profiles


if __name__ == "__main__":
    pytest.main([__file__, "-v"])