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


async def run_backtest(strategy, symbol: str, days: int = 60):
    """Run backtest for a strategy.

    Args:
        strategy: Strategy instance
        symbol: Stock symbol
        days: Number of days to backtest
    """
    # Generate test data
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    print(f"\n{'='*60}")
    print(f"Backtesting Strategy: {strategy.name}")
    print(f"Symbol: {symbol}")
    print(f"Period: {start_date} to {end_date} ({days} days)")
    print(f"{'='*60}\n")

    # Create test data (simulate price movement)
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
            'commission_rate': 0.0003,
            'min_commission': 5.0,
            'stamp_tax_rate': 0.001
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
        result = await run_backtest(strategy, args.symbol, args.days)
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