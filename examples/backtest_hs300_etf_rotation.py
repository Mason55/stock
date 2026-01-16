# examples/backtest_hs300_etf_rotation.py - Backtest HS300 + ETF rotation strategy
"""
Usage:
    python examples/backtest_hs300_etf_rotation.py --days 365
    python examples/backtest_hs300_etf_rotation.py --stock-list data/hs300.txt --days 365
"""

import argparse
import asyncio
import random
import time
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import List

import pandas as pd
import akshare as ak

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.stock_symbols import A_SHARE_STOCKS
from src.backtest.engine import BacktestEngine
from src.strategies.hs300_etf_rotation import HS300EtfRotation, DEFAULT_ETF_UNIVERSE


def _load_symbol_list(path: str) -> List[str]:
    symbols = []
    if not path:
        return symbols
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        symbols.append(line.split(",")[0].strip())
    return symbols


def _normalize_em_df(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    }
    df = df.rename(columns=rename_map)
    needed = ["date", "open", "high", "low", "close", "volume"]
    df = df[[col for col in needed if col in df.columns]]
    df["date"] = pd.to_datetime(df["date"])
    return df


def _fetch_akshare(
    symbol: str,
    start_date: date,
    end_date: date,
    etf_symbols: set,
    index_symbol: str,
) -> pd.DataFrame:
    code = symbol.split(".")[0]
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    if symbol == index_symbol:
        df = ak.index_zh_a_hist(symbol=code, period="daily", start_date=start_str, end_date=end_str)
    elif symbol in etf_symbols:
        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date=start_str,
            end_date=end_str,
            adjust="qfq",
        )
    else:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_str,
            end_date=end_str,
            adjust="qfq",
        )

    if df is None or df.empty:
        return pd.DataFrame()

    return _normalize_em_df(df)


def _simulate_data(symbol: str, start_date: date, days: int) -> pd.DataFrame:
    rng = random.Random(abs(hash(symbol)) % 100000)
    price = 20 + (abs(hash(symbol)) % 1000) / 50.0
    data = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        drift = 0.0005
        shock = rng.uniform(-0.02, 0.02)
        price = max(1.0, price * (1 + drift + shock))
        data.append(
            {
                "date": current_date,
                "open": price * (1 - rng.uniform(0, 0.01)),
                "high": price * (1 + rng.uniform(0, 0.01)),
                "low": price * (1 - rng.uniform(0, 0.01)),
                "close": price,
                "volume": 1_000_000 + rng.randint(0, 500_000),
            }
        )
    return pd.DataFrame(data)


async def main():
    parser = argparse.ArgumentParser(description="Backtest HS300 + ETF rotation strategy")
    parser.add_argument("--days", type=int, default=365, help="Backtest window length")
    parser.add_argument("--capital", type=float, default=1_000_000.0, help="Initial capital")
    parser.add_argument("--stock-list", type=str, help="Path to HS300 symbol list file")
    parser.add_argument("--etf-list", type=str, help="Path to ETF symbol list file")
    parser.add_argument("--index", type=str, default="000300.SH", help="Market index symbol")
    parser.add_argument("--max-dd", type=float, default=0.15, help="Max drawdown threshold")
    parser.add_argument("--use-simulated", action="store_true", help="Use simulated data if fetch fails")
    parser.add_argument("--throttle", type=float, default=0.05, help="Sleep between requests (seconds)")
    args = parser.parse_args()

    stocks = _load_symbol_list(args.stock_list)
    if not stocks:
        stocks = [item["code"] for item in A_SHARE_STOCKS]

    etfs = _load_symbol_list(args.etf_list)
    if not etfs:
        etfs = list(DEFAULT_ETF_UNIVERSE)

    symbols = list(dict.fromkeys(stocks + etfs + [args.index, "511010.SH"]))

    end_date = date.today()
    start_date = end_date - timedelta(days=args.days)

    etf_symbols = set(etfs + ["511010.SH"])
    symbol_data = {}
    fetched = 0
    simulated = 0
    for symbol in symbols:
        try:
            df = _fetch_akshare(symbol, start_date, end_date, etf_symbols, args.index)
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            if args.use_simulated:
                df = _simulate_data(symbol, start_date, args.days + 10)
                simulated += 1
            else:
                print(f"Skip {symbol}: no data")
                continue
        else:
            fetched += 1

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = df.tail(args.days)
        symbol_data[symbol] = df
        if args.throttle:
            time.sleep(args.throttle)

    if args.index not in symbol_data:
        print(f"Missing index data for {args.index}.")
        return

    if not symbol_data:
        print("No market data available. Exiting.")
        return

    strategy_config = {
        "market_index_symbol": args.index,
        "stock_universe": stocks,
        "etf_universe": etfs,
        "initial_capital": args.capital,
        "max_drawdown_pct": args.max_dd,
        "top_n_stocks": min(10, len(stocks)),
        "top_n_etf": min(3, len(etfs)),
        "max_total_weight": 0.95,
        "max_position_weight": 0.08,
        "cash_buffer_pct": 0.05,
        "min_order_value": 1000.0,
        "max_order_value": 3000000.0,
        "use_available_cash_only": True,
        "defensive_only_on_drawdown": True,
        "min_defensive_weeks": 4,
        "drawdown_recover_pct": 0.08,
        "two_phase_rebalance": True,
    }

    strategy = HS300EtfRotation(config=strategy_config)

    engine = BacktestEngine(
        start_date=start_date,
        end_date=end_date,
        initial_capital=args.capital,
        config={
            "market": {"ignore_trading_hours": True},
            "costs": {"commission_rate": 0.0001, "min_commission": 5.0},
            "risk": {
                "max_position_pct": 0.25,
                "max_total_exposure": 0.98,
                "min_order_value": 1000,
                "max_order_value": 3000000,
            },
        },
    )

    for symbol, df in symbol_data.items():
        engine.load_market_data(symbol, df)

    engine.add_strategy(strategy)

    print(f"Loaded data: real={fetched}, simulated={simulated}")
    print("Running backtest...")
    results = await engine.run()

    if not results:
        print("No results generated.")
        return

    print("\nBACKTEST RESULTS")
    print("=" * 60)
    print(f"Initial Capital:    ¥{results['initial_capital']:,.2f}")
    print(f"Final Value:        ¥{results['final_value']:,.2f}")
    print(f"Total Return:       {results['total_return']:.2%}")
    print(f"Annualized Return:  {results['annualized_return']:.2%}")
    print(f"Volatility:         {results['volatility']:.2%}")
    print(f"Sharpe Ratio:       {results['sharpe_ratio']:.3f}")
    print(f"Max Drawdown:       {results['max_drawdown']:.2%}")
    print(f"Total Trades:       {results['total_trades']}")

    if results["positions"]:
        print("\nFINAL POSITIONS:")
        for symbol, qty in results["positions"].items():
            if qty > 0:
                print(f"{symbol}: {qty} shares")


if __name__ == "__main__":
    asyncio.run(main())
