#!/usr/bin/env python3
"""Backtest ETF T-Trading Strategy

Usage:
    python backtest_t_trading.py 513090.SH --days 60
    python backtest_t_trading.py 513090.SH --mode regular_t --t_ratio 0.3
"""
import argparse
import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Dict

from src.backtest.engine import BacktestEngine
from src.strategies.etf_t_trading import ETFTTradingStrategy
from src.api.stock_api import fetch_history_df
from src.models.trading import OrderStatus, OrderSide

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def run_backtest(etf_code: str, config: Dict):
    """Run backtest for ETF T-trading strategy"""

    print(f"{'=' * 70}")
    print(f"ETF做T策略回测 - {etf_code}")
    print(f"{'=' * 70}\n")

    # Fetch historical data
    days = config.get('days', 60)
    print(f"正在获取{days}天历史数据...")

    df = fetch_history_df(etf_code, days=days)
    if df is None or df.empty:
        print(f"⚠️  无法获取{etf_code}的历史数据")
        return

    print(f"✓ 获取到{len(df)}条数据记录")
    print(f"  日期范围: {df.iloc[0]['date']} 至 {df.iloc[-1]['date']}\n")

    # Extract date range
    start_date = df.iloc[0]['date']
    end_date = df.iloc[-1]['date']

    # Convert to date objects if they're not already
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date[:10], '%Y-%m-%d').date()
    elif hasattr(start_date, 'date'):
        start_date = start_date.date()

    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date[:10], '%Y-%m-%d').date()
    elif hasattr(end_date, 'date'):
        end_date = end_date.date()

    # Configure strategy
    strategy_config = {
        'mode': config.get('mode', 'auto'),
        't_ratio': config.get('t_ratio', 0.3),
        'rsi_period': config.get('rsi_period', 14),
        'rsi_oversold': config.get('rsi_oversold', 30),
        'rsi_overbought': config.get('rsi_overbought', 70),
        'premium_threshold': config.get('premium_threshold', 1.0),
        'discount_threshold': config.get('discount_threshold', -0.5),
        'support_lookback': config.get('support_lookback', 20)
    }

    print("策略配置:")
    for key, value in strategy_config.items():
        print(f"  {key}: {value}")
    print()

    # Initialize strategy
    strategy = ETFTTradingStrategy(config=strategy_config)

    # Configure backtest engine
    initial_capital = config.get('initial_capital', 100000)

    engine_config = {
        'market': {
            'ignore_trading_hours': True  # Ignore trading hours check for backtest
        },
        'costs': {
            'commission_rate': 0.0003,  # 0.03% commission
            'min_commission': 5.0,  # Minimum 5 yuan
            'slippage_rate': 0.0001  # 0.01% slippage
        },
        'risk': {
            'max_position_size': 1.0,  # Max 100% of capital in one position
            'max_leverage': 1.0  # No leverage for A-shares
        }
    }

    # Run backtest
    print(f"开始回测 (初始资金: ¥{initial_capital:,.0f})...")
    engine = BacktestEngine(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        config=engine_config
    )

    # Add strategy and load data
    engine.add_strategy(strategy)
    engine.load_market_data(etf_code, df)

    # Run the backtest
    try:
        await engine.run()
    except Exception as e:
        print(f"⚠️  回测运行出错: {e}")
        import traceback
        traceback.print_exc()
        return

    # Get results from portfolio
    portfolio = engine.portfolio

    print(f"\n{'=' * 70}")
    print("回测结果")
    print(f"{'=' * 70}\n")

    # Calculate final capital - use portfolio's total_value directly
    final_capital = portfolio.total_value

    total_return = final_capital - initial_capital
    total_return_pct = (total_return / initial_capital) * 100

    # Annualized return
    days_elapsed = (end_date - start_date).days
    years = days_elapsed / 365.0
    annualized_return = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

    print(f"【收益指标】")
    print(f"  初始资金: ¥{initial_capital:,.2f}")
    print(f"  最终资金: ¥{final_capital:,.2f}")
    print(f"  总收益: ¥{total_return:,.2f}")
    print(f"  总收益率: {total_return_pct:.2f}%")
    print(f"  年化收益率: {annualized_return:.2f}%\n")

    # Trade statistics
    all_orders = list(portfolio.orders.values())
    filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]
    total_trades = len(filled_orders)

    print(f"【订单统计】")
    print(f"  总订单数: {len(all_orders)}")
    print(f"  已成交: {len(filled_orders)}")
    print(f"  其他状态: {len(all_orders) - len(filled_orders)}")

    if len(all_orders) > len(filled_orders):
        print(f"\n  未成交订单状态分布:")
        from collections import Counter
        status_count = Counter(str(o.status) for o in all_orders if o.status != OrderStatus.FILLED)
        for status, count in status_count.items():
            print(f"    {status}: {count}")
    print()

    # Calculate wins/losses (simplified - pair buy/sell orders)
    trades_by_symbol = {}
    for order in filled_orders:
        symbol = order.symbol
        if symbol not in trades_by_symbol:
            trades_by_symbol[symbol] = []
        trades_by_symbol[symbol].append(order)

    winning_trades = 0
    losing_trades = 0
    total_profit = 0
    total_loss = 0

    for symbol, orders in trades_by_symbol.items():
        # Pair buy and sell orders
        buys = [o for o in orders if o.side == OrderSide.BUY]
        sells = [o for o in orders if o.side == OrderSide.SELL]

        for i in range(min(len(buys), len(sells))):
            buy_order = buys[i]
            sell_order = sells[i]
            # Use avg_fill_price for filled orders
            buy_price = float(buy_order.avg_fill_price) if hasattr(buy_order, 'avg_fill_price') and buy_order.avg_fill_price else 0
            sell_price = float(sell_order.avg_fill_price) if hasattr(sell_order, 'avg_fill_price') and sell_order.avg_fill_price else 0
            profit = (sell_price - buy_price) * buy_order.quantity

            if profit > 0:
                winning_trades += 1
                total_profit += profit
            else:
                losing_trades += 1
                total_loss += abs(profit)

    win_rate = (winning_trades / (winning_trades + losing_trades) * 100) if (winning_trades + losing_trades) > 0 else 0
    avg_win = total_profit / winning_trades if winning_trades > 0 else 0
    avg_loss = total_loss / losing_trades if losing_trades > 0 else 0

    print(f"【交易统计】")
    print(f"  总交易次数: {total_trades}")
    print(f"  盈利次数: {winning_trades}")
    print(f"  亏损次数: {losing_trades}")
    print(f"  胜率: {win_rate:.2f}%")
    print(f"  平均盈利: ¥{avg_win:.2f}")
    print(f"  平均亏损: ¥{avg_loss:.2f}\n")

    # Display recent trades
    if filled_orders:
        print(f"【交易记录】 (最近{min(10, len(filled_orders))}笔)")
        print(f"{'订单ID':<12} {'方向':<10} {'数量':<8} {'价格':<10} {'金额':<12} {'状态':<10}")
        print('-' * 70)

        for order in filled_orders[-10:]:
            order_id = order.order_id[:12] if hasattr(order, 'order_id') else 'N/A'
            side = str(order.side).split('.')[-1]  # Extract 'BUY' or 'SELL' from 'OrderSide.BUY'
            quantity = order.quantity
            price = float(order.avg_fill_price) if hasattr(order, 'avg_fill_price') and order.avg_fill_price else 0
            amount = quantity * price
            status = str(order.status).split('.')[-1]  # Extract status name

            print(f"{order_id:<12} {side:<10} {quantity:<8} ¥{price:<9.3f} ¥{amount:<11,.2f} {status:<10}")

    print(f"\n{'=' * 70}")

    # Summary
    print(f"\n策略总结:")
    print(f"  策略类型: {config.get('mode', 'auto')}")
    print(f"  做T比例: {config.get('t_ratio', 0.3) * 100:.0f}%")
    print(f"  测试周期: {days}天")

    if total_return > 0:
        print(f"  ✓ 策略盈利，总收益 ¥{total_return:,.2f} ({total_return_pct:.2f}%)")
    else:
        print(f"  ⚠️  策略亏损，总亏损 ¥{abs(total_return):,.2f} ({abs(total_return_pct):.2f}%)")


def main():
    parser = argparse.ArgumentParser(description='Backtest ETF T-Trading Strategy')
    parser.add_argument('etf_code', help='ETF code (e.g., 513090.SH)')
    parser.add_argument('--days', type=int, default=60,
                       help='Backtest period in days (default: 60)')
    parser.add_argument('--mode', choices=['regular_t', 'reverse_t', 'auto'],
                       default='auto',
                       help='Trading mode (default: auto)')
    parser.add_argument('--t_ratio', type=float, default=0.3,
                       help='T trading position ratio (default: 0.3)')
    parser.add_argument('--initial_capital', type=float, default=100000,
                       help='Initial capital (default: 100000)')
    parser.add_argument('--rsi_oversold', type=int, default=30,
                       help='RSI oversold threshold (default: 30)')
    parser.add_argument('--rsi_overbought', type=int, default=70,
                       help='RSI overbought threshold (default: 70)')

    args = parser.parse_args()

    config = {
        'days': args.days,
        'mode': args.mode,
        't_ratio': args.t_ratio,
        'initial_capital': args.initial_capital,
        'rsi_oversold': args.rsi_oversold,
        'rsi_overbought': args.rsi_overbought
    }

    asyncio.run(run_backtest(args.etf_code, config))


if __name__ == '__main__':
    main()
