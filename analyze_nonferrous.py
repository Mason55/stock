#!/usr/bin/env python
# analyze_nonferrous.py - 有色板块批量分析
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from src.api.stock_api import (
    fetch_sina_realtime_sync,
    fetch_history_df,
    compute_indicators,
)
from src.services.fundamental_provider import fundamental_data_provider
from src.services.sentiment_provider import sentiment_data_provider
import pandas as pd

# Define non-ferrous metals sector stocks
NONFERROUS_STOCKS = {
    '601899.SH': '紫金矿业',  # 黄金+铜
    '603993.SH': '洛阳钼业',  # 钼+钴+铜
    '601600.SH': '中国铝业',  # 铝
    '600362.SH': '江西铜业',  # 铜
    '603799.SH': '华友钴业',  # 钴+镍
    '002460.SZ': '赣锋锂业',  # 锂
    '002466.SZ': '天齐锂业',  # 锂
    '600547.SH': '山东黄金',  # 黄金
    '601168.SH': '西部矿业',  # 铜+铅锌
    '600497.SH': '驰宏锌锗',  # 铅锌+锗
    '600711.SH': '盛屯矿业',  # 钴+铜
    '000807.SZ': '云铝股份',  # 铝
}

def quick_analyze_stock(stock_code: str, stock_name: str):
    """Quick analysis for single stock"""
    result = {
        'code': stock_code,
        'name': stock_name,
        'price': None,
        'change_pct': None,
        'tech_score': 5.0,
        'fund_score': None,
        'sentiment_score': None,
        'final_score': 5.0,
        'recommendation': '观望',
        'trend': '中性',
        'rsi': None,
        'volume': None,
        'error': None
    }

    try:
        # Get real-time data
        sina = fetch_sina_realtime_sync(stock_code)
        if not sina:
            result['error'] = '实时数据获取失败'
            return result

        result['price'] = sina['current_price']
        result['volume'] = sina['volume']
        change_pct = ((sina['current_price'] - sina['previous_close']) / sina['previous_close'] * 100) if sina['previous_close'] else 0
        result['change_pct'] = change_pct

        # Get historical data and compute indicators
        hist = fetch_history_df(stock_code, days=120)
        if hist is None or hist.empty:
            result['error'] = '历史数据获取失败'
            return result

        inds = compute_indicators(hist)
        current_price = sina['current_price']

        # Extract key indicators
        ma5 = inds.get('ma5')
        ma20 = inds.get('ma20')
        ma60 = inds.get('ma60')
        rsi = inds.get('rsi14')
        macd = inds.get('macd')
        macd_signal = inds.get('macd_signal')

        result['rsi'] = rsi

        # Trend analysis
        trend = "中性"
        if current_price and ma5 and ma20:
            if current_price > ma5 > ma20:
                trend = "多头排列"
            elif current_price < ma5 < ma20:
                trend = "空头排列"
            elif current_price > ma20:
                trend = "震荡偏强"
            else:
                trend = "震荡偏弱"
        result['trend'] = trend

        # Technical score
        tech_score = 5.0
        if trend == "多头排列":
            tech_score = 7.5 if (rsi and rsi < 70) else 6.5
        elif trend == "震荡偏强":
            tech_score = 6.0
        elif trend == "震荡偏弱":
            tech_score = 4.5
        elif trend == "空头排列":
            tech_score = 3.0 if (rsi and rsi < 30) else 2.5

        if macd and macd_signal:
            if macd > macd_signal and macd > 0:
                tech_score += 0.5
            elif macd < macd_signal and macd < 0:
                tech_score -= 0.5

        result['tech_score'] = round(tech_score, 1)

        # Fundamental score
        fundamentals = fundamental_data_provider.get_fundamental_analysis(
            stock_code, price_hint=current_price
        )
        if fundamentals and not fundamentals.get('degraded'):
            fund_score = 5.0
            valuation = fundamentals.get('valuation', {})
            profitability = fundamentals.get('profitability', {})
            growth = fundamentals.get('growth', {})

            pe = valuation.get('pe_ratio')
            if pe:
                if pe <= 15:
                    fund_score += 1.0
                elif pe >= 40:
                    fund_score -= 1.0

            roe = profitability.get('roe')
            if roe:
                fund_score += max(-1.5, min(1.5, (roe - 0.1) * 30))

            revenue_growth = growth.get('revenue_growth')
            if revenue_growth:
                fund_score += max(-1.0, min(1.5, revenue_growth * 10))

            result['fund_score'] = round(min(max(fund_score, 0.0), 10.0), 1)

        # Sentiment score
        sentiment = sentiment_data_provider.get_sentiment_analysis(stock_code)
        if sentiment and not sentiment.get('degraded'):
            overall = sentiment.get('overall_sentiment')
            result['sentiment_score'] = round(overall * 10, 1) if overall else 5.0

        # Final score
        scores = [result['tech_score']]
        if result['fund_score'] is not None:
            scores.append(result['fund_score'])
        if result['sentiment_score'] is not None:
            scores.append(result['sentiment_score'])

        result['final_score'] = round(sum(scores) / len(scores), 1)

        # Recommendation
        if result['final_score'] >= 7:
            result['recommendation'] = '买入'
        elif result['final_score'] >= 5:
            result['recommendation'] = '持有'
        else:
            result['recommendation'] = '观望'

    except Exception as e:
        result['error'] = str(e)

    return result

def analyze_nonferrous_sector():
    """Analyze non-ferrous metals sector"""
    print(f"\n{'='*80}")
    print(f"有色板块综合分析报告")
    print(f"{'='*80}\n")
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"分析股票数: {len(NONFERROUS_STOCKS)}只\n")

    results = []

    print("正在分析...")
    for code, name in NONFERROUS_STOCKS.items():
        print(f"  分析 {name} ({code})...", end='', flush=True)
        result = quick_analyze_stock(code, name)
        results.append(result)
        if result['error']:
            print(f" ❌ {result['error']}")
        else:
            print(f" ✓")

    print("\n" + "="*80)
    print("分析结果汇总")
    print("="*80 + "\n")

    # Create DataFrame for better display
    df = pd.DataFrame(results)
    df = df[df['error'].isna()]  # Filter out errors

    if df.empty:
        print("❌ 所有股票分析失败")
        return

    # Sort by final score
    df = df.sort_values('final_score', ascending=False)

    # Display results table
    print(f"{'排名':<4} {'代码':<12} {'名称':<12} {'价格':<8} {'涨跌幅':<8} {'趋势':<12} {'RSI':<6} {'技术':<6} {'基本':<6} {'综合':<6} {'建议':<6}")
    print("-" * 100)

    for idx, row in df.iterrows():
        rank = len([r for r in df.itertuples() if r.final_score > row['final_score']]) + 1
        price_str = f"¥{row['price']:.2f}" if row['price'] else '-'
        change_str = f"{row['change_pct']:+.2f}%" if row['change_pct'] else '-'
        rsi_str = f"{row['rsi']:.1f}" if row['rsi'] else '-'
        fund_str = f"{row['fund_score']:.1f}" if row['fund_score'] else '-'

        # Color coding for recommendation
        rec_symbol = {
            '买入': '🟢',
            '持有': '🟡',
            '观望': '🔴'
        }.get(row['recommendation'], '')

        print(f"{rank:<4} {row['code']:<12} {row['name']:<12} {price_str:<8} {change_str:<8} {row['trend']:<12} {rsi_str:<6} {row['tech_score']:<6.1f} {fund_str:<6} {row['final_score']:<6.1f} {rec_symbol}{row['recommendation']}")

    # Top recommendations
    print("\n" + "="*80)
    print("📊 投资建议")
    print("="*80 + "\n")

    top_buy = df[df['recommendation'] == '买入'].head(3)
    if not top_buy.empty:
        print("🟢 推荐买入 (综合评分≥7分):")
        for idx, row in top_buy.iterrows():
            rsi_display = f"{row['rsi']:.1f}" if row['rsi'] else '-'
            print(f"  • {row['name']} ({row['code']})")
            print(f"    价格: ¥{row['price']:.2f} | 综合评分: {row['final_score']:.1f}/10")
            print(f"    趋势: {row['trend']} | RSI: {rsi_display}")
            print()
    else:
        print("🟢 推荐买入: 当前板块无强烈买入信号\n")

    top_hold = df[df['recommendation'] == '持有'].head(3)
    if not top_hold.empty:
        print("🟡 可以持有 (综合评分5-7分):")
        for idx, row in top_hold.iterrows():
            print(f"  • {row['name']} ({row['code']})")
            print(f"    价格: ¥{row['price']:.2f} | 综合评分: {row['final_score']:.1f}/10")
            print()

    # Sector statistics
    print("="*80)
    print("📈 板块统计")
    print("="*80 + "\n")

    avg_score = df['final_score'].mean()
    avg_change = df['change_pct'].mean()

    print(f"平均综合评分: {avg_score:.1f}/10")
    print(f"平均涨跌幅: {avg_change:+.2f}%")
    print(f"推荐买入: {len(df[df['recommendation'] == '买入'])}只")
    print(f"建议持有: {len(df[df['recommendation'] == '持有'])}只")
    print(f"建议观望: {len(df[df['recommendation'] == '观望'])}只")

    # Trend distribution
    trend_counts = df['trend'].value_counts()
    print(f"\n趋势分布:")
    for trend, count in trend_counts.items():
        print(f"  {trend}: {count}只 ({count/len(df)*100:.0f}%)")

    # Risk warning
    print("\n" + "="*80)
    print("⚠️  风险提示")
    print("="*80 + "\n")
    print("1. 有色板块受宏观经济和大宗商品价格影响大，波动性较高")
    print("2. 建议分散投资，不要集中于单一品种")
    print("3. 关注全球经济形势、美元指数、工业需求等因素")
    print("4. 注意个股基本面变化，特别是成本控制和矿产储量")
    print("5. 本分析仅供参考，不构成投资建议，投资有风险，入市需谨慎")

    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    analyze_nonferrous_sector()
