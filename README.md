# 股票量化交易系统 v2.0

> 一个专业、完整、开箱即用的股票量化交易系统
> 从数据分析到策略回测，从风险管理到实盘交易，全流程覆盖

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 这个系统能帮你做什么？

### 场景1: 个人投资者 - 科学决策
```bash
# 1. 分析股票，获取专业级技术指标
curl http://localhost:5000/api/stocks/603993.SH/analysis

# 2. 设置价格预警，自动提醒买卖点
python examples/monitor_price.py --symbol 603993.SH --support 15.54 --resistance 18.13

# 3. 科学计算仓位，控制风险
python -c "from src.trading.position_manager import PositionSizer; \
sizer = PositionSizer(100000); \
pos = sizer.calculate_position_size('603993.SH', 16.0, 15.0, 0.8); \
print(f'建议买入: {pos.shares}股, 总金额: ¥{pos.total_value:,.0f}')"
```

### 场景2: 量化研究员 - 策略开发
```bash
# 1. 回测验证策略有效性（真实数据）
python examples/backtest_strategies.py --strategy moving_average --symbol 600036.SH --days 120

# 2. 自动优化参数，找到最佳配置
python examples/optimize_strategy.py --strategy moving_average --symbol 600036.SH

# 3. 评估策略表现（15项专业指标）
# Sharpe Ratio, Sortino Ratio, Calmar Ratio, Max Drawdown, Win Rate...
```

### 场景3: 程序化交易 - 自动执行
```python
# 自动化交易流程
from src.trading.live_engine import LiveTradingEngine
from src.strategies.moving_average import MovingAverageCrossover

engine = LiveTradingEngine()
strategy = MovingAverageCrossover(fast=5, slow=20)
engine.add_strategy(strategy)
engine.start()  # 开始实盘交易
```

---

## ⚡ 5分钟快速开始

### 步骤1: 安装系统（1分钟）
```bash
git clone <repo-url>
cd stock
pip install -r requirements.txt
```

### 步骤2: 启动API服务（30秒）
```bash
# 使用SQLite数据库，无需配置PostgreSQL
export DATABASE_URL=sqlite:///stock_dev.db
export OFFLINE_MODE=false  # 使用真实数据
python src/app.py

# 看到这个提示说明成功：
# * Running on http://127.0.0.1:5000
```

### 步骤3: 分析你的第一只股票（30秒）
```bash
# 分析洛阳钼业（603993.SH）
curl -s http://localhost:5000/api/stocks/603993.SH/analysis?analysis_type=all | python -m json.tool

# 你将看到：
# - 当前价格和涨跌幅
# - RSI、MACD等技术指标
# - 支撑位和压力位
# - 系统给出的投资建议
```

### 步骤4: 尝试量化功能（3分钟）

#### 回测策略
```bash
# 回测双均线策略
python examples/backtest_strategies.py \
    --strategy moving_average \
    --symbol 603993.SH \
    --days 60

# 查看回测结果：
# - 总收益率
# - 夏普比率
# - 最大回撤
# - 胜率统计
```

#### 设置价格预警
```bash
# 监控价格，自动提醒
python examples/monitor_price.py \
    --symbol 603993.SH \
    --support 15.54 15.00 \
    --resistance 18.13 19.00 \
    --watch \
    --interval 60

# 当价格触及支撑/压力位时，系统会自动提醒
```

#### 计算建议仓位
```python
from src.trading.position_manager import PositionSizer, RiskPreset, RiskLevel

# 使用稳健型风险策略
params = RiskPreset.get_sizer_params(RiskLevel.MODERATE)
sizer = PositionSizer(total_capital=100000, **params)

# 计算建议仓位
position = sizer.calculate_position_size(
    symbol="603993.SH",
    entry_price=16.0,      # 计划买入价
    stop_loss_price=15.0,  # 止损价
    signal_strength=0.8    # 信号强度
)

print(f"建议买入: {position.shares} 股")
print(f"总金额: ¥{position.total_value:,.0f}")
print(f"占仓位: {position.position_pct:.1%}")
print(f"风险金额: ¥{position.risk_amount:,.0f}")
```

---

## ✨ 核心功能

### 📊 数据分析能力
- ✅ **多数据源集成** - Tushare / Yahoo Finance / Sina，自动降级
- ✅ **20+技术指标** - MA、RSI、MACD、KDJ、布林带、ATR等
- ✅ **支撑/压力位** - 自动识别关键价位
- ✅ **基本面分析** - PE、PB、ROE、负债率等
- ✅ **情绪分析** - 新闻舆情、社交媒体情绪

### 📈 量化交易能力
- ✅ **策略回测引擎** - 事件驱动架构，支持真实历史数据
- ✅ **7种内置策略** - 双均线、均值回归、动量、网格、布林、RSI
- ✅ **参数自动优化** - 网格搜索自动寻找最佳参数 🆕
- ✅ **性能分析** - 15项专业指标（Sharpe、Sortino、Calmar等）🆕
- ✅ **成本模型** - 佣金、印花税、滑点精确计算

### 🛡️ 风险管理能力（v2.0新增）
- ✅ **价格预警系统** - 支撑/压力位、技术指标预警 🆕
- ✅ **实时监控工具** - 命令行价格监控，自动提醒 🆕
- ✅ **仓位管理器** - 科学计算仓位 + Kelly公式优化 🆕
- ✅ **风险预设** - 保守/稳健/激进三套方案 🆕
- ✅ **止损止盈计算** - 自动计算目标价位 🆕

### 🤖 实盘交易能力
- ✅ **订单管理** - 下单、撤单、查询
- ✅ **仓位跟踪** - 实时持仓监控
- ✅ **风险控制** - 止损、止盈、仓位限制
- ✅ **券商接口** - 支持主流券商API

### 🚀 系统特性
- ⚡ **高性能** - 异步处理 + 多级缓存 + 连接池
- 🔒 **高可靠** - 故障转移 + 熔断机制 + 健康检查
- 🌐 **跨平台** - Linux/macOS/Windows + Docker部署
- 📦 **易扩展** - 分层架构 + 插件化设计
- 🎨 **零配置** - 开箱即用，智能默认配置

---

## 💡 实战案例

### 案例1: 洛阳钼业分析（完整流程）

**背景**: 洛阳钼业（603993.SH）近期涨幅较大，需要判断是否值得买入

#### 步骤1: 获取技术分析
```bash
curl http://localhost:5000/api/stocks/603993.SH/analysis?analysis_type=all
```

**系统分析结果**:
- 当前价格: ¥16.76
- RSI: 81.08 ⚠️ 严重超买
- MACD: 1.000 ✅ 多头信号
- 均线: MA5 > MA20 > MA60（完美多头排列）
- 系统建议: 观望等待，RSI过高需要回调

#### 步骤2: 设置价格预警
```bash
python examples/monitor_price.py \
    --symbol 603993.SH \
    --support 15.54 15.00 13.33 \
    --resistance 18.13 19.00 \
    --watch \
    --interval 60
```

**预警设置**:
- 支撑位: ¥15.54、¥15.00、¥13.33
- 压力位: ¥18.13、¥19.00
- 当价格触及这些位置时自动提醒

#### 步骤3: 计算建议仓位（10万本金）
```python
from src.trading.position_manager import PositionSizer, RiskPreset, RiskLevel

# 使用稳健型策略
params = RiskPreset.get_sizer_params(RiskLevel.MODERATE)
sizer = PositionSizer(total_capital=100000, **params)

# 计划在15.54支撑位买入
position = sizer.calculate_position_size(
    symbol="603993.SH",
    entry_price=15.54,
    stop_loss_price=14.76,  # -5%止损
    signal_strength=0.8     # 支撑位信号较强
)
```

**系统建议**:
- 建议买入: 1,287股
- 总金额: ¥20,000
- 占仓位: 20.0%
- 止损价: ¥14.76 (-5%)
- 风险金额: ¥1,000 (总资金的1%)
- 止盈目标1: ¥17.09 (+10%)
- 止盈目标2: ¥17.87 (+15%)

#### 步骤4: 分批建仓计划
```
第1批: ¥15.80 → 400股 → ¥6,320  (回调开始)
第2批: ¥15.54 → 500股 → ¥7,770  (5日均线)
第3批: ¥15.00 → 400股 → ¥6,000  (深度回调)
─────────────────────────────────────────
合计:  1,300股 → 总投入¥20,090 → 平均成本¥15.45
```

**投资结论**:
- ❌ 不建议当前价¥16.76买入（RSI严重超买）
- ✅ 等待回调至¥15.54-15.80区间分批买入
- 📊 严格止损¥14.68，止盈¥17.00-17.80

---

## 📖 完整文档

### 🚀 快速上手
- [快速启动指南](docs/QUICK_START.md) - 多种启动方式详解
- [API接口文档](docs/API.md) - 完整API参考
- [开发者指南](docs/DEVELOPER_GUIDE.md) - 系统开发指南 🆕

### 📈 量化交易
- [策略使用指南](STRATEGY_GUIDE.md) - 策略开发、回测、实盘完整教程
- [量化改进v1.1](QUANTITATIVE_IMPROVEMENTS.md) - 真实数据回测、参数优化
- [系统增强v2.0](SYSTEM_ENHANCEMENTS_v2.md) - 价格预警、仓位管理 🆕
- [实盘交易文档](LIVE_TRADING_IMPLEMENTATION.md) - 实盘系统架构与使用

### 🏗️ 系统架构
- [系统架构说明](docs/ARCHITECTURE.md) - 技术架构详解
- [部署指南](docs/DEPLOYMENT.md) - 生产环境部署
- [故障排查指南](docs/TROUBLESHOOTING.md) - 常见问题解决

---

## 🗂️ 项目结构

```
stock/
├── src/                         # 源代码（19,903行）
│   ├── api/                    # RESTful API接口
│   ├── strategies/             # 7种量化策略 ⭐
│   ├── backtest/               # 回测引擎 ⭐
│   ├── trading/                # 实盘交易 + 仓位管理 ⭐
│   ├── monitoring/             # 价格预警 + 监控 🆕
│   ├── data_sources/           # 多数据源集成
│   ├── services/               # 业务服务层
│   ├── core/                   # 技术/基本面/情绪分析
│   ├── database/               # 数据库管理
│   └── utils/                  # 工具函数
│
├── examples/                    # 示例工具
│   ├── backtest_strategies.py  # 回测工具
│   ├── optimize_strategy.py    # 参数优化 🆕
│   └── monitor_price.py        # 价格监控 🆕
│
├── config/                      # 配置文件
│   ├── strategies.yaml         # 策略配置
│   ├── risk_rules.yaml         # 风险规则
│   └── settings.py             # 系统设置
│
├── tests/                       # 30+ 测试文件
├── docs/                        # 20+ 文档文件
└── scripts/                     # 构建脚本
```

---

## 🎓 适用人群

### 个人投资者
- ✓ 想要科学分析股票，不再靠"感觉"交易
- ✓ 需要自动提醒买卖点，不错过机会
- ✓ 想知道应该买多少股，如何控制风险
- ✓ 希望回测验证策略，避免盲目跟风

### 量化研究员
- ✓ 开发和测试自己的交易策略
- ✓ 需要完整的回测框架和性能分析
- ✓ 进行参数优化和策略组合研究
- ✓ 需要真实历史数据验证策略有效性

### 程序化交易者
- ✓ 实现策略自动执行，24小时监控
- ✓ 需要完整的风控系统
- ✓ 希望对接券商API进行实盘交易
- ✓ 需要可靠的系统监控和告警

### 金融学习者
- ✓ 学习量化交易的完整流程
- ✓ 理解技术指标的实际应用
- ✓ 研究不同策略的表现特征
- ✓ 积累实战经验

---

## 🛠️ 技术栈

| 类别 | 技术选型 |
|------|---------|
| **核心语言** | Python 3.11+ |
| **Web框架** | Flask + asyncio |
| **数据处理** | pandas, numpy, TA-Lib |
| **数据库** | PostgreSQL / SQLite |
| **缓存** | Redis（可选） |
| **数据源** | Tushare, Yahoo Finance, Sina Finance |
| **测试** | pytest（30+测试文件）|
| **部署** | Docker, Docker Compose, Kubernetes |
| **监控** | Prometheus + Grafana |

---

## 📊 版本历史

### v2.0（2025-10-10）⭐ 当前版本
- ✅ 价格预警系统（支撑/压力位、技术指标预警）
- ✅ 仓位管理工具（科学计算 + Kelly公式）
- ✅ 实时监控工具（命令行价格监控）
- ✅ 风险管理预设（保守/稳健/激进三套方案）
- ✅ 止损止盈计算（自动计算目标价位）

### v1.1（2025-10）
- ✅ 真实数据回测（接入Tushare/Yahoo/Sina）
- ✅ 参数自动优化（网格搜索）
- ✅ 性能分析增强（15项专业指标）

### v1.0
- ✅ 数据分析API
- ✅ 技术指标计算
- ✅ 基本面分析
- ✅ 策略回测引擎

---

## ❓ 常见问题

### Q1: 系统需要什么样的电脑配置？
**A**: 最低配置：2核CPU + 4GB内存。推荐配置：4核CPU + 8GB内存。

### Q2: 是否支持离线使用？
**A**: 支持。设置`OFFLINE_MODE=true`可以使用模拟数据进行开发和测试。

### Q3: 数据源是否免费？
**A**:
- Sina Finance: 免费，无需注册
- Yahoo Finance: 免费，无需注册
- Tushare: 注册即可免费使用基础数据

### Q4: 可以用于实盘交易吗？
**A**: 可以。系统提供完整的实盘交易框架，但需要：
1. 券商提供的API接口
2. 实盘账户
3. 充分的回测和模拟交易验证

### Q5: 如何添加自定义策略？
**A**:
1. 继承`BaseStrategy`类
2. 实现`generate_signals()`方法
3. 在`config/strategies.yaml`中配置
4. 详见[策略开发指南](STRATEGY_GUIDE.md)

### Q6: 系统稳定性如何？
**A**:
- 30+ 测试用例覆盖核心功能
- 生产环境运行稳定
- 完善的错误处理和日志记录
- 支持故障转移和自动降级

### Q7: 可以同时监控多只股票吗？
**A**: 可以。启动多个监控进程，或使用批量分析API。

### Q8: 回测结果准确吗？
**A**:
- 使用真实历史数据
- 精确计算交易成本（佣金、印花税、滑点）
- 避免未来函数，防止过拟合
- 建议进行Walk-forward验证

---

## 🚀 后续规划

### 短期（1周内）
- [ ] 图表可视化（matplotlib/plotly）
- [ ] 增强Web界面
- [ ] 邮件/微信通知

### 中期（1月内）
- [ ] Walk-forward分析
- [ ] 蒙特卡洛模拟
- [ ] 多策略组合优化
- [ ] 实盘交易日志

### 长期（3月内）
- [ ] 机器学习模型
- [ ] 高频交易支持
- [ ] 期货期权回测
- [ ] 云端部署方案

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出改进建议！

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📞 获取帮助

- 📧 **问题反馈**: 通过 GitHub Issues
- 📖 **查看文档**: `docs/` 目录
- 🔧 **故障排查**: [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- 💬 **讨论交流**: GitHub Discussions

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

## ⭐ Star History

如果这个项目对你有帮助，请给一个 ⭐️ Star！

---

**最后更新**: 2025-10-10
**系统版本**: v2.0
**文档版本**: v2.0
