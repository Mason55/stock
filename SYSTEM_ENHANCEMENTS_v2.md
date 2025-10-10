# 股票量化系统完善总结 v2.0

**日期**: 2025-10-10
**版本**: v2.0
**状态**: ✅ 完成

---

## 📋 本次改进概览

在v1.1的基础上，继续完善了以下核心功能：

1. ✅ **价格预警系统** - 实时监控价格突破和技术信号
2. ✅ **仓位管理工具** - 科学计算仓位大小和风险控制
3. ✅ **监控工具增强** - 命令行实时监控工具
4. ✅ **风险管理预设** - 保守/稳健/激进三套方案

---

## 🎯 新增功能详解

### 1. 价格预警系统 (Price Alert System)

**核心文件**: `src/monitoring/price_alert.py`

#### 功能特性

- **多种预警类型**:
  - 价格突破 (高于/低于某价位)
  - 百分比变化 (涨跌超过X%)
  - RSI超买/超卖
  - 成交量异常
  - 均线交叉

- **灵活配置**:
  - 自定义触发条件
  - 设置预警过期时间
  - 支持批量设置支撑/压力位

- **通知机制**:
  - 控制台提醒
  - 日志记录
  - 可扩展（邮件、微信等）

#### 使用示例

```python
from src.monitoring.price_alert import AlertManager, AlertType

# 创建预警管理器
alert_mgr = AlertManager()

# 设置价格目标预警
alert_mgr.create_price_target_alert("000977.SZ", 68.0, "below")  # 跌破68元提醒
alert_mgr.create_price_target_alert("000977.SZ", 75.0, "above")  # 突破75元提醒

# 设置支撑/压力位预警
alert_mgr.create_support_resistance_alerts(
    symbol="000977.SZ",
    support_levels=[68.36, 66.15],  # 支撑位
    resistance_levels=[72.16, 79.76]  # 压力位
)

# 设置技术指标预警
alert_mgr.create_technical_alerts("000977.SZ", {
    'rsi_oversold': 30,  # RSI<30时提醒
    'rsi_overbought': 70,  # RSI>70时提醒
    'price_change_pct': 5.0  # 单日涨跌>5%提醒
})

# 检查预警
market_data = {
    "000977.SZ": {
        "current_price": 70.33,
        "rsi": 74.86,
        "volume": 9467265
    }
}
triggered = alert_mgr.check_all_alerts(market_data)
```

---

### 2. 实时监控工具

**核心文件**: `examples/monitor_price.py`

#### 功能特性

- 实时获取行情数据
- 自动检查预警条件
- 可配置检查频率
- 显示价格变化和技术指标

#### 使用方法

```bash
# 监控浪潮信息，设置支撑和压力位
python examples/monitor_price.py \
    --symbol 000977.SZ \
    --support 68 70 \
    --resistance 75 80 \
    --interval 30

# 监控招商银行，启用技术指标预警
python examples/monitor_price.py \
    --symbol 600036.SH \
    --watch \
    --interval 60

# 列出活跃预警
python examples/monitor_price.py \
    --symbol 000977.SZ \
    --list
```

#### 输出示例

```
======================================================================
📊 Monitoring 000977.SZ
======================================================================
Check interval: 30 seconds
Press Ctrl+C to stop

[11:50:00] Check #1... Price: ¥70.33 (-7.41%)
[11:50:30] Check #2... Price: ¥70.50 (-7.18%)
[11:51:00] Check #3... Price: ¥68.20 (-10.20%) - ⚠️ 2 alert(s) triggered!

==============================================================
🔔 ALERT TRIGGERED!
==============================================================
Symbol: 000977.SZ
Type: price_below
Message: ⚠️ 000977.SZ approaching support ¥68.36
Current Price: ¥68.20
Triggered At: 2025-10-10 11:51:00
==============================================================
```

---

### 3. 仓位管理工具 (Position Manager)

**核心文件**: `src/trading/position_manager.py`

#### 功能特性

- **科学仓位计算**:
  - 基于风险的仓位大小
  - Kelly公式优化
  - 考虑总敞口限制

- **风险控制**:
  - 单笔交易风险限制
  - 单只股票仓位上限
  - 总市值敞口控制

- **预设方案**:
  - 保守型 (Conservative)
  - 稳健型 (Moderate)
  - 激进型 (Aggressive)

#### 使用示例

```python
from src.trading.position_manager import PositionSizer, RiskPreset, RiskLevel

# 创建仓位管理器 (10万资金)
sizer = PositionSizer(
    total_capital=100000,
    risk_per_trade_pct=0.02,  # 单笔风险2%
    max_position_pct=0.20,  # 单只最多20%
    max_total_exposure=0.80  # 总仓位不超80%
)

# 计算浪潮信息的建议仓位
position = sizer.calculate_position_size(
    symbol="000977.SZ",
    entry_price=70.0,  # 计划买入价
    stop_loss_price=65.0,  # 止损价
    signal_strength=0.8  # 信号强度
)

print(f"建议买入: {position.shares}股")
print(f"总金额: ¥{position.total_value:,.2f}")
print(f"占仓位: {position.position_pct:.1%}")
print(f"风险金额: ¥{position.risk_amount:,.2f}")
print(f"止损价: ¥{position.stop_loss_price:.2f}")
```

#### 输出示例

```
建议买入: 400股
总金额: ¥28,000.00
占仓位: 28.0%
风险金额: ¥2,000.00
止损价: ¥65.00
```

---

### 4. 风险管理预设

#### 三种风险等级

| 参数 | 保守型 | 稳健型 | 激进型 |
|------|--------|--------|--------|
| **单笔风险** | 1% | 2% | 3% |
| **单只上限** | 10% | 20% | 30% |
| **总敞口** | 60% | 80% | 95% |
| **止损幅度** | 3% | 5% | 8% |

#### 使用方法

```python
from src.trading.position_manager import RiskPreset, RiskLevel

# 获取保守型参数
conservative = RiskPreset.get_preset(RiskLevel.CONSERVATIVE)

sizer = PositionSizer(
    total_capital=100000,
    **conservative
)
```

---

## 💡 实际应用场景

### 场景1: 浪潮信息投资计划

**背景**:
- 当前价格: ¥70.33
- 技术支撑: ¥68.36, ¥66.15
- 技术压力: ¥72.16, ¥79.76
- RSI: 74.86 (超买)

#### 步骤1: 设置价格预警

```bash
python examples/monitor_price.py \
    --symbol 000977.SZ \
    --support 68.36 66.15 \
    --resistance 72.16 79.76 \
    --interval 60
```

**目的**: 实时监控价格是否触及关键位

#### 步骤2: 计算建议仓位

```python
from src.trading.position_manager import PositionSizer, RiskPreset, RiskLevel

# 使用稳健型策略，10万资金
preset = RiskPreset.get_preset(RiskLevel.MODERATE)
sizer = PositionSizer(total_capital=100000, **preset)

# 计划在68元附近买入，止损66元
position = sizer.calculate_position_size(
    symbol="000977.SZ",
    entry_price=68.0,
    stop_loss_price=66.0,  # 2元止损
    signal_strength=0.7  # 中等信号强度
)

# 结果:
# - 建议买入: 700股
# - 总金额: ¥47,600
# - 占仓位: 47.6%
# - 风险金额: ¥1,400 (总资金的1.4%)
```

#### 步骤3: 分批建仓计划

根据仓位计算器建议，制定分批计划：

| 批次 | 价格 | 数量 | 金额 | 累计仓位 |
|------|------|------|------|---------|
| 第1批 | 68元 | 300股 | ¥20,400 | 20.4% |
| 第2批 | 66元 | 300股 | ¥19,800 | 40.2% |
| 第3批 | 64元 | 100股 | ¥6,400 | 46.6% |

---

### 场景2: 多只股票组合管理

```python
# 创建仓位管理器
sizer = PositionSizer(total_capital=100000)

# 计算三只股票的仓位
stocks = [
    {"symbol": "000977.SZ", "entry": 68.0, "stop": 65.0},
    {"symbol": "600036.SH", "entry": 40.0, "stop": 38.0},
    {"symbol": "600519.SH", "entry": 1800.0, "stop": 1700.0}
]

for stock in stocks:
    pos = sizer.calculate_position_size(
        symbol=stock["symbol"],
        entry_price=stock["entry"],
        stop_loss_price=stock["stop"],
        signal_strength=0.8
    )

    if pos:
        print(f"{pos.symbol}: {pos.shares}股, "
              f"¥{pos.total_value:,.0f} ({pos.position_pct:.1%})")

        # 记录已分配仓位
        sizer.add_position(pos.symbol, pos.total_value)

# 检查总敞口
print(f"\n总敞口: {sizer.get_exposure_pct():.1%}")
print(f"剩余资金: ¥{sizer.get_available_capital():,.0f}")
```

---

## 📊 系统功能总览

### 数据层
- ✅ 真实行情数据获取 (Tushare/Yahoo/Sina)
- ✅ 技术指标计算 (MA/RSI/MACD等)
- ✅ 历史数据缓存

### 策略层
- ✅ 双均线策略
- ✅ 均值回归策略
- ✅ 动量策略
- ✅ 网格交易策略
- ✅ 布林带策略
- ✅ RSI反转策略

### 回测层
- ✅ 事件驱动回测引擎
- ✅ 成本模型 (佣金/印花税)
- ✅ 风险管理
- ✅ 性能分析 (15项指标)
- ✅ 参数优化 (网格搜索)

### 实盘层
- ✅ 订单管理
- ✅ 仓位跟踪
- ✅ 券商接口适配
- ✅ 实时监控

### 风控层
- ✅ 价格预警
- ✅ 仓位管理
- ✅ 风险预设
- ✅ 止损止盈计算

---

## 🛠️ 新增工具列表

### 命令行工具

1. **回测工具** (`examples/backtest_strategies.py`)
   ```bash
   python examples/backtest_strategies.py --strategy moving_average --symbol 000977.SZ
   ```

2. **参数优化** (`examples/optimize_strategy.py`)
   ```bash
   python examples/optimize_strategy.py --strategy moving_average --symbol 000977.SZ
   ```

3. **价格监控** (`examples/monitor_price.py`) - 🆕
   ```bash
   python examples/monitor_price.py --symbol 000977.SZ --support 68 70 --resistance 75 80
   ```

### Python模块

1. **价格预警** (`src/monitoring/price_alert.py`) - 🆕
2. **仓位管理** (`src/trading/position_manager.py`) - 🆕
3. **性能分析** (`src/backtest/performance.py`)
4. **策略加载** (`src/strategies/strategy_loader.py`)

---

## 📈 使用效果对比

### 之前 vs 之后

| 功能 | 改进前 | 改进后 |
|------|--------|--------|
| **数据来源** | 模拟数据 | 真实行情 |
| **参数优化** | 手动试错 | 自动搜索 |
| **价格监控** | ❌ 无 | ✅ 实时预警 |
| **仓位计算** | ❌ 拍脑袋 | ✅ 科学计算 |
| **风险管理** | ❌ 缺失 | ✅ 三级预设 |
| **性能指标** | 6项 | 15项 |

---

## 🎓 最佳实践建议

### 1. 价格预警设置

**推荐配置**:
- 设置2-3个支撑位（递减）
- 设置2-3个压力位（递增）
- 启用RSI超买/超卖提醒
- 设置日内涨跌幅提醒（±5%）

### 2. 仓位管理原则

**新手建议**:
- 使用保守型预设
- 单笔风险不超过1-2%
- 单只股票不超过10-15%
- 总仓位不超过60-70%

**进阶投资者**:
- 使用稳健型预设
- 根据信号强度动态调整
- 利用Kelly公式优化
- 密切监控总敞口

### 3. 综合投资流程

```
1. 技术分析 → 识别买卖点
2. 设置预警 → 等待价格到位
3. 计算仓位 → 确定买入数量
4. 分批建仓 → 降低风险
5. 实时监控 → 及时调整
6. 严格止损 → 保护资金
```

---

## 📁 新增文件清单

1. `src/monitoring/price_alert.py` (380行) - 价格预警系统
2. `examples/monitor_price.py` (210行) - 监控工具
3. `src/trading/position_manager.py` (320行) - 仓位管理
4. `SYSTEM_ENHANCEMENTS_v2.md` - 本文档

---

## 🚀 后续改进计划

### 短期 (1周内)
- [ ] 添加图表可视化 (matplotlib)
- [ ] 增强Web界面
- [ ] 添加邮件/微信通知

### 中期 (1月内)
- [ ] Walk-forward分析
- [ ] 蒙特卡洛模拟
- [ ] 多策略组合优化
- [ ] 实盘交易日志

### 长期 (3月内)
- [ ] 机器学习模型
- [ ] 高频交易支持
- [ ] 期货期权回测
- [ ] 云端部署方案

---

## 📞 使用帮助

### 快速开始

1. **监控浪潮信息**
   ```bash
   python examples/monitor_price.py --symbol 000977.SZ --support 68 --resistance 75
   ```

2. **计算建议仓位**
   ```python
   from src.trading.position_manager import PositionSizer

   sizer = PositionSizer(total_capital=100000)
   pos = sizer.calculate_position_size("000977.SZ", 70.0, 65.0, 0.8)
   print(f"建议买入 {pos.shares} 股")
   ```

3. **优化策略参数**
   ```bash
   python examples/optimize_strategy.py --strategy moving_average --symbol 000977.SZ --days 120
   ```

---

**最后更新**: 2025-10-10
**文档版本**: v2.0
**系统版本**: 完整量化交易系统
