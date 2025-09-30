# src/trading/broker_gateway.py - Mock broker implementation for testing
import asyncio
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
import random

from src.models.trading import Order, Position, OrderStatus, OrderSide
from src.trading.broker_adapter import BrokerAdapter, OrderRejectedException

logger = logging.getLogger(__name__)


class MockBrokerGateway(BrokerAdapter):
    """Mock broker for testing without real broker connection.

    Simulates:
    - Order acceptance/rejection
    - Fill simulation with random latency
    - Position tracking
    - Account balance updates
    """

    def __init__(self, initial_cash: float = 1000000.0, config: Dict = None):
        self.config = config or {}
        self.initial_cash = initial_cash
        self.cash_balance = initial_cash
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0
        self._connected = False

        # Mock market prices (for fill simulation)
        self._market_prices: Dict[str, Decimal] = {}

        # Simulation parameters
        self.fill_delay = self.config.get('fill_delay', 0.1)  # seconds
        self.rejection_rate = self.config.get('rejection_rate', 0.0)  # 0-1
        self.slippage = self.config.get('slippage', 0.001)  # 0.1%

    async def connect(self) -> bool:
        """Simulate connection."""
        await asyncio.sleep(0.1)
        self._connected = True
        logger.info("Mock broker connected")
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        logger.info("Mock broker disconnected")

    async def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    async def place_order(self, order: Order) -> str:
        """Simulate order placement."""
        if not self._connected:
            raise ConnectionError("Broker not connected")

        # Random rejection simulation
        if random.random() < self.rejection_rate:
            raise OrderRejectedException(f"Order rejected by broker: insufficient buying power")

        # Generate broker order ID
        self.order_counter += 1
        broker_order_id = f"MOCK_{datetime.now().strftime('%Y%m%d')}_{self.order_counter:06d}"

        # Store order
        order.submitted_at = datetime.utcnow()
        order.status = OrderStatus.NEW
        self.orders[broker_order_id] = order

        logger.info(f"Order placed: {broker_order_id} {order.side.value} {order.quantity} {order.symbol}")

        # Simulate fill in background
        asyncio.create_task(self._simulate_fill(broker_order_id, order))

        return broker_order_id

    async def _simulate_fill(self, broker_order_id: str, order: Order):
        """Simulate order fill with delay."""
        await asyncio.sleep(self.fill_delay)

        # Get market price
        market_price = self._market_prices.get(order.symbol, order.price or Decimal("40.0"))

        # Apply slippage
        if order.side == OrderSide.BUY:
            fill_price = market_price * (1 + Decimal(str(self.slippage)))
        else:
            fill_price = market_price * (1 - Decimal(str(self.slippage)))

        # Update order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.filled_at = datetime.utcnow()

        # Update position
        await self._update_position(order.symbol, order.side, order.quantity, fill_price)

        logger.info(f"Order filled: {broker_order_id} @ {fill_price:.2f}")

    async def _update_position(self, symbol: str, side: OrderSide, quantity: int, price: Decimal):
        """Update position after fill."""
        if symbol not in self.positions:
            self.positions[symbol] = Position(
                account_id="MOCK_ACCOUNT",
                symbol=symbol,
                quantity=0,
                available_quantity=0,
                avg_cost=Decimal("0"),
                created_at=datetime.utcnow()
            )

        pos = self.positions[symbol]

        if side == OrderSide.BUY:
            # Update average cost
            total_cost = float(pos.avg_cost or 0) * pos.quantity + float(price) * quantity
            new_quantity = pos.quantity + quantity
            pos.avg_cost = Decimal(str(total_cost / new_quantity)) if new_quantity > 0 else Decimal("0")
            pos.quantity = new_quantity

            # Update cash (T+0 for mock, real T+1 handled by broker)
            self.cash_balance -= float(price * quantity)
        else:  # SELL
            pos.quantity -= quantity
            self.cash_balance += float(price * quantity)

            # Remove position if zero
            if pos.quantity == 0:
                del self.positions[symbol]

        pos.updated_at = datetime.utcnow()

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED]:
            return False

        order.status = OrderStatus.CANCELED
        order.canceled_at = datetime.utcnow()
        logger.info(f"Order canceled: {order_id}")
        return True

    async def get_order_status(self, order_id: str) -> Dict:
        """Query order status."""
        if order_id not in self.orders:
            raise ValueError(f"Order not found: {order_id}")

        order = self.orders[order_id]
        return {
            'order_id': order_id,
            'symbol': order.symbol,
            'side': order.side.value,
            'quantity': order.quantity,
            'filled_quantity': order.filled_quantity,
            'status': order.status.value,
            'avg_fill_price': float(order.avg_fill_price) if order.avg_fill_price else None,
            'submitted_at': order.submitted_at,
            'filled_at': order.filled_at
        }

    async def get_positions(self) -> List[Position]:
        """Get all positions."""
        return list(self.positions.values())

    async def get_account(self) -> Dict:
        """Get account info."""
        stock_value = sum(
            float(pos.quantity * (pos.last_price or pos.avg_cost or Decimal("0")))
            for pos in self.positions.values()
        )

        return {
            'account_id': 'MOCK_ACCOUNT',
            'total_assets': self.cash_balance + stock_value,
            'cash_balance': self.cash_balance,
            'stock_value': stock_value,
            'available_cash': self.cash_balance  # T+1 settlement handled elsewhere
        }

    async def subscribe_quotes(self, symbols: List[str]) -> None:
        """Mock quote subscription."""
        logger.info(f"Subscribed to quotes: {symbols}")

    async def unsubscribe_quotes(self, symbols: List[str]) -> None:
        """Mock quote unsubscription."""
        logger.info(f"Unsubscribed from quotes: {symbols}")

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get latest quote."""
        price = self._market_prices.get(symbol)
        if not price:
            return None

        return {
            'symbol': symbol,
            'price': float(price),
            'timestamp': datetime.utcnow(),
            'volume': 1000000
        }

    def update_market_price(self, symbol: str, price: float):
        """Update market price for simulation."""
        self._market_prices[symbol] = Decimal(str(price))