#!/usr/bin/env python
# analyze_stock.py - 通用股票分析脚本
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from src.api.stock_api import (
    fetch_sina_realtime_sync,
    fetch_history_df,
    compute_indicators,
    is_offline_mode
)
from src.services.fundamental_provider import fundamental_data_provider
from src.services.sentiment_provider import sentiment_data_provider
import json

def analyze_stock(stock_code: str):
    """分析股票趋势"""
    print(f"\n{'='*60}")
    print(f"股票综合趋势分析 - {stock_code}")
    print(f"{'='*60}\n")

    # 1. 获取实时行情
    print("【实时行情】")
    sina = fetch_sina_realtime_sync(stock_code)
    if sina:
        print(f"  股票名称: {sina['company_name']}")
        print(f"  当前价格: ¥{sina['current_price']:.2f}")
        print(f"  昨日收盘: ¥{sina['previous_close']:.2f}")
        change_pct = ((sina['current_price'] - sina['previous_close']) / sina['previous_close'] * 100) if sina['previous_close'] else 0
        print(f"  涨跌幅: {change_pct:+.2f}%")
        print(f"  今日开盘: ¥{sina['open_price']:.2f}")
        print(f"  最高价: ¥{sina['high_price']:.2f}")
        print(f"  最低价: ¥{sina['low_price']:.2f}")
        print(f"  成交量: {sina['volume']:,}手")
        print(f"  成交额: ¥{sina['turnover']/100000000:.2f}亿")
        current_price = sina['current_price']
        company_name = sina['company_name']
    else:
        print("  ⚠️  实时行情获取失败")
        current_price = None
        company_name = stock_code

    # 2. 获取历史数据并计算技术指标
    print(f"\n【技术分析】(基于120日历史数据)")
    hist = fetch_history_df(stock_code, days=120)
    if hist is not None and not hist.empty:
        print(f"  数据范围: {hist['date'].iloc[0]} ~ {hist['date'].iloc[-1]}")
        print(f"  数据点数: {len(hist)}个交易日")

        # 计算技术指标
        inds = compute_indicators(hist)

        # 价格与均线
        if current_price is None and 'close' in hist.columns:
            current_price = float(hist['close'].iloc[-1])

        print(f"\n  移动平均线:")
        ma5 = inds.get('ma5')
        ma20 = inds.get('ma20')
        ma60 = inds.get('ma60')
        if ma5: print(f"    MA5:  ¥{ma5:.2f}")
        if ma20: print(f"    MA20: ¥{ma20:.2f}")
        if ma60: print(f"    MA60: ¥{ma60:.2f}")

        # 趋势判断
        trend = "中性"
        trend_desc = []
        if current_price and ma5 and ma20:
            if current_price > ma5 > ma20:
                trend = "多头排列"
                trend_desc.append("价格位于短期均线上方")
            elif current_price < ma5 < ma20:
                trend = "空头排列"
                trend_desc.append("价格位于短期均线下方")
            elif current_price > ma20:
                trend = "震荡偏强"
            else:
                trend = "震荡偏弱"

        print(f"\n  趋势判断: {trend}")
        if trend_desc:
            for desc in trend_desc:
                print(f"    • {desc}")

        # RSI指标
        rsi = inds.get('rsi14')
        if rsi:
            print(f"\n  RSI(14): {rsi:.2f}")
            if rsi > 70:
                print(f"    → 超买区域,有回调风险")
            elif rsi < 30:
                print(f"    → 超卖区域,可能反弹")
            elif 40 <= rsi <= 60:
                print(f"    → 中性区域")
            else:
                print(f"    → 正常波动范围")

        # MACD指标
        macd = inds.get('macd')
        macd_signal = inds.get('macd_signal')
        macd_hist = inds.get('macd_hist')
        if macd is not None and macd_signal is not None:
            print(f"\n  MACD指标:")
            print(f"    MACD线: {macd:.4f}")
            print(f"    信号线: {macd_signal:.4f}")
            print(f"    柱状图: {macd_hist:.4f}")
            if macd > macd_signal:
                print(f"    → 多头信号(MACD在信号线上方)")
            else:
                print(f"    → 空头信号(MACD在信号线下方)")
            if abs(macd_hist) < 0.05:
                print(f"    → 即将金叉/死叉,注意方向变化")

        # 支撑与压力位
        if current_price:
            support1 = current_price * 0.95
            support2 = current_price * 0.90
            resistance1 = current_price * 1.05
            resistance2 = current_price * 1.10
            print(f"\n  支撑与压力位:")
            print(f"    支撑1: ¥{support1:.2f} (-5%)")
            print(f"    支撑2: ¥{support2:.2f} (-10%)")
            print(f"    压力1: ¥{resistance1:.2f} (+5%)")
            print(f"    压力2: ¥{resistance2:.2f} (+10%)")
    else:
        print("  ⚠️  历史数据获取失败")
        rsi = None
        macd = None
        macd_signal = None

    # 3. 基本面分析
    print(f"\n【基本面分析】")
    fundamentals = fundamental_data_provider.get_fundamental_analysis(
        stock_code, price_hint=current_price
    )
    if fundamentals and not fundamentals.get('degraded'):
        valuation = fundamentals.get('valuation', {})
        profitability = fundamentals.get('profitability', {})
        growth = fundamentals.get('growth', {})

        print(f"  估值指标:")
        if valuation.get('pe_ratio'):
            print(f"    市盈率(PE): {valuation['pe_ratio']:.2f}")
        if valuation.get('pb_ratio'):
            print(f"    市净率(PB): {valuation['pb_ratio']:.2f}")
        if valuation.get('ps_ratio'):
            print(f"    市销率(PS): {valuation['ps_ratio']:.2f}")

        print(f"\n  盈利能力:")
        if profitability.get('roe'):
            print(f"    净资产收益率(ROE): {profitability['roe']*100:.2f}%")
        if profitability.get('net_margin'):
            print(f"    净利润率: {profitability['net_margin']*100:.2f}%")
        if profitability.get('gross_margin'):
            print(f"    毛利率: {profitability['gross_margin']*100:.2f}%")

        print(f"\n  成长性:")
        if growth.get('revenue_growth'):
            print(f"    营收增长率: {growth['revenue_growth']*100:+.2f}%")
        if growth.get('profit_growth'):
            print(f"    净利润增长率: {growth['profit_growth']*100:+.2f}%")
    else:
        print("  ⚠️  基本面数据未接入")

    # 4. 市场情绪
    print(f"\n【市场情绪】")
    sentiment = sentiment_data_provider.get_sentiment_analysis(stock_code)
    if sentiment and not sentiment.get('degraded'):
        overall = sentiment.get('overall_sentiment')
        if overall is not None:
            sentiment_label = "积极" if overall > 0.6 else "中性" if overall > 0.4 else "消极"
            print(f"  综合情绪: {sentiment_label} ({overall:.2f})")

        source = sentiment.get('source', 'unknown')
        if source == 'eastmoney_guba':
            print(f"  数据来源: 东方财富股吧 (实时爬取)")
            social = sentiment.get('social_sentiment', {})
            post_count = sentiment.get('post_count', 0)
            engagement = social.get('total_engagement', 0)
            print(f"  帖子数量: {post_count}条")
            print(f"  互动热度: {engagement:,}")
            keywords = social.get('keywords', [])
            if keywords:
                print(f"  热门关键词: {', '.join(keywords)}")
        elif source == 'technical_derived':
            print(f"  数据来源: 技术指标推导")
    else:
        print("  ⚠️  情绪数据未接入")

    # 5. 综合评分与建议
    print(f"\n【综合评分与建议】")

    # 技术评分
    tech_score = 5.0
    if hist is not None and not hist.empty and current_price:
        if trend == "多头排列":
            tech_score = 7.5 if (rsi and rsi < 70) else 6.5
        elif trend == "震荡偏强":
            tech_score = 6.0
        elif trend == "震荡偏弱":
            tech_score = 4.5
        elif trend == "空头排列":
            tech_score = 3.0 if (rsi and rsi < 30) else 2.5

        # MACD调整
        if macd and macd_signal:
            if macd > macd_signal and macd > 0:
                tech_score += 0.5
            elif macd < macd_signal and macd < 0:
                tech_score -= 0.5

    print(f"  技术面评分: {tech_score:.1f}/10")

    # 基本面评分
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

        fund_score = round(min(max(fund_score, 0.0), 10.0), 1)
        print(f"  基本面评分: {fund_score:.1f}/10")
    else:
        fund_score = None
        print(f"  基本面评分: 未接入数据")

    # 情绪评分
    if sentiment and not sentiment.get('degraded'):
        overall = sentiment.get('overall_sentiment')
        sent_score = round(overall * 10, 1) if overall else 5.0
        print(f"  市场情绪评分: {sent_score:.1f}/10")
    else:
        sent_score = None
        print(f"  市场情绪评分: 未接入数据")

    # 综合评分
    scores = [tech_score]
    if fund_score is not None:
        scores.append(fund_score)
    if sent_score is not None:
        scores.append(sent_score)

    final_score = sum(scores) / len(scores)
    print(f"\n  🎯 综合评分: {final_score:.1f}/10")

    # 投资建议
    if final_score >= 7:
        action = "买入"
        risk = "低风险"
        color = "🟢"
    elif final_score >= 5:
        action = "持有"
        risk = "中等风险"
        color = "🟡"
    else:
        action = "观望"
        risk = "高风险"
        color = "🔴"

    print(f"  {color} 投资建议: {action}")
    print(f"  风险等级: {risk}")
    print(f"  置信度: {min(1.0, final_score/10.0):.0%}")

    print(f"\n{'='*60}")
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        stock_code = sys.argv[1]
    else:
        stock_code = "600418.SH"  # 默认江淮汽车

    analyze_stock(stock_code)
