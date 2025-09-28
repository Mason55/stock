# seres_analyzer.py - 赛力斯(SERES)专门分析器
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

class SeresAnalyzer:
    """赛力斯专门分析器"""
    
    def __init__(self):
        self.symbol = "601127.SH"
        self.sina_code = "sh601127"
        self.company_name = "赛力斯"
        self.industry = "汽车制造"
        
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
                    
                    # 解析数据 - A股数据格式
                    data_line = content.split('"')[1]
                    if not data_line.strip():
                        return None
                    
                    parts = data_line.split(',')
                    if len(parts) < 32:  # A股数据格式有32个字段
                        return None
                    
                    # A股数据格式解析
                    name = parts[0]  # 股票名称
                    open_price = float(parts[1]) if parts[1] else 0
                    yesterday_close = float(parts[2]) if parts[2] else 0
                    current_price = float(parts[3]) if parts[3] else 0
                    high_price = float(parts[4]) if parts[4] else 0
                    low_price = float(parts[5]) if parts[5] else 0
                    
                    # 成交量和成交额
                    volume = int(parts[8]) if parts[8] else 0  # 成交量(股)
                    turnover = float(parts[9]) if parts[9] else 0  # 成交额(元)
                    
                    # 计算涨跌
                    change = current_price - yesterday_close
                    change_pct = (change / yesterday_close * 100) if yesterday_close > 0 else 0
                    
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
        volume = data['volume']
        
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
            if amplitude > 8:
                signals.append("振幅很大")
                score -= 1  # 高波动性降低评分
            elif amplitude > 5:
                signals.append("振幅较大")
                score -= 0.5
            elif amplitude < 2:
                signals.append("振幅较小")
                score += 0.5
        
        # 涨跌幅分析
        if change_pct > 5:
            signals.append("大涨")
            score += 2
        elif change_pct > 2:
            signals.append("上涨")
            score += 1
        elif change_pct < -5:
            signals.append("大跌")
            score -= 2
        elif change_pct < -2:
            signals.append("下跌")
            score -= 1
        else:
            signals.append("窄幅震荡")
        
        # 成交量分析（简化处理）
        if volume > 50000000:  # 5千万股以上
            signals.append("成交量放大")
            score += 0.5
        elif volume < 10000000:  # 1千万股以下
            signals.append("成交量萎缩")
            score -= 0.5
        
        # 生成建议
        if score >= 2:
            recommendation = "BUY"
            confidence = min(80, 50 + score * 10)
        elif score <= -2:
            recommendation = "SELL"
            confidence = min(80, 50 + abs(score) * 10)
        else:
            recommendation = "HOLD"
            confidence = 60
        
        return {
            'signals': signals,
            'score': score,
            'recommendation': recommendation,
            'confidence': confidence
        }
    
    def get_company_background(self) -> Dict:
        """获取赛力斯公司背景信息"""
        return {
            'company_profile': {
                'full_name': '重庆赛力斯汽车股份有限公司',
                'business': '新能源智能汽车制造',
                'main_products': ['赛力斯SF5', '问界M5', '问界M7', '问界M9'],
                'partnerships': ['华为智选车合作伙伴', '与华为深度合作'],
                'technology': ['增程式电动技术', '智能驾驶', '智能座舱']
            },
            'market_position': {
                'sector': '新能源汽车',
                'sub_sector': '增程式电动车',
                'main_competitors': ['理想汽车', '蔚来', '小鹏', '比亚迪'],
                'advantages': ['华为技术加持', '增程技术路线', '智能化程度高']
            },
            'recent_developments': {
                'sales_trend': '问界系列销量快速增长',
                'product_updates': '问界新M7改款上市',
                'partnerships': '与华为合作不断深化',
                'challenges': '市场竞争激烈，盈利压力较大'
            }
        }
    
    def get_market_context(self) -> Dict:
        """获取市场环境背景"""
        now = datetime.now()
        hour = now.hour
        
        # 判断交易时段
        if (9 <= hour < 12) or (13 <= hour < 15):
            session = "正常交易时间"
            status = "TRADING"
        elif hour == 15:
            session = "收盘时间"
            status = "CLOSED"
        else:
            session = "休市时间"
            status = "CLOSED"
        
        return {
            'trading_session': session,
            'market_status': status,
            'market_sentiment': '新能源汽车板块关注度较高',
            'policy_environment': '国家持续支持新能源汽车发展'
        }
    
    async def run_analysis(self) -> Dict:
        """运行完整分析"""
        print(f"🔍 开始分析 {self.company_name} ({self.symbol})...")
        
        # 获取基础数据
        market_context = self.get_market_context()
        company_bg = self.get_company_background()
        sina_data = await self.get_sina_data()
        
        analysis_result = {
            'company': self.company_name,
            'symbol': self.symbol,
            'industry': self.industry,
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'market_context': market_context,
            'company_background': company_bg
        }
        
        if sina_data:
            analysis_result['market_data'] = sina_data
            
            # 技术分析
            technical_analysis = self.analyze_technical_signals(sina_data)
            analysis_result['technical_analysis'] = technical_analysis
            
            # 估值简单评估
            current_price = sina_data['current_price']
            turnover = sina_data['turnover']
            analysis_result['valuation_note'] = f"当前价格 ¥{current_price:.2f}, 成交额 {turnover/100000000:.2f}亿元"
            
        else:
            analysis_result['error'] = '无法获取实时市场数据'
        
        return analysis_result

def format_seres_report(analysis: Dict) -> str:
    """格式化赛力斯分析报告"""
    if 'error' in analysis:
        return f"❌ 分析失败: {analysis['error']}"
    
    report = []
    report.append("=" * 60)
    report.append(f"🚗 {analysis['company']} 股票分析报告")
    report.append("=" * 60)
    report.append(f"📅 分析时间: {analysis['analysis_time']}")
    report.append(f"🏢 股票代码: {analysis['symbol']} | 行业: {analysis['industry']}")
    
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
        report.append(f"  {color_indicator} 现价: ¥{data['current_price']:.2f}")
        report.append(f"  📊 涨跌: {change_symbol}{data['change']:.2f} ({change_symbol}{data['change_pct']:.2f}%)")
        report.append(f"  🌅 今开: ¥{data['open_price']:.2f}")
        report.append(f"  ⬆️  最高: ¥{data['high_price']:.2f}")
        report.append(f"  ⬇️  最低: ¥{data['low_price']:.2f}")
        report.append(f"  📦 成交量: {data['volume']:,}股")
        report.append(f"  💰 成交额: ¥{data['turnover']/100000000:.2f}亿")
        report.append("")
        
        # 技术分析
        if 'technical_analysis' in analysis:
            tech = analysis['technical_analysis']
            rec_emoji = {'BUY': '🚀', 'SELL': '📉', 'HOLD': '🤝'}
            rec_text = {'BUY': '买入', 'SELL': '卖出', 'HOLD': '持有'}
            
            rec = tech['recommendation']
            report.append("🎯 技术分析:")
            report.append(f"  建议: {rec_emoji.get(rec, '🤝')} {rec_text.get(rec, '持有')}")
            report.append(f"  置信度: {tech['confidence']}%")
            report.append(f"  技术信号: {', '.join(tech['signals'])}")
            report.append(f"  综合评分: {tech['score']}")
            report.append("")
        
        # 估值信息
        if 'valuation_note' in analysis:
            report.append("💰 市场表现:")
            report.append(f"  {analysis['valuation_note']}")
            report.append("")
    
    # 公司背景
    if 'company_background' in analysis:
        bg = analysis['company_background']
        profile = bg['company_profile']
        position = bg['market_position']
        developments = bg['recent_developments']
        
        report.append("🏭 公司背景:")
        report.append(f"  公司全称: {profile['full_name']}")
        report.append(f"  主营业务: {profile['business']}")
        report.append(f"  主要产品: {', '.join(profile['main_products'])}")
        report.append(f"  合作伙伴: {', '.join(profile['partnerships'])}")
        report.append("")
        
        report.append("🎯 市场定位:")
        report.append(f"  细分领域: {position['sub_sector']}")
        report.append(f"  主要竞争对手: {', '.join(position['main_competitors'])}")
        report.append(f"  核心优势: {', '.join(position['advantages'])}")
        report.append("")
        
        report.append("📈 最新发展:")
        report.append(f"  销量趋势: {developments['sales_trend']}")
        report.append(f"  产品动态: {developments['product_updates']}")
        report.append(f"  合作进展: {developments['partnerships']}")
        report.append(f"  面临挑战: {developments['challenges']}")
        report.append("")
    
    report.append("=" * 60)
    report.append("📝 投资要点:")
    report.append("• 赛力斯与华为深度合作，问界品牌快速发展")
    report.append("• 增程式技术路线，解决续航焦虑问题")
    report.append("• 智能化程度高，华为技术加持优势明显")
    report.append("• 关注月度销量、新车型发布、合作进展等关键指标")
    report.append("")
    report.append("⚠️  风险提示:")
    report.append("• 新能源汽车行业竞争激烈，技术和市场变化快")
    report.append("• 对华为合作依赖度较高，需关注合作稳定性")
    report.append("• 股票投资有风险，本分析仅供参考，请谨慎决策")
    report.append("=" * 60)
    
    return "\n".join(report)

async def main():
    """主函数"""
    print("🚀 赛力斯股票分析系统启动...")
    
    analyzer = SeresAnalyzer()
    
    try:
        # 运行分析
        analysis_result = await analyzer.run_analysis()
        
        # 生成报告
        report = format_seres_report(analysis_result)
        print(report)
        
        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"seres_analysis_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 分析结果已保存至: {filename}")
        
    except Exception as e:
        print(f"❌ 分析过程出错: {e}")

if __name__ == "__main__":
    asyncio.run(main())