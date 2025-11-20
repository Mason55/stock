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
        self.analyzer = ETFAnalyzer(use_cache=True)
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
        """Display monitoring data"""
        print('\033[2J\033[H', end='')

        print('=' * 70)
        print(f'ETF实时监控 - {self.etf_code}')
        print(f'更新时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print('=' * 70)

        # Get real-time quote
        quote = fetch_sina_realtime_sync(self.etf_code)
        if not quote:
            print('⚠️  无法获取实时行情')
            return

        # Display quote
        print('\n【实时行情】')
        current_price = quote.get('current_price', 0)
        change_pct = quote.get('change_percent', 0)
        change_symbol = '+' if change_pct >= 0 else ''
        color = '\033[91m' if change_pct < 0 else '\033[92m' if change_pct > 0 else '\033[0m'

        print(f'  当前价格: ¥{current_price:.3f}  {color}{change_symbol}{change_pct:.2f}%\033[0m')
        print(f'  今日开盘: ¥{quote.get("open", 0):.3f}')
        print(f'  最高/最低: ¥{quote.get("high", 0):.3f} / ¥{quote.get("low", 0):.3f}')

        daily_amplitude = 0
        if quote.get('low', 0) > 0:
            daily_amplitude = ((quote.get('high', 0) - quote.get('low', 0)) / quote.get('low', 0)) * 100
        print(f'  日内振幅: {daily_amplitude:.2f}%')

        volume_yi = quote.get('volume', 0) / 100000000
        print(f'  成交量: {volume_yi:.2f}亿手')

        # Premium rate analysis
        print('\n【溢价率分析】')
        premium_data = self.analyzer.get_premium_discount(self.etf_code)
        if premium_data and premium_data.get('premium_rate') is not None:
            premium_rate = premium_data['premium_rate']
            nav = premium_data['nav']
            status = premium_data['status']

            status_text = {
                'premium': '⚠️  溢价',
                'discount': '💰 折价',
                'fair': '✓ 合理'
            }.get(status, status)

            print(f'  单位净值: ¥{nav:.3f}')
            print(f'  溢价率: {premium_rate:+.2f}%  [{status_text}]')

            if abs(premium_rate) > 1.0:
                if premium_rate > 0:
                    print('  💡 溢价较高，可考虑卖出做T')
                else:
                    print('  💡 折价明显，可考虑买入做T')
        else:
            print('  ⚠️  溢价率数据暂不可用')
            premium_data = {}

        # Technical analysis
        print('\n【技术指标】')
        df = fetch_history_df(self.etf_code, days=120)
        indicators = None

        if df is not None and not df.empty:
            prices = df['close'].tolist()
            highs = df['high'].tolist()
            lows = df['low'].tolist()
            volumes = df['volume'].tolist()

            indicators = self.tech_analyzer.calculate_comprehensive_indicators(
                prices=prices,
                volumes=volumes,
                highs=highs,
                lows=lows,
                current_price=current_price
            )

            if indicators:
                # RSI
                if indicators.rsi:
                    rsi_status = '超卖' if indicators.rsi < 30 else '超买' if indicators.rsi > 70 else '中性'
                    print(f'  RSI(14): {indicators.rsi:.2f}  [{rsi_status}]')

                # MACD
                if indicators.macd is not None:
                    macd_status = '多头' if indicators.macd > (indicators.macd_signal or 0) else '空头'
                    print(f'  MACD: {indicators.macd:.4f}  [{macd_status}]')

                # KDJ
                if indicators.kdj_k is not None:
                    print(f'  KDJ: K={indicators.kdj_k:.1f} D={indicators.kdj_d:.1f} J={indicators.kdj_j:.1f}')

                # Moving averages
                if indicators.ma5 and indicators.ma20:
                    print(f'  MA5: ¥{indicators.ma5:.3f}  MA20: ¥{indicators.ma20:.3f}')

                    if current_price > indicators.ma5 > indicators.ma20:
                        print(f'  趋势: 📈 多头排列')
                    elif current_price < indicators.ma5 < indicators.ma20:
                        print(f'  趋势: 📉 空头排列')
                    else:
                        print(f'  趋势: ↔️  震荡')

                # Support and resistance
                if indicators.support_level and indicators.resistance_level:
                    print(f'  支撑位: ¥{indicators.support_level:.3f}  压力位: ¥{indicators.resistance_level:.3f}')

                # Bollinger Bands
                if indicators.bb_percent is not None:
                    print(f'  布林带位置: {indicators.bb_percent:.1f}%')

        # Trading signal
        print('\n【交易信号】')
        signal_data = self.get_trading_signal(quote, premium_data, indicators)

        signal_icon = {
            'BUY': '🟢 买入',
            'SELL': '🔴 卖出',
            'HOLD': '🟡 观望'
        }.get(signal_data['signal'], signal_data['signal'])

        print(f'  信号: {signal_icon}')
        print(f'  置信度: {signal_data["confidence"]:.0f}%')
        print(f'  理由:')
        for reason in signal_data['reasons']:
            print(f'    • {reason}')

        # T trading suggestions
        print('\n【做T建议】')
        if signal_data['signal'] == 'BUY':
            print('  ✓ 可考虑低吸做T（盘中回调时买入）')
            if indicators and indicators.support_level:
                print(f'  建议买入区间: ¥{indicators.support_level:.3f} - ¥{indicators.support_level * 1.02:.3f}')
        elif signal_data['signal'] == 'SELL':
            print('  ✓ 可考虑高抛做T（盘中反弹时卖出）')
            if indicators and indicators.resistance_level:
                print(f'  建议卖出区间: ¥{indicators.resistance_level * 0.98:.3f} - ¥{indicators.resistance_level:.3f}')
        else:
            print('  ⚠️  暂无明确机会，建议观望')

        print(f'\n  ⚠️  A股实行T+1，当日买入次日才能卖出')
        print(f'  💡 做T需要有底仓，或提前一天买入')

        print('\n' + '=' * 70)
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
