# jac_demo_analysis.py - 江淮汽车演示分析（使用模拟数据）
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

class JACDemoAnalyzer:
    """江淮汽车演示分析器（基于当前市场数据模拟）"""
    
    def __init__(self):
        self.symbol = "600418.SH"
        self.company_name = "江淮汽车"
        # 基于网络搜索的实际数据模拟
        self.current_price = 49.99
        self.previous_close = 46.85
        
    def generate_demo_data(self):
        """生成演示用的历史数据"""
        # 生成最近6个月的交易日数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        
        # 创建交易日序列
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')  # B表示工作日
        
        # 基于真实价格生成模拟数据
        base_price = 35.0  # 6个月前的大概价格
        prices = []
        volumes = []
        
        np.random.seed(42)  # 固定随机种子确保结果一致
        
        for i, date in enumerate(date_range):
            # 模拟价格趋势：总体上涨趋势
            trend = (self.current_price - base_price) * i / len(date_range)
            # 加入随机波动
            daily_change = np.random.normal(0, 0.02)  # 2%的日波动
            price = base_price + trend + base_price * daily_change
            
            # 确保价格合理
            if len(prices) > 0:
                price = max(prices[-1] * 0.9, min(prices[-1] * 1.1, price))
            
            prices.append(price)
            
            # 模拟成交量
            volume = np.random.normal(150000, 50000)  # 平均15万股
            volumes.append(max(10000, int(volume)))
        
        # 调整最后一天的价格为当前价格
        if len(prices) > 0:
            prices[-1] = self.current_price
        
        # 生成OHLC数据
        data = []
        for i, (date, close, volume) in enumerate(zip(date_range, prices, volumes)):
            # 生成开高低价
            high = close * (1 + abs(np.random.normal(0, 0.01)))
            low = close * (1 - abs(np.random.normal(0, 0.01)))
            open_price = close + np.random.normal(0, close * 0.005)
            
            # 确保OHLC逻辑正确
            high = max(high, close, open_price)
            low = min(low, close, open_price)
            
            data.append({
                'Date': date,
                'Open': round(open_price, 2),
                'High': round(high, 2),
                'Low': round(low, 2),
                'Close': round(close, 2),
                'Volume': volume
            })
        
        df = pd.DataFrame(data)
        df.set_index('Date', inplace=True)
        return df
    
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
        else:
            signals.append("均线交错，方向不明")
        
        # RSI分析
        rsi = latest['RSI']
        if pd.notna(rsi):
            if rsi > 70:
                signals.append("RSI超买区域，注意回调风险")
                score -= 1
            elif rsi < 30:
                signals.append("RSI超卖区域，存在反弹机会")
                score += 1
            else:
                signals.append("RSI中性区域")
        
        # MACD分析
        if latest['MACD'] > latest['MACD_Signal'] and latest['MACD_Histogram'] > 0:
            signals.append("MACD金叉信号，动能向好")
            score += 1
        elif latest['MACD'] < latest['MACD_Signal'] and latest['MACD_Histogram'] < 0:
            signals.append("MACD死叉信号，动能走弱")
            score -= 1
        
        # 布林带分析
        price = latest['Close']
        if price > latest['BB_Upper']:
            signals.append("价格突破布林带上轨，强势上涨")
            score += 0.5
        elif price < latest['BB_Lower']:
            signals.append("价格跌破布林带下轨，弱势下跌")
            score -= 0.5
        elif price > latest['BB_Middle']:
            signals.append("价格位于布林带上半部，偏强")
        else:
            signals.append("价格位于布林带下半部，偏弱")
        
        # 成交量分析
        volume_ma5 = df['Volume'].rolling(window=5).mean().iloc[-1]
        if latest['Volume'] > volume_ma5 * 1.5:
            signals.append("成交量显著放大，关注度提升")
            score += 0.5
        elif latest['Volume'] < volume_ma5 * 0.7:
            signals.append("成交量相对萎缩")
            score -= 0.3
        
        # 价格位置分析
        price_position = (price - df['Low'].tail(20).min()) / (df['High'].tail(20).max() - df['Low'].tail(20).min())
        if price_position > 0.8:
            signals.append("价格接近近期高点")
        elif price_position < 0.2:
            signals.append("价格接近近期低点")
        
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
    
    def comprehensive_analysis(self):
        """综合分析"""
        try:
            print("📊 正在生成江淮汽车演示数据...")
            
            # 生成演示数据
            hist_data = self.generate_demo_data()
            
            # 计算技术指标
            hist_data = self.calculate_technical_indicators(hist_data)
            
            # 获取最新数据
            latest = hist_data.iloc[-1]
            previous = hist_data.iloc[-2]
            
            # 趋势分析
            trend_analysis = self.analyze_trend(hist_data)
            
            # 支撑阻力分析
            recent_data = hist_data.tail(20)
            resistance = recent_data['High'].quantile(0.8)
            support = recent_data['Low'].quantile(0.2)
            
            sr_analysis = {
                'support': round(support, 2),
                'resistance': round(resistance, 2),
                'current_price': round(latest['Close'], 2),
                'distance_to_support': round((latest['Close'] - support) / latest['Close'] * 100, 2),
                'distance_to_resistance': round((resistance - latest['Close']) / latest['Close'] * 100, 2)
            }
            
            # 价格变化分析
            price_changes = {
                '1d_change': round(((latest['Close'] - previous['Close']) / previous['Close']) * 100, 2),
                '5d_change': round(((latest['Close'] - hist_data['Close'].iloc[-6]) / hist_data['Close'].iloc[-6]) * 100, 2),
                '20d_change': round(((latest['Close'] - hist_data['Close'].iloc[-21]) / hist_data['Close'].iloc[-21]) * 100, 2)
            }
            
            # 波动率分析
            volatility = hist_data['Close'].pct_change().std() * np.sqrt(252) * 100
            
            return {
                'symbol': self.symbol,
                'company_name': self.company_name,
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
                    'ma5': round(latest['MA5'], 2),
                    'ma10': round(latest['MA10'], 2),
                    'ma20': round(latest['MA20'], 2),
                    'ma60': round(latest['MA60'], 2),
                    'rsi': round(latest['RSI'], 1),
                    'macd': round(latest['MACD'], 3),
                    'macd_signal': round(latest['MACD_Signal'], 3),
                    'bb_upper': round(latest['BB_Upper'], 2),
                    'bb_middle': round(latest['BB_Middle'], 2),
                    'bb_lower': round(latest['BB_Lower'], 2),
                    'volume': int(latest['Volume'])
                },
                'trend_analysis': trend_analysis,
                'support_resistance': sr_analysis,
                'price_changes': price_changes,
                'volatility': round(volatility, 2),
                'historical_data': hist_data.tail(30).to_dict('records'),  # 最近30天数据用于图表
                'market_status': "演示模式"
            }
            
        except Exception as e:
            print(f"分析失败: {e}")
            return {"error": f"分析失败: {str(e)}"}
    
    def create_charts(self, analysis_data):
        """创建可视化图表"""
        try:
            hist_data = pd.DataFrame(analysis_data['historical_data'])
            hist_data['Date'] = pd.to_datetime(hist_data.index) if 'Date' not in hist_data.columns else pd.to_datetime(hist_data['Date'])
            
            # 创建图表
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle(f'{self.company_name} ({self.symbol}) 技术分析图表', fontsize=16, fontweight='bold')
            
            # 1. 价格与移动平均线
            ax1.plot(hist_data.index, hist_data['Close'], label='收盘价', linewidth=2, color='black')
            ax1.plot(hist_data.index, hist_data['MA5'], label='MA5', alpha=0.7, color='red')
            ax1.plot(hist_data.index, hist_data['MA10'], label='MA10', alpha=0.7, color='blue')
            ax1.plot(hist_data.index, hist_data['MA20'], label='MA20', alpha=0.7, color='green')
            ax1.set_title('价格走势与移动平均线')
            ax1.set_ylabel('价格 (¥)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. 布林带
            ax2.plot(hist_data.index, hist_data['Close'], label='收盘价', color='black', linewidth=2)
            ax2.plot(hist_data.index, hist_data['BB_Upper'], label='布林上轨', alpha=0.5, color='red', linestyle='--')
            ax2.plot(hist_data.index, hist_data['BB_Middle'], label='布林中轨', alpha=0.7, color='blue')
            ax2.plot(hist_data.index, hist_data['BB_Lower'], label='布林下轨', alpha=0.5, color='green', linestyle='--')
            ax2.fill_between(hist_data.index, hist_data['BB_Upper'], hist_data['BB_Lower'], alpha=0.1, color='gray')
            ax2.set_title('布林带指标')
            ax2.set_ylabel('价格 (¥)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # 3. RSI指标
            ax3.plot(hist_data.index, hist_data['RSI'], label='RSI', color='purple', linewidth=2)
            ax3.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='超买线 (70)')
            ax3.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='超卖线 (30)')
            ax3.axhline(y=50, color='gray', linestyle='-', alpha=0.5)
            ax3.set_title('RSI相对强弱指标')
            ax3.set_ylabel('RSI')
            ax3.set_ylim(0, 100)
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            
            # 4. MACD指标
            ax4.plot(hist_data.index, hist_data['MACD'], label='MACD', color='blue')
            ax4.plot(hist_data.index, hist_data['MACD_Signal'], label='Signal', color='red')
            colors = ['green' if h >= 0 else 'red' for h in hist_data['MACD_Histogram']]
            ax4.bar(hist_data.index, hist_data['MACD_Histogram'], alpha=0.3, color=colors, label='Histogram')
            ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax4.set_title('MACD指标')
            ax4.set_ylabel('MACD')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            
            # 调整布局
            plt.tight_layout()
            
            # 保存图表
            chart_filename = f"jac_charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            plt.savefig(chart_filename, dpi=300, bbox_inches='tight')
            print(f"📊 技术分析图表已保存: {chart_filename}")
            
            return chart_filename
            
        except Exception as e:
            print(f"图表生成失败: {e}")
            return None

def format_analysis_report(analysis_data):
    """格式化分析报告"""
    if 'error' in analysis_data:
        return f"❌ 分析失败: {analysis_data['error']}"
    
    report = []
    report.append("=" * 60)
    report.append("🚗 江淮汽车 (600418.SH) 技术分析报告 [演示版]")
    report.append("=" * 60)
    report.append(f"📅 分析时间: {analysis_data['analysis_time']}")
    report.append(f"📊 数据模式: {analysis_data['market_status']}")
    report.append("")
    
    # 实时数据
    real_time = analysis_data['real_time_data']
    report.append("📈 模拟行情数据:")
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
    
    report.append("=" * 60)
    report.append("⚠️ 本报告为演示版本，使用模拟数据")
    report.append("⚠️ 投资有风险，入市需谨慎")
    report.append("⚠️ 本分析仅供参考，不构成投资建议")
    report.append("=" * 60)
    
    return "\n".join(report)

def main():
    """主函数"""
    print("🚀 启动江淮汽车技术分析 [演示版]...")
    
    try:
        # 创建分析器
        analyzer = JACDemoAnalyzer()
        
        # 执行分析
        analysis_result = analyzer.comprehensive_analysis()
        
        if 'error' in analysis_result:
            print(f"❌ 分析失败: {analysis_result['error']}")
            return None
        
        # 格式化并输出报告
        report = format_analysis_report(analysis_result)
        print(report)
        
        # 生成图表
        print("\n📊 正在生成技术分析图表...")
        chart_file = analyzer.create_charts(analysis_result)
        
        # 保存分析结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"jac_demo_analysis_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # 移除历史数据以减小文件大小
            save_data = analysis_result.copy()
            save_data.pop('historical_data', None)
            json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 详细分析结果已保存到: {output_file}")
        
        if chart_file:
            print(f"📊 技术分析图表已保存到: {chart_file}")
        
        print("\n✅ 江淮汽车技术分析完成！")
        
        return analysis_result
        
    except Exception as e:
        print(f"❌ 分析过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = main()