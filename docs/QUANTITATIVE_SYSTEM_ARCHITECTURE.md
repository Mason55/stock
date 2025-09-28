# 量化交易系统架构文档

## 概述

本文档描述了基于现有股票分析系统构建的量化交易系统架构，该系统采用事件驱动设计，支持策略回测、风险管理和实盘交易。

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    量化交易系统架构                          │
│                                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │   策略层    │ │   信号层    │ │      组合管理层         │ │
│  │ Strategies  │ │  Signals    │ │    Portfolio Mgmt       │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
│                              │                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  事件驱动引擎                           │ │
│  │              Event-Driven Engine                        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                              │                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │   市场模拟  │ │   风险控制  │ │      成本模型           │ │
│  │Market Sim   │ │Risk Mgmt    │ │    Cost Model           │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
│                              │                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    数据层                               │ │
│  │        历史数据 + 实时数据 + 公司行为                    │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

#### 1. 数据层 (Data Layer)

**历史数据模型** (`src/models/market_data.py`)
- `HistoricalPrice`: 多频率OHLCV数据，支持前复权/后复权
- `CorporateAction`: 公司行为数据（分红、拆股、配股等）
- `TradingCalendar`: 交易日历，支持多市场

**数据源管理** (`src/data_sources/data_source_manager.py`)
- 统一数据源接口，支持多数据源自动降级
- 支持的数据源：新浪财经、Tushare、Yahoo Finance
- 自动容错和负载均衡机制

**特性**:
- ✅ 多频率支持：日线、小时、分钟、Tick
- ✅ 复权处理：前复权、后复权、不复权
- ✅ 数据质量控制：缺失值检测、异常值处理
- ✅ 容错机制：多数据源自动切换

#### 2. 交易系统模型 (`src/models/trading.py`)

**订单管理**
- `Order`: 订单生命周期管理
- `Fill`: 成交记录和执行质量追踪
- `Position`: 持仓管理，支持T+1规则
- `Portfolio`: 组合级别的P&L和风险指标

**订单类型支持**:
- Market Order (市价单)
- Limit Order (限价单)
- Stop Order (止损单)
- Stop Limit Order (止损限价单)

#### 3. 回测引擎 (`src/backtest/engine.py`)

**事件驱动架构**
```python
Event Types:
├── MarketDataEvent     # 市场数据事件
├── SignalEvent         # 交易信号事件
├── OrderEvent          # 订单事件
└── FillEvent          # 成交事件

Event Flow:
MarketData → Strategy → Signal → Portfolio → Order → MarketSim → Fill
```

**核心类**:
- `BacktestEngine`: 主引擎，协调所有组件
- `Strategy`: 策略基类，实现交易逻辑
- `Portfolio`: 组合管理，资金分配和风险控制
- `EventHandler`: 事件处理接口

#### 4. 市场模拟器 (`src/backtest/market_simulator.py`)

**中国市场规则**:
- ✅ 涨跌停限制：主板10%，科创板/创业板20%
- ✅ T+1交易规则：当日买入股票次日可卖
- ✅ 交易时间：9:30-11:30, 13:00-15:00
- ✅ 最小变动单位：0.01元
- ✅ 交易单位：100股整数倍

**订单撮合逻辑**:
```python
def process_order(order, market_data):
    1. 检查交易时间
    2. 验证价格限制（涨跌停）
    3. 检查流动性约束
    4. 计算市场冲击
    5. 生成成交结果
```

#### 5. 成本模型 (`src/backtest/cost_model.py`)

**中国A股成本结构**:
- 佣金：默认万分之3，最低5元
- 印花税：卖出时千分之1
- 过户费：万分之0.2
- 市场冲击：基于订单大小的滑点模型

#### 6. 风险管理 (`src/backtest/risk_manager.py`)

**风控检查项**:
- 单只股票最大仓位：默认10%
- 总仓位上限：默认95%
- 订单金额限制：最大100万，最小1000元
- 现金充足性检查
- 持仓可用性检查

## 使用指南

### 1. 基础数据准备

```python
from src.data_sources.data_source_manager import data_source_manager
from datetime import date

# 获取历史数据
data = await data_source_manager.get_historical_data(
    "600036.SH", 
    date(2024, 1, 1), 
    date(2024, 12, 31)
)

# 获取实时数据
realtime = await data_source_manager.get_realtime_data(["600036.SH"])
```

### 2. 策略开发

```python
from src.backtest.engine import Strategy, MarketDataEvent

class MovingAverageStrategy(Strategy):
    def __init__(self):
        super().__init__("ma_strategy")
        self.price_history = {}
        self.ma_period = 20
    
    async def handle_market_data(self, event: MarketDataEvent):
        symbol = event.symbol
        price = event.price_data['close']
        
        # 更新价格历史
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)
        
        # 保持固定长度
        if len(self.price_history[symbol]) > self.ma_period:
            self.price_history[symbol] = self.price_history[symbol][-self.ma_period:]
        
        # 生成交易信号
        if len(self.price_history[symbol]) >= self.ma_period:
            ma = sum(self.price_history[symbol]) / len(self.price_history[symbol])
            
            if price > ma * 1.02:  # 突破均线2%
                self.generate_signal(symbol, "BUY", 0.8)
            elif price < ma * 0.98:  # 跌破均线2%
                self.generate_signal(symbol, "SELL", 0.8)
```

### 3. 回测执行

```python
from src.backtest.engine import BacktestEngine
from datetime import date

# 创建回测引擎
engine = BacktestEngine(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
    initial_capital=1000000.0,
    config={
        'costs': {
            'commission_rate': 0.0003,
            'min_commission': 5.0
        },
        'risk': {
            'max_position_pct': 0.1,
            'max_total_exposure': 0.95
        }
    }
)

# 加载数据
engine.load_market_data("600036.SH", historical_data)

# 添加策略
strategy = MovingAverageStrategy()
engine.add_strategy(strategy)

# 运行回测
results = await engine.run()

# 分析结果
print(f"总收益: {results['total_return']:.2%}")
print(f"夏普比率: {results['sharpe_ratio']:.2f}")
print(f"最大回撤: {results['max_drawdown']:.2%}")
```

### 4. 结果分析

```python
import matplotlib.pyplot as plt

# 绘制净值曲线
equity_curve = results['equity_curve']
plt.figure(figsize=(12, 6))
plt.plot(equity_curve['timestamp'], equity_curve['total_value'])
plt.title('Portfolio Equity Curve')
plt.xlabel('Date')
plt.ylabel('Portfolio Value')
plt.show()

# 交易记录分析
trades_df = pd.DataFrame(results['trades'])
print("交易统计:")
print(f"总交易次数: {len(trades_df)}")
print(f"平均每笔收益: {trades_df['pnl'].mean():.2f}")
print(f"胜率: {(trades_df['pnl'] > 0).mean():.2%}")
```

## 性能特性

### 1. 执行性能
- **事件驱动设计**: 避免look-ahead bias，保证回测真实性
- **异步处理**: 支持大规模历史数据回测
- **内存优化**: 流式数据处理，支持长期回测

### 2. 市场真实性
- **精确的中国市场规则**: 涨跌停、T+1、交易时间等
- **真实成本模型**: 佣金、印花税、过户费、滑点
- **流动性约束**: 基于历史成交量的可交易数量限制

### 3. 风险控制
- **多层风控**: 订单级、策略级、组合级风险检查
- **实时监控**: 持仓、现金、风险暴露实时跟踪
- **应急机制**: 止损、熔断、强制平仓

## 扩展性设计

### 1. 策略扩展
- 继承`Strategy`基类，实现自定义策略逻辑
- 支持多策略并行运行
- 策略间信号组合和冲突处理

### 2. 数据源扩展
- 实现`BaseDataProvider`接口
- 自动注册到数据源管理器
- 支持自定义数据质量和成本配置

### 3. 风控模型扩展
- 自定义风险指标计算
- 动态风控参数调整
- 行业、市值等多维度风控

### 4. 成本模型扩展
- 支持不同市场的成本结构
- 动态佣金费率（基于资金量、交易频率）
- 更复杂的市场冲击模型

## 部署和运维

### 1. 依赖管理
```bash
# 安装基础依赖
pip install -r build/requirements/base.txt

# 安装量化分析依赖
pip install pandas numpy scikit-learn

# 安装回测依赖
pip install matplotlib seaborn plotly
```

### 2. 数据库配置
```sql
-- 创建历史数据表
CREATE TABLE historical_prices (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(15) NOT NULL,
    trade_date DATE NOT NULL,
    frequency VARCHAR(10) NOT NULL,
    adjust_type VARCHAR(10) NOT NULL,
    open_price DECIMAL(10,3) NOT NULL,
    high_price DECIMAL(10,3) NOT NULL,
    low_price DECIMAL(10,3) NOT NULL,
    close_price DECIMAL(10,3) NOT NULL,
    volume BIGINT NOT NULL,
    amount DECIMAL(18,2)
);

-- 创建索引
CREATE INDEX idx_symbol_date_freq ON historical_prices(symbol, trade_date, frequency);
```

### 3. 监控和告警
- 数据质量监控：缺失率、延迟、异常值
- 系统性能监控：内存、CPU、磁盘使用
- 策略表现监控：收益、回撤、夏普比率

## 最佳实践

### 1. 策略开发
- 避免未来函数：确保信号生成时只使用历史数据
- 参数优化：使用walk-forward验证避免过拟合
- 风险预算：合理分配资金，控制单策略风险

### 2. 数据管理
- 数据验证：定期检查数据完整性和准确性
- 版本控制：重要数据变更需要版本记录
- 备份策略：关键数据多地备份

### 3. 风险管理
- 分散投资：避免过度集中在单一股票或行业
- 动态调整：根据市场波动调整风控参数
- 压力测试：定期进行极端市场情况的压力测试

## 路线图

### Phase 1 (已完成)
- ✅ 基础数据模型设计
- ✅ 事件驱动回测引擎
- ✅ 中国市场规则模拟
- ✅ 基础风控和成本模型

### Phase 2 (规划中)
- 🔄 实时数据接入
- 🔄 纸上交易系统
- 🔄 更多策略模板
- 🔄 性能优化和并行化

### Phase 3 (未来)
- 📋 实盘交易接口
- 📋 多资产类别支持
- 📋 机器学习策略框架
- 📋 云部署和服务化

## 贡献指南

1. Fork项目并创建功能分支
2. 遵循现有代码风格和架构设计
3. 添加相应的测试用例
4. 更新文档说明
5. 提交Pull Request

## 联系方式

- 技术讨论：GitHub Issues
- 文档问题：docs/目录下的相关文档
- 系统架构：参考ARCHITECTURE.md

---

*本文档最后更新：2024年9月28日*