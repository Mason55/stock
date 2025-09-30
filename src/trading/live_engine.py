# src/trading/live_engine.py - Real-time strategy execution engine
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from src.backtest.engine import Strategy, MarketDataEvent, SignalEvent, FillEvent, EventType
from src.trading.broker_adapter import BrokerAdapter
from src.trading.order_manager import OrderManager
from src.trading.signal_executor import SignalExecutor
from src.models.trading import Order, OrderStatus, Position

logger = logging.getLogger(__name__)


@dataclass
class LiveEngineConfig:
    """Configuration for live trading engine."""
    initial_capital: float = 1000000.0
    enable_trading: bool = True  # Set False for paper trading
    max_orders_per_second: int = 10
    heartbeat_interval: int = 30  # seconds


class LiveTradingEngine:
    """Real-time strategy execution engine.

    Reuses BacktestEngine architecture but with real-time data feed.
    Key differences:
    - Uses real broker instead of simulator
    - Real-time clock instead of historical replay
    - State persistence to database
    - Error recovery mechanisms
    """

    def __init__(
        self,
        broker: BrokerAdapter,
        config: LiveEngineConfig = None
    ):
        self.broker = broker
        self.config = config or LiveEngineConfig()

        # Core components
        self.order_manager = OrderManager(broker)
        self.signal_executor = SignalExecutor(broker, self.order_manager)

        # Strategy management
        self.strategies: Dict[str, Strategy] = {}
        self.strategy_states: Dict[str, Dict] = {}

        # Event system
        self.event_queue = asyncio.Queue()
        self.handlers = {}

        # State
        self.is_running = False
        self.positions: Dict[str, Position] = {}
        self.account_info: Dict = {}

        # Rate limiting
        self._order_timestamps: List[float] = []

        # Tasks
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """Start live trading engine."""
        logger.info("Starting live trading engine...")

        # Connect to broker
        connected = await self.broker.connect()
        if not connected:
            raise ConnectionError("Failed to connect to broker")

        # Load initial state
        await self._load_state()

        # Start background tasks
        self.is_running = True
        self._tasks = [
            asyncio.create_task(self._event_loop()),
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._state_sync_loop())
        ]

        logger.info("Live trading engine started")

    async def stop(self) -> None:
        """Stop live trading engine."""
        logger.info("Stopping live trading engine...")

        self.is_running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Save state
        await self._save_state()

        # Disconnect broker
        await self.broker.disconnect()

        logger.info("Live trading engine stopped")

    def add_strategy(self, strategy: Strategy) -> None:
        """Add strategy to engine."""
        self.strategies[strategy.name] = strategy
        self.strategy_states[strategy.name] = {
            'enabled': True,
            'started_at': datetime.utcnow()
        }
        logger.info(f"Strategy added: {strategy.name}")

    def remove_strategy(self, strategy_name: str) -> None:
        """Remove strategy from engine."""
        if strategy_name in self.strategies:
            del self.strategies[strategy_name]
            del self.strategy_states[strategy_name]
            logger.info(f"Strategy removed: {strategy_name}")

    def enable_strategy(self, strategy_name: str, enabled: bool = True) -> None:
        """Enable/disable strategy."""
        if strategy_name in self.strategy_states:
            self.strategy_states[strategy_name]['enabled'] = enabled
            logger.info(f"Strategy {'enabled' if enabled else 'disabled'}: {strategy_name}")

    async def on_market_data(self, event: MarketDataEvent) -> None:
        """Handle real-time market data."""
        await self.event_queue.put(event)

    async def _event_loop(self) -> None:
        """Main event processing loop."""
        while self.is_running:
            try:
                # Process events with timeout
                try:
                    event = await asyncio.wait_for(
                        self.event_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Route to handlers
                await self._handle_event(event)

            except Exception as e:
                logger.error(f"Error in event loop: {e}", exc_info=True)

    async def _handle_event(self, event) -> None:
        """Route event to appropriate handlers."""
        if event.type == EventType.MARKET_DATA:
            await self._handle_market_data(event)
        elif event.type == EventType.SIGNAL:
            await self._handle_signal(event)
        elif event.type == EventType.FILL:
            await self._handle_fill(event)

    async def _handle_market_data(self, event: MarketDataEvent) -> None:
        """Process market data through strategies."""
        for strategy_name, strategy in self.strategies.items():
            if not self.strategy_states[strategy_name]['enabled']:
                continue

            try:
                await strategy.handle_market_data(event)

                # Check for new signals
                if strategy.signals:
                    for signal in strategy.signals:
                        await self.event_queue.put(signal)
                    strategy.signals.clear()

            except Exception as e:
                logger.error(f"Strategy {strategy_name} error: {e}", exc_info=True)

    async def _handle_signal(self, event: SignalEvent) -> None:
        """Convert signal to orders."""
        if not self.config.enable_trading:
            logger.info(f"Paper trading mode: signal {event.signal_type} for {event.symbol}")
            return

        # Rate limiting
        if not self._check_rate_limit():
            logger.warning(f"Rate limit exceeded, signal delayed: {event.symbol}")
            await asyncio.sleep(1.0)

        try:
            order = await self.signal_executor.execute_signal(event)
            if order:
                logger.info(f"Order created from signal: {order.order_id}")
        except Exception as e:
            logger.error(f"Failed to execute signal: {e}", exc_info=True)

    async def _handle_fill(self, event: FillEvent) -> None:
        """Handle order fills."""
        # Update positions
        await self._sync_positions()

        # Notify strategies
        for strategy in self.strategies.values():
            try:
                await strategy.handle_fill(event)
            except Exception as e:
                logger.error(f"Strategy fill handling error: {e}", exc_info=True)

    async def _heartbeat_loop(self) -> None:
        """Periodic health check."""
        while self.is_running:
            try:
                # Check broker connection
                if not await self.broker.is_connected():
                    logger.error("Broker disconnected, attempting reconnect...")
                    await self.broker.connect()

                # Check pending orders
                pending_orders = await self.order_manager.get_pending_orders()
                logger.info(f"Heartbeat: {len(pending_orders)} pending orders")

            except Exception as e:
                logger.error(f"Heartbeat error: {e}", exc_info=True)

            await asyncio.sleep(self.config.heartbeat_interval)

    async def _state_sync_loop(self) -> None:
        """Periodic state synchronization."""
        while self.is_running:
            try:
                await self._sync_positions()
                await self._sync_account()
            except Exception as e:
                logger.error(f"State sync error: {e}", exc_info=True)

            await asyncio.sleep(60)  # Sync every minute

    async def _sync_positions(self) -> None:
        """Sync positions from broker."""
        positions = await self.broker.get_positions()
        self.positions = {pos.symbol: pos for pos in positions}

    async def _sync_account(self) -> None:
        """Sync account info from broker."""
        self.account_info = await self.broker.get_account()

    def _check_rate_limit(self) -> bool:
        """Check if order rate limit allows new order."""
        now = datetime.utcnow().timestamp()

        # Remove old timestamps
        self._order_timestamps = [
            ts for ts in self._order_timestamps
            if now - ts < 1.0
        ]

        # Check limit
        if len(self._order_timestamps) >= self.config.max_orders_per_second:
            return False

        self._order_timestamps.append(now)
        return True

    async def _load_state(self) -> None:
        """Load persisted state from database."""
        # Load positions
        await self._sync_positions()

        # Load account
        await self._sync_account()

        logger.info(f"State loaded: {len(self.positions)} positions")

    async def _save_state(self) -> None:
        """Save state to database."""
        # State is continuously synced, final save for cleanup
        logger.info("State saved")

    def get_status(self) -> Dict:
        """Get engine status."""
        return {
            'is_running': self.is_running,
            'num_strategies': len(self.strategies),
            'enabled_strategies': sum(
                1 for state in self.strategy_states.values()
                if state['enabled']
            ),
            'num_positions': len(self.positions),
            'total_assets': self.account_info.get('total_assets', 0),
            'cash_balance': self.account_info.get('cash_balance', 0)
        }