#!/usr/bin/env python3
# simple_test.py - 简化测试长江电力查询
import os
import sys
import sqlite3
from datetime import datetime

def create_test_data():
    """创建测试数据"""
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    
    # 创建stocks表
    cursor.execute('''
        CREATE TABLE stocks (
            id INTEGER PRIMARY KEY,
            code VARCHAR(10) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            exchange VARCHAR(10) NOT NULL,
            industry VARCHAR(50),
            market_cap DECIMAL(15,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建stock_prices表
    cursor.execute('''
        CREATE TABLE stock_prices (
            id INTEGER PRIMARY KEY,
            stock_code VARCHAR(10) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            open_price DECIMAL(10,3),
            high_price DECIMAL(10,3),
            low_price DECIMAL(10,3),
            close_price DECIMAL(10,3),
            volume BIGINT,
            change_pct DECIMAL(5,2)
        )
    ''')
    
    # 插入长江电力数据
    cursor.execute('''
        INSERT INTO stocks (code, name, exchange, industry, market_cap) 
        VALUES (?, ?, ?, ?, ?)
    ''', ('600900.SH', '长江电力', 'SH', '电力', 580000000000))
    
    # 插入招商银行数据 (用于批量测试)
    cursor.execute('''
        INSERT INTO stocks (code, name, exchange, industry, market_cap) 
        VALUES (?, ?, ?, ?, ?)
    ''', ('600036.SH', '招商银行', 'SH', '银行', 1200000000000))
    
    # 插入价格数据
    cursor.execute('''
        INSERT INTO stock_prices (stock_code, timestamp, open_price, high_price, low_price, close_price, volume, change_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('600900.SH', datetime.now(), 23.50, 24.20, 23.30, 24.15, 15680000, 2.85))
    
    cursor.execute('''
        INSERT INTO stock_prices (stock_code, timestamp, open_price, high_price, low_price, close_price, volume, change_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('600036.SH', datetime.now(), 41.20, 42.10, 40.95, 41.80, 8520000, 1.45))
    
    conn.commit()
    return conn

def query_changjian_power():
    """查询长江电力信息"""
    print("=" * 60)
    print("🔍 股票分析系统 - 长江电力查询测试")
    print("=" * 60)
    
    # 创建测试数据库
    conn = create_test_data()
    cursor = conn.cursor()
    
    try:
        # 1. 基础信息查询
        print("\n📊 1. 长江电力基础信息:")
        print("-" * 40)
        cursor.execute('''
            SELECT code, name, exchange, industry, market_cap
            FROM stocks 
            WHERE code = ?
        ''', ('600900.SH',))
        
        stock_info = cursor.fetchone()
        if stock_info:
            print(f"股票代码: {stock_info[0]}")
            print(f"公司名称: {stock_info[1]}")
            print(f"交易所: {stock_info[2]}")
            print(f"所属行业: {stock_info[3]}")
            print(f"市值: {stock_info[4]:,.0f} 元")
        else:
            print("❌ 未找到长江电力数据")
            return
        
        # 2. 最新价格信息
        print("\n💰 2. 最新价格信息:")
        print("-" * 40)
        cursor.execute('''
            SELECT open_price, high_price, low_price, close_price, volume, change_pct, timestamp
            FROM stock_prices 
            WHERE stock_code = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', ('600900.SH',))
        
        price_info = cursor.fetchone()
        if price_info:
            print(f"开盘价: ¥{price_info[0]:.2f}")
            print(f"最高价: ¥{price_info[1]:.2f}")
            print(f"最低价: ¥{price_info[2]:.2f}")
            print(f"收盘价: ¥{price_info[3]:.2f}")
            print(f"成交量: {price_info[4]:,} 股")
            print(f"涨跌幅: {price_info[5]:+.2f}%")
            print(f"更新时间: {price_info[6]}")
        
        # 3. 模拟技术分析
        print("\n📈 3. 技术分析 (模拟):")
        print("-" * 40)
        current_price = price_info[3] if price_info else 24.15
        ma5 = current_price * 0.98   # 模拟5日均线
        ma20 = current_price * 0.95  # 模拟20日均线
        
        print(f"当前价格: ¥{current_price:.2f}")
        print(f"5日均线: ¥{ma5:.2f}")
        print(f"20日均线: ¥{ma20:.2f}")
        
        # 简单趋势判断
        if current_price > ma5 > ma20:
            trend = "🟢 上升趋势"
            trend_strength = "强"
        elif current_price > ma20:
            trend = "🔵 震荡上行"
            trend_strength = "中"
        else:
            trend = "🔴 下降趋势"
            trend_strength = "弱"
        
        print(f"趋势判断: {trend}")
        print(f"趋势强度: {trend_strength}")
        
        # 4. 模拟基本面分析
        print("\n🏢 4. 基本面分析 (模拟):")
        print("-" * 40)
        market_cap = stock_info[4] if stock_info else 580000000000
        pe_ratio = 12.5  # 模拟市盈率
        pb_ratio = 1.8   # 模拟市净率
        roe = 0.125      # 模拟净资产收益率
        
        print(f"市盈率 (PE): {pe_ratio:.1f}")
        print(f"市净率 (PB): {pb_ratio:.1f}")
        print(f"净资产收益率 (ROE): {roe:.1%}")
        print(f"市值: {market_cap/100000000:.0f} 亿元")
        
        # 估值判断
        if pe_ratio < 15 and pb_ratio < 2:
            valuation = "🟢 估值合理"
        elif pe_ratio < 20:
            valuation = "🔵 估值偏高"
        else:
            valuation = "🔴 估值过高"
        
        print(f"估值水平: {valuation}")
        
        # 5. 投资建议
        print("\n🎯 5. 综合投资建议:")
        print("-" * 40)
        
        # 综合评分计算
        tech_score = 7 if "上升" in trend else (6 if "震荡" in trend else 4)
        fund_score = 8 if "合理" in valuation else (6 if "偏高" in valuation else 4)
        industry_score = 7  # 电力行业稳定性评分
        
        overall_score = (tech_score + fund_score + industry_score) / 3
        
        print(f"技术面评分: {tech_score}/10")
        print(f"基本面评分: {fund_score}/10")
        print(f"行业评分: {industry_score}/10")
        print(f"综合评分: {overall_score:.1f}/10")
        
        # 投资建议
        if overall_score >= 7:
            recommendation = "🟢 买入"
            risk_level = "低风险"
        elif overall_score >= 6:
            recommendation = "🔵 持有"
            risk_level = "中等风险"
        else:
            recommendation = "🔴 观望"
            risk_level = "高风险"
        
        print(f"投资建议: {recommendation}")
        print(f"风险等级: {risk_level}")
        
        # 6. 批量对比
        print("\n📊 6. 行业对比 (长江电力 vs 招商银行):")
        print("-" * 40)
        cursor.execute('''
            SELECT s.code, s.name, s.industry, p.close_price, p.change_pct
            FROM stocks s
            LEFT JOIN stock_prices p ON s.code = p.stock_code
            WHERE s.code IN ('600900.SH', '600036.SH')
        ''')
        
        comparison = cursor.fetchall()
        for stock in comparison:
            code, name, industry, price, change = stock
            status = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            print(f"{status} {code} {name} ({industry}): ¥{price:.2f} ({change:+.2f}%)")
        
        print("\n" + "=" * 60)
        print("✅ 查询完成! 长江电力作为电力行业龙头，具有稳定的现金流和分红能力。")
        print("🔍 建议关注电力体制改革和清洁能源转型对公司的影响。")
        print("=" * 60)
    
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()

if __name__ == "__main__":
    query_changjian_power()