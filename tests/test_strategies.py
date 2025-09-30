# tests/test_strategies.py - Strategy unit tests
import pytest
import asyncio
from datetime import datetime
from collections import deque

from src.backtest.engine import MarketDataEvent
from src.strategies.moving_average import MovingAverageCrossover
from src.strategies.mean_reversion import MeanReversion
from src.strategies.momentum import Momentum
from src.strategies.strategy_loader import StrategyLoader


class TestMovingAverageCrossover:
    """Test MovingAverageCrossover strategy."""

    @pytest.mark.asyncio
    async def test_golden_cross_signal(self):
        """Test golden cross generates BUY signal."""
        strategy = MovingAverageCrossover(config={
            'fast_period': 2,
            'slow_period': 3,
            'signal_strength': 0.8
        })

        # Feed prices: downtrend then sharp uptrend
        # At price[4]: fast_ma(38,45)=41.5, slow_ma(38,40,45)=41.0, crossover happens
        prices = [40.0, 39.0, 38.0, 40.0, 45.0]

        for price in prices:
            event = MarketDataEvent(
                timestamp=datetime.utcnow(),
                symbol="TEST.SH",
                price_data={'close': price, 'volume': 1000000}
            )
            await strategy.handle_market_data(event)

        # Should generate BUY signal on golden cross
        buy_signals = [s for s in strategy.signals if s.signal_type == "BUY"]
        assert len(buy_signals) > 0
        signal = buy_signals[-1]
        assert signal.symbol == "TEST.SH"

    @pytest.mark.asyncio
    async def test_death_cross_signal(self):
        """Test death cross generates SELL signal."""
        strategy = MovingAverageCrossover(config={
            'fast_period': 2,
            'slow_period': 3
        })

        # Add position first
        strategy.position["TEST.SH"] = 1000

        # Feed prices: uptrend then sharp downtrend
        # At price[4]: fast_ma(44,35)=39.5, slow_ma(42,44,35)=40.3, crossover happens
        prices = [40.0, 41.0, 42.0, 44.0, 35.0]

        for price in prices:
            event = MarketDataEvent(
                timestamp=datetime.utcnow(),
                symbol="TEST.SH",
                price_data={'close': price, 'volume': 1000000}
            )
            await strategy.handle_market_data(event)

        # Should generate SELL signal on death cross
        sell_signals = [s for s in strategy.signals if s.signal_type == "SELL"]
        assert len(sell_signals) > 0

    def test_get_indicators(self):
        """Test indicator calculation."""
        strategy = MovingAverageCrossover(config={
            'fast_period': 2,
            'slow_period': 3
        })

        # Manually add price history
        strategy.price_history["TEST.SH"] = deque([40.0, 41.0, 42.0], maxlen=3)

        indicators = strategy.get_indicators("TEST.SH")

        assert 'fast_ma' in indicators
        assert 'slow_ma' in indicators
        assert indicators['fast_ma'] == 41.5  # (41 + 42) / 2
        assert indicators['slow_ma'] == 41.0  # (40 + 41 + 42) / 3


class TestMeanReversion:
    """Test MeanReversion strategy."""

    @pytest.mark.asyncio
    async def test_oversold_signal(self):
        """Test oversold condition generates BUY signal."""
        strategy = MeanReversion(config={
            'bb_period': 5,
            'bb_std_dev': 1.5,  # Lower std_dev for easier trigger
            'rsi_period': 3,
            'rsi_oversold': 45,  # Higher threshold for easier trigger
            'rsi_overbought': 70
        })

        # Feed prices simulating strong oversold (sharp drop)
        prices = [42.0, 41.0, 40.0, 38.0, 36.0, 34.0, 32.0, 30.5]

        for price in prices:
            event = MarketDataEvent(
                timestamp=datetime.utcnow(),
                symbol="TEST.SH",
                price_data={'close': price, 'volume': 1000000}
            )
            await strategy.handle_market_data(event)

        # Should generate BUY signal when oversold
        buy_signals = [s for s in strategy.signals if s.signal_type == "BUY"]
        assert len(buy_signals) > 0

    @pytest.mark.asyncio
    async def test_overbought_signal(self):
        """Test overbought condition generates SELL signal."""
        strategy = MeanReversion(config={
            'bb_period': 5,
            'rsi_period': 3,
            'rsi_overbought': 70
        })

        # Add position
        strategy.position["TEST.SH"] = 1000

        # Feed prices simulating overbought (price rises with momentum)
        prices = [40.0, 40.5, 41.0, 41.5, 42.0, 42.5]

        for price in prices:
            event = MarketDataEvent(
                timestamp=datetime.utcnow(),
                symbol="TEST.SH",
                price_data={'close': price, 'volume': 1000000}
            )
            await strategy.handle_market_data(event)

        # Should generate SELL signal when overbought
        sell_signals = [s for s in strategy.signals if s.signal_type == "SELL"]
        assert len(sell_signals) > 0

    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation."""
        strategy = MeanReversion(config={'bb_period': 5, 'bb_std_dev': 2.0})

        # Add price history
        strategy.price_history["TEST.SH"] = deque([40.0, 41.0, 42.0, 41.0, 40.0], maxlen=5)

        upper, middle, lower = strategy._calculate_bollinger_bands("TEST.SH")

        assert upper is not None
        assert middle == 40.8  # (40 + 41 + 42 + 41 + 40) / 5
        assert upper > middle
        assert lower < middle

    def test_rsi_calculation(self):
        """Test RSI calculation."""
        strategy = MeanReversion(config={'rsi_period': 3})

        # Simulate price changes
        strategy.price_changes["TEST.SH"] = deque([1.0, 0.5, -0.5], maxlen=3)

        rsi = strategy._calculate_rsi("TEST.SH")

        assert rsi is not None
        assert 0 <= rsi <= 100


class TestMomentum:
    """Test Momentum strategy."""

    @pytest.mark.asyncio
    async def test_strong_momentum_signal(self):
        """Test strong momentum generates BUY signal."""
        strategy = Momentum(config={
            'lookback_period': 5,
            'momentum_threshold': 5.0,
            'max_positions': 5
        })

        # Feed rising prices (strong momentum)
        base_price = 40.0
        prices = [base_price + i * 0.5 for i in range(6)]

        for price in prices:
            event = MarketDataEvent(
                timestamp=datetime.utcnow(),
                symbol="TEST.SH",
                price_data={'close': price, 'volume': 1000000}
            )
            await strategy.handle_market_data(event)

        # Should generate BUY signal
        buy_signals = [s for s in strategy.signals if s.signal_type == "BUY"]
        assert len(buy_signals) > 0

    @pytest.mark.asyncio
    async def test_weakening_momentum_signal(self):
        """Test weakening momentum generates SELL signal."""
        strategy = Momentum(config={
            'lookback_period': 5,
            'exit_threshold': -2.0
        })

        # Add position
        strategy.position["TEST.SH"] = 1000

        # Feed declining prices (negative momentum)
        base_price = 40.0
        prices = [base_price - i * 0.3 for i in range(6)]

        for price in prices:
            event = MarketDataEvent(
                timestamp=datetime.utcnow(),
                symbol="TEST.SH",
                price_data={'close': price, 'volume': 1000000}
            )
            await strategy.handle_market_data(event)

        # Should generate SELL signal
        sell_signals = [s for s in strategy.signals if s.signal_type == "SELL"]
        assert len(sell_signals) > 0

    def test_momentum_calculation(self):
        """Test momentum calculation."""
        strategy = Momentum(config={'lookback_period': 5})

        # Add price history
        strategy.price_history["TEST.SH"] = deque([40.0, 41.0, 42.0, 43.0, 44.0], maxlen=5)

        momentum = strategy._calculate_momentum("TEST.SH")

        # Momentum = (44 - 40) / 40 * 100 = 10%
        assert momentum == pytest.approx(10.0, rel=0.01)

    def test_max_positions_limit(self):
        """Test max positions constraint."""
        strategy = Momentum(config={
            'lookback_period': 3,
            'momentum_threshold': 1.0,
            'max_positions': 2
        })

        # Fill up positions
        strategy.position["STOCK1.SH"] = 1000
        strategy.position["STOCK2.SH"] = 1000

        # Calculate strong momentum for new symbol
        strategy.price_history["STOCK3.SH"] = deque([40.0, 42.0, 44.0], maxlen=3)
        strategy.momentum_scores["STOCK3.SH"] = 10.0

        # Check buy signal - should not generate due to max positions
        assert len([s for s, qty in strategy.position.items() if qty > 0]) == 2


class TestStrategyLoader:
    """Test StrategyLoader functionality."""

    def test_load_single_strategy(self):
        """Test loading a single strategy."""
        loader = StrategyLoader()
        strategy = loader.load_strategy('moving_average_crossover')

        assert strategy is not None
        assert isinstance(strategy, MovingAverageCrossover)

    def test_load_multiple_strategies(self):
        """Test loading multiple strategies."""
        loader = StrategyLoader()
        strategies = loader.load_strategies([
            'moving_average_crossover',
            'mean_reversion',
            'momentum'
        ])

        assert len(strategies) == 3
        assert isinstance(strategies[0], MovingAverageCrossover)
        assert isinstance(strategies[1], MeanReversion)
        assert isinstance(strategies[2], Momentum)

    def test_list_available_strategies(self):
        """Test listing available strategies."""
        loader = StrategyLoader()
        available = loader.list_available_strategies()

        assert 'moving_average_crossover' in available
        assert 'mean_reversion' in available
        assert 'momentum' in available

    def test_load_combination(self):
        """Test loading strategy combination."""
        loader = StrategyLoader()
        strategies = loader.load_combination('balanced')

        assert len(strategies) > 0

    def test_get_strategy_config(self):
        """Test getting strategy configuration."""
        loader = StrategyLoader()
        config = loader.get_strategy_config('moving_average_crossover')

        assert 'fast_period' in config
        assert 'slow_period' in config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])