# examples/monitor_price.py - Price monitoring example
"""
Price monitoring and alert system example.

Usage:
    python examples/monitor_price.py --symbol 000977.SZ --support 68 70 --resistance 75 80
    python examples/monitor_price.py --symbol 600036.SH --watch
"""

import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring.price_alert import (
    AlertManager,
    AlertType,
    console_notification,
    log_notification
)


async def fetch_current_data(symbol: str) -> dict:
    """Fetch current market data."""
    try:
        from src.api.stock_api import fetch_sina_realtime_sync, fetch_history_df, compute_indicators
        import pandas as pd

        # Get realtime quote
        realtime = fetch_sina_realtime_sync(symbol)
        if not realtime:
            print(f"⚠️ Failed to fetch realtime data for {symbol}")
            return None

        current_price = realtime.get('current_price', 0)
        previous_close = realtime.get('previous_close', current_price)
        volume = realtime.get('volume', 0)

        # Get historical data for indicators
        hist = fetch_history_df(symbol, days=30)
        indicators = {}
        if hist is not None and not hist.empty:
            indicators = compute_indicators(hist)

        return {
            'symbol': symbol,
            'current_price': current_price,
            'previous_close': previous_close,
            'volume': volume,
            'rsi': indicators.get('rsi14'),
            'ma5': indicators.get('ma5'),
            'ma20': indicators.get('ma20'),
            'macd': indicators.get('macd'),
            'timestamp': datetime.now()
        }

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None


async def monitor_stock(
    symbol: str,
    alert_manager: AlertManager,
    check_interval: int = 30
):
    """Monitor stock and check alerts.

    Args:
        symbol: Stock symbol
        alert_manager: Alert manager instance
        check_interval: Seconds between checks
    """
    print(f"\n{'='*70}")
    print(f"📊 Monitoring {symbol}")
    print(f"{'='*70}")
    print(f"Check interval: {check_interval} seconds")
    print(f"Press Ctrl+C to stop\n")

    iteration = 0
    try:
        while True:
            iteration += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Check #{iteration}...", end=' ')

            # Fetch current data
            data = await fetch_current_data(symbol)

            if data:
                price = data['current_price']
                change_pct = ((price - data['previous_close']) / data['previous_close'] * 100) if data['previous_close'] else 0

                print(f"Price: ¥{price:.2f} ({change_pct:+.2f}%)", end='')

                # Check alerts
                market_data = {symbol: data}
                triggered = alert_manager.check_all_alerts(market_data)

                if triggered:
                    print(f" - ⚠️ {len(triggered)} alert(s) triggered!")
                else:
                    print()
            else:
                print("⚠️ Data fetch failed")

            # Wait for next check
            await asyncio.sleep(check_interval)

    except KeyboardInterrupt:
        print("\n\n✓ Monitoring stopped")


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Monitor stock prices and alerts")
    parser.add_argument(
        '--symbol',
        type=str,
        required=True,
        help='Stock symbol to monitor'
    )
    parser.add_argument(
        '--support',
        type=float,
        nargs='+',
        help='Support levels (e.g., --support 68 70)'
    )
    parser.add_argument(
        '--resistance',
        type=float,
        nargs='+',
        help='Resistance levels (e.g., --resistance 75 80)'
    )
    parser.add_argument(
        '--target',
        type=float,
        help='Target price alert'
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Enable technical indicator alerts (RSI, volume)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Check interval in seconds (default: 30)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List active alerts and exit'
    )

    args = parser.parse_args()

    # Create alert manager
    alert_manager = AlertManager()

    # Register notification callbacks
    alert_manager.register_notification_callback(console_notification)
    alert_manager.register_notification_callback(log_notification)

    # Create alerts based on arguments
    if args.support:
        support_levels = args.support
        print(f"\n✓ Creating support alerts at: {support_levels}")
        for level in support_levels:
            alert_manager.create_price_target_alert(args.symbol, level, "below")

    if args.resistance:
        resistance_levels = args.resistance
        print(f"✓ Creating resistance alerts at: {resistance_levels}")
        for level in resistance_levels:
            alert_manager.create_price_target_alert(args.symbol, level, "above")

    if args.target:
        print(f"✓ Creating target price alert at ¥{args.target:.2f}")
        alert_manager.create_price_target_alert(args.symbol, args.target, "above")

    if args.watch:
        print(f"✓ Creating technical indicator alerts")
        alert_manager.create_technical_alerts(args.symbol, {
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'price_change_pct': 5.0
        })

    # List alerts if requested
    if args.list:
        active_alerts = alert_manager.get_active_alerts(args.symbol)
        print(f"\n{'='*70}")
        print(f"ACTIVE ALERTS FOR {args.symbol}")
        print(f"{'='*70}")

        if active_alerts:
            for alert in active_alerts:
                print(f"\nID: {alert.alert_id}")
                print(f"Type: {alert.alert_type.value}")
                print(f"Threshold: {alert.threshold}")
                print(f"Message: {alert.message}")
                print(f"Expires: {alert.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("\nNo active alerts")

        print(f"{'='*70}\n")
        return 0

    # Start monitoring
    if not alert_manager.get_active_alerts(args.symbol):
        print("\n⚠️ No alerts configured. Use --support, --resistance, --target, or --watch")
        print("\nExample:")
        print(f"  python {sys.argv[0]} --symbol 000977.SZ --support 68 70 --resistance 75 80")
        return 1

    # Show initial status
    print(f"\n✓ {len(alert_manager.get_active_alerts())} active alerts configured")

    # Monitor
    await monitor_stock(args.symbol, alert_manager, args.interval)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
