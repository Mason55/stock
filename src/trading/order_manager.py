# src/trading/order_manager.py - Order lifecycle management
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

from src.models.trading import Order, OrderStatus, Fill
from src.trading.broker_adapter import BrokerAdapter, OrderRejectedException
from src.database.session import DatabaseManager

logger = logging.getLogger(__name__)


class OrderState(Enum):
    """Order state machine states."""
    CREATED = "created"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELING = "canceling"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderManager:
    """Manages order lifecycle with state machine.

    Order flow:
    CREATED → VALIDATED → SUBMITTED → ACCEPTED → FILLED
                      ↓                       ↓
                   REJECTED              CANCELED

    Responsibilities:
    - Order validation
    - Submission to broker
    - Status tracking
    - Fill processing
    - Database persistence
    """

    def __init__(self, broker: BrokerAdapter):
        self.broker = broker
        self.orders: Dict[str, Order] = {}
        self.order_states: Dict[str, OrderState] = {}

        # Database session
        self.db_session = None

    async def initialize(self) -> None:
        """Initialize order manager."""
        # Setup database connection
        try:
            db_manager = DatabaseManager()
            db_manager.initialize()
            self.db_session = db_manager.get_session()
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
            self.db_session = None

        # Load pending orders from database
        if self.db_session:
            await self._load_pending_orders()

        logger.info("Order manager initialized")

    async def submit_order(self, order: Order) -> str:
        """Submit order through complete lifecycle.

        Args:
            order: Order object

        Returns:
            Broker order ID

        Raises:
            OrderRejectedException: If order validation or submission fails
        """
        # Validate order
        self._validate_order(order)
        self.order_states[order.order_id] = OrderState.VALIDATED

        # Persist to database
        await self._persist_order(order)

        # Submit to broker
        try:
            broker_order_id = await self.broker.place_order(order)

            # Update state
            order.submitted_at = datetime.utcnow()
            order.status = OrderStatus.NEW
            self.order_states[order.order_id] = OrderState.SUBMITTED

            # Store order
            self.orders[order.order_id] = order

            # Update database
            await self._update_order(order)

            # Start monitoring
            asyncio.create_task(self._monitor_order(order.order_id, broker_order_id))

            return broker_order_id

        except OrderRejectedException as e:
            order.status = OrderStatus.REJECTED
            order.reject_reason = str(e)
            self.order_states[order.order_id] = OrderState.REJECTED
            await self._update_order(order)
            raise

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: Internal order ID

        Returns:
            True if cancellation successful
        """
        if order_id not in self.orders:
            logger.warning(f"Order not found: {order_id}")
            return False

        order = self.orders[order_id]

        # Check if cancelable
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED]:
            logger.warning(f"Order not cancelable: {order_id} status={order.status}")
            return False

        # Update state
        self.order_states[order_id] = OrderState.CANCELING

        # Cancel with broker
        try:
            success = await self.broker.cancel_order(order_id)

            if success:
                order.status = OrderStatus.CANCELED
                order.canceled_at = datetime.utcnow()
                self.order_states[order_id] = OrderState.CANCELED
                await self._update_order(order)
                logger.info(f"Order canceled: {order_id}")
                return True
            else:
                logger.warning(f"Broker failed to cancel order: {order_id}")
                return False

        except Exception as e:
            logger.error(f"Error canceling order {order_id}: {e}", exc_info=True)
            return False

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)

    async def get_pending_orders(self) -> List[Order]:
        """Get all pending orders."""
        return [
            order for order in self.orders.values()
            if order.status in [OrderStatus.PENDING, OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]
        ]

    async def _monitor_order(self, order_id: str, broker_order_id: str) -> None:
        """Monitor order status updates from broker."""
        order = self.orders[order_id]

        # Poll broker for updates
        while order.status not in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED]:
            try:
                # Get status from broker
                status_data = await self.broker.get_order_status(broker_order_id)

                # Update order
                old_status = order.status
                order.status = OrderStatus[status_data['status'].upper()]
                order.filled_quantity = status_data.get('filled_quantity', 0)
                order.avg_fill_price = status_data.get('avg_fill_price')

                # State transition
                if order.status == OrderStatus.FILLED:
                    order.filled_at = datetime.utcnow()
                    self.order_states[order_id] = OrderState.FILLED
                    logger.info(f"Order filled: {order_id}")
                elif order.status == OrderStatus.PARTIALLY_FILLED:
                    self.order_states[order_id] = OrderState.PARTIALLY_FILLED

                # Persist changes
                if old_status != order.status:
                    await self._update_order(order)

            except Exception as e:
                logger.error(f"Error monitoring order {order_id}: {e}")

            # Poll interval
            await asyncio.sleep(1.0)

    def _validate_order(self, order: Order) -> None:
        """Validate order before submission.

        Raises:
            ValueError: If order validation fails
        """
        # Check required fields
        if not order.symbol:
            raise ValueError("Order symbol required")

        if order.quantity <= 0:
            raise ValueError(f"Invalid order quantity: {order.quantity}")

        # Check lot size (100 shares for A-shares)
        if order.quantity % 100 != 0:
            raise ValueError(f"Order quantity must be multiple of 100: {order.quantity}")

        # Check order type
        if order.order_type not in [order.order_type.MARKET, order.order_type.LIMIT]:
            raise ValueError(f"Unsupported order type: {order.order_type}")

        # Limit order must have price
        if order.order_type == order.order_type.LIMIT and not order.price:
            raise ValueError("Limit order requires price")

        logger.debug(f"Order validated: {order.order_id}")

    async def _persist_order(self, order: Order) -> None:
        """Save order to database."""
        if not self.db_session:
            return

        try:
            self.db_session.add(order)
            self.db_session.commit()
            logger.debug(f"Order persisted: {order.order_id}")
        except Exception as e:
            logger.error(f"Failed to persist order: {e}", exc_info=True)
            self.db_session.rollback()

    async def _update_order(self, order: Order) -> None:
        """Update order in database."""
        if not self.db_session:
            return

        try:
            self.db_session.merge(order)
            self.db_session.commit()
            logger.debug(f"Order updated: {order.order_id}")
        except Exception as e:
            logger.error(f"Failed to update order: {e}", exc_info=True)
            self.db_session.rollback()

    async def _load_pending_orders(self) -> None:
        """Load pending orders from database."""
        if not self.db_session:
            return

        try:
            pending_orders = self.db_session.query(Order).filter(
                Order.status.in_([
                    OrderStatus.PENDING,
                    OrderStatus.NEW,
                    OrderStatus.PARTIALLY_FILLED
                ])
            ).all()

            for order in pending_orders:
                self.orders[order.order_id] = order
                self.order_states[order.order_id] = OrderState.SUBMITTED

            logger.info(f"Loaded {len(pending_orders)} pending orders")

        except Exception as e:
            logger.error(f"Failed to load pending orders: {e}", exc_info=True)