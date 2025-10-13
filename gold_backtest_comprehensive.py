#!/usr/bin/env python3
# test_gold_backtest.py - Comprehensive gold stocks backtest analysis
"""
Custom backtest script for gold stocks with detailed analysis
"""
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.backtest.engine import BacktestEngine
from src.strategies.moving_average import MovingAverageCrossover
from src.strategies.mean_reversion import MeanReversion
from src.strategies.momentum import Momentum
from src.api.stock_api import fetch_history_df


async def run_backtest(symbol, strategy_name, strategy, days=120):
    """Run backtest for a single strategy"""
    print(f"\n{'='*70}")
    print(f"Running backtest: {strategy_name} on {symbol}")
    print(f"{'='*70}")

    # Fetch real data
    print(f"Fetching {days} days of data...")
    hist_data = fetch_history_df(symbol, days=days)

    if hist_data is None or hist_data.empty:
        print(f"❌ Failed to fetch data for {symbol}")
        return None

    print(f"✓ Loaded {len(hist_data)} trading days")
    print(f"  Date range: {hist_data['date'].min()} to {hist_data['date'].max()}")
    print(f"  Price range: ¥{hist_data['close'].min():.2f} - ¥{hist_data['close'].max():.2f}")

    # Calculate backtest period
    end_date = hist_data['date'].max()
    start_date = hist_data['date'].min()

    # Convert to date objects
    if hasattr(end_date, 'date'):
        end_date = end_date.date()
    if hasattr(start_date, 'date'):
        start_date = start_date.date()

    # Initialize engine
    engine = BacktestEngine(
        start_date=start_date,
        end_date=end_date,
        initial_capital=1000000.0,
        config={
            'costs': {
                'commission_rate': 0.0003,  # 0.03%
                'min_commission': 5.0,
                'stamp_duty_rate': 0.001     # 0.1% on sell
            }
        }
    )

    # Load data
    engine.load_market_data(symbol, hist_data)

    # Add strategy
    engine.add_strategy(strategy)

    # Run backtest
    print("\nRunning backtest...")
    results = await engine.run()

    # Display results
    print(f"\n{'='*70}")
    print(f"RESULTS: {strategy_name}")
    print(f"{'='*70}")
    print(f"Initial Capital:    ¥{results['initial_capital']:,.2f}")
    print(f"Final Value:        ¥{results['final_value']:,.2f}")
    print(f"Total Return:       {results['total_return']:.2%}")
    print(f"Annualized Return:  {results['annualized_return']:.2%}")
    print(f"Sharpe Ratio:       {results['sharpe_ratio']:.3f}")
    print(f"Max Drawdown:       {results['max_drawdown']:.2%}")
    print(f"Total Trades:       {results['total_trades']}")

    if results['total_trades'] > 0:
        # Calculate win rate
        winning_trades = sum(1 for t in results['trades']
                           if t['side'].value == 'SELL' and
                           float(t['price']) > float(results['trades'][0]['price']))
        win_rate = winning_trades / max(1, results['total_trades'] // 2)
        print(f"Win Rate:           {win_rate:.1%}")

        # Show trades
        print(f"\nTrade History:")
        for i, trade in enumerate(results['trades'][:10], 1):  # Show first 10
            print(f"  {i}. {trade['timestamp'].strftime('%Y-%m-%d')} "
                  f"{trade['side'].value:4s} {trade['quantity']:5d} shares "
                  f"@ ¥{float(trade['price']):7.2f}")

        if len(results['trades']) > 10:
            print(f"  ... and {len(results['trades']) - 10} more trades")

    print(f"{'='*70}\n")

    return results


async def main():
    """Main backtest execution"""
    print("="*70)
    print("GOLD STOCKS COMPREHENSIVE BACKTEST ANALYSIS")
    print("="*70)

    # Define stocks to test
    gold_stocks = [
        ('600547.SH', '山东黄金'),
        ('600489.SH', '中金黄金'),
        ('600916.SH', '中国黄金')
    ]

    # Define strategies
    strategies = {
        'MA(3,10)': MovingAverageCrossover({'fast_period': 3, 'slow_period': 10}),
        'MA(5,15)': MovingAverageCrossover({'fast_period': 5, 'slow_period': 15}),
        'MA(8,10)': MovingAverageCrossover({'fast_period': 8, 'slow_period': 10}),
        'Mean Reversion': MeanReversion({'period': 20, 'std_dev': 2.0}),
        'Momentum': Momentum({'lookback_period': 20, 'momentum_threshold': 0.05})
    }

    # Results collection
    all_results = {}

    # Test each stock with each strategy
    for symbol, name in gold_stocks:
        print(f"\n{'#'*70}")
        print(f"# {name} ({symbol})")
        print(f"{'#'*70}")

        stock_results = {}

        for strategy_name, strategy in strategies.items():
            try:
                results = await run_backtest(symbol, strategy_name, strategy, days=90)
                if results:
                    stock_results[strategy_name] = results
            except Exception as e:
                print(f"❌ Error running {strategy_name}: {e}")
                import traceback
                traceback.print_exc()

        all_results[name] = stock_results

    # Summary comparison
    print("\n" + "="*70)
    print("COMPREHENSIVE RESULTS SUMMARY")
    print("="*70)

    for stock_name, strategies_results in all_results.items():
        if strategies_results:
            print(f"\n{stock_name}:")
            print(f"{'Strategy':<20} {'Return':>10} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>8}")
            print("-" * 70)

            sorted_results = sorted(
                strategies_results.items(),
                key=lambda x: x[1]['total_return'],
                reverse=True
            )

            for strategy_name, result in sorted_results:
                print(f"{strategy_name:<20} "
                      f"{result['total_return']:>9.2%} "
                      f"{result['sharpe_ratio']:>8.3f} "
                      f"{result['max_drawdown']:>8.2%} "
                      f"{result['total_trades']:>8d}")

    print("\n" + "="*70)
    print("Backtest analysis completed!")
    print("="*70)


if __name__ == '__main__':
    asyncio.run(main())
