#!/usr/bin/env python3
"""Live Trading System for 513090.SH (Hong Kong Securities ETF)

Automated T+0 trading system with:
- Real-time price monitoring
- Wave-based T trading strategy
- Risk management
- Trade notifications
- Performance tracking

Usage:
    # Paper trading (simulation)
    python live_trading_513090.py --mode paper

    # Real trading (requires broker API)
    python live_trading_513090.py --mode live --broker etrading

    # Monitor only (no trading)
    python live_trading_513090.py --mode monitor
"""
import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime, time
from typing import Dict, Optional
import signal

sys.path.insert(0, os.path.dirname(__file__))

from src.trading.live_engine import LiveTradingEngine, LiveEngineConfig
from src.trading.broker_gateway import MockBrokerGateway
from src.strategies.etf_t_trading import ETFTTradingStrategy, TradingMode
from src.backtest.engine import MarketDataEvent
from src.api.stock_api import fetch_sina_realtime_sync
from src.services.etf_analyzer import ETFAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/live_trading_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Live513090TradingSystem:
    """Live trading system specifically for 513090.SH"""

    def __init__(self, mode: str = 'paper', initial_capital: float = 100000.0,
                 initial_position: int = 52800, cost_basis: float = 2.318):
        """
        Initialize trading system

        Args:
            mode: Trading mode ('paper', 'live', 'monitor')
            initial_capital: Available cash for T trading
            initial_position: Initial shares of 513090.SH
            cost_basis: User's cost basis per share
        """
        self.etf_code = "513090.SH"
        self.mode = mode
        self.initial_capital = initial_capital
        self.initial_position = initial_position

        # Components
        self.broker = None
        self.engine = None
        self.strategy = None
        self.etf_analyzer = ETFAnalyzer(use_cache=True)

        # State
        self.is_running = False
        self.current_price = 2.033  # Current price
        self.user_cost_basis = cost_basis  # User's cost basis

        # T-trading tracking
        self.t_trades_today = []
        self.total_t_profit = 0.0
        self.accumulated_cost_reduction = 0.0

        # Market hours (China stock market)
        self.market_open = time(9, 30)
        self.market_close = time(15, 0)
        self.lunch_start = time(11, 30)
        self.lunch_end = time(13, 0)

        logger.info(f"Trading system initialized for {self.etf_code}")
        logger.info(f"Mode: {mode}, Initial capital: ¥{initial_capital:,.2f}, "
                   f"Initial position: {initial_position} shares")

    async def initialize(self):
        """Initialize all components"""

        # 1. Setup broker
        if self.mode == 'live':
            # TODO: Integrate with real broker API (e.g., eTrading, XTP, etc.)
            raise NotImplementedError("Real broker API integration not yet implemented")
        else:
            # Use mock broker for paper trading
            self.broker = MockBrokerGateway(
                initial_cash=self.initial_capital,
                config={
                    'fill_delay': 0.1,  # 100ms simulated fill delay
                    'slippage_rate': 0.0001  # 0.01% slippage
                }
            )

            # Set initial position
            if self.initial_position > 0:
                # Simulate existing position at user's cost basis
                await self.broker.connect()
                self.broker._add_initial_position(
                    symbol=self.etf_code,
                    quantity=self.initial_position,
                    avg_price=self.user_cost_basis
                )
                logger.info(f"Set initial position: {self.initial_position} shares @ ¥{self.user_cost_basis:.3f}")

        # 2. Configure strategy based on volatility analysis
        # Based on analyze_volatility.py results:
        # - Average amplitude: 2.80%
        # - 65% days have amplitude >= 2%
        # - Average wave: 3 days, +5.37% / -5.88%
        # - Current support: ¥2.093, resistance: ¥2.333

        # Calculate T-trading quantity based on position (40% for T)
        t_quantity = int(self.initial_position * 0.4 / 100) * 100  # Round to lots

        strategy_config = {
            'mode': 'regular_t',  # User has base position, use regular T
            't_ratio': 0.4,  # Trade 40% of position
            'base_position_ratio': 0.6,  # Keep 60% as base
            't_quantity': t_quantity,  # Fixed T quantity: ~21,100 shares

            # Risk management
            'stop_loss_pct': 0.03,  # 3% stop loss
            'take_profit_pct': 0.007,  # 0.7% take profit target
            'max_hold_days': 3,  # Max hold 3 days

            # Technical indicators (tuned for 513090.SH)
            'rsi_period': 14,
            'rsi_oversold': 35,
            'rsi_overbought': 65,
            'support_lookback': 10,

            # ETF specific
            'premium_threshold': 1.0,  # Sell if premium > 1%
            'discount_threshold': -1.5,  # Buy if discount < -1.5%

            # User's breakeven tracking
            'cost_basis': self.user_cost_basis,
            'target_profit': (self.user_cost_basis - self.current_price) * self.initial_position,
        }

        self.strategy = ETFTTradingStrategy(config=strategy_config)
        logger.info(f"Strategy configured: {strategy_config}")

        # 3. Setup live engine
        engine_config = LiveEngineConfig(
            initial_capital=self.initial_capital,
            enable_trading=(self.mode != 'monitor'),
            max_orders_per_second=10,
            heartbeat_interval=30
        )

        self.engine = LiveTradingEngine(
            broker=self.broker,
            config=engine_config
        )

        self.engine.add_strategy(self.strategy)

        # 4. Start engine
        await self.engine.start()
        logger.info("Trading engine started")

    async def market_data_loop(self):
        """Real-time market data polling loop"""
        poll_interval = 3  # Poll every 3 seconds

        while self.is_running:
            try:
                # Check if market is open
                now = datetime.now().time()
                if not self._is_market_open(now):
                    logger.debug("Market closed, waiting...")
                    await asyncio.sleep(60)  # Check every minute
                    continue

                # Fetch real-time quote
                quote = fetch_sina_realtime_sync(self.etf_code)

                if quote:
                    price = quote.get('current_price')

                    if price and price > 0:
                        self.current_price = price

                        # Get ETF premium rate
                        premium_data = self.etf_analyzer.get_premium_discount(self.etf_code)
                        premium_rate = premium_data.get('premium_rate', 0.0) if premium_data else 0.0

                        # Update strategy's premium rate
                        if hasattr(self.strategy, 'update_premium_rate'):
                            self.strategy.update_premium_rate(self.etf_code, premium_rate)

                        # Create market data event
                        market_event = MarketDataEvent(
                            timestamp=datetime.now(),
                            symbol=self.etf_code,
                            price_data={
                                'close': price,
                                'high': quote.get('high_price', price),
                                'low': quote.get('low_price', price),
                                'volume': quote.get('volume', 0),
                                'open': quote.get('open_price', price)
                            }
                        )

                        # Send to engine
                        await self.engine.on_market_data(market_event)

                        # Log status
                        cost_diff = ((price / self.user_cost_basis - 1) * 100)
                        logger.info(
                            f"[{self.etf_code}] Price: ¥{price:.3f}, "
                            f"Premium: {premium_rate:+.2f}%, "
                            f"Cost P/L: {cost_diff:+.2f}%"
                        )

                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error in market data loop: {e}", exc_info=True)
                await asyncio.sleep(poll_interval)

    async def status_loop(self):
        """Status reporting loop"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Report every minute

                # Get account status
                if self.broker and await self.broker.is_connected():
                    account = await self.broker.get_account()
                    positions = await self.broker.get_positions()

                    total_value = account['cash_balance'] + account['stock_value']
                    total_pnl = total_value - (self.initial_capital + self.initial_position * self.user_cost_basis)

                    logger.info("=" * 70)
                    logger.info("Account Status:")
                    logger.info(f"  Cash: ¥{account['cash_balance']:,.2f}")
                    logger.info(f"  Stock Value: ¥{account['stock_value']:,.2f}")
                    logger.info(f"  Total Value: ¥{total_value:,.2f}")
                    logger.info(f"  Total P/L: ¥{total_pnl:,.2f} ({total_pnl/(self.initial_capital + self.initial_position * self.user_cost_basis)*100:+.2f}%)")

                    if positions:
                        logger.info("\nPositions:")
                        for pos in positions:
                            pos_pnl = (self.current_price - pos.avg_price) * pos.quantity
                            logger.info(f"  {pos.symbol}: {pos.quantity} shares @ ¥{pos.avg_price:.3f}, "
                                      f"P/L: ¥{pos_pnl:,.2f}")

                    # Get strategy status
                    if self.strategy:
                        t_status = self.strategy.get_t_status(self.etf_code)
                        logger.info(f"\nT Trading Status:")
                        logger.info(f"  State: {t_status.get('state', 'unknown')}")
                        logger.info(f"  T Position: {t_status.get('t_position', 0)} shares")
                        if t_status.get('entry_price'):
                            logger.info(f"  Entry Price: ¥{t_status['entry_price']:.3f}")
                        logger.info(f"  Accumulated Profit: ¥{t_status.get('accumulated_profit', 0):,.2f}")
                        if t_status.get('target_profit', 0) > 0:
                            logger.info(f"  Breakeven Progress: {t_status.get('progress', 0):.1f}%")

                    logger.info("=" * 70)

            except Exception as e:
                logger.error(f"Error in status loop: {e}", exc_info=True)

    def _is_market_open(self, current_time: time) -> bool:
        """Check if market is currently open"""
        # Morning session: 9:30 - 11:30
        morning_open = self.market_open <= current_time < self.lunch_start
        # Afternoon session: 13:00 - 15:00
        afternoon_open = self.lunch_end <= current_time < self.market_close

        return morning_open or afternoon_open

    async def start(self):
        """Start the trading system"""
        logger.info("=" * 70)
        logger.info("Starting Live Trading System for 513090.SH")
        logger.info("=" * 70)

        self.is_running = True

        # Initialize components
        await self.initialize()

        # Start background tasks
        tasks = [
            asyncio.create_task(self.market_data_loop()),
            asyncio.create_task(self.status_loop())
        ]

        # Wait for all tasks
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")

    async def stop(self):
        """Stop the trading system"""
        logger.info("Stopping trading system...")

        self.is_running = False

        # Stop engine
        if self.engine:
            await self.engine.stop()

        logger.info("Trading system stopped")

    def print_startup_info(self):
        """Print startup information"""
        loss = (self.current_price - self.user_cost_basis) * self.initial_position
        loss_pct = (self.current_price / self.user_cost_basis - 1) * 100
        t_qty = int(self.initial_position * 0.4 / 100) * 100
        profit_per_t = t_qty * 0.015  # Estimated profit per T (0.7% price diff)
        t_needed = int(abs(loss) / profit_per_t) + 1

        print("\n" + "=" * 70)
        print("513090.SH 香港科技50ETF 做T交易系统")
        print("=" * 70)
        print(f"\n运行模式: {self.mode.upper()}")
        print(f"ETF代码: {self.etf_code}")
        print(f"\n【持仓信息】")
        print(f"  持仓数量: {self.initial_position:,} 股")
        print(f"  成本价:   ¥{self.user_cost_basis:.3f}")
        print(f"  现价:     ¥{self.current_price:.3f}")
        print(f"  持仓成本: ¥{self.user_cost_basis * self.initial_position:,.2f}")
        print(f"  当前市值: ¥{self.current_price * self.initial_position:,.2f}")
        print(f"  浮动盈亏: ¥{loss:,.2f} ({loss_pct:+.2f}%)")
        print(f"\n【做T配置】")
        print(f"  底仓:     {self.initial_position - t_qty:,} 股 (60%) - 持有不动")
        print(f"  机动仓:   {t_qty:,} 股 (40%) - 用于做T")
        print(f"  可用资金: ¥{self.initial_capital:,.2f}")
        print(f"\n【回本计划】")
        print(f"  需回本:   ¥{abs(loss):,.2f}")
        print(f"  单次预期: ¥{profit_per_t:,.2f} (价差0.7%)")
        print(f"  预计次数: ~{t_needed} 次")
        print(f"\n【策略参数】")
        print(f"  买入信号: RSI<35, 接近支撑位, 折价>1.5%")
        print(f"  卖出信号: RSI>65, 接近阻力位, 溢价>1%")
        print(f"  止损: 3% | 止盈: 0.7%")
        print("\n" + "=" * 70)
        print("\n按 Ctrl+C 停止系统\n")


async def main():
    parser = argparse.ArgumentParser(description='Live Trading System for 513090.SH')
    parser.add_argument('--mode', choices=['paper', 'live', 'monitor'],
                       default='paper',
                       help='Trading mode (default: paper)')
    parser.add_argument('--capital', type=float, default=100000.0,
                       help='Available cash for T trading (default: 100000)')
    parser.add_argument('--position', type=int, default=52800,
                       help='Initial position in shares (default: 52800)')
    parser.add_argument('--cost', type=float, default=2.318,
                       help='Cost basis per share (default: 2.318)')

    args = parser.parse_args()

    # Create trading system
    system = Live513090TradingSystem(
        mode=args.mode,
        initial_capital=args.capital,
        initial_position=args.position,
        cost_basis=args.cost
    )

    # Print startup info
    system.print_startup_info()

    # Setup graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(system.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start system
    try:
        await system.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await system.stop()


if __name__ == '__main__':
    # Create logs directory if not exists
    os.makedirs('logs', exist_ok=True)

    # Run system
    asyncio.run(main())
