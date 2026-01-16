#!/usr/bin/env python3
"""ETF Real-time Monitor - Monitor premium rate and trading signals

Usage:
    python monitor_etf.py 513090.SH
    python monitor_etf.py 513090.SH --interval 60
"""
import argparse
import time
from datetime import datetime
from typing import Dict, Any

from src.services.etf_analyzer import ETFAnalyzer
from src.api.stock_api import fetch_sina_realtime_sync, fetch_history_df
from src.core.technical_analysis import AdvancedTechnicalAnalyzer, analyze_technical_strength


class ETFMonitor:
    """Real-time ETF monitor for T+0/T+1 trading"""

    def __init__(self, etf_code: str):
        self.etf_code = etf_code
        self.analyzer = ETFAnalyzer(use_cache=False)  # Disable cache for real-time monitoring
        self.tech_analyzer = AdvancedTechnicalAnalyzer()

    def get_trading_signal(self, quote: Dict, premium_data: Dict, indicators) -> Dict[str, Any]:
        """Generate trading signal based on multiple factors"""
        signals = []
        confidence = 0
        reasons = []

        current_price = quote.get('current_price', 0)
        premium_rate = premium_data.get('premium_rate')

        # Premium rate signal
        if premium_rate is not None:
            if premium_rate > 1.0:
                signals.append('SELL')
                confidence += 20
                reasons.append(f'High premium ({premium_rate:.2f}%)')
            elif premium_rate < -0.5:
                signals.append('BUY')
                confidence += 20
                reasons.append(f'Discount ({premium_rate:.2f}%)')

        # RSI signal
        rsi = indicators.rsi if indicators else None
        if rsi is not None:
            if rsi < 30:
                signals.append('BUY')
                confidence += 30
                reasons.append(f'Oversold (RSI {rsi:.1f})')
            elif rsi > 70:
                signals.append('SELL')
                confidence += 30
                reasons.append(f'Overbought (RSI {rsi:.1f})')

        # MACD signal
        if indicators and indicators.macd is not None and indicators.macd_signal is not None:
            if indicators.macd > indicators.macd_signal:
                signals.append('BUY')
                confidence += 20
                reasons.append('MACD bullish')
            else:
                signals.append('SELL')
                confidence += 20
                reasons.append('MACD bearish')

        # KDJ signal
        if indicators and indicators.kdj_j is not None:
            if indicators.kdj_j < 20:
                signals.append('BUY')
                confidence += 15
                reasons.append(f'KDJ oversold (J={indicators.kdj_j:.1f})')
            elif indicators.kdj_j > 80:
                signals.append('SELL')
                confidence += 15
                reasons.append(f'KDJ overbought (J={indicators.kdj_j:.1f})')

        # Support/Resistance
        if indicators and indicators.support_level and current_price <= indicators.support_level * 1.01:
            signals.append('BUY')
            confidence += 15
            reasons.append(f'Near support (¥{indicators.support_level:.3f})')
        elif indicators and indicators.resistance_level and current_price >= indicators.resistance_level * 0.99:
            signals.append('SELL')
            confidence += 15
            reasons.append(f'Near resistance (¥{indicators.resistance_level:.3f})')

        # Determine final signal
        buy_count = signals.count('BUY')
        sell_count = signals.count('SELL')

        if buy_count > sell_count:
            final_signal = 'BUY'
        elif sell_count > buy_count:
            final_signal = 'SELL'
        else:
            final_signal = 'HOLD'
            confidence = max(confidence * 0.5, 30)

        return {
            'signal': final_signal,
            'confidence': min(confidence, 100),
            'reasons': reasons
        }

    def display_monitor_data(self):
        """Display monitoring data (simplified version)"""
        print('\033[2J\033[H', end='')

        print('=' * 50)
        print(f'ETF监控 - {self.etf_code}')
        print(f'时间: {datetime.now().strftime("%H:%M:%S")}')
        print('=' * 50)

        # Get real-time quote
        quote = fetch_sina_realtime_sync(self.etf_code)
        if not quote:
            print('⚠️  无法获取实时行情')
            return

        # Display simplified quote
        current_price = quote.get('current_price', 0)
        previous_close = quote.get('previous_close', 0)

        # Calculate change percentage
        if previous_close > 0:
            change_pct = ((current_price - previous_close) / previous_close) * 100
        else:
            change_pct = 0

        change_symbol = '+' if change_pct >= 0 else ''
        color = '\033[91m' if change_pct < 0 else '\033[92m' if change_pct > 0 else '\033[0m'

        print(f'\n当前价格: ¥{current_price:.3f}  {color}{change_symbol}{change_pct:.2f}%\033[0m')
        print(f'开盘/最高/最低: ¥{quote.get("open_price", 0):.3f} / ¥{quote.get("high_price", 0):.3f} / ¥{quote.get("low_price", 0):.3f}')

        # Premium rate
        premium_data = self.analyzer.get_premium_discount(self.etf_code)
        if premium_data and premium_data.get('premium_rate') is not None:
            premium_rate = premium_data['premium_rate']
            nav = premium_data['nav']

            status_icon = '⚠️' if abs(premium_rate) > 1.0 else '✓'
            print(f'\n净值: ¥{nav:.3f}  溢价率: {status_icon} {premium_rate:+.2f}%')
        else:
            print('\n溢价率数据暂不可用')

        print('\n' + '=' * 50)
        print('按 Ctrl+C 停止监控')


def main():
    parser = argparse.ArgumentParser(description='ETF Real-time Monitor')
    parser.add_argument('etf_code', help='ETF code (e.g., 513090.SH)')
    parser.add_argument('--interval', type=int, default=300,
                       help='Refresh interval in seconds (default: 300)')
    parser.add_argument('--once', action='store_true',
                       help='Run once without loop')

    args = parser.parse_args()
    monitor = ETFMonitor(args.etf_code)

    try:
        if args.once:
            monitor.display_monitor_data()
        else:
            while True:
                monitor.display_monitor_data()
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print('\n\n监控已停止')


if __name__ == '__main__':
    main()
