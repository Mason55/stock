# src/trading/order_manager.py - Order lifecycle management
import asyncio
import logging
from contextlib import contextmanager
from typing import Callable, Dict, List, Optional
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session

from src.models.trading import Order, OrderStatus
from src.trading.broker_adapter import BrokerAdapter, OrderRejectedException
from src.database import db_manager

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


SessionFactory = Callable[[], Session]


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

    def __init__(
        self,
        broker: BrokerAdapter,
        session_factory: Optional[SessionFactory] = None,
        enable_persistence: bool = True,
    ):
        self.broker = broker
        self.orders: Dict[str, Order] = {}
        self.order_states: Dict[str, OrderState] = {}
        self._session_factory = session_factory
        self._force_disable_persistence = not enable_persistence
        self._persistence_enabled = False
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize order manager and load persisted state."""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            if self._force_disable_persistence:
                self._persistence_enabled = False
            elif self._session_factory is not None:
                self._persistence_enabled = True
            else:
                try:
                    self._persistence_enabled = db_manager.ensure_initialized()
                except Exception as e:
                    logger.warning("Database initialization failed, persistence disabled: %s", e)
                    self._persistence_enabled = False

            if self._persistence_enabled:
                await self._load_pending_orders()
                logger.info("Order manager initialized with database persistence")
            else:
                logger.info("Order manager running without database persistence")

            self._initialized = True

    async def submit_order(self, order: Order) -> str:
        """Submit order through complete lifecycle.

        Args:
            order: Order object

        Returns:
            Broker order ID

        Raises:
            OrderRejectedException: If order validation or submission fails
        """
        await self.initialize()

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
        await self.initialize()

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

    def _session_scope(self):
        """Context manager that yields a database session if persistence is enabled."""
        @contextmanager
        def _null_context():
            yield None

        if not self._persistence_enabled:
            return _null_context()

        if self._session_factory is not None:
            @contextmanager
            def _factory_context():
                session = self._session_factory()
                try:
                    yield session
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()

            return _factory_context()

        return db_manager.get_session()

    async def _persist_order(self, order: Order) -> None:
        """Save order to database."""
        with self._session_scope() as session:
            if session is None:
                return

            try:
                session.add(order)
                logger.debug(f"Order persisted: {order.order_id}")
            except Exception as e:
                logger.error(f"Failed to persist order: {e}", exc_info=True)
                session.rollback()
                raise

    async def _update_order(self, order: Order) -> None:
        """Update order in database."""
        with self._session_scope() as session:
            if session is None:
                return

            try:
                session.merge(order)
                logger.debug(f"Order updated: {order.order_id}")
            except Exception as e:
                logger.error(f"Failed to update order: {e}", exc_info=True)
                session.rollback()
                return

    async def _load_pending_orders(self) -> None:
        """Load pending orders from database."""
        with self._session_scope() as session:
            if session is None:
                return

            try:
                pending_orders = session.query(Order).filter(
                    Order.status.in_([
                        OrderStatus.PENDING,
                        OrderStatus.NEW,
                        OrderStatus.PARTIALLY_FILLED
                    ])
                ).all()

                for order in pending_orders:
                    self.orders[order.order_id] = order
                    self.order_states[order.order_id] = OrderState.SUBMITTED

                logger.info("Loaded %d pending orders", len(pending_orders))

            except Exception as e:
                logger.error(f"Failed to load pending orders: {e}", exc_info=True)
