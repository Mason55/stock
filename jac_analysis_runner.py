# jac_analysis_runner.py - 江淮汽车分析执行脚本
import asyncio
import json
import sys
import os
from datetime import datetime

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from services.jac_analyzer import JACAnalyzer

def format_analysis_report(analysis_data: dict) -> str:
    """格式化分析报告为可读文本"""
    if 'error' in analysis_data:
        return f"❌ 分析失败: {analysis_data['error']}"
    
    report = []
    report.append("=" * 60)
    report.append("🚗 江淮汽车 (600418.SH) 技术分析报告")
    report.append("=" * 60)
    report.append(f"📅 分析时间: {analysis_data['analysis_time']}")
    report.append(f"📊 市场状态: {analysis_data['market_status']}")
    report.append("")
    
    # 实时数据
    real_time = analysis_data['real_time_data']
    report.append("📈 实时行情:")
    report.append(f"  当前价格: ¥{real_time['price']:.2f}")
    if real_time['change'] is not None:
        change_symbol = "📈" if real_time['change'] >= 0 else "📉"
        report.append(f"  涨跌幅度: {change_symbol} {real_time['change']:+.2f} ({real_time['change_percent']:+.2f}%)")
    report.append(f"  成交量: {real_time['volume']:,}")
    report.append("")
    
    # 技术指标
    indicators = analysis_data['technical_indicators']
    report.append("🔍 技术指标:")
    report.append(f"  MA5:  ¥{indicators['ma5']:.2f}")
    report.append(f"  MA10: ¥{indicators['ma10']:.2f}")
    report.append(f"  MA20: ¥{indicators['ma20']:.2f}")
    report.append(f"  MA60: ¥{indicators['ma60']:.2f}")
    report.append(f"  RSI:  {indicators['rsi']:.1f}")
    report.append(f"  MACD: {indicators['macd']:.3f}")
    report.append("")
    
    # 趋势分析
    trend = analysis_data['trend_analysis']
    rating_emoji = {
        "强烈买入": "🟢🟢",
        "买入": "🟢",
        "持有": "🟡",
        "卖出": "🔴",
        "强烈卖出": "🔴🔴"
    }
    report.append("📊 趋势分析:")
    report.append(f"  综合评级: {rating_emoji.get(trend['rating'], '❓')} {trend['rating']} (评分: {trend['score']})")
    report.append("  技术信号:")
    for signal in trend['signals']:
        report.append(f"    • {signal}")
    report.append("")
    
    # 支撑阻力
    sr = analysis_data['support_resistance']
    report.append("📏 支撑阻力位:")
    report.append(f"  支撑位: ¥{sr['support']:.2f} (距离: {sr['distance_to_support']:+.1f}%)")
    report.append(f"  阻力位: ¥{sr['resistance']:.2f} (距离: {sr['distance_to_resistance']:+.1f}%)")
    report.append("")
    
    # 价格变化
    changes = analysis_data['price_changes']
    report.append("📊 价格变化:")
    report.append(f"  1日涨跌: {changes['1d_change']:+.2f}%")
    report.append(f"  5日涨跌: {changes['5d_change']:+.2f}%")
    report.append(f"  20日涨跌: {changes['20d_change']:+.2f}%")
    report.append(f"  年化波动率: {analysis_data['volatility']:.1f}%")
    report.append("")
    
    # 布林带
    report.append("📈 布林带指标:")
    bb_position = "上轨" if real_time['price'] > indicators['bb_upper'] else \
                  "下轨" if real_time['price'] < indicators['bb_lower'] else \
                  "中轨上方" if real_time['price'] > indicators['bb_middle'] else "中轨下方"
    report.append(f"  上轨: ¥{indicators['bb_upper']:.2f}")
    report.append(f"  中轨: ¥{indicators['bb_middle']:.2f}")
    report.append(f"  下轨: ¥{indicators['bb_lower']:.2f}")
    report.append(f"  当前位置: {bb_position}")
    report.append("")
    
    report.append("=" * 60)
    report.append("⚠️ 风险提示: 投资有风险，入市需谨慎")
    report.append("=" * 60)
    
    return "\n".join(report)

async def main():
    """主函数"""
    print("🚀 启动江淮汽车技术分析...")
    
    try:
        # 创建分析器
        analyzer = JACAnalyzer()
        
        # 执行综合分析
        print("📊 正在获取数据并进行技术分析...")
        analysis_result = await analyzer.comprehensive_analysis()
        
        # 格式化并输出报告
        report = format_analysis_report(analysis_result)
        print(report)
        
        # 保存分析结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"jac_analysis_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 分析结果已保存到: {output_file}")
        
        return analysis_result
        
    except Exception as e:
        print(f"❌ 分析过程中出现错误: {e}")
        return None

if __name__ == "__main__":
    # 运行分析
    result = asyncio.run(main())