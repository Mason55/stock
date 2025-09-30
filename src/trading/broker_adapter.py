# src/trading/broker_adapter.py - Abstract broker interface
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from src.models.trading import Order, Position


class BrokerAdapter(ABC):
    """Abstract interface for broker integration.

    Implementations should handle:
    - Authentication and connection management
    - Order placement and cancellation
    - Position and account queries
    - Real-time market data subscription
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to broker.

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to broker."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connection is active."""
        pass

    @abstractmethod
    async def place_order(self, order: Order) -> str:
        """Submit order to broker.

        Args:
            order: Order object with details

        Returns:
            Broker order ID

        Raises:
            OrderRejectedException: If order is rejected
            ConnectionError: If broker connection fails
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order.

        Args:
            order_id: Broker order ID

        Returns:
            True if cancellation successful
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict:
        """Query order status.

        Args:
            order_id: Broker order ID

        Returns:
            Dict with order status details
        """
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get current positions.

        Returns:
            List of Position objects
        """
        pass

    @abstractmethod
    async def get_account(self) -> Dict:
        """Get account information.

        Returns:
            Dict with:
                - total_assets: Total account value
                - cash_balance: Available cash
                - stock_value: Market value of holdings
                - available_cash: Cash available for trading
        """
        pass

    @abstractmethod
    async def subscribe_quotes(self, symbols: List[str]) -> None:
        """Subscribe to real-time quotes.

        Args:
            symbols: List of stock symbols to subscribe
        """
        pass

    @abstractmethod
    async def unsubscribe_quotes(self, symbols: List[str]) -> None:
        """Unsubscribe from real-time quotes.

        Args:
            symbols: List of stock symbols to unsubscribe
        """
        pass

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get latest quote for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with quote data or None if unavailable
        """
        pass


class OrderRejectedException(Exception):
    """Raised when broker rejects an order."""
    pass


class BrokerConnectionError(Exception):
    """Raised when broker connection fails."""
    pass