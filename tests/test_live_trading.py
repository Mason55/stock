# tests/test_live_trading.py - Integration tests for live trading system
import pytest
import asyncio
from datetime import datetime
from decimal import Decimal

from src.trading.broker_adapter import BrokerAdapter
from src.trading.broker_gateway import MockBrokerGateway
from src.trading.live_engine import LiveTradingEngine, LiveEngineConfig
from src.trading.order_manager import OrderManager
from src.trading.signal_executor import SignalExecutor
from src.backtest.engine import Strategy, MarketDataEvent, SignalEvent
from src.models.trading import Order, OrderType, OrderSide, OrderStatus


class SimpleTestStrategy(Strategy):
    """Simple test strategy for integration testing."""

    def __init__(self):
        super().__init__("simple_test_strategy")
        self.signal_count = 0

    async def handle_market_data(self, event: MarketDataEvent):
        """Generate buy signal on first tick."""
        if self.signal_count == 0:
            self.generate_signal(event.symbol, "BUY", strength=0.5)
            self.signal_count += 1


class TestMockBrokerGateway:
    """Test MockBrokerGateway functionality."""

    @pytest.mark.asyncio
    async def test_connection(self):
        """Test broker connection."""
        broker = MockBrokerGateway()

        # Connect
        connected = await broker.connect()
        assert connected is True
        assert await broker.is_connected() is True

        # Disconnect
        await broker.disconnect()
        assert await broker.is_connected() is False

    @pytest.mark.asyncio
    async def test_place_order(self):
        """Test order placement."""
        broker = MockBrokerGateway(initial_cash=1000000)
        await broker.connect()

        # Update market price
        broker.update_market_price("600036.SH", 40.0)

        # Create order
        order = Order(
            order_id="TEST_001",
            account_id="TEST",
            symbol="600036.SH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )

        # Place order
        broker_order_id = await broker.place_order(order)
        assert broker_order_id is not None
        assert broker_order_id.startswith("MOCK_")

        # Wait for fill
        await asyncio.sleep(0.2)

        # Check order status
        status = await broker.get_order_status(broker_order_id)
        assert status['status'] == 'filled'
        assert status['filled_quantity'] == 1000

    @pytest.mark.asyncio
    async def test_position_tracking(self):
        """Test position tracking after order fill."""
        broker = MockBrokerGateway(initial_cash=1000000)
        await broker.connect()
        broker.update_market_price("600036.SH", 40.0)

        # Place buy order
        order = Order(
            order_id="TEST_BUY_001",
            account_id="TEST",
            symbol="600036.SH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )

        await broker.place_order(order)
        await asyncio.sleep(0.2)

        # Check positions
        positions = await broker.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "600036.SH"
        assert positions[0].quantity == 1000

        # Check account
        account = await broker.get_account()
        assert account['cash_balance'] < 1000000  # Cash reduced
        assert account['stock_value'] > 0

    @pytest.mark.asyncio
    async def test_order_cancellation(self):
        """Test order cancellation."""
        broker = MockBrokerGateway(
            initial_cash=1000000,
            config={'fill_delay': 1.0}  # Slow fill for testing
        )
        await broker.connect()
        broker.update_market_price("600036.SH", 40.0)

        # Place order
        order = Order(
            order_id="TEST_CANCEL_001",
            account_id="TEST",
            symbol="600036.SH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )

        broker_order_id = await broker.place_order(order)

        # Cancel before fill
        await asyncio.sleep(0.1)
        success = await broker.cancel_order(broker_order_id)
        assert success is True

        # Check status
        status = await broker.get_order_status(broker_order_id)
        assert status['status'] == 'canceled'


class TestOrderManager:
    """Test OrderManager functionality."""

    @pytest.mark.asyncio
    async def test_order_validation(self):
        """Test order validation."""
        broker = MockBrokerGateway()
        await broker.connect()

        order_manager = OrderManager(broker, enable_persistence=False)

        # Valid order
        valid_order = Order(
            order_id="VALID_001",
            account_id="TEST",
            symbol="600036.SH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,  # Multiple of 100
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )

        # Should not raise
        order_manager._validate_order(valid_order)

        # Invalid quantity (not multiple of 100)
        invalid_order = Order(
            order_id="INVALID_001",
            account_id="TEST",
            symbol="600036.SH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=150,  # Invalid
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )

        with pytest.raises(ValueError, match="multiple of 100"):
            order_manager._validate_order(invalid_order)

    @pytest.mark.asyncio
    async def test_order_submission(self):
        """Test order submission workflow."""
        broker = MockBrokerGateway()
        await broker.connect()
        broker.update_market_price("600036.SH", 40.0)

        order_manager = OrderManager(broker, enable_persistence=False)

        order = Order(
            order_id="SUBMIT_001",
            account_id="TEST",
            symbol="600036.SH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )

        # Submit order
        broker_order_id = await order_manager.submit_order(order)
        assert broker_order_id is not None

        # Check order stored
        stored_order = await order_manager.get_order(order.order_id)
        assert stored_order is not None
        assert stored_order.status == OrderStatus.NEW


class TestSignalExecutor:
    """Test SignalExecutor functionality."""

    @pytest.mark.asyncio
    async def test_buy_signal_execution(self):
        """Test buy signal execution."""
        broker = MockBrokerGateway(initial_cash=1000000)
        await broker.connect()
        broker.update_market_price("600036.SH", 40.0)

        order_manager = OrderManager(broker, enable_persistence=False)
        executor = SignalExecutor(broker, order_manager)

        # Create buy signal
        signal = SignalEvent(
            timestamp=datetime.utcnow(),
            symbol="600036.SH",
            signal_type="BUY",
            strength=0.5,
            metadata={}
        )

        # Execute signal
        order = await executor.execute_signal(signal)

        assert order is not None
        assert order.side == OrderSide.BUY
        assert order.quantity == 1200  # 1M cash * 10% * 0.5 / ¥40 -> 1200 shares

    @pytest.mark.asyncio
    async def test_sell_signal_execution(self):
        """Test sell signal execution."""
        broker = MockBrokerGateway(initial_cash=1000000)
        await broker.connect()
        broker.update_market_price("600036.SH", 40.0)

        # First create a position
        buy_order = Order(
            order_id="BUY_BEFORE_SELL",
            account_id="TEST",
            symbol="600036.SH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        await broker.place_order(buy_order)
        await asyncio.sleep(0.2)

        # Now test sell
        order_manager = OrderManager(broker, enable_persistence=False)
        executor = SignalExecutor(broker, order_manager)

        signal = SignalEvent(
            timestamp=datetime.utcnow(),
            symbol="600036.SH",
            signal_type="SELL",
            strength=0.8,  # Sell 80%
            metadata={}
        )

        order = await executor.execute_signal(signal)

        assert order is not None
        assert order.side == OrderSide.SELL
        assert order.quantity == 800  # 80% of 1000 shares rounded to board lot


class TestLiveTradingEngine:
    """Test LiveTradingEngine integration."""

    @pytest.mark.asyncio
    async def test_engine_start_stop(self):
        """Test engine lifecycle."""
        broker = MockBrokerGateway()
        config = LiveEngineConfig(enable_trading=False)  # Paper trading
        engine = LiveTradingEngine(
            broker,
            config,
            order_manager=OrderManager(broker, enable_persistence=False),
        )

        # Start engine
        await engine.start()
        assert engine.is_running is True
        assert await broker.is_connected() is True

        # Stop engine
        await engine.stop()
        assert engine.is_running is False

    @pytest.mark.asyncio
    async def test_strategy_execution(self):
        """Test strategy execution in engine."""
        broker = MockBrokerGateway(initial_cash=1000000)
        broker.update_market_price("600036.SH", 40.0)

        config = LiveEngineConfig(enable_trading=True)
        engine = LiveTradingEngine(
            broker,
            config,
            order_manager=OrderManager(broker, enable_persistence=False),
        )

        # Add strategy
        strategy = SimpleTestStrategy()
        engine.add_strategy(strategy)

        # Start engine
        await engine.start()

        # Send market data
        market_event = MarketDataEvent(
            timestamp=datetime.utcnow(),
            symbol="600036.SH",
            price_data={'close': 40.0, 'volume': 1000000}
        )

        await engine.on_market_data(market_event)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Check signal was generated
        assert strategy.signal_count == 1

        # Stop engine
        await engine.stop()

    @pytest.mark.asyncio
    async def test_engine_status(self):
        """Test engine status reporting."""
        broker = MockBrokerGateway()
        engine = LiveTradingEngine(
            broker,
            order_manager=OrderManager(broker, enable_persistence=False),
        )

        await engine.start()

        # Add strategy
        strategy = SimpleTestStrategy()
        engine.add_strategy(strategy)

        status = engine.get_status()
        assert status['is_running'] is True
        assert status['num_strategies'] == 1
        assert status['enabled_strategies'] == 1

        await engine.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
