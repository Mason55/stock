# examples/backtest_strategies.py - Strategy backtesting examples
"""
Example scripts for backtesting different trading strategies.

Usage:
    python examples/backtest_strategies.py --strategy moving_average
    python examples/backtest_strategies.py --strategy mean_reversion
    python examples/backtest_strategies.py --strategy momentum
    python examples/backtest_strategies.py --combination conservative
"""

import asyncio
import sys
import argparse
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine
from src.strategies.strategy_loader import StrategyLoader


async def run_backtest(strategy, symbol: str, days: int = 60, use_real_data: bool = True):
    """Run backtest for a strategy.

    Args:
        strategy: Strategy instance
        symbol: Stock symbol
        days: Number of days to backtest
        use_real_data: Whether to use real market data (default: True)
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    print(f"\n{'='*60}")
    print(f"Backtesting Strategy: {strategy.name}")
    print(f"Symbol: {symbol}")
    print(f"Period: {start_date} to {end_date} ({days} days)")
    print(f"{'='*60}\n")

    # Try to fetch real historical data
    test_df = None
    if use_real_data:
        try:
            from src.api.stock_api import fetch_history_df
            print("Fetching real market data...")
            test_df = fetch_history_df(symbol, days=days + 30)  # Fetch extra for buffer

            if test_df is not None and not test_df.empty:
                # Ensure date column is datetime
                test_df['date'] = pd.to_datetime(test_df['date'])
                # Sort by date
                test_df = test_df.sort_values('date').reset_index(drop=True)
                # Take last N days
                test_df = test_df.tail(days)
                print(f"✓ Successfully loaded {len(test_df)} days of real data")
            else:
                print("⚠ Failed to fetch real data, falling back to simulated data")
                test_df = None
        except Exception as e:
            print(f"⚠ Error fetching real data: {e}")
            print("  Falling back to simulated data")
            test_df = None

    # Fallback: Generate simulated test data
    if test_df is None:
        print("Using simulated market data...")
        base_price = 40.0
        test_data = []

        for i in range(days):
            current_date = start_date + timedelta(days=i)

            # Simulate different price patterns for different strategies
            if "moving_average" in strategy.name:
                # Trending market
                price = base_price + (i * 0.1) + (i % 5) * 0.5
            elif "mean_reversion" in strategy.name:
                # Oscillating market
                import math
                price = base_price + 5 * math.sin(i * 0.3)
            elif "momentum" in strategy.name:
                # Strong trend with pullbacks
                trend = i * 0.15
                volatility = (i % 7 - 3) * 0.3
                price = base_price + trend + volatility
            else:
                price = base_price + (i * 0.05)

            test_data.append({
                'date': current_date,
                'open': price - 0.2,
                'high': price + 0.3,
                'low': price - 0.3,
                'close': price,
                'volume': 8500000 + i * 100000
            })

        test_df = pd.DataFrame(test_data)

    # Create backtest engine
    config = {
        'costs': {
            'commission_rate': 0.0001,
            'min_commission': 5.0,
            'transfer_fee_rate': 0.0001,
            'stamp_tax_rate': 0.0
        },
        'risk': {
            'max_position_pct': 0.1,
            'max_total_exposure': 0.95
        }
    }

    engine = BacktestEngine(
        start_date=start_date,
        end_date=end_date,
        initial_capital=1000000.0,
        config=config
    )

    # Load market data
    engine.load_market_data(symbol, test_df)

    # Add strategy
    engine.add_strategy(strategy)

    # Run backtest
    print("Running backtest...")
    results = await engine.run()

    # Display strategy indicators (MA values, etc.)
    print("\nSTRATEGY INDICATORS (last 5 days):")
    print("-" * 60)
    for i in range(max(0, len(test_df) - 5), len(test_df)):
        row = test_df.iloc[i]
        date_str = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])[:10]
        print(f"{date_str}: Close=¥{float(row['close']):.2f}, High=¥{float(row['high']):.2f}, Low=¥{float(row['low']):.2f}")

        # Show MA values if strategy has them
        indicators = strategy.get_indicators(symbol)
        if indicators:
            if 'fast_ma' in indicators and 'slow_ma' in indicators:
                print(f"  MA({strategy.fast_period})=¥{indicators['fast_ma']:.2f}, MA({strategy.slow_period})=¥{indicators['slow_ma']:.2f}")
            elif 'bb_upper' in indicators:
                print(f"  BB_Upper=¥{indicators['bb_upper']:.2f}, BB_Lower=¥{indicators['bb_lower']:.2f}, RSI={indicators.get('rsi', 0):.2f}")
            elif 'momentum' in indicators:
                print(f"  Momentum={indicators['momentum']:.2f}%")

    # Display results
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)
    print(f"Initial Capital:    ¥{results['initial_capital']:,.2f}")
    print(f"Final Value:        ¥{results['final_value']:,.2f}")
    print(f"Total Return:       {results['total_return']:.2%}")
    print(f"Annualized Return:  {results['annualized_return']:.2%}")
    print(f"Volatility:         {results['volatility']:.2%}")
    print(f"Sharpe Ratio:       {results['sharpe_ratio']:.3f}")
    print(f"Max Drawdown:       {results['max_drawdown']:.2%}")
    print(f"Total Trades:       {results['total_trades']}")

    # Display trades
    if results['trades']:
        print(f"\nTRADE HISTORY:")
        print("-" * 60)
        for i, trade in enumerate(results['trades'][:10], 1):  # Show first 10
            print(
                f"{i}. {trade['timestamp'].strftime('%Y-%m-%d')} "
                f"{trade['side'].value:4s} {trade['quantity']:5d} shares "
                f"@ ¥{float(trade['price']):6.2f}"
            )
        if len(results['trades']) > 10:
            print(f"... and {len(results['trades']) - 10} more trades")

    # Display final positions
    if results['positions']:
        print(f"\nFINAL POSITIONS:")
        print("-" * 60)
        for symbol, qty in results['positions'].items():
            if qty > 0:
                print(f"{symbol}: {qty} shares")

    print("="*60 + "\n")

    return results


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Backtest trading strategies")
    parser.add_argument(
        '--strategy',
        type=str,
        choices=['moving_average', 'mean_reversion', 'momentum', 'all'],
        default='moving_average',
        help='Strategy to backtest'
    )
    parser.add_argument(
        '--combination',
        type=str,
        help='Strategy combination name (e.g., conservative, aggressive, balanced)'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default='600036.SH',
        help='Stock symbol to test'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=60,
        help='Number of days to backtest'
    )
    parser.add_argument(
        '--use-simulated',
        action='store_true',
        help='Use simulated data instead of real market data'
    )

    args = parser.parse_args()

    # Load strategies
    loader = StrategyLoader()

    strategies = []
    if args.combination:
        # Load strategy combination
        strategies = loader.load_combination(args.combination)
        if not strategies:
            print(f"Error: Combination '{args.combination}' not found")
            print(f"Available combinations: {loader.list_combinations()}")
            return 1
    elif args.strategy == 'all':
        # Load all enabled strategies
        strategies = loader.load_strategies()
    else:
        # Load single strategy
        strategy_map = {
            'moving_average': 'moving_average_crossover',
            'mean_reversion': 'mean_reversion',
            'momentum': 'momentum'
        }
        strategy_name = strategy_map[args.strategy]
        strategy = loader.load_strategy(strategy_name)
        if not strategy:
            print(f"Error: Failed to load strategy '{strategy_name}'")
            return 1
        strategies = [strategy]

    if not strategies:
        print("Error: No strategies loaded")
        return 1

    # Run backtests
    print(f"\nBacktesting {len(strategies)} strategy(ies)...")

    results_list = []
    for strategy in strategies:
        result = await run_backtest(
            strategy,
            args.symbol,
            args.days,
            use_real_data=not args.use_simulated
        )
        results_list.append((strategy.name, result))

    # Compare results if multiple strategies
    if len(results_list) > 1:
        print("\n" + "="*60)
        print("STRATEGY COMPARISON")
        print("="*60)
        print(f"{'Strategy':<30} {'Return':>10} {'Sharpe':>8} {'Trades':>8}")
        print("-" * 60)
        for name, result in results_list:
            print(
                f"{name:<30} "
                f"{result['total_return']:>9.2%} "
                f"{result['sharpe_ratio']:>8.3f} "
                f"{result['total_trades']:>8d}"
            )
        print("="*60 + "\n")

    print("Backtest completed successfully!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)