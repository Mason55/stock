# src/trading/signal_executor.py - Convert signals to orders
import logging
from typing import Optional
from decimal import Decimal
from datetime import datetime

from src.backtest.engine import SignalEvent
from src.models.trading import Order, OrderType, OrderSide, OrderStatus, TimeInForce
from src.trading.broker_adapter import BrokerAdapter
from src.trading.order_manager import OrderManager

logger = logging.getLogger(__name__)


class SignalExecutor:
    """Converts trading signals to executable orders.

    Responsibilities:
    - Signal validation
    - Position sizing
    - Order creation
    - Risk checks
    """

    def __init__(self, broker: BrokerAdapter, order_manager: 'OrderManager'):
        self.broker = broker
        self.order_manager = order_manager

        # Configuration
        self.max_position_pct = 0.10  # Max 10% per position
        self.default_order_type = OrderType.MARKET

    async def execute_signal(self, signal: SignalEvent) -> Optional[Order]:
        """Execute trading signal.

        Args:
            signal: SignalEvent from strategy

        Returns:
            Order object if created, None if signal rejected
        """
        # Get account info
        account = await self.broker.get_account()
        available_cash = account['available_cash']

        # Get current positions
        positions = await self.broker.get_positions()
        current_position = next(
            (p for p in positions if p.symbol == signal.symbol),
            None
        )
        current_qty = current_position.quantity if current_position else 0

        # Route to appropriate handler
        if signal.signal_type == "BUY":
            return await self._handle_buy_signal(
                signal, available_cash, current_qty
            )
        elif signal.signal_type == "SELL":
            return await self._handle_sell_signal(
                signal, current_qty
            )
        elif signal.signal_type == "HOLD":
            logger.debug(f"HOLD signal for {signal.symbol}, no action")
            return None
        else:
            logger.warning(f"Unknown signal type: {signal.signal_type}")
            return None

    async def _handle_buy_signal(
        self,
        signal: SignalEvent,
        available_cash: float,
        current_qty: int
    ) -> Optional[Order]:
        """Handle BUY signal."""
        # Get current price
        quote = await self.broker.get_quote(signal.symbol)
        if not quote:
            logger.warning(f"No quote available for {signal.symbol}")
            return None

        current_price = Decimal(str(quote['price']))

        # Calculate position size
        max_investment = available_cash * self.max_position_pct * signal.strength
        quantity = int(max_investment / float(current_price) / 100) * 100  # Round to 100 shares

        if quantity < 100:
            logger.info(f"Buy signal too small: {quantity} shares")
            return None

        # Create order
        order = Order(
            order_id=self._generate_order_id(),
            account_id=self._get_account_id(),
            symbol=signal.symbol,
            side=OrderSide.BUY,
            order_type=self.default_order_type,
            quantity=quantity,
            price=current_price if self.default_order_type == OrderType.LIMIT else None,
            status=OrderStatus.PENDING,
            time_in_force=TimeInForce.DAY,
            created_at=datetime.utcnow()
        )

        # Submit order
        try:
            broker_order_id = await self.order_manager.submit_order(order)
            logger.info(f"BUY order submitted: {signal.symbol} {quantity} @ {current_price:.2f}")
            return order
        except Exception as e:
            logger.error(f"Failed to submit BUY order: {e}")
            return None

    async def _handle_sell_signal(
        self,
        signal: SignalEvent,
        current_qty: int
    ) -> Optional[Order]:
        """Handle SELL signal."""
        if current_qty <= 0:
            logger.info(f"No position to sell for {signal.symbol}")
            return None

        # Calculate sell quantity based on signal strength
        quantity = int(current_qty * signal.strength / 100) * 100  # Round to 100

        if quantity < 100:
            logger.info(f"Sell signal too small: {quantity} shares")
            return None

        # Get current price
        quote = await self.broker.get_quote(signal.symbol)
        current_price = Decimal(str(quote['price'])) if quote else None

        # Create order
        order = Order(
            order_id=self._generate_order_id(),
            account_id=self._get_account_id(),
            symbol=signal.symbol,
            side=OrderSide.SELL,
            order_type=self.default_order_type,
            quantity=quantity,
            price=current_price if self.default_order_type == OrderType.LIMIT else None,
            status=OrderStatus.PENDING,
            time_in_force=TimeInForce.DAY,
            created_at=datetime.utcnow()
        )

        # Submit order
        try:
            broker_order_id = await self.order_manager.submit_order(order)
            logger.info(f"SELL order submitted: {signal.symbol} {quantity} @ {current_price:.2f}")
            return order
        except Exception as e:
            logger.error(f"Failed to submit SELL order: {e}")
            return None

    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        return f"ORDER_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"

    def _get_account_id(self) -> str:
        """Get account ID."""
        return "LIVE_ACCOUNT"