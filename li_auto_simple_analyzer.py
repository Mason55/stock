# li_auto_simple_analyzer.py - 理想汽车简化分析器
import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, Optional

class SimpleStockQuote:
    def __init__(self, symbol: str, price: float, change: float = 0, change_pct: float = 0, volume: int = 0):
        self.symbol = symbol
        self.price = price
        self.change = change
        self.change_pct = change_pct
        self.volume = volume

class LiAutoSimpleAnalyzer:
    """理想汽车简化分析器 - 主要基于实时数据"""
    
    def __init__(self):
        self.hk_symbol = "2015.HK"
        self.us_symbol = "LI"
        self.sina_code = "rt_hk02015"
        self.company_name = "理想汽车"
        
    async def get_sina_data(self) -> Optional[Dict]:
        """获取新浪财经实时数据"""
        sina_url = f"https://hq.sinajs.cn/list={self.sina_code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/',
            'Accept': '*/*'
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(sina_url) as response:
                    if response.status != 200:
                        return None
                    
                    content = await response.text()
                    
                    if 'hq_str_' not in content or '"' not in content:
                        return None
                    
                    # 解析数据
                    data_line = content.split('"')[1]
                    if not data_line.strip():
                        return None
                    
                    parts = data_line.split(',')
                    if len(parts) < 15:
                        return None
                    
                    # 港股数据格式解析
                    name = parts[1]  # 中文名称
                    open_price = float(parts[2]) if parts[2] else 0
                    yesterday_close = float(parts[3]) if parts[3] else 0
                    current_price = float(parts[6]) if parts[6] else 0
                    high_price = float(parts[4]) if parts[4] else 0
                    low_price = float(parts[5]) if parts[5] else 0
                    
                    # 计算涨跌
                    change = current_price - yesterday_close
                    change_pct = (change / yesterday_close * 100) if yesterday_close > 0 else 0
                    
                    # 成交额转换为成交量（简化处理）
                    turnover = float(parts[10]) if len(parts) > 10 and parts[10] else 0
                    volume = int(turnover / current_price) if current_price > 0 else 0
                    
                    return {
                        'name': name,
                        'current_price': current_price,
                        'yesterday_close': yesterday_close,
                        'open_price': open_price,
                        'high_price': high_price,
                        'low_price': low_price,
                        'change': change,
                        'change_pct': change_pct,
                        'volume': volume,
                        'turnover': turnover
                    }
                    
        except Exception as e:
            print(f"获取数据失败: {e}")
            return None
    
    def analyze_technical_signals(self, data: Dict) -> Dict:
        """基于当日数据的技术信号分析"""
        if not data:
            return {}
        
        signals = []
        score = 0
        
        current = data['current_price']
        open_price = data['open_price']
        high = data['high_price']
        low = data['low_price']
        change_pct = data['change_pct']
        
        # 日内表现分析
        if current > open_price:
            signals.append("日内上涨")
            score += 1
        else:
            signals.append("日内下跌")
            score -= 1
            
        # 振幅分析
        if high > 0 and low > 0:
            amplitude = ((high - low) / low) * 100
            if amplitude > 5:
                signals.append("振幅较大")
                score -= 0.5  # 高波动性降低评分
            elif amplitude < 2:
                signals.append("振幅较小")
                score += 0.5  # 低波动性加分
        
        # 涨跌幅分析
        if change_pct > 3:
            signals.append("大涨")
            score += 2
        elif change_pct > 1:
            signals.append("上涨")
            score += 1
        elif change_pct < -3:
            signals.append("大跌")
            score -= 2
        elif change_pct < -1:
            signals.append("下跌")
            score -= 1
        else:
            signals.append("窄幅震荡")
        
        # 生成建议
        if score >= 2:
            recommendation = "BUY"
            confidence = min(75, 50 + score * 10)
        elif score <= -2:
            recommendation = "SELL"
            confidence = min(75, 50 + abs(score) * 10)
        else:
            recommendation = "HOLD"
            confidence = 60
        
        return {
            'signals': signals,
            'score': score,
            'recommendation': recommendation,
            'confidence': confidence
        }
    
    def get_market_context(self) -> Dict:
        """获取市场环境背景"""
        now = datetime.now()
        hour = now.hour
        
        # 判断交易时段
        if 9 <= hour <= 12 or 13 <= hour <= 16:
            session = "正常交易时间"
            status = "TRADING"
        elif 17 <= hour <= 20:
            session = "盘后时间"
            status = "AFTER_HOURS"
        else:
            session = "休市时间"
            status = "CLOSED"
        
        # 新能源汽车行业背景
        industry_context = {
            'sector': '新能源汽车',
            'market_trend': '电动汽车渗透率持续提升',
            'policy_support': '国家政策大力支持新能源汽车发展',
            'competition': '行业竞争激烈，技术创新是关键'
        }
        
        return {
            'trading_session': session,
            'market_status': status,
            'industry': industry_context
        }
    
    async def run_analysis(self) -> Dict:
        """运行完整分析"""
        print(f"🔍 开始分析 {self.company_name} ({self.hk_symbol})...")
        
        # 获取基础数据
        market_context = self.get_market_context()
        sina_data = await self.get_sina_data()
        
        analysis_result = {
            'company': self.company_name,
            'symbol_hk': self.hk_symbol,
            'symbol_us': self.us_symbol,
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'market_context': market_context
        }
        
        if sina_data:
            analysis_result['market_data'] = sina_data
            
            # 技术分析
            technical_analysis = self.analyze_technical_signals(sina_data)
            analysis_result['technical_analysis'] = technical_analysis
            
            # 估值简单评估（基于PE倍数）
            # 理想汽车2024年大致PE在15-25倍区间
            current_price = sina_data['current_price']
            estimated_pe_range = (15, 25)
            analysis_result['valuation_note'] = f"当前价格 HK${current_price:.2f}, 预估PE倍数范围 {estimated_pe_range[0]}-{estimated_pe_range[1]}倍"
            
        else:
            analysis_result['error'] = '无法获取实时市场数据'
        
        return analysis_result

def format_simple_report(analysis: Dict) -> str:
    """格式化简化分析报告"""
    if 'error' in analysis:
        return f"❌ 分析失败: {analysis['error']}"
    
    report = []
    report.append("=" * 60)
    report.append(f"🚗 {analysis['company']} 股票分析报告")
    report.append("=" * 60)
    report.append(f"📅 分析时间: {analysis['analysis_time']}")
    report.append(f"🏢 港股代码: {analysis['symbol_hk']} | 美股代码: {analysis['symbol_us']}")
    
    # 市场环境
    context = analysis['market_context']
    report.append(f"📊 交易状态: {context['trading_session']} ({context['market_status']})")
    report.append("")
    
    # 实时行情
    if 'market_data' in analysis:
        data = analysis['market_data']
        change_symbol = "+" if data['change'] >= 0 else ""
        color_indicator = "🔴" if data['change'] < 0 else "🟢"
        
        report.append("📈 实时行情:")
        report.append(f"  {color_indicator} 现价: HK${data['current_price']:.2f}")
        report.append(f"  📊 涨跌: {change_symbol}{data['change']:.2f} ({change_symbol}{data['change_pct']:.2f}%)")
        report.append(f"  🌅 今开: HK${data['open_price']:.2f}")
        report.append(f"  ⬆️  最高: HK${data['high_price']:.2f}")
        report.append(f"  ⬇️  最低: HK${data['low_price']:.2f}")
        report.append(f"  📦 成交额: HK${data['turnover']:,.0f}")
        report.append("")
        
        # 技术分析
        if 'technical_analysis' in analysis:
            tech = analysis['technical_analysis']
            rec_emoji = {'BUY': '🚀', 'SELL': '📉', 'HOLD': '🤝'}
            rec_text = {'BUY': '买入', 'SELL': '卖出', 'HOLD': '持有'}
            
            report.append("🎯 技术分析:")
            report.append(f"  建议: {rec_emoji.get(tech['recommendation'], '🤝')} {rec_text.get(tech['recommendation'], '持有')}")
            report.append(f"  置信度: {tech['confidence']}%")
            report.append(f"  技术信号: {', '.join(tech['signals'])}")
            report.append(f"  综合评分: {tech['score']}")
            report.append("")
        
        # 估值备注
        if 'valuation_note' in analysis:
            report.append("💰 估值参考:")
            report.append(f"  {analysis['valuation_note']}")
            report.append("")
    
    # 行业背景
    industry = analysis['market_context']['industry']
    report.append("🏭 行业背景:")
    report.append(f"  行业: {industry['sector']}")
    report.append(f"  趋势: {industry['market_trend']}")
    report.append(f"  政策: {industry['policy_support']}")
    report.append(f"  竞争: {industry['competition']}")
    report.append("")
    
    report.append("=" * 60)
    report.append("📝 分析说明:")
    report.append("• 本分析基于实时市场数据和技术指标")
    report.append("• 理想汽车是中国领先的新能源汽车制造商")
    report.append("• 主要产品包括增程式电动SUV车型") 
    report.append("• 建议关注销量数据、新车型发布、电池技术进展等关键指标")
    report.append("")
    report.append("⚠️  风险提示: 股票投资有风险，本分析仅供参考，请谨慎决策")
    report.append("=" * 60)
    
    return "\n".join(report)

async def main():
    """主函数"""
    print("🚀 理想汽车股票分析系统启动...")
    
    analyzer = LiAutoSimpleAnalyzer()
    
    try:
        # 运行分析
        analysis_result = await analyzer.run_analysis()
        
        # 生成报告
        report = format_simple_report(analysis_result)
        print(report)
        
        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"li_auto_simple_analysis_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 分析结果已保存至: {filename}")
        
        # 生成图表数据
        if 'market_data' in analysis_result:
            chart_data = generate_chart_data(analysis_result['market_data'])
            chart_filename = f"li_auto_chart_data_{timestamp}.json"
            
            with open(chart_filename, 'w', encoding='utf-8') as f:
                json.dump(chart_data, f, ensure_ascii=False, indent=2)
            
            print(f"📊 图表数据已保存至: {chart_filename}")
        
    except Exception as e:
        print(f"❌ 分析过程出错: {e}")

def generate_chart_data(market_data: Dict) -> Dict:
    """生成图表数据"""
    return {
        'chart_type': 'stock_summary',
        'data': {
            'labels': ['昨收', '今开', '最高', '最低', '现价'],
            'values': [
                market_data['yesterday_close'],
                market_data['open_price'],
                market_data['high_price'],
                market_data['low_price'],
                market_data['current_price']
            ]
        },
        'metadata': {
            'company': '理想汽车',
            'symbol': '2015.HK',
            'change_pct': market_data['change_pct'],
            'currency': 'HKD'
        }
    }

if __name__ == "__main__":
    asyncio.run(main())