"""ETF T+1 Trading Strategy - Intraday trading with T+1 settlement rules

This strategy implements T+1 trading patterns for ETFs:
- Regular T (正T): Sell existing position first, buyback lower
- Reverse T (倒T): Buy additional position first (T+1), sell higher next day

Key considerations for A-share T+1 rules:
- Cannot sell shares bought on the same day
- Must have base position for Regular T
- Reverse T requires available cash and next-day execution
"""
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from enum import Enum

import numpy as np

from src.backtest.engine import MarketDataEvent, Strategy, SignalEvent

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """T trading modes"""
    REGULAR_T = "regular_t"  # Sell high, buy low (need base position)
    REVERSE_T = "reverse_t"  # Buy low, sell high next day (need cash)
    AUTO = "auto"  # Automatically choose based on signal


class ETFTTradingStrategy(Strategy):
    """ETF T+1 Trading Strategy with premium rate monitoring

    Trading Logic:

    Regular T (正T):
    1. Sell X% of base position when price rises to resistance
    2. Buy back when price drops to support
    3. Profit = (sell_price - buy_price) * quantity

    Reverse T (倒T):
    1. Buy X% new position when price drops to support
    2. Sell next day when price rises to resistance
    3. Profit = (sell_price - buy_price) * quantity

    Signals:
    - RSI oversold/overbought
    - Price near support/resistance
    - Premium rate anomaly (for ETFs)
    - KDJ indicators

    Parameters:
    - mode: Trading mode (regular_t, reverse_t, auto)
    - t_ratio: Percentage of position to trade (default: 0.3 = 30%)
    - rsi_period: RSI calculation period (default: 14)
    - rsi_oversold: RSI oversold threshold (default: 30)
    - rsi_overbought: RSI overbought threshold (default: 70)
    - premium_threshold: Premium rate threshold for ETF (default: 1.0%)
    - discount_threshold: Discount rate threshold for ETF (default: -0.5%)
    - support_lookback: Lookback period for support/resistance (default: 20)
    """

    def __init__(self, config: Dict = None, event_queue=None):
        config = config or {}
        super().__init__("etf_t_trading", config, event_queue)

        # Trading mode
        mode_str = config.get("mode", "auto")
        self.mode = TradingMode(mode_str) if isinstance(mode_str, str) else mode_str

        # Position management
        self.t_ratio = config.get("t_ratio", 0.3)  # 30% of position
        self.base_position_ratio = config.get("base_position_ratio", 0.7)  # Keep 70% as base

        # Risk management
        self.stop_loss_pct = config.get("stop_loss_pct", 0.03)  # 3% stop loss
        self.take_profit_pct = config.get("take_profit_pct", 0.007)  # 0.7% take profit
        self.max_hold_days = config.get("max_hold_days", 5)  # Max hold 5 days for T trade
        self.t_quantity = config.get("t_quantity", 0)  # Fixed T quantity if specified

        # Breakeven tracking
        self.cost_basis = config.get("cost_basis", 0.0)
        self.target_profit = config.get("target_profit", 0.0)
        self.accumulated_profit = 0.0

        # Technical indicators
        self.rsi_period = config.get("rsi_period", 14)
        self.rsi_oversold = config.get("rsi_oversold", 35)
        self.rsi_overbought = config.get("rsi_overbought", 65)
        self.support_lookback = config.get("support_lookback", 10)

        # ETF specific
        self.premium_threshold = config.get("premium_threshold", 1.0)
        self.discount_threshold = config.get("discount_threshold", -0.5)

        # State tracking
        self.price_history: Dict[str, deque] = {}
        self.high_history: Dict[str, deque] = {}
        self.low_history: Dict[str, deque] = {}
        self.premium_rate: Dict[str, float] = {}

        # T trading state
        self.t_state: Dict[str, str] = {}  # symbol -> 'waiting_buy' | 'waiting_sell' | 'idle'
        self.t_entry_price: Dict[str, float] = {}
        self.t_position: Dict[str, int] = {}  # Tracks T trading position separately
        self.last_trade_date: Dict[str, datetime] = {}

        logger.info(
            f"ETF T-Trading Strategy initialized: mode={self.mode.value}, "
            f"t_ratio={self.t_ratio}, t_quantity={self.t_quantity}, rsi_period={self.rsi_period}, "
            f"stop_loss={self.stop_loss_pct:.1%}, take_profit={self.take_profit_pct:.1%}, "
            f"max_hold={self.max_hold_days}d, target_profit=¥{self.target_profit:.2f}"
        )

    def _init_symbol_data(self, symbol: str):
        """Initialize tracking data for a symbol"""
        if symbol not in self.price_history:
            max_period = max(self.rsi_period + 1, self.support_lookback)
            self.price_history[symbol] = deque(maxlen=max_period)
            self.high_history[symbol] = deque(maxlen=self.support_lookback)
            self.low_history[symbol] = deque(maxlen=self.support_lookback)
            self.t_state[symbol] = 'idle'
            self.t_position[symbol] = 0
            self.premium_rate[symbol] = 0.0

    def calculate_rsi(self, prices: deque) -> Optional[float]:
        """Calculate RSI indicator"""
        if len(prices) < self.rsi_period + 1:
            return None

        prices_array = np.array(list(prices))
        deltas = np.diff(prices_array)

        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-self.rsi_period:])
        avg_loss = np.mean(losses[-self.rsi_period:])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_support_resistance(self, highs: deque, lows: deque, prices: deque) -> Dict[str, float]:
        """Calculate support and resistance levels"""
        if len(highs) < self.support_lookback or len(lows) < self.support_lookback:
            return {'support': None, 'resistance': None}

        highs_array = np.array(list(highs))
        lows_array = np.array(list(lows))

        resistance = float(np.max(highs_array[-self.support_lookback:]))
        support = float(np.min(lows_array[-self.support_lookback:]))

        return {'support': support, 'resistance': resistance}

    def update_premium_rate(self, symbol: str, premium_rate: float):
        """Update ETF premium rate from external source"""
        self.premium_rate[symbol] = premium_rate

    async def handle_market_data(self, event: MarketDataEvent):
        """Handle market data and generate T trading signals"""
        symbol = event.symbol

        # Access price data from price_data dict
        price_data = event.price_data
        price = price_data.get('close')
        high = price_data.get('high')
        low = price_data.get('low')
        
        # Get timestamp from event
        current_time = event.timestamp

        if price is None:
            logger.warning(f"No close price in market data for {symbol}")
            return

        self._init_symbol_data(symbol)

        # Update price history
        self.price_history[symbol].append(price)
        self.high_history[symbol].append(high if high is not None else price)
        self.low_history[symbol].append(low if low is not None else price)

        # Need sufficient data
        if len(self.price_history[symbol]) < max(self.rsi_period + 1, self.support_lookback):
            return

        # Calculate indicators
        rsi = self.calculate_rsi(self.price_history[symbol])
        levels = self.calculate_support_resistance(
            self.high_history[symbol],
            self.low_history[symbol],
            self.price_history[symbol]
        )

        support = levels.get('support')
        resistance = levels.get('resistance')
        current_premium = self.premium_rate.get(symbol, 0.0)

        if rsi is None or support is None or resistance is None:
            return

        # Get current position
        current_pos = self.position.get(symbol, 0)
        t_pos = self.t_position.get(symbol, 0)
        state = self.t_state.get(symbol, 'idle')

        # Debug output
        logger.info(
            f"[{symbol}] Price: ¥{price:.3f}, RSI: {rsi:.1f}, "
            f"Support: ¥{support:.3f}, Resistance: ¥{resistance:.3f}, "
            f"Premium: {current_premium:+.2f}%, Pos: {current_pos}, State: {state}"
        )

        # Generate T trading signals
        await self._generate_t_signals(
            symbol, price, rsi, support, resistance,
            current_premium, current_pos, t_pos, state, current_time
        )

    async def _generate_t_signals(self, symbol: str, price: float, rsi: float,
                                  support: float, resistance: float,
                                  premium_rate: float, current_pos: int,
                                  t_pos: int, state: str, current_time: datetime):
        """Generate T trading signals based on market conditions"""

        # Signal strength accumulator
        buy_strength = 0
        sell_strength = 0
        reasons = []

        # RSI signals
        if rsi < self.rsi_oversold:
            buy_strength += 40
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > self.rsi_overbought:
            sell_strength += 40
            reasons.append(f"RSI overbought ({rsi:.1f})")

        # Support/Resistance signals
        if price <= support * 1.01:  # Within 1% of support
            buy_strength += 35  # Increased from 25 - key signal for T trading
            reasons.append(f"Near support (¥{support:.3f})")
        elif price >= resistance * 0.99:  # Within 1% of resistance
            sell_strength += 35  # Increased from 25 - key signal for T trading
            reasons.append(f"Near resistance (¥{resistance:.3f})")

        # Premium rate signals (ETF specific)
        if premium_rate > self.premium_threshold:
            sell_strength += 20
            reasons.append(f"High premium ({premium_rate:+.2f}%)")
        elif premium_rate < self.discount_threshold:
            buy_strength += 20
            reasons.append(f"Discount ({premium_rate:+.2f}%)")

        # Determine trading action based on mode and state
        logger.info(
            f"[{symbol}] Buy strength: {buy_strength}, Sell strength: {sell_strength}, "
            f"Mode: {self.mode.value}, Current pos: {current_pos}"
        )

        # Determine effective mode for AUTO
        effective_mode = self.mode
        if self.mode == TradingMode.AUTO:
            if state == 'waiting_sell':
                effective_mode = TradingMode.REVERSE_T
            elif state == 'waiting_buy':
                effective_mode = TradingMode.REGULAR_T
            elif current_pos > 0:
                effective_mode = TradingMode.REGULAR_T
            else:
                effective_mode = TradingMode.REVERSE_T

        if effective_mode == TradingMode.REGULAR_T:
            # Regular T: Need base position
            if state == 'idle' and sell_strength > buy_strength and sell_strength >= 35:  # Lowered from 50
                # Sell signal: Sell part of base position
                if current_pos > 0:
                    sell_qty = int(current_pos * self.t_ratio)
                    if sell_qty >= 100:  # Minimum 1 lot
                        self.generate_signal(
                            symbol, 'SELL',
                            strength=sell_strength / 100,
                            metadata={
                                'quantity': sell_qty,
                                'reasons': reasons,
                                't_type': 'regular_t_sell',
                                'entry_price': price
                            }
                        )
                        self.t_state[symbol] = 'waiting_buy'
                        self.t_entry_price[symbol] = price
                        self.t_position[symbol] = sell_qty
                        logger.info(f"Regular T SELL: {symbol} {sell_qty} @ ¥{price:.3f}, reasons: {reasons}")

            elif state == 'waiting_buy' and buy_strength > sell_strength and buy_strength >= 35:  # Lowered from 50
                # Buy signal: Buy back the sold quantity
                buy_qty = self.t_position.get(symbol, 0)
                if buy_qty > 0 and price < self.t_entry_price.get(symbol, float('inf')):
                    self.generate_signal(
                        symbol, 'BUY',
                        strength=buy_strength / 100,
                        metadata={
                            'quantity': buy_qty,
                            'reasons': reasons,
                            't_type': 'regular_t_buy',
                            'expected_profit': (self.t_entry_price[symbol] - price) * buy_qty
                        }
                    )
                    self.t_state[symbol] = 'idle'
                    self.t_position[symbol] = 0
                    logger.info(f"Regular T BUY: {symbol} {buy_qty} @ ¥{price:.3f}, profit: ¥{(self.t_entry_price[symbol] - price) * buy_qty:.2f}")

        elif effective_mode == TradingMode.REVERSE_T:
            # Reverse T: Buy first, sell next day
            if state == 'idle' and buy_strength > sell_strength and buy_strength >= 35:  # Lowered from 50
                # Buy signal: Buy new position for T trading
                # Quantity should be calculated based on available cash
                # For now, use a fixed amount (could be parameter)
                buy_qty = int(10000 / price / 100) * 100  # Roughly 10k yuan worth, rounded to lots
                if buy_qty >= 100:
                    self.generate_signal(
                        symbol, 'BUY',
                        strength=buy_strength / 100,
                        metadata={
                            'quantity': buy_qty,
                            'reasons': reasons,
                            't_type': 'reverse_t_buy',
                            'entry_price': price
                        }
                    )
                    self.t_state[symbol] = 'waiting_sell'
                    self.t_entry_price[symbol] = price
                    self.t_position[symbol] = buy_qty
                    self.last_trade_date[symbol] = current_time
                    logger.info(f"Reverse T BUY: {symbol} {buy_qty} @ ¥{price:.3f}, reasons: {reasons}")

            elif state == 'waiting_sell':
                # Check strict exit conditions first (Stop Loss / Time Exit)
                sell_qty = self.t_position.get(symbol, 0)
                last_trade = self.last_trade_date.get(symbol, current_time)
                entry_price = self.t_entry_price.get(symbol, price)
                
                if sell_qty > 0:
                    # 1. Stop Loss Check
                    if price < entry_price * (1 - self.stop_loss_pct):
                        self.generate_signal(
                            symbol, 'SELL',
                            strength=1.0,  # Max strength for forced exit
                            metadata={
                                'quantity': sell_qty,
                                'reasons': [f"Stop Loss triggered (Price: {price:.3f} < Entry: {entry_price:.3f} * {(1-self.stop_loss_pct):.2f})"],
                                't_type': 'stop_loss_sell',
                                'loss': (entry_price - price) * sell_qty
                            }
                        )
                        self.t_state[symbol] = 'idle'
                        self.t_position[symbol] = 0
                        logger.info(f"Stop Loss SELL: {symbol} {sell_qty} @ ¥{price:.3f}, loss: ¥{(entry_price - price) * sell_qty:.2f}")
                        return

                    # 2. Time Exit Check (Force sell if held too long)
                    days_held = (current_time - last_trade).days
                    if days_held >= self.max_hold_days:
                        self.generate_signal(
                            symbol, 'SELL',
                            strength=0.8,
                            metadata={
                                'quantity': sell_qty,
                                'reasons': [f"Max hold time exceeded ({days_held} days)"],
                                't_type': 'time_exit_sell',
                                'profit': (price - entry_price) * sell_qty
                            }
                        )
                        self.t_state[symbol] = 'idle'
                        self.t_position[symbol] = 0
                        logger.info(f"Time Exit SELL: {symbol} {sell_qty} @ ¥{price:.3f}, days held: {days_held}")
                        return

                    # 3. Normal Profit Take Check (T+1 rule)
                    if sell_strength > buy_strength and sell_strength >= 35:
                        # Check if we can sell (T+1 rule: must wait until next day)
                        if days_held >= 1:
                            if price > entry_price:
                                self.generate_signal(
                                    symbol, 'SELL',
                                    strength=sell_strength / 100,
                                    metadata={
                                        'quantity': sell_qty,
                                        'reasons': reasons,
                                        't_type': 'reverse_t_sell',
                                        'expected_profit': (price - entry_price) * sell_qty
                                    }
                                )
                                self.t_state[symbol] = 'idle'
                                self.t_position[symbol] = 0
                                logger.info(f"Reverse T SELL: {symbol} {sell_qty} @ ¥{price:.3f}, profit: ¥{(price - entry_price) * sell_qty:.2f}")

    def get_t_status(self, symbol: str) -> Dict:
        """Get current T trading status for a symbol"""
        return {
            'state': self.t_state.get(symbol, 'idle'),
            'entry_price': self.t_entry_price.get(symbol, 0),
            't_position': self.t_position.get(symbol, 0),
            'last_trade_date': self.last_trade_date.get(symbol, None),
            'accumulated_profit': self.accumulated_profit,
            'target_profit': self.target_profit,
            'progress': (self.accumulated_profit / self.target_profit * 100) if self.target_profit > 0 else 0
        }

    def record_profit(self, profit: float):
        """Record profit from a completed T trade"""
        self.accumulated_profit += profit
        if self.target_profit > 0:
            progress = self.accumulated_profit / self.target_profit * 100
            logger.info(f"T-Trade profit: ¥{profit:.2f}, Total: ¥{self.accumulated_profit:.2f}, "
                       f"Progress: {progress:.1f}% towards ¥{self.target_profit:.2f}")
