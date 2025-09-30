# src/trading/__init__.py - Live trading module
"""
Live trading infrastructure for real-time strategy execution.

Components:
- broker_adapter: Abstract interface for broker integration
- broker_gateway: Mock/real broker implementations
- live_engine: Real-time strategy execution engine
- signal_executor: Convert signals to orders
- order_manager: Order lifecycle management
"""

from src.trading.broker_adapter import BrokerAdapter, OrderRejectedException, BrokerConnectionError
from src.trading.broker_gateway import MockBrokerGateway
from src.trading.live_engine import LiveTradingEngine, LiveEngineConfig
from src.trading.signal_executor import SignalExecutor
from src.trading.order_manager import OrderManager, OrderState

__all__ = [
    'BrokerAdapter',
    'OrderRejectedException',
    'BrokerConnectionError',
    'MockBrokerGateway',
    'LiveTradingEngine',
    'LiveEngineConfig',
    'SignalExecutor',
    'OrderManager',
    'OrderState',
]