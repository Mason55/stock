# src/backtest/engine.py - Event-driven backtest engine core
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from decimal import Decimal
import pandas as pd
from enum import Enum

from src.models.trading import Order, OrderStatus, OrderType, OrderSide, TimeInForce
from src.backtest.market_simulator import MarketSimulator
from src.backtest.cost_model import CostModel
from src.backtest.risk_manager import BacktestRiskManager

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types in backtest engine"""
    MARKET_DATA = "market_data"
    ORDER = "order"
    FILL = "fill"
    TIMER = "timer"
    SIGNAL = "signal"


@dataclass
class Event:
    """Base event class"""
    type: EventType
    timestamp: datetime
    data: Any = None


@dataclass
class MarketDataEvent:
    """Market data event"""
    timestamp: datetime
    symbol: str
    price_data: Dict = field(default_factory=dict)
    data: Any = None
    
    def __post_init__(self):
        self.type = EventType.MARKET_DATA


@dataclass
class OrderEvent:
    """Order event"""
    timestamp: datetime
    order: Order
    data: Any = None
    
    def __post_init__(self):
        self.type = EventType.ORDER


@dataclass
class FillEvent:
    """Fill event"""
    timestamp: datetime
    order_id: str
    symbol: str
    quantity: int
    price: Decimal
    commission: Decimal
    data: Any = None
    
    def __post_init__(self):
        self.type = EventType.FILL


@dataclass
class SignalEvent:
    """Trading signal event"""
    timestamp: datetime
    symbol: str
    signal_type: str  # BUY, SELL, HOLD
    strength: float   # Signal strength 0-1
    metadata: Dict = field(default_factory=dict)
    data: Any = None
    
    def __post_init__(self):
        self.type = EventType.SIGNAL


class EventHandler(ABC):
    """Abstract event handler"""
    
    @abstractmethod
    async def handle_event(self, event: Event):
        """Handle an event"""
        pass


class Strategy(EventHandler):
    """Base strategy class"""

    def __init__(self, name: str, config: Dict = None, event_queue: asyncio.Queue = None):
        self.name = name
        self.config = config or {}
        self.position = {}  # symbol -> quantity
        self.signals = []
        self.event_queue = event_queue  # For submitting signals
        self.pending_signals: List[SignalEvent] = []
        
    @abstractmethod
    async def handle_market_data(self, event: MarketDataEvent):
        """Handle market data and generate signals"""
        pass
    
    async def handle_event(self, event: Event):
        """Route events to appropriate handlers"""
        if event.type == EventType.MARKET_DATA:
            await self.handle_market_data(event)
        elif event.type == EventType.FILL:
            await self.handle_fill(event)
    
    async def handle_fill(self, event: FillEvent):
        """Update position on fill"""
        if event.symbol not in self.position:
            self.position[event.symbol] = 0
        
        # Note: FillEvent doesn't directly store order side
        # This would need to be passed from the order or portfolio context
        # For now, we'll determine from quantity sign or add order reference
        if event.quantity > 0:
            self.position[event.symbol] += event.quantity
        else:
            self.position[event.symbol] -= abs(event.quantity)
    
    def generate_signal(self, symbol: str, signal_type: str, strength: float = 1.0, metadata: Dict = None):
        """Generate a trading signal and submit to event queue.

        兼容同步/异步调用场景：策略在协程中可直接调用该方法，无需 ``await``，
        同时事件仍会推送到异步队列。
        """
        signal = SignalEvent(
            timestamp=datetime.now(),
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            metadata=metadata or {}
        )
        self.signals.append(signal)

        # Submit signal to event queue for processing
        if self.event_queue:
            try:
                self.event_queue.put_nowait(signal)
            except asyncio.QueueFull:
                logger.warning(
                    "Signal queue full, using fallback for %s", signal.symbol
                )
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop:
                    loop.create_task(self.event_queue.put(signal))
                else:
                    try:
                        asyncio.run(self.event_queue.put(signal))
                    except RuntimeError as exc:
                        logger.error(
                            "Failed to enqueue signal synchronously: %s", exc
                        )
                        self.pending_signals.append(signal)
                        logger.warning(
                            "Signal stored in pending queue (size=%d)",
                            len(self.pending_signals),
                        )
            else:
                # Flush any pending signals if we currently have a running loop
                if self.pending_signals:
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop:
                        while self.pending_signals:
                            pending = self.pending_signals.pop(0)
                            loop.create_task(self.event_queue.put(pending))

        return signal


class Portfolio(EventHandler):
    """Portfolio manager"""

    def __init__(self, initial_capital: float = 1000000.0, event_queue: asyncio.Queue = None):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # symbol -> quantity
        self.holdings = {}   # symbol -> market_value
        self.total_value = initial_capital
        self.orders = {}     # order_id -> Order
        self.event_queue = event_queue  # For submitting orders

        # Performance tracking
        self.equity_curve = []
        self.returns = []
        self.trades = []

        # Track current market prices for position sizing
        self.current_prices = {}  # symbol -> price
        
    async def handle_event(self, event: Event):
        """Handle portfolio events"""
        if event.type == EventType.SIGNAL:
            await self.handle_signal(event)
        elif event.type == EventType.FILL:
            await self.handle_fill(event)
        elif event.type == EventType.MARKET_DATA:
            await self.update_portfolio_value(event)
    
    async def handle_signal(self, event: SignalEvent):
        """Convert signals to orders"""
        # Simple signal to order conversion
        if event.signal_type == "BUY":
            quantity = self.calculate_position_size(event.symbol, event.strength)
            if quantity > 0:
                order = self.create_market_order(event.symbol, OrderSide.BUY, quantity)
                # Submit order to event queue for processing
                if self.event_queue:
                    order_event = OrderEvent(timestamp=event.timestamp, order=order)
                    await self.event_queue.put(order_event)
                return order
        elif event.signal_type == "SELL":
            current_position = self.positions.get(event.symbol, 0)
            if current_position > 0:
                quantity = int(current_position * event.strength)
                if quantity > 0:
                    order = self.create_market_order(event.symbol, OrderSide.SELL, quantity)
                    # Submit order to event queue for processing
                    if self.event_queue:
                        order_event = OrderEvent(timestamp=event.timestamp, order=order)
                        await self.event_queue.put(order_event)
                    return order

        return None
    
    def calculate_position_size(self, symbol: str, signal_strength: float) -> int:
        """Calculate position size based on available cash and signal strength"""
        max_position_value = self.cash * 0.1 * signal_strength  # Max 10% per position

        # Use current market price if available
        current_price = self.current_prices.get(symbol, 40.0)
        quantity = int(max_position_value / current_price / 100) * 100  # Round to 100 shares

        return quantity
    
    def create_market_order(self, symbol: str, side: OrderSide, quantity: int) -> Order:
        """Create a market order"""
        order_id = f"ORDER_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        order = Order(
            order_id=order_id,
            account_id="BACKTEST",
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            status=OrderStatus.NEW,
            time_in_force=TimeInForce.DAY,
            created_at=datetime.now()
        )
        
        self.orders[order_id] = order
        return order
    
    async def handle_fill(self, event: FillEvent):
        """Update portfolio on fill"""
        if event.symbol not in self.positions:
            self.positions[event.symbol] = 0

        # Determine order side from fill event's order or default to event's order field
        order = self.orders.get(event.order_id)
        if not order and hasattr(event, 'order'):
            order = event.order

        if order and order.side == OrderSide.BUY:
            self.positions[event.symbol] += event.quantity
            self.cash -= float(event.price * event.quantity + event.commission)
        elif order and order.side == OrderSide.SELL:
            self.positions[event.symbol] -= event.quantity
            self.cash += float(event.price * event.quantity - event.commission)
        
        # Record trade
        if order:
            self.trades.append({
                'timestamp': event.timestamp,
                'symbol': event.symbol,
                'side': order.side,
                'quantity': event.quantity,
                'price': event.price,
                'commission': event.commission
            })
    
    async def update_portfolio_value(self, event: MarketDataEvent):
        """Update portfolio value based on current market prices"""
        # Update current price
        close_price = float(event.price_data.get('close', 0))
        if close_price > 0:
            self.current_prices[event.symbol] = close_price

        # Update holdings value
        if event.symbol in self.positions:
            quantity = self.positions[event.symbol]
            current_price = Decimal(str(close_price))
            self.holdings[event.symbol] = float(current_price * quantity)

        # Calculate total portfolio value
        total_holdings = sum(self.holdings.values())
        self.total_value = self.cash + total_holdings
        
        # Record equity curve
        self.equity_curve.append({
            'timestamp': event.timestamp,
            'total_value': self.total_value,
            'cash': self.cash,
            'holdings': total_holdings
        })
        
        # Calculate returns
        if len(self.equity_curve) > 1:
            prev_value = self.equity_curve[-2]['total_value']
            daily_return = (self.total_value - prev_value) / prev_value
            self.returns.append(daily_return)


class BacktestEngine:
    """Main backtest engine"""
    
    def __init__(self, 
                 start_date: date, 
                 end_date: date, 
                 initial_capital: float = 1000000.0,
                 config: Dict = None):
        self.start_date = start_date
        self.end_date = end_date
        self.config = config or {}
        
        # Event system
        self.event_queue = asyncio.Queue()
        self.handlers = {}  # event_type -> List[EventHandler]
        self.strategies = []

        # Core components (portfolio needs event_queue reference)
        self.market_simulator = MarketSimulator(self.config.get('market', {}))
        self.cost_model = CostModel(self.config.get('costs', {}))
        self.risk_manager = BacktestRiskManager(self.config.get('risk', {}))
        self.portfolio = Portfolio(initial_capital, self.event_queue)
        
        # State
        self.current_time = None
        self.is_running = False
        self.market_data = {}  # symbol -> DataFrame
        
        self._register_handlers()
    
    def _register_handlers(self):
        """Register event handlers"""
        self.register_handler(EventType.MARKET_DATA, self.portfolio)
        self.register_handler(EventType.FILL, self.portfolio)
        self.register_handler(EventType.SIGNAL, self.portfolio)
    
    def register_handler(self, event_type: EventType, handler: EventHandler):
        """Register an event handler"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    def add_strategy(self, strategy: Strategy):
        """Add a trading strategy"""
        # Inject event_queue into strategy so it can emit signals
        strategy.event_queue = self.event_queue

        self.strategies.append(strategy)
        self.register_handler(EventType.MARKET_DATA, strategy)
        self.register_handler(EventType.FILL, strategy)
    
    def load_market_data(self, symbol: str, data: pd.DataFrame):
        """Load market data for a symbol"""
        # Ensure data is sorted by date
        data = data.sort_values('date' if 'date' in data.columns else data.index)
        self.market_data[symbol] = data
        logger.info(f"Loaded {len(data)} records for {symbol}")
    
    async def run(self):
        """Run the backtest"""
        logger.info(f"Starting backtest from {self.start_date} to {self.end_date}")
        
        self.is_running = True
        current_date = self.start_date
        
        try:
            while current_date <= self.end_date and self.is_running:
                from datetime import time
                self.current_time = datetime.combine(current_date, time.min)
                
                # Generate market data events for current date
                await self._generate_market_events(current_date)
                
                # Process all events for this time step
                await self._process_events()
                
                current_date += timedelta(days=1)
            
            # Generate final report
            results = await self._generate_results()
            logger.info("Backtest completed successfully")
            
            return results
            
        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            raise
        finally:
            self.is_running = False
    
    async def _generate_market_events(self, date: date):
        """Generate market data events for given date"""
        for symbol, data in self.market_data.items():
            # Find data for current date
            if 'date' in data.columns:
                # Handle both date and datetime objects
                if hasattr(data['date'].iloc[0], 'date'):
                    # datetime objects - use .dt accessor
                    day_data = data[data['date'].dt.date == date]
                else:
                    # date objects - direct comparison
                    day_data = data[data['date'] == date]
            else:
                # Assume index is date
                if hasattr(data.index[0], 'date'):
                    day_data = data[data.index.date == date]
                else:
                    day_data = data[data.index == date]

            if not day_data.empty:
                price_data = day_data.iloc[0].to_dict()
                event = MarketDataEvent(
                    timestamp=self.current_time,
                    symbol=symbol,
                    price_data=price_data
                )
                await self.event_queue.put(event)
            else:
                # Data not found for this date - this might be weekends
                logger.debug(f"No data for {symbol} on {date}")
    
    async def _process_events(self):
        """Process all events in the queue"""
        while not self.event_queue.empty():
            try:
                event = await self.event_queue.get()
                
                # Route event to registered handlers
                if event.type in self.handlers:
                    for handler in self.handlers[event.type]:
                        await handler.handle_event(event)
                
                # Handle special event types
                if event.type == EventType.ORDER:
                    await self._process_order(event.order)
                
                self.event_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def _process_order(self, order: Order):
        """Process an order through the market simulator"""
        # Risk check
        if not await self.risk_manager.check_order(order, self.portfolio):
            order.status = OrderStatus.REJECTED
            order.reject_reason = "Risk check failed"
            return
        
        # Market simulation
        fill_result = await self.market_simulator.process_order(
            order, 
            self.market_data.get(order.symbol),
            self.current_time
        )
        
        if fill_result:
            # Calculate costs
            commission = self.cost_model.calculate_commission(
                order.symbol, 
                fill_result['quantity'], 
                fill_result['price']
            )
            
            # Generate fill event
            fill_event = FillEvent(
                timestamp=self.current_time,
                order_id=order.order_id,
                symbol=order.symbol,
                quantity=fill_result['quantity'],
                price=fill_result['price'],
                commission=commission
            )
            
            await self.event_queue.put(fill_event)
    
    async def _generate_results(self) -> Dict:
        """Generate backtest results"""
        if not self.portfolio.equity_curve:
            return {}
        
        # Convert to DataFrame for analysis
        equity_df = pd.DataFrame(self.portfolio.equity_curve)
        
        # Calculate performance metrics
        total_return = (self.portfolio.total_value - self.portfolio.initial_capital) / self.portfolio.initial_capital
        
        if len(self.portfolio.returns) > 0:
            returns_series = pd.Series(self.portfolio.returns)
            volatility = returns_series.std() * (252 ** 0.5)  # Annualized
            sharpe_ratio = returns_series.mean() / returns_series.std() * (252 ** 0.5) if returns_series.std() > 0 else 0
            max_drawdown = self._calculate_max_drawdown(equity_df['total_value'])
        else:
            volatility = 0
            sharpe_ratio = 0
            max_drawdown = 0
        
        results = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.portfolio.initial_capital,
            'final_value': self.portfolio.total_value,
            'total_return': total_return,
            'annualized_return': (1 + total_return) ** (365 / (self.end_date - self.start_date).days) - 1,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_trades': len(self.portfolio.trades),
            'equity_curve': equity_df,
            'trades': self.portfolio.trades,
            'positions': self.portfolio.positions.copy()
        }
        
        return results
    
    def _calculate_max_drawdown(self, equity_series):
        """Calculate maximum drawdown"""
        peak = equity_series.expanding().max()
        drawdown = (equity_series - peak) / peak
        return drawdown.min()
