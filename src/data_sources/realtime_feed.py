# src/data_sources/realtime_feed.py - WebSocket realtime market data feed
import asyncio
import logging
import json
from typing import Dict, List, Callable, Optional
from datetime import datetime
from collections import defaultdict
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class RealtimeFeed(ABC):
    """Abstract base for realtime market data feeds."""

    @abstractmethod
    async def connect(self):
        """Establish connection."""
        pass

    @abstractmethod
    async def subscribe(self, symbols: List[str]):
        """Subscribe to symbols."""
        pass

    @abstractmethod
    async def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close connection."""
        pass


class SinaRealtimeFeed(RealtimeFeed):
    """Sina Finance realtime data feed.

    Features:
    - Real-time tick data
    - Multi-symbol subscription
    - Automatic reconnection
    - Data callback system
    """

    def __init__(self, config: Dict = None):
        config = config or {}

        # Configuration
        self.update_interval = config.get('update_interval', 1.0)  # 1 second
        self.max_retries = config.get('max_retries', 5)
        self.retry_delay = config.get('retry_delay', 5)

        # State
        self.subscribed_symbols: set = set()
        self.callbacks: List[Callable] = []
        self.is_running = False
        self.is_connected = False

        # Data cache
        self.latest_data: Dict[str, Dict] = {}

        # Tasks
        self._update_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        logger.info("Sina Realtime Feed initialized")

    async def connect(self):
        """Establish connection (polling-based for Sina)."""
        if self.is_connected:
            logger.warning("Already connected")
            return

        try:
            self.is_connected = True
            self.is_running = True

            # Start background tasks
            self._update_task = asyncio.create_task(self._update_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info("Sina feed connected")

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.is_connected = False
            raise

    async def subscribe(self, symbols: List[str]):
        """Subscribe to symbols."""
        new_symbols = set(symbols) - self.subscribed_symbols

        if new_symbols:
            self.subscribed_symbols.update(new_symbols)
            logger.info(f"Subscribed to {len(new_symbols)} symbols: {new_symbols}")

    async def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols."""
        removed = self.subscribed_symbols.intersection(symbols)

        if removed:
            self.subscribed_symbols -= removed
            logger.info(f"Unsubscribed from {len(removed)} symbols")

            # Remove from cache
            for symbol in removed:
                self.latest_data.pop(symbol, None)

    async def disconnect(self):
        """Close connection."""
        if not self.is_connected:
            return

        logger.info("Disconnecting...")

        self.is_running = False

        # Cancel tasks
        if self._update_task:
            self._update_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        self.is_connected = False
        logger.info("Disconnected")

    def register_callback(self, callback: Callable):
        """Register data callback.

        Callback signature: callback(symbol: str, data: Dict)
        """
        self.callbacks.append(callback)
        logger.info(f"Callback registered: {callback.__name__}")

    async def _update_loop(self):
        """Fetch and distribute updates."""
        from src.data_sources.sina_finance import SinaFinanceAPI

        api = SinaFinanceAPI()

        while self.is_running:
            try:
                if not self.subscribed_symbols:
                    await asyncio.sleep(self.update_interval)
                    continue

                # Fetch realtime data for all subscribed symbols
                for symbol in list(self.subscribed_symbols):
                    try:
                        data = api.get_realtime_quote(symbol)

                        if data:
                            self.latest_data[symbol] = {
                                'symbol': symbol,
                                'price': data.get('current_price'),
                                'change': data.get('change_pct'),
                                'volume': data.get('volume'),
                                'turnover': data.get('turnover'),
                                'bid': data.get('bid_price'),
                                'ask': data.get('ask_price'),
                                'high': data.get('high'),
                                'low': data.get('low'),
                                'open': data.get('open'),
                                'prev_close': data.get('prev_close'),
                                'timestamp': datetime.now()
                            }

                            # Notify callbacks
                            for callback in self.callbacks:
                                try:
                                    if asyncio.iscoroutinefunction(callback):
                                        await callback(symbol, self.latest_data[symbol])
                                    else:
                                        callback(symbol, self.latest_data[symbol])
                                except Exception as e:
                                    logger.error(f"Callback error: {e}")

                    except Exception as e:
                        logger.error(f"Failed to fetch {symbol}: {e}")

                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update loop error: {e}")
                await asyncio.sleep(self.retry_delay)

    async def _heartbeat_loop(self):
        """Heartbeat to monitor connection."""
        while self.is_running:
            try:
                await asyncio.sleep(30)

                if self.subscribed_symbols:
                    logger.debug(
                        f"Heartbeat: {len(self.subscribed_symbols)} symbols, "
                        f"{len(self.latest_data)} with data"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def get_latest(self, symbol: str) -> Optional[Dict]:
        """Get latest data for symbol."""
        return self.latest_data.get(symbol)

    def get_all_latest(self) -> Dict[str, Dict]:
        """Get latest data for all symbols."""
        return self.latest_data.copy()


class TencentRealtimeFeed(RealtimeFeed):
    """Tencent Finance realtime feed (placeholder for future implementation)."""

    async def connect(self):
        logger.warning("Tencent feed not implemented")

    async def subscribe(self, symbols: List[str]):
        logger.warning("Tencent feed not implemented")

    async def unsubscribe(self, symbols: List[str]):
        logger.warning("Tencent feed not implemented")

    async def disconnect(self):
        logger.warning("Tencent feed not implemented")


class EastMoneyRealtimeFeed(RealtimeFeed):
    """East Money realtime feed (placeholder for future implementation)."""

    async def connect(self):
        logger.warning("East Money feed not implemented")

    async def subscribe(self, symbols: List[str]):
        logger.warning("East Money feed not implemented")

    async def unsubscribe(self, symbols: List[str]):
        logger.warning("East Money feed not implemented")

    async def disconnect(self):
        logger.warning("East Money feed not implemented")