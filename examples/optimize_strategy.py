# examples/optimize_strategy.py - Strategy parameter optimization
"""
Strategy parameter optimization using grid search.

Usage:
    python examples/optimize_strategy.py --strategy moving_average --symbol 000977.SZ
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path
import argparse
import pandas as pd
from typing import Dict, List, Tuple
import itertools

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine
from src.strategies import MovingAverageCrossover, MeanReversion, Momentum


async def backtest_with_params(strategy_class, params: Dict, symbol: str, df: pd.DataFrame, days: int):
    """Run backtest with specific parameters."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Create strategy with custom params
    strategy = strategy_class(config=params)

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
    engine.load_market_data(symbol, df)

    # Add strategy
    engine.add_strategy(strategy)

    # Run backtest
    results = await engine.run()

    return results


async def optimize_moving_average(symbol: str, df: pd.DataFrame, days: int):
    """Optimize Moving Average Crossover strategy parameters."""
    print("\n" + "="*70)
    print("OPTIMIZING MOVING AVERAGE CROSSOVER STRATEGY")
    print("="*70)

    # Parameter grid
    fast_periods = [3, 5, 8, 10]
    slow_periods = [10, 15, 20, 30]

    best_result = None
    best_params = None
    best_return = -999999

    results_list = []

    total_combinations = len(fast_periods) * len(slow_periods)
    current = 0

    for fast, slow in itertools.product(fast_periods, slow_periods):
        if fast >= slow:
            continue

        current += 1
        params = {
            'fast_period': fast,
            'slow_period': slow,
            'signal_strength': 0.8
        }

        print(f"\nTesting [{current}/{total_combinations}]: MA({fast},{slow})...", end='')

        result = await backtest_with_params(
            MovingAverageCrossover,
            params,
            symbol,
            df,
            days
        )

        total_return = result['total_return']
        sharpe = result['sharpe_ratio']
        trades = result['total_trades']

        print(f" Return={total_return:>7.2%}, Sharpe={sharpe:>6.3f}, Trades={trades:>3d}")

        results_list.append({
            'params': f"MA({fast},{slow})",
            'fast': fast,
            'slow': slow,
            'return': total_return,
            'sharpe': sharpe,
            'trades': trades,
            'max_dd': result['max_drawdown']
        })

        if total_return > best_return:
            best_return = total_return
            best_params = params
            best_result = result

    # Display results
    print("\n" + "="*70)
    print("OPTIMIZATION RESULTS (sorted by return)")
    print("="*70)
    print(f"{'Parameters':<15} {'Return':>10} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>8}")
    print("-" * 70)

    # Sort by return
    results_list.sort(key=lambda x: x['return'], reverse=True)

    for i, r in enumerate(results_list[:10], 1):  # Top 10
        marker = " ★" if i == 1 else ""
        print(
            f"{r['params']:<15} "
            f"{r['return']:>9.2%} "
            f"{r['sharpe']:>8.3f} "
            f"{r['max_dd']:>8.2%} "
            f"{r['trades']:>8d}{marker}"
        )

    print("="*70)
    print(f"\nBEST PARAMETERS: MA({best_params['fast_period']},{best_params['slow_period']})")
    print(f"Total Return: {best_result['total_return']:.2%}")
    print(f"Sharpe Ratio: {best_result['sharpe_ratio']:.3f}")
    print(f"Max Drawdown: {best_result['max_drawdown']:.2%}")
    print(f"Total Trades: {best_result['total_trades']}")

    return best_params, best_result


async def optimize_mean_reversion(symbol: str, df: pd.DataFrame, days: int):
    """Optimize Mean Reversion strategy parameters."""
    print("\n" + "="*70)
    print("OPTIMIZING MEAN REVERSION STRATEGY")
    print("="*70)

    # Parameter grid
    bb_periods = [15, 20, 25]
    bb_std_devs = [1.5, 2.0, 2.5]
    rsi_oversolds = [25, 30, 35]

    best_result = None
    best_params = None
    best_return = -999999

    results_list = []

    total_combinations = len(bb_periods) * len(bb_std_devs) * len(rsi_oversolds)
    current = 0

    for bb_period, bb_std, rsi_os in itertools.product(bb_periods, bb_std_devs, rsi_oversolds):
        current += 1
        params = {
            'bb_period': bb_period,
            'bb_std_dev': bb_std,
            'rsi_period': 14,
            'rsi_oversold': rsi_os,
            'rsi_overbought': 70,
            'signal_strength': 0.7
        }

        print(f"\nTesting [{current}/{total_combinations}]: BB({bb_period},{bb_std:.1f}), RSI<{rsi_os}...", end='')

        result = await backtest_with_params(
            MeanReversion,
            params,
            symbol,
            df,
            days
        )

        total_return = result['total_return']
        sharpe = result['sharpe_ratio']
        trades = result['total_trades']

        print(f" Return={total_return:>7.2%}, Sharpe={sharpe:>6.3f}, Trades={trades:>3d}")

        results_list.append({
            'params': f"BB({bb_period},{bb_std:.1f}),RSI<{rsi_os}",
            'return': total_return,
            'sharpe': sharpe,
            'trades': trades,
            'max_dd': result['max_drawdown']
        })

        if total_return > best_return:
            best_return = total_return
            best_params = params
            best_result = result

    # Display results
    print("\n" + "="*70)
    print("OPTIMIZATION RESULTS (sorted by return)")
    print("="*70)
    print(f"{'Parameters':<30} {'Return':>10} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>8}")
    print("-" * 70)

    results_list.sort(key=lambda x: x['return'], reverse=True)

    for i, r in enumerate(results_list[:10], 1):
        marker = " ★" if i == 1 else ""
        print(
            f"{r['params']:<30} "
            f"{r['return']:>9.2%} "
            f"{r['sharpe']:>8.3f} "
            f"{r['max_dd']:>8.2%} "
            f"{r['trades']:>8d}{marker}"
        )

    print("="*70)
    print(f"\nBEST PARAMETERS: {best_params}")
    print(f"Total Return: {best_result['total_return']:.2%}")
    print(f"Sharpe Ratio: {best_result['sharpe_ratio']:.3f}")

    return best_params, best_result


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Optimize strategy parameters")
    parser.add_argument(
        '--strategy',
        type=str,
        choices=['moving_average', 'mean_reversion', 'momentum'],
        default='moving_average',
        help='Strategy to optimize'
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
        default=120,
        help='Number of days to backtest (recommended: 90-180)'
    )

    args = parser.parse_args()

    # Fetch real data
    print(f"\nFetching real market data for {args.symbol}...")
    try:
        from src.api.stock_api import fetch_history_df
        df = fetch_history_df(args.symbol, days=args.days + 30)

        if df is None or df.empty:
            print("✗ Failed to fetch real data")
            return 1

        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df = df.tail(args.days)

        print(f"✓ Successfully loaded {len(df)} days of real data")
        print(f"  Date range: {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
        print(f"  Price range: ¥{df['close'].min():.2f} - ¥{df['close'].max():.2f}")

    except Exception as e:
        print(f"✗ Error fetching data: {e}")
        return 1

    # Run optimization
    if args.strategy == 'moving_average':
        best_params, best_result = await optimize_moving_average(args.symbol, df, args.days)
    elif args.strategy == 'mean_reversion':
        best_params, best_result = await optimize_mean_reversion(args.symbol, df, args.days)
    else:
        print(f"Optimization not yet implemented for {args.strategy}")
        return 1

    print("\nOptimization completed successfully!")
    print("\nRecommended configuration for config/strategies.yaml:")
    print("-" * 70)
    import yaml
    print(yaml.dump({args.strategy: best_params}, default_flow_style=False))

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
