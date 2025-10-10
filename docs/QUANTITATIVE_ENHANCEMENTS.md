# 量化功能增强指南

快速索引：
- 真实数据回测使用方法
- 策略参数优化教程
- 性能分析指标说明
- 常见问题解决

详细内容请参考根目录下的 `QUANTITATIVE_IMPROVEMENTS.md`

## 快速开始

### 1. 使用真实数据回测
\`\`\`bash
python examples/backtest_strategies.py --strategy moving_average --symbol 000977.SZ --days 60
\`\`\`

### 2. 优化策略参数
\`\`\`bash
python examples/optimize_strategy.py --strategy moving_average --symbol 600036.SH --days 120
\`\`\`

### 3. 对比多个策略
\`\`\`bash
python examples/backtest_strategies.py --strategy all --symbol 600036.SH --days 90
\`\`\`

## 新增文件

- `examples/optimize_strategy.py` - 策略参数优化工具
- `src/backtest/performance.py` - 性能分析模块
- `QUANTITATIVE_IMPROVEMENTS.md` - 详细改进文档

## 性能指标说明

- **Sharpe Ratio**: 风险调整后收益 (>1.0 较好)
- **Sortino Ratio**: 只考虑下行风险 (>1.5 优秀)
- **Calmar Ratio**: 收益/最大回撤比 (>3.0 优秀)
- **Max Drawdown**: 最大回撤 (<15% 较好)
- **Win Rate**: 胜率 (>50% 较好)
- **Profit Factor**: 盈亏比 (>1.5 较好)

