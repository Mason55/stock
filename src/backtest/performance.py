# src/backtest/performance.py - Performance analysis and visualization
"""Performance analysis tools for backtesting results."""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Analyze backtest performance with detailed metrics."""

    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital

    def analyze(self, equity_curve: pd.DataFrame, trades: List) -> Dict:
        """Comprehensive performance analysis.

        Args:
            equity_curve: DataFrame with columns ['date', 'equity', 'cash', 'holdings']
            trades: List of trade records

        Returns:
            Dictionary with performance metrics
        """
        if equity_curve is None or len(equity_curve) == 0:
            return self._empty_results()

        equity = equity_curve['equity'].values
        dates = equity_curve['date'].values

        # Basic metrics
        final_value = equity[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital

        # Time-based metrics
        days = len(equity)
        years = days / 252.0  # Trading days
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # Volatility
        returns = pd.Series(equity).pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0

        # Sharpe ratio (assuming 3% risk-free rate)
        risk_free_rate = 0.03
        sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0

        # Drawdown analysis
        dd_results = self._calculate_drawdowns(equity)

        # Win rate and profit factor
        trade_stats = self._analyze_trades(trades)

        # Monthly returns
        monthly_returns = self._calculate_monthly_returns(equity_curve)

        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': self._calculate_sortino(returns, risk_free_rate),
            'calmar_ratio': annualized_return / dd_results['max_drawdown'] if dd_results['max_drawdown'] != 0 else 0,
            'max_drawdown': dd_results['max_drawdown'],
            'max_drawdown_duration': dd_results['max_dd_duration'],
            'total_trades': len(trades),
            'win_rate': trade_stats['win_rate'],
            'profit_factor': trade_stats['profit_factor'],
            'avg_win': trade_stats['avg_win'],
            'avg_loss': trade_stats['avg_loss'],
            'largest_win': trade_stats['largest_win'],
            'largest_loss': trade_stats['largest_loss'],
            'avg_trade_return': trade_stats['avg_trade_return'],
            'monthly_returns': monthly_returns,
            'equity_curve': equity_curve,
            'trades': trades
        }

    def _empty_results(self) -> Dict:
        """Return empty results for failed backtests."""
        return {
            'initial_capital': self.initial_capital,
            'final_value': self.initial_capital,
            'total_return': 0.0,
            'annualized_return': 0.0,
            'volatility': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'calmar_ratio': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_duration': 0,
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'avg_trade_return': 0.0,
            'monthly_returns': [],
            'equity_curve': pd.DataFrame(),
            'trades': []
        }

    def _calculate_drawdowns(self, equity: np.ndarray) -> Dict:
        """Calculate drawdown metrics."""
        running_max = np.maximum.accumulate(equity)
        drawdowns = (equity - running_max) / running_max

        max_dd = abs(drawdowns.min())

        # Calculate drawdown duration
        in_dd = drawdowns < 0
        dd_duration = 0
        current_duration = 0
        max_duration = 0

        for is_dd in in_dd:
            if is_dd:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        return {
            'max_drawdown': max_dd,
            'max_dd_duration': max_duration,
            'drawdowns': drawdowns
        }

    def _calculate_sortino(self, returns: pd.Series, risk_free_rate: float = 0.03) -> float:
        """Calculate Sortino ratio (downside deviation)."""
        if len(returns) == 0:
            return 0.0

        excess_returns = returns - (risk_free_rate / 252)
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0:
            return 0.0

        downside_std = downside_returns.std() * np.sqrt(252)

        if downside_std == 0:
            return 0.0

        return (returns.mean() * 252 - risk_free_rate) / downside_std

    def _analyze_trades(self, trades: List) -> Dict:
        """Analyze individual trades."""
        if not trades:
            return {
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
                'avg_trade_return': 0.0
            }

        # Match buys with sells
        pnls = []
        position = {}

        for trade in trades:
            symbol = trade['symbol']
            side = str(trade['side'])
            qty = trade['quantity']
            price = float(trade['price'])

            if side == 'OrderSide.BUY':
                if symbol not in position:
                    position[symbol] = {'qty': 0, 'avg_cost': 0}

                # Update average cost
                total_cost = position[symbol]['qty'] * position[symbol]['avg_cost']
                position[symbol]['qty'] += qty
                position[symbol]['avg_cost'] = (total_cost + qty * price) / position[symbol]['qty']

            elif side == 'OrderSide.SELL':
                if symbol in position and position[symbol]['qty'] > 0:
                    # Calculate P&L
                    cost = position[symbol]['avg_cost']
                    pnl_pct = (price - cost) / cost
                    pnls.append(pnl_pct)

                    # Reduce position
                    position[symbol]['qty'] -= qty

        if not pnls:
            return {
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
                'avg_trade_return': 0.0
            }

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_rate = len(wins) / len(pnls) if pnls else 0
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0
        profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0

        return {
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': max(pnls) if pnls else 0,
            'largest_loss': min(pnls) if pnls else 0,
            'avg_trade_return': np.mean(pnls) if pnls else 0
        }

    def _calculate_monthly_returns(self, equity_curve: pd.DataFrame) -> List[Dict]:
        """Calculate monthly returns."""
        if equity_curve is None or len(equity_curve) == 0:
            return []

        df = equity_curve.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')

        # Resample to month end
        monthly = df['equity'].resample('M').last()

        returns = []
        prev_value = self.initial_capital

        for date, value in monthly.items():
            ret = (value - prev_value) / prev_value
            returns.append({
                'month': date.strftime('%Y-%m'),
                'return': ret,
                'equity': value
            })
            prev_value = value

        return returns

    def print_report(self, results: Dict, detailed: bool = True):
        """Print formatted performance report."""
        print("\n" + "="*70)
        print("PERFORMANCE REPORT")
        print("="*70)

        print(f"\nCapital:")
        print(f"  Initial:         ¥{results['initial_capital']:,.2f}")
        print(f"  Final:           ¥{results['final_value']:,.2f}")
        print(f"  Profit/Loss:     ¥{results['final_value'] - results['initial_capital']:,.2f}")

        print(f"\nReturns:")
        print(f"  Total Return:    {results['total_return']:>7.2%}")
        print(f"  Annualized:      {results['annualized_return']:>7.2%}")

        print(f"\nRisk Metrics:")
        print(f"  Volatility:      {results['volatility']:>7.2%}")
        print(f"  Max Drawdown:    {results['max_drawdown']:>7.2%}")
        print(f"  DD Duration:     {results['max_drawdown_duration']:>4d} days")

        print(f"\nRisk-Adjusted Returns:")
        print(f"  Sharpe Ratio:    {results['sharpe_ratio']:>7.3f}")
        print(f"  Sortino Ratio:   {results['sortino_ratio']:>7.3f}")
        print(f"  Calmar Ratio:    {results['calmar_ratio']:>7.3f}")

        print(f"\nTrading Stats:")
        print(f"  Total Trades:    {results['total_trades']:>4d}")
        print(f"  Win Rate:        {results['win_rate']:>7.2%}")
        print(f"  Profit Factor:   {results['profit_factor']:>7.2f}")
        print(f"  Avg Win:         {results['avg_win']:>7.2%}")
        print(f"  Avg Loss:        {results['avg_loss']:>7.2%}")
        print(f"  Largest Win:     {results['largest_win']:>7.2%}")
        print(f"  Largest Loss:    {results['largest_loss']:>7.2%}")

        if detailed and results['monthly_returns']:
            print(f"\nMonthly Returns:")
            print(f"  {'Month':<10} {'Return':>10} {'Equity':>15}")
            print("  " + "-" * 40)
            for month_data in results['monthly_returns'][-12:]:  # Last 12 months
                print(
                    f"  {month_data['month']:<10} "
                    f"{month_data['return']:>9.2%} "
                    f"¥{month_data['equity']:>14,.2f}"
                )

        print("="*70 + "\n")
