# simple_jac_analysis.py - 简化版江淮汽车分析脚本
import asyncio
import json
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleJACAnalyzer:
    """简化版江淮汽车分析器"""
    
    def __init__(self):
        self.symbol = "600418.SS"  # Yahoo Finance格式
        self.symbol_display = "600418.SH"  # 显示格式
        
    def get_stock_data(self, period="6mo"):
        """获取股票数据"""
        try:
            ticker = yf.Ticker(self.symbol)
            
            # 获取股票信息
            info = ticker.info
            
            # 获取历史数据
            hist = ticker.history(period=period)
            
            if hist.empty:
                logger.error("无法获取历史数据")
                return None, None
                
            return info, hist
            
        except Exception as e:
            logger.error(f"获取股票数据失败: {e}")
            return None, None
    
    def calculate_technical_indicators(self, df):
        """计算技术指标"""
        # 移动平均线
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA10'] = df['Close'].rolling(window=10).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        # RSI指标
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD指标
        ema12 = df['Close'].ewm(span=12).mean()
        ema26 = df['Close'].ewm(span=26).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        
        # 布林带
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        
        return df
    
    def analyze_trend(self, df):
        """趋势分析"""
        latest = df.iloc[-1]
        signals = []
        score = 0
        
        # 移动平均线分析
        if latest['MA5'] > latest['MA10'] > latest['MA20']:
            signals.append("短期均线多头排列")
            score += 2
        elif latest['MA5'] < latest['MA10'] < latest['MA20']:
            signals.append("短期均线空头排列")
            score -= 2
        
        # RSI分析
        rsi = latest['RSI']
        if pd.notna(rsi):
            if rsi > 70:
                signals.append("RSI超买区域")
                score -= 1
            elif rsi < 30:
                signals.append("RSI超卖区域")
                score += 1
            else:
                signals.append("RSI中性区域")
        
        # MACD分析
        if latest['MACD'] > latest['MACD_Signal']:
            signals.append("MACD金叉信号")
            score += 1
        else:
            signals.append("MACD死叉信号")
            score -= 1
        
        # 布林带分析
        price = latest['Close']
        if price > latest['BB_Upper']:
            signals.append("价格突破布林带上轨")
            score -= 1
        elif price < latest['BB_Lower']:
            signals.append("价格跌破布林带下轨")
            score += 1
        elif price > latest['BB_Middle']:
            signals.append("价格位于布林带上半部")
        else:
            signals.append("价格位于布林带下半部")
        
        # 成交量分析
        volume_ma5 = df['Volume'].rolling(window=5).mean().iloc[-1]
        if latest['Volume'] > volume_ma5 * 1.5:
            signals.append("成交量放大")
            score += 0.5
        elif latest['Volume'] < volume_ma5 * 0.5:
            signals.append("成交量萎缩")
            score -= 0.5
        
        # 综合评级
        if score >= 3:
            rating = "强烈买入"
        elif score >= 1:
            rating = "买入"
        elif score >= -1:
            rating = "持有"
        elif score >= -3:
            rating = "卖出"
        else:
            rating = "强烈卖出"
        
        return {
            'rating': rating,
            'score': round(score, 1),
            'signals': signals
        }
    
    def calculate_support_resistance(self, df):
        """计算支撑阻力位"""
        # 最近20个交易日的高低点
        recent_data = df.tail(20)
        resistance = recent_data['High'].quantile(0.8)
        support = recent_data['Low'].quantile(0.2)
        current_price = df['Close'].iloc[-1]
        
        return {
            'support': round(support, 2),
            'resistance': round(resistance, 2),
            'current_price': round(current_price, 2),
            'distance_to_support': round((current_price - support) / current_price * 100, 2),
            'distance_to_resistance': round((resistance - current_price) / current_price * 100, 2)
        }
    
    def comprehensive_analysis(self):
        """综合分析"""
        try:
            print("📊 正在获取江淮汽车数据...")
            
            # 获取数据
            info, hist_data = self.get_stock_data()
            
            if hist_data is None:
                return {"error": "无法获取股票数据"}
            
            print("🔍 正在计算技术指标...")
            
            # 计算技术指标
            hist_data = self.calculate_technical_indicators(hist_data)
            
            # 获取最新数据
            latest = hist_data.iloc[-1]
            previous = hist_data.iloc[-2]
            
            # 趋势分析
            trend_analysis = self.analyze_trend(hist_data)
            
            # 支撑阻力分析
            sr_analysis = self.calculate_support_resistance(hist_data)
            
            # 价格变化分析
            price_changes = {
                '1d_change': round(((latest['Close'] - previous['Close']) / previous['Close']) * 100, 2),
                '5d_change': round(((latest['Close'] - hist_data['Close'].iloc[-6]) / hist_data['Close'].iloc[-6]) * 100, 2) if len(hist_data) >= 6 else 0,
                '20d_change': round(((latest['Close'] - hist_data['Close'].iloc[-21]) / hist_data['Close'].iloc[-21]) * 100, 2) if len(hist_data) >= 21 else 0
            }
            
            # 波动率分析
            volatility = hist_data['Close'].pct_change().std() * np.sqrt(252) * 100
            
            # 基本面信息
            company_info = {
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'pb_ratio': info.get('priceToBook', 0),
                'dividend_yield': info.get('dividendYield', 0)
            }
            
            return {
                'symbol': self.symbol_display,
                'company_name': '江淮汽车',
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'real_time_data': {
                    'price': round(latest['Close'], 2),
                    'change': round(latest['Close'] - previous['Close'], 2),
                    'change_percent': round(((latest['Close'] - previous['Close']) / previous['Close']) * 100, 2),
                    'volume': int(latest['Volume']),
                    'high': round(latest['High'], 2),
                    'low': round(latest['Low'], 2),
                    'open': round(latest['Open'], 2)
                },
                'technical_indicators': {
                    'price': round(latest['Close'], 2),
                    'ma5': round(latest['MA5'], 2) if pd.notna(latest['MA5']) else 0,
                    'ma10': round(latest['MA10'], 2) if pd.notna(latest['MA10']) else 0,
                    'ma20': round(latest['MA20'], 2) if pd.notna(latest['MA20']) else 0,
                    'ma60': round(latest['MA60'], 2) if pd.notna(latest['MA60']) else 0,
                    'rsi': round(latest['RSI'], 1) if pd.notna(latest['RSI']) else 0,
                    'macd': round(latest['MACD'], 3) if pd.notna(latest['MACD']) else 0,
                    'macd_signal': round(latest['MACD_Signal'], 3) if pd.notna(latest['MACD_Signal']) else 0,
                    'bb_upper': round(latest['BB_Upper'], 2) if pd.notna(latest['BB_Upper']) else 0,
                    'bb_middle': round(latest['BB_Middle'], 2) if pd.notna(latest['BB_Middle']) else 0,
                    'bb_lower': round(latest['BB_Lower'], 2) if pd.notna(latest['BB_Lower']) else 0,
                    'volume': int(latest['Volume'])
                },
                'trend_analysis': trend_analysis,
                'support_resistance': sr_analysis,
                'price_changes': price_changes,
                'volatility': round(volatility, 2),
                'company_info': company_info,
                'market_status': self._get_market_status()
            }
            
        except Exception as e:
            logger.error(f"分析失败: {e}")
            return {"error": f"分析失败: {str(e)}"}
    
    def _get_market_status(self):
        """获取市场状态"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()
        
        if weekday >= 5:
            return "休市"
        
        if (9 <= hour < 11) or (hour == 11 and minute <= 30) or (13 <= hour < 15):
            return "交易中"
        else:
            return "休市"

def format_analysis_report(analysis_data):
    """格式化分析报告"""
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
    change_symbol = "📈" if real_time['change'] >= 0 else "📉"
    report.append(f"  涨跌幅度: {change_symbol} {real_time['change']:+.2f} ({real_time['change_percent']:+.2f}%)")
    report.append(f"  开盘价格: ¥{real_time['open']:.2f}")
    report.append(f"  最高价格: ¥{real_time['high']:.2f}")
    report.append(f"  最低价格: ¥{real_time['low']:.2f}")
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
    
    # 布林带
    report.append("📈 布林带指标:")
    bb_position = "上轨突破" if real_time['price'] > indicators['bb_upper'] else \
                  "下轨突破" if real_time['price'] < indicators['bb_lower'] else \
                  "中轨上方" if real_time['price'] > indicators['bb_middle'] else "中轨下方"
    report.append(f"  上轨: ¥{indicators['bb_upper']:.2f}")
    report.append(f"  中轨: ¥{indicators['bb_middle']:.2f}")
    report.append(f"  下轨: ¥{indicators['bb_lower']:.2f}")
    report.append(f"  位置: {bb_position}")
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
    
    # 基本面信息
    company_info = analysis_data['company_info']
    report.append("💼 基本面信息:")
    if company_info['market_cap'] > 0:
        market_cap_billion = company_info['market_cap'] / 1e9
        report.append(f"  市值: ¥{market_cap_billion:.0f}亿")
    if company_info['pe_ratio'] > 0:
        report.append(f"  市盈率: {company_info['pe_ratio']:.1f}")
    if company_info['pb_ratio'] > 0:
        report.append(f"  市净率: {company_info['pb_ratio']:.2f}")
    if company_info['dividend_yield'] > 0:
        report.append(f"  股息率: {company_info['dividend_yield']*100:.2f}%")
    report.append("")
    
    report.append("=" * 60)
    report.append("⚠️ 风险提示: 投资有风险，入市需谨慎")
    report.append("⚠️ 本分析仅供参考，不构成投资建议")
    report.append("=" * 60)
    
    return "\n".join(report)

def main():
    """主函数"""
    print("🚀 启动江淮汽车技术分析...")
    
    try:
        # 创建分析器
        analyzer = SimpleJACAnalyzer()
        
        # 执行分析
        analysis_result = analyzer.comprehensive_analysis()
        
        # 格式化并输出报告
        report = format_analysis_report(analysis_result)
        print(report)
        
        # 保存分析结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"jac_analysis_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 详细分析结果已保存到: {output_file}")
        
        return analysis_result
        
    except Exception as e:
        print(f"❌ 分析过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = main()