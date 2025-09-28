# li_auto_chart_generator.py - 理想汽车分析图表生成器
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class LiAutoChartGenerator:
    """理想汽车分析图表生成器"""
    
    def __init__(self, data_file: str):
        self.data_file = data_file
        self.analysis_data = self.load_data()
        
    def load_data(self) -> dict:
        """加载分析数据"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载数据失败: {e}")
            return {}
    
    def create_price_summary_chart(self):
        """创建价格摘要图表"""
        if 'market_data' not in self.analysis_data:
            print("没有市场数据，无法生成图表")
            return
        
        data = self.analysis_data['market_data']
        
        # 准备数据
        labels = ['昨收', '今开', '最高', '最低', '现价']
        values = [
            data['yesterday_close'],
            data['open_price'], 
            data['high_price'],
            data['low_price'],
            data['current_price']
        ]
        
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # 子图1: 价格柱状图
        colors = ['gray', 'blue', 'green', 'red', 'orange']
        bars = ax1.bar(labels, values, color=colors, alpha=0.7)
        ax1.set_title(f'{self.analysis_data["company"]} 价格摘要', fontsize=14, fontweight='bold')
        ax1.set_ylabel('价格 (HKD)', fontsize=12)
        ax1.grid(True, alpha=0.3)
        
        # 在柱状图上添加数值标签
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'${value:.2f}', ha='center', va='bottom', fontsize=10)
        
        # 子图2: 涨跌可视化
        change = data['change']
        change_pct = data['change_pct']
        
        # 创建温度计样式的涨跌图
        ax2.set_xlim(0, 10)
        ax2.set_ylim(-5, 5)
        
        # 绘制温度计
        rect = patches.Rectangle((4, -4), 2, 8, linewidth=2, edgecolor='black', facecolor='lightgray')
        ax2.add_patch(rect)
        
        # 根据涨跌填充颜色
        if change >= 0:
            fill_height = min(change_pct / 5 * 4, 4)  # 最大4个单位
            fill_rect = patches.Rectangle((4, 0), 2, fill_height, facecolor='red', alpha=0.7)
            ax2.add_patch(fill_rect)
            status_color = 'red'
            status_text = '上涨'
        else:
            fill_height = max(change_pct / 5 * 4, -4)  # 最小-4个单位
            fill_rect = patches.Rectangle((4, fill_height), 2, -fill_height, facecolor='green', alpha=0.7)
            ax2.add_patch(fill_rect)
            status_color = 'green'
            status_text = '下跌'
        
        ax2.text(5, 4.5, f'{change_pct:.2f}%', ha='center', va='center', 
                fontsize=16, fontweight='bold', color=status_color)
        ax2.text(5, -4.8, status_text, ha='center', va='center', 
                fontsize=12, color=status_color)
        
        ax2.set_title('涨跌幅', fontsize=14, fontweight='bold')
        ax2.set_xticks([])
        ax2.set_yticks([])
        ax2.set_aspect('equal')
        
        plt.tight_layout()
        
        # 保存图表
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'li_auto_price_summary_{timestamp}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"📊 价格摘要图表已保存: {filename}")
        
        return filename
    
    def create_technical_analysis_chart(self):
        """创建技术分析图表"""
        if 'technical_analysis' not in self.analysis_data:
            print("没有技术分析数据")
            return
        
        tech_data = self.analysis_data['technical_analysis']
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # 子图1: 建议饼图
        recommendation = tech_data['recommendation']
        confidence = tech_data['confidence']
        
        # 准备饼图数据
        if recommendation == 'BUY':
            labels = ['买入建议', '其他']
            sizes = [confidence, 100 - confidence]
            colors = ['green', 'lightgray']
            explode = (0.1, 0)
        elif recommendation == 'SELL':
            labels = ['卖出建议', '其他']
            sizes = [confidence, 100 - confidence]
            colors = ['red', 'lightgray']
            explode = (0.1, 0)
        else:
            labels = ['持有建议', '其他']
            sizes = [confidence, 100 - confidence]
            colors = ['orange', 'lightgray']
            explode = (0.1, 0)
        
        ax1.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
                shadow=True, startangle=90)
        ax1.set_title(f'投资建议: {recommendation}\n置信度: {confidence}%', 
                     fontsize=14, fontweight='bold')
        
        # 子图2: 技术信号雷达图
        signals = tech_data['signals']
        score = tech_data['score']
        
        # 创建简单的信号强度图
        ax2.barh(range(len(signals)), [1] * len(signals), color='lightblue', alpha=0.6)
        
        for i, signal in enumerate(signals):
            ax2.text(0.5, i, signal, ha='center', va='center', fontsize=10, fontweight='bold')
        
        ax2.set_yticks(range(len(signals)))
        ax2.set_yticklabels([])
        ax2.set_xlim(0, 1)
        ax2.set_xlabel('技术信号')
        ax2.set_title(f'技术信号分析\n综合评分: {score}', fontsize=14, fontweight='bold')
        
        # 根据评分添加背景色
        if score > 0:
            ax2.set_facecolor('#e8f5e8')  # 浅绿色
        elif score < 0:
            ax2.set_facecolor('#ffe8e8')  # 浅红色
        else:
            ax2.set_facecolor('#f0f0f0')  # 浅灰色
        
        plt.tight_layout()
        
        # 保存图表
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'li_auto_technical_analysis_{timestamp}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"📊 技术分析图表已保存: {filename}")
        
        return filename
    
    def create_comprehensive_dashboard(self):
        """创建综合仪表板"""
        if not self.analysis_data:
            print("没有分析数据")
            return
        
        fig = plt.figure(figsize=(16, 10))
        
        # 创建网格布局
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # 标题
        fig.suptitle(f'{self.analysis_data["company"]} 股票分析仪表板', 
                    fontsize=18, fontweight='bold', y=0.95)
        
        # 基本信息 (第一行左侧)
        ax1 = fig.add_subplot(gs[0, 0])
        info_text = f"""代码: {self.analysis_data['symbol_hk']}
美股: {self.analysis_data['symbol_us']}
分析时间: {self.analysis_data['analysis_time'][:16]}
市场状态: {self.analysis_data['market_context']['market_status']}"""
        
        ax1.text(0.1, 0.5, info_text, fontsize=11, va='center', ha='left',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.5))
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 1)
        ax1.set_title('基本信息', fontweight='bold')
        ax1.axis('off')
        
        # 如果有市场数据，显示详细信息
        if 'market_data' in self.analysis_data:
            data = self.analysis_data['market_data']
            
            # 当前价格 (第一行中间)
            ax2 = fig.add_subplot(gs[0, 1])
            current_price = data['current_price']
            change = data['change']
            change_pct = data['change_pct']
            
            color = 'red' if change >= 0 else 'green'
            symbol = '+' if change >= 0 else ''
            
            ax2.text(0.5, 0.7, f'HK${current_price:.2f}', fontsize=24, fontweight='bold',
                    ha='center', va='center', color=color)
            ax2.text(0.5, 0.3, f'{symbol}{change:.2f} ({symbol}{change_pct:.2f}%)', 
                    fontsize=14, ha='center', va='center', color=color)
            ax2.set_xlim(0, 1)
            ax2.set_ylim(0, 1)
            ax2.set_title('当前价格', fontweight='bold')
            ax2.axis('off')
            
            # 价格范围 (第一行右侧)
            ax3 = fig.add_subplot(gs[0, 2])
            high = data['high_price']
            low = data['low_price']
            open_price = data['open_price']
            
            range_text = f"""今开: HK${open_price:.2f}
最高: HK${high:.2f}
最低: HK${low:.2f}
振幅: {((high-low)/low*100):.2f}%"""
            
            ax3.text(0.1, 0.5, range_text, fontsize=11, va='center', ha='left',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.5))
            ax3.set_xlim(0, 1)
            ax3.set_ylim(0, 1)
            ax3.set_title('价格范围', fontweight='bold')
            ax3.axis('off')
            
            # 价格走势模拟图 (第二行跨两列)
            ax4 = fig.add_subplot(gs[1, :2])
            
            # 模拟日内走势（简化版）
            time_points = np.linspace(0, 6.5, 50)  # 6.5小时交易时间
            base_trend = np.sin(time_points) * 2
            random_noise = np.random.normal(0, 0.5, 50)
            
            # 构造从开盘到当前价格的走势
            price_trend = open_price + (current_price - open_price) * time_points / 6.5
            price_trend += base_trend + random_noise
            
            # 确保价格在合理范围内
            price_trend = np.clip(price_trend, low * 0.98, high * 1.02)
            
            ax4.plot(time_points, price_trend, linewidth=2, color=color)
            ax4.fill_between(time_points, price_trend, alpha=0.3, color=color)
            ax4.axhline(y=open_price, color='blue', linestyle='--', alpha=0.7, label='开盘价')
            ax4.axhline(y=current_price, color=color, linestyle='-', alpha=0.8, label='现价')
            
            ax4.set_title('模拟日内走势', fontweight='bold')
            ax4.set_xlabel('时间 (小时)')
            ax4.set_ylabel('价格 (HKD)')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        
        # 技术分析结果 (第二行右侧)
        if 'technical_analysis' in self.analysis_data:
            ax5 = fig.add_subplot(gs[1, 2])
            tech = self.analysis_data['technical_analysis']
            
            rec_colors = {'BUY': 'green', 'SELL': 'red', 'HOLD': 'orange'}
            rec_names = {'BUY': '买入', 'SELL': '卖出', 'HOLD': '持有'}
            
            rec = tech['recommendation']
            confidence = tech['confidence']
            
            # 创建置信度表盘
            theta = np.linspace(0, 2*np.pi, 100)
            r = np.ones_like(theta)
            
            ax5.plot(theta, r, 'k-', linewidth=2)
            
            # 填充置信度区域
            conf_angle = 2 * np.pi * confidence / 100
            theta_conf = np.linspace(0, conf_angle, int(confidence))
            r_conf = np.ones_like(theta_conf)
            
            ax5.fill_between(theta_conf, 0, r_conf, alpha=0.7, color=rec_colors[rec])
            ax5.text(0, 0, f'{rec_names[rec]}\n{confidence}%', 
                    ha='center', va='center', fontsize=14, fontweight='bold')
            
            ax5.set_xlim(-1.2, 1.2)
            ax5.set_ylim(-1.2, 1.2)
            ax5.set_title('投资建议', fontweight='bold')
            ax5.axis('off')
        
        # 行业背景 (第三行)
        ax6 = fig.add_subplot(gs[2, :])
        industry = self.analysis_data['market_context']['industry']
        
        industry_text = f"""行业: {industry['sector']}    趋势: {industry['market_trend']}
政策: {industry['policy_support']}
竞争: {industry['competition']}

📝 投资要点: 理想汽车是中国领先的新能源汽车制造商，专注于增程式电动车技术。
关注指标: 月度销量、新车型发布、充电网络建设、技术创新等。"""
        
        ax6.text(0.05, 0.5, industry_text, fontsize=11, va='center', ha='left',
                bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgreen", alpha=0.3))
        ax6.set_xlim(0, 1)
        ax6.set_ylim(0, 1)
        ax6.set_title('行业背景与投资要点', fontweight='bold')
        ax6.axis('off')
        
        # 保存综合仪表板
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'li_auto_dashboard_{timestamp}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"📊 综合仪表板已保存: {filename}")
        
        return filename

def main():
    """主函数"""
    # 查找最新的分析数据文件
    import glob
    analysis_files = glob.glob("li_auto_simple_analysis_*.json")
    
    if not analysis_files:
        print("❌ 未找到分析数据文件，请先运行分析")
        return
    
    # 使用最新的文件
    latest_file = max(analysis_files)
    print(f"📁 使用分析数据文件: {latest_file}")
    
    # 创建图表生成器
    chart_gen = LiAutoChartGenerator(latest_file)
    
    print("🎨 开始生成可视化图表...")
    
    # 生成各类图表
    try:
        chart_gen.create_price_summary_chart()
        chart_gen.create_technical_analysis_chart()
        chart_gen.create_comprehensive_dashboard()
        
        print("✅ 所有图表生成完成！")
        
    except Exception as e:
        print(f"❌ 图表生成失败: {e}")

if __name__ == "__main__":
    main()