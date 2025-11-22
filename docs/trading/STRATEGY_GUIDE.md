# 量化策略使用指南

**版本**: v1.0
**更新日期**: 2025-09-30

---

## 📋 目录

1. [快速开始](#快速开始)
2. [可用策略](#可用策略)
3. [策略配置](#策略配置)
4. [回测使用](#回测使用)
5. [实盘交易](#实盘交易)
6. [自定义策略](#自定义策略)
7. [性能优化](#性能优化)

---

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行第一个回测

```bash
# 双均线策略回测
python examples/backtest_strategies.py --strategy moving_average --symbol 600036.SH --days 60

# 查看所有选项
python examples/backtest_strategies.py --help
```

### 配置策略参数

编辑 `config/strategies.yaml`:

```yaml
moving_average_crossover:
  enabled: true
  fast_period: 5
  slow_period: 20
  signal_strength: 0.8
```

---

## 📊 可用策略

### 1. 双均线交叉策略 (MovingAverageCrossover)

**策略逻辑**:
- **买入**: 快速均线(5日)上穿慢速均线(20日) - 金叉
- **卖出**: 快速均线下穿慢速均线 - 死叉

**适用市场**: 趋势明显的市场

**参数**:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `fast_period` | 5 | 快速MA周期 |
| `slow_period` | 20 | 慢速MA周期 |
| `signal_strength` | 0.8 | 信号强度(0-1) |

**示例**:
```python
from src.strategies import MovingAverageCrossover

strategy = MovingAverageCrossover(config={
    'fast_period': 10,
    'slow_period': 30,
    'signal_strength': 0.9
})
```

**优点**:
- ✅ 简单易懂
- ✅ 趋势跟踪能力强
- ✅ 延迟信号过滤噪音

**缺点**:
- ⚠️ 震荡市频繁交易
- ⚠️ 信号滞后
- ⚠️ 回撤可能较大

---

### 2. 均值回归策略 (MeanReversion)

**策略逻辑**:
- **买入**: 价格触及布林带下轨 AND RSI < 30 (超卖)
- **卖出**: 价格触及布林带上轨 OR RSI > 70 (超买)

**适用市场**: 横盘震荡市场

**参数**:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `bb_period` | 20 | 布林带周期 |
| `bb_std_dev` | 2.0 | 标准差倍数 |
| `rsi_period` | 14 | RSI周期 |
| `rsi_oversold` | 30 | 超卖阈值 |
| `rsi_overbought` | 70 | 超买阈值 |

**示例**:
```python
from src.strategies import MeanReversion

strategy = MeanReversion(config={
    'bb_period': 20,
    'bb_std_dev': 2.5,
    'rsi_oversold': 25,
    'rsi_overbought': 75
})
```

**优点**:
- ✅ 震荡市表现好
- ✅ 胜率较高
- ✅ 双重确认减少假信号

**缺点**:
- ⚠️ 趋势市容易反向
- ⚠️ 需要及时止损
- ⚠️ 计算复杂度较高

---

### 3. 动量策略 (Momentum)

**策略逻辑**:
- **买入**: 20日涨幅 > 5% (强势)
- **卖出**: 20日涨幅 < -2% (转弱)

**适用市场**: 单边趋势市场

**参数**:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `lookback_period` | 20 | 动量计算周期 |
| `momentum_threshold` | 5.0 | 买入动量阈值(%) |
| `exit_threshold` | -2.0 | 卖出动量阈值(%) |
| `max_positions` | 5 | 最大持仓数 |

**示例**:
```python
from src.strategies import Momentum

strategy = Momentum(config={
    'lookback_period': 30,
    'momentum_threshold': 8.0,
    'max_positions': 3
})
```

**优点**:
- ✅ 捕捉强势股
- ✅ 风险分散(多持仓)
- ✅ 适合牛市

**缺点**:
- ⚠️ 熊市表现差
- ⚠️ 追涨风险
- ⚠️ 需要严格止损

---

## ⚙️ 策略配置

### 配置文件结构

```yaml
# config/strategies.yaml

# 单个策略配置
moving_average_crossover:
  enabled: true          # 是否启用
  fast_period: 5
  slow_period: 20
  signal_strength: 0.8

# 策略组合
combinations:
  conservative:          # 保守组合
    - moving_average_crossover
    - mean_reversion

  aggressive:            # 激进组合
    - momentum

  balanced:              # 平衡组合
    - moving_average_crossover
    - mean_reversion
    - momentum
```

### 加载策略

```python
from src.strategies.strategy_loader import StrategyLoader

loader = StrategyLoader()

# 加载单个策略
strategy = loader.load_strategy('moving_average_crossover')

# 加载多个策略
strategies = loader.load_strategies([
    'moving_average_crossover',
    'mean_reversion'
])

# 加载预定义组合
strategies = loader.load_combination('balanced')

# 查看可用策略
print(loader.list_available_strategies())
# ['moving_average_crossover', 'mean_reversion', 'momentum']

# 查看启用的策略
print(loader.list_enabled_strategies())
```

---

## 📈 回测使用

### 命令行回测

```bash
# 单策略回测
python examples/backtest_strategies.py --strategy moving_average --symbol 600036.SH --days 60

# 策略组合回测
python examples/backtest_strategies.py --combination balanced --symbol 600036.SH --days 90

# 所有策略对比
python examples/backtest_strategies.py --strategy all --symbol 600036.SH --days 120
```

### 编程方式回测

```python
import asyncio
from datetime import date, timedelta
import pandas as pd

from src.backtest.engine import BacktestEngine
from src.strategies import MovingAverageCrossover

async def run_backtest():
    # 准备数据
    end_date = date.today()
    start_date = end_date - timedelta(days=60)

    # 加载历史数据 (此处需实际数据源)
    data = pd.DataFrame({
        'date': pd.date_range(start_date, end_date),
        'open': [...],
        'high': [...],
        'low': [...],
        'close': [...],
        'volume': [...]
    })

    # 创建回测引擎
    engine = BacktestEngine(
        start_date=start_date,
        end_date=end_date,
        initial_capital=1000000.0,
        config={
            'costs': {
                'commission_rate': 0.0003,  # 万三佣金
                'stamp_tax_rate': 0.001      # 千一印花税
            }
        }
    )

    # 加载数据和策略
    engine.load_market_data('600036.SH', data)
    strategy = MovingAverageCrossover()
    engine.add_strategy(strategy)

    # 运行回测
    results = await engine.run()

    # 查看结果
    print(f"Total Return: {results['total_return']:.2%}")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.3f}")
    print(f"Max Drawdown: {results['max_drawdown']:.2%}")

    return results

asyncio.run(run_backtest())
```

### 回测结果分析

回测输出包含以下指标:

| 指标 | 说明 |
|------|------|
| `total_return` | 总收益率 |
| `annualized_return` | 年化收益率 |
| `volatility` | 波动率 |
| `sharpe_ratio` | 夏普比率 (风险调整后收益) |
| `max_drawdown` | 最大回撤 |
| `total_trades` | 交易次数 |
| `equity_curve` | 权益曲线 (DataFrame) |
| `trades` | 交易明细 (List) |

---

## 🔴 实盘交易

### 纸上交易模式

```python
import asyncio
from src.trading import MockBrokerGateway, LiveTradingEngine, LiveEngineConfig
from src.strategies import MovingAverageCrossover

async def run_paper_trading():
    # 创建模拟券商
    broker = MockBrokerGateway(initial_cash=1000000)

    # 配置引擎 (纸上交易)
    config = LiveEngineConfig(
        enable_trading=False,  # 关键: 设为False启用纸上交易
        max_orders_per_second=10
    )

    engine = LiveTradingEngine(broker, config)

    # 添加策略
    strategy = MovingAverageCrossover()
    engine.add_strategy(strategy)

    # 启动引擎
    await engine.start()

    # 模拟发送行情数据
    from src.backtest.engine import MarketDataEvent
    from datetime import datetime

    event = MarketDataEvent(
        timestamp=datetime.utcnow(),
        symbol="600036.SH",
        price_data={'close': 40.5, 'volume': 1000000}
    )
    await engine.on_market_data(event)

    # 运行一段时间
    await asyncio.sleep(60)

    # 查看状态
    status = engine.get_status()
    print(f"Status: {status}")

    # 停止引擎
    await engine.stop()

asyncio.run(run_paper_trading())
```

### 实盘交易模式

⚠️ **警告**: 实盘交易涉及真实资金，请务必:
1. 先进行充分回测
2. 使用纸上交易验证
3. 小资金试运行
4. 设置止损保护

```python
# 实盘交易 (需要真实券商接口)
config = LiveEngineConfig(
    enable_trading=True,    # 启用真实下单
    max_orders_per_second=5  # 限流保护
)

# 使用真实券商接口 (需要实现BrokerAdapter子类)
# broker = XTPBrokerGateway(account_id="...", password="...")

engine = LiveTradingEngine(broker, config)
# ... 其余代码同上
```

### 实盘监控

```python
# 查看引擎状态
status = engine.get_status()
print(f"Running: {status['is_running']}")
print(f"Strategies: {status['num_strategies']}")
print(f"Positions: {status['num_positions']}")
print(f"Assets: ¥{status['total_assets']:,.2f}")

# 查看持仓
positions = await broker.get_positions()
for pos in positions:
    print(f"{pos.symbol}: {pos.quantity} shares @ ¥{pos.avg_cost:.2f}")

# 查看账户
account = await broker.get_account()
print(f"Cash: ¥{account['cash_balance']:,.2f}")
print(f"Stock Value: ¥{account['stock_value']:,.2f}")
```

---

## 🛠️ 自定义策略

### 策略模板

```python
from src.backtest.engine import Strategy, MarketDataEvent
import logging

logger = logging.getLogger(__name__)

class MyCustomStrategy(Strategy):
    """自定义策略模板."""

    def __init__(self, config: dict = None):
        config = config or {}
        super().__init__("my_custom_strategy", config)

        # 策略参数
        self.param1 = config.get('param1', 10)
        self.param2 = config.get('param2', 0.5)

        # 内部状态
        self.price_history = {}

        logger.info(f"Strategy initialized: {self.name}")

    async def handle_market_data(self, event: MarketDataEvent):
        """处理行情数据，生成交易信号."""
        symbol = event.symbol
        price = float(event.price_data.get('close', 0))

        if price <= 0:
            return

        # 1. 更新内部状态
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)

        # 2. 计算指标
        if len(self.price_history[symbol]) < self.param1:
            return

        indicator = self._calculate_indicator(symbol)

        # 3. 生成信号
        if indicator > self.param2:
            self.generate_signal(
                symbol,
                "BUY",
                strength=0.8,
                metadata={'indicator': indicator}
            )
            logger.info(f"BUY signal: {symbol} @ {price:.2f}")

        elif symbol in self.position and self.position[symbol] > 0:
            if indicator < -self.param2:
                self.generate_signal(
                    symbol,
                    "SELL",
                    strength=1.0,
                    metadata={'indicator': indicator}
                )
                logger.info(f"SELL signal: {symbol} @ {price:.2f}")

    def _calculate_indicator(self, symbol: str) -> float:
        """计算自定义指标."""
        prices = self.price_history[symbol][-self.param1:]
        # 示例: 简单动量
        return (prices[-1] - prices[0]) / prices[0] * 100

    def get_indicators(self, symbol: str) -> dict:
        """获取当前指标值."""
        if symbol not in self.price_history:
            return {}

        return {
            'indicator': self._calculate_indicator(symbol),
            'current_price': self.price_history[symbol][-1]
        }
```

### 注册自定义策略

1. 将策略文件放入 `src/strategies/`
2. 在 `src/strategies/__init__.py` 中导出
3. 在 `src/strategies/strategy_loader.py` 中注册

```python
# src/strategies/strategy_loader.py
STRATEGY_REGISTRY = {
    'moving_average_crossover': MovingAverageCrossover,
    'mean_reversion': MeanReversion,
    'momentum': Momentum,
    'my_custom_strategy': MyCustomStrategy,  # 添加新策略
}
```

4. 在 `config/strategies.yaml` 中配置

```yaml
my_custom_strategy:
  enabled: true
  param1: 15
  param2: 0.6
```

---

## ⚡ 性能优化

### 1. 数据处理优化

```python
# 使用deque限制历史数据长度
from collections import deque

self.price_history = deque(maxlen=100)  # 只保留最近100个数据点
```

### 2. 指标缓存

```python
# 缓存已计算的指标
def _get_ma(self, symbol: str, period: int) -> float:
    cache_key = f"{symbol}_{period}"
    if cache_key in self._indicator_cache:
        return self._indicator_cache[cache_key]

    ma = self._calculate_ma(symbol, period)
    self._indicator_cache[cache_key] = ma
    return ma
```

### 3. 限制信号频率

```python
# 避免频繁交易
from datetime import datetime, timedelta

def should_generate_signal(self, symbol: str) -> bool:
    if symbol in self.last_signal_time:
        elapsed = datetime.utcnow() - self.last_signal_time[symbol]
        if elapsed < timedelta(minutes=5):
            return False
    return True
```

### 4. 异步处理

```python
# 使用异步避免阻塞
async def handle_market_data(self, event: MarketDataEvent):
    # 异步数据处理
    await asyncio.sleep(0)  # 让出控制权
    # 计算指标...
```

---

## 📞 支持与反馈

### 常见问题

**Q: 为什么回测收益和实盘不一致?**
A: 可能原因:
- 回测未考虑滑点
- 手续费设置不准确
- 数据拟合过度
- 市场环境变化

**Q: 如何避免过度拟合?**
A: 建议:
- 使用样本外数据验证
- 参数不要过于复杂
- 策略逻辑要有经济意义
- 多市场/多时期测试

**Q: 策略何时需要调整?**
A: 观察指标:
- 连续亏损超过3次
- 收益率显著低于回测
- 市场风格发生变化
- 波动率异常

### 获取帮助

- 📚 文档: `docs/` 目录
- 🐛 问题反馈: GitHub Issues
- 💬 讨论: GitHub Discussions

---

**最后更新**: 2025-09-30
**文档版本**: v1.0
**系统版本**: 阶段2 (策略库完成)