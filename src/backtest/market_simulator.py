# src/backtest/market_simulator.py - Market simulation with Chinese market rules
import logging
from datetime import datetime, time
from typing import Dict, Optional, List
from decimal import Decimal
import pandas as pd
from dataclasses import dataclass

from src.models.trading import Order, OrderType, OrderSide

logger = logging.getLogger(__name__)


@dataclass
class MarketRules:
    """Chinese stock market trading rules"""
    # Price limits
    price_limit_pct: float = 0.10  # 10% for main board
    st_price_limit_pct: float = 0.05  # 5% for ST stocks
    gem_price_limit_pct: float = 0.20  # 20% for GEM/STAR market
    
    # Trading hours (Beijing time)
    morning_open: time = time(9, 30)
    morning_close: time = time(11, 30)
    afternoon_open: time = time(13, 0)
    afternoon_close: time = time(15, 0)
    
    # Settlement rules
    settlement_days: int = 1  # T+1
    
    # Minimum price tick
    min_tick: Decimal = Decimal('0.01')
    
    # Lot size
    board_lot: int = 100  # 100 shares per lot


class OrderBook:
    """Simple order book for market simulation"""
    
    def __init__(self):
        self.buy_orders = []   # List of (price, quantity, timestamp)
        self.sell_orders = []  # List of (price, quantity, timestamp)
        
    def add_order(self, order: Order):
        """Add order to book"""
        if order.side == OrderSide.BUY:
            self.buy_orders.append((order.price, order.quantity, order.created_at))
            # Sort buy orders by price descending (highest first)
            self.buy_orders.sort(key=lambda x: x[0], reverse=True)
        else:
            self.sell_orders.append((order.price, order.quantity, order.created_at))
            # Sort sell orders by price ascending (lowest first)
            self.sell_orders.sort(key=lambda x: x[0])
    
    def get_best_bid(self) -> Optional[Decimal]:
        """Get best bid price"""
        return self.buy_orders[0][0] if self.buy_orders else None
    
    def get_best_ask(self) -> Optional[Decimal]:
        """Get best ask price"""
        return self.sell_orders[0][0] if self.sell_orders else None


class MarketSimulator:
    """Market simulator with Chinese market characteristics"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.rules = MarketRules()
        self.order_books = {}  # symbol -> OrderBook
        
        # Market impact parameters
        self.impact_model = self.config.get('impact_model', 'linear')
        self.base_impact = self.config.get('base_impact', 0.001)  # 0.1% base impact
        
        # Liquidity simulation
        self.avg_daily_volume = {}  # symbol -> average daily volume
        
    def set_market_rules(self, symbol: str) -> MarketRules:
        """Set market-specific rules based on symbol"""
        rules = MarketRules()
        
        # Determine market type from symbol
        if symbol.endswith('.SH'):
            if symbol.startswith('688'):  # STAR market
                rules.price_limit_pct = 0.20
            elif symbol.startswith('600') or symbol.startswith('601'):  # Main board
                rules.price_limit_pct = 0.10
        elif symbol.endswith('.SZ'):
            if symbol.startswith('300'):  # GEM
                rules.price_limit_pct = 0.20
            elif symbol.startswith('000') or symbol.startswith('001'):  # Main board
                rules.price_limit_pct = 0.10
        
        return rules
    
    def calculate_price_limits(self, symbol: str, prev_close: Decimal) -> tuple[Decimal, Decimal]:
        """Calculate daily price limits"""
        rules = self.set_market_rules(symbol)
        limit_amount = prev_close * Decimal(str(rules.price_limit_pct))
        
        upper_limit = prev_close + limit_amount
        lower_limit = prev_close - limit_amount
        
        # Round to minimum tick
        upper_limit = self._round_price(upper_limit)
        lower_limit = self._round_price(lower_limit)
        
        return upper_limit, lower_limit
    
    def _round_price(self, price: Decimal) -> Decimal:
        """Round price to minimum tick"""
        return (price / self.rules.min_tick).quantize(Decimal('1')) * self.rules.min_tick
    
    def is_trading_time(self, timestamp: datetime) -> bool:
        """检查给定时间是否处于交易时段。

        默认严格执行沪深股票交易时段：
        - 上午 09:30-11:30
        - 下午 13:00-15:00
        中午休市、夜间以及周末都会返回 False。
        如果配置显式设置 ``ignore_trading_hours=True``，则始终允许交易，
        便于特定回测场景。
        """
        if self.config.get('ignore_trading_hours'):
            return True

        # 仅限工作日
        if timestamp.weekday() >= 5:  # 5=Saturday, 6=Sunday
            return False

        time_of_day = timestamp.time()
        in_morning = self.rules.morning_open <= time_of_day <= self.rules.morning_close
        in_afternoon = self.rules.afternoon_open <= time_of_day <= self.rules.afternoon_close

        return in_morning or in_afternoon
    
    async def process_order(self, order: Order, market_data: pd.DataFrame, timestamp: datetime) -> Optional[Dict]:
        """
        Process order through market simulation

        Args:
            order: Order to process
            market_data: Historical market data for the symbol
            timestamp: Current simulation timestamp

        Returns:
            Dict with fill information or None if no fill
        """
        logger.info(f"[MarketSim] Processing {order.side} {order.quantity} {order.symbol} @ {timestamp}")

        if not self.is_trading_time(timestamp):
            logger.warning(f"[MarketSim] Order {order.order_id} rejected: outside trading hours (timestamp: {timestamp})")
            return None

        # Get current market data
        current_data = self._get_current_market_data(market_data, timestamp)
        if current_data is None:
            logger.warning(f"[MarketSim] No market data available for {order.symbol} at {timestamp}")
            return None

        logger.info(f"[MarketSim] Current data: open={current_data.get('open')}, close={current_data.get('close')}, volume={current_data.get('volume')}")

        # Extract prices
        open_price = Decimal(str(current_data.get('open', 0)))
        high_price = Decimal(str(current_data.get('high', 0)))
        low_price = Decimal(str(current_data.get('low', 0)))
        close_price = Decimal(str(current_data.get('close', 0)))
        volume = int(current_data.get('volume', 0))

        # Check for suspension
        if current_data.get('is_suspended', False):
            logger.warning(f"[MarketSim] Order {order.order_id} rejected: stock suspended")
            return None

        # Calculate price limits
        prev_close = Decimal(str(current_data.get('pre_close', close_price)))
        upper_limit, lower_limit = self.calculate_price_limits(order.symbol, prev_close)

        # Check for limit up/down
        is_limit_up = close_price >= upper_limit
        is_limit_down = close_price <= lower_limit

        # Process different order types
        if order.order_type == OrderType.MARKET:
            result = await self._process_market_order(order, current_data, upper_limit, lower_limit)
            if result:
                logger.info(f"[MarketSim] Market order filled: {result['quantity']} @ ¥{result['price']}")
            else:
                logger.warning(f"[MarketSim] Market order NOT filled")
            return result
        elif order.order_type == OrderType.LIMIT:
            return await self._process_limit_order(order, current_data, upper_limit, lower_limit)
        else:
            logger.warning(f"[MarketSim] Order type {order.order_type} not supported")
            return None
    
    def _get_current_market_data(self, market_data: pd.DataFrame, timestamp: datetime) -> Optional[Dict]:
        """Get market data for current timestamp"""
        if market_data is None or market_data.empty:
            return None
        
        # Convert timestamp to date for daily data
        target_date = timestamp.date()
        
        if 'date' in market_data.columns:
            matching_data = market_data[market_data['date'].dt.date == target_date]
        else:
            # Assume index is datetime
            matching_data = market_data[market_data.index.date == target_date]
        
        if matching_data.empty:
            return None
        
        return matching_data.iloc[0].to_dict()
    
    async def _process_market_order(self, order: Order, market_data: Dict, upper_limit: Decimal, lower_limit: Decimal) -> Optional[Dict]:
        """Process market order"""
        
        # For buy orders, use ask price (slightly above close)
        # For sell orders, use bid price (slightly below close)
        close_price = Decimal(str(market_data.get('close', 0)))
        
        if order.side == OrderSide.BUY:
            # Check if limit up prevents buying
            if market_data.get('is_limit_up', False):
                logger.debug(f"Buy order {order.order_id} cannot fill: limit up")
                return None
            
            # Simulate market impact for large orders
            fill_price = self._calculate_fill_price(order, close_price, market_data)
            fill_price = min(fill_price, upper_limit)  # Cannot exceed upper limit
            
        else:  # SELL
            # Check if limit down prevents selling
            if market_data.get('is_limit_down', False):
                logger.debug(f"Sell order {order.order_id} cannot fill: limit down")
                return None
            
            fill_price = self._calculate_fill_price(order, close_price, market_data)
            fill_price = max(fill_price, lower_limit)  # Cannot go below lower limit
        
        # Check liquidity constraints
        max_fill_quantity = self._calculate_max_fill_quantity(order, market_data)
        fill_quantity = min(order.quantity, max_fill_quantity)
        
        if fill_quantity <= 0:
            return None
        
        return {
            'quantity': fill_quantity,
            'price': fill_price,
            'timestamp': order.created_at
        }
    
    async def _process_limit_order(self, order: Order, market_data: Dict, upper_limit: Decimal, lower_limit: Decimal) -> Optional[Dict]:
        """Process limit order"""
        
        if order.price is None:
            logger.error(f"Limit order {order.order_id} has no price")
            return None
        
        # Check if limit price is within daily limits
        if order.price > upper_limit or order.price < lower_limit:
            logger.debug(f"Limit order {order.order_id} price outside daily limits")
            return None
        
        # Simple fill logic: order fills if limit price is better than market
        close_price = Decimal(str(market_data.get('close', 0)))
        high_price = Decimal(str(market_data.get('high', 0)))
        low_price = Decimal(str(market_data.get('low', 0)))
        
        can_fill = False
        fill_price = order.price
        
        if order.side == OrderSide.BUY:
            # Buy limit order fills if limit price >= low of the day
            can_fill = order.price >= low_price
        else:
            # Sell limit order fills if limit price <= high of the day
            can_fill = order.price <= high_price
        
        if not can_fill:
            return None
        
        # Calculate fill quantity considering liquidity
        max_fill_quantity = self._calculate_max_fill_quantity(order, market_data)
        fill_quantity = min(order.quantity, max_fill_quantity)
        
        if fill_quantity <= 0:
            return None
        
        return {
            'quantity': fill_quantity,
            'price': fill_price,
            'timestamp': order.created_at
        }
    
    def _calculate_fill_price(self, order: Order, base_price: Decimal, market_data: Dict) -> Decimal:
        """Calculate fill price considering market impact"""
        
        volume = int(market_data.get('volume', 1000000))
        order_ratio = order.quantity / volume if volume > 0 else 0
        
        # Simple linear market impact model
        if self.impact_model == 'linear':
            impact = self.base_impact * order_ratio
        else:
            # Square root impact
            impact = self.base_impact * (order_ratio ** 0.5)
        
        if order.side == OrderSide.BUY:
            # Buying increases price
            fill_price = base_price * (1 + Decimal(str(impact)))
        else:
            # Selling decreases price
            fill_price = base_price * (1 - Decimal(str(impact)))
        
        return self._round_price(fill_price)
    
    def _calculate_max_fill_quantity(self, order: Order, market_data: Dict) -> int:
        """Calculate maximum fillable quantity based on liquidity"""
        
        volume = int(market_data.get('volume', 0))
        
        # Assume we can trade up to 10% of daily volume
        max_participation_rate = self.config.get('max_participation_rate', 0.10)
        max_quantity = int(volume * max_participation_rate)
        
        # Ensure minimum lot size
        max_quantity = (max_quantity // self.rules.board_lot) * self.rules.board_lot
        
        return max(0, max_quantity)
    
    def get_trading_calendar(self, start_date, end_date) -> List[datetime]:
        """Get trading days (simplified - excludes holidays)"""
        trading_days = []
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends (0=Monday, 6=Sunday)
            if current_date.weekday() < 5:
                trading_days.append(current_date)
            current_date += pd.Timedelta(days=1)
        
        return trading_days
