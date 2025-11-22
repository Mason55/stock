# 实盘交易完整指南

**版本**: v2.0
**更新日期**: 2025-11-22

---

## 📋 目录

1. [系统架构](#系统架构)
2. [快速开始](#快速开始)
3. [核心组件](#核心组件)
4. [使用示例](#使用示例)
5. [券商对接](#券商对接)
6. [风险控制](#风险控制)
7. [故障排查](#故障排查)

---

## 🏗️ 系统架构

### 组件依赖关系

```
LiveTradingEngine
    ├── BrokerAdapter (接口)
    │   └── MockBrokerGateway (测试实现)
    ├── OrderManager
    │   └── DatabaseManager
    └── SignalExecutor
        ├── BrokerAdapter
        └── OrderManager

策略 (Strategy)
    └── handle_market_data() → SignalEvent
                                    ↓
                            LiveTradingEngine
                                    ↓
                            SignalExecutor
                                    ↓
                            OrderManager
                                    ↓
                            BrokerAdapter
```

### 事件流处理

```
1. 行情数据到达 (WebSocket/HTTP)
    ↓
2. MarketDataEvent → event_queue
    ↓
3. Strategy.handle_market_data()
    ↓
4. Strategy.generate_signal() → SignalEvent
    ↓
5. SignalExecutor.execute_signal()
    ↓
6. OrderManager.submit_order()
    ↓
7. BrokerAdapter.place_order()
    ↓
8. OrderManager._monitor_order() (后台)
    ↓
9. FillEvent → Strategy.handle_fill()
```

---

## 🚀 快速开始

### 1. 环境准备

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from src.database import DatabaseManager; DatabaseManager().init_db()"
```

### 2. 纸上交易测试

```python
import asyncio
from src.trading import MockBrokerGateway, LiveTradingEngine, LiveEngineConfig
from src.strategies import MovingAverageCrossover

async def main():
    # Create mock broker
    broker = MockBrokerGateway(initial_cash=1000000)

    # Configure engine (paper trading mode)
    config = LiveEngineConfig(
        initial_capital=1000000,
        enable_trading=False,  # Paper trading mode
        max_orders_per_second=10
    )

    # Create engine
    engine = LiveTradingEngine(broker, config)

    # Add strategy
    strategy = MovingAverageCrossover()
    engine.add_strategy(strategy)

    # Start engine
    await engine.start()

    # Send market data (in production, use WebSocket)
    from src.backtest.engine import MarketDataEvent
    from datetime import datetime

    event = MarketDataEvent(
        timestamp=datetime.utcnow(),
        symbol="600036.SH",
        price_data={'close': 40.5, 'volume': 1000000}
    )

    await engine.on_market_data(event)

    # Wait for processing
    await asyncio.sleep(2)

    # Check status
    status = engine.get_status()
    print(f"Engine Status: {status}")

    # Stop engine
    await engine.stop()

asyncio.run(main())
```

### 3. 启用真实交易

```python
# Change config to enable real trading
config = LiveEngineConfig(
    initial_capital=1000000,
    enable_trading=True,  # ⚠️ Real trading enabled
    max_orders_per_second=10
)
```

---

## 🔧 核心组件

### 1. BrokerAdapter 抽象接口

统一的券商接口定义 (`src/trading/broker_adapter.py`):

```python
class BrokerAdapter(ABC):
    @abstractmethod
    async def connect() -> bool

    @abstractmethod
    async def place_order(order: Order) -> str

    @abstractmethod
    async def cancel_order(order_id: str) -> bool

    @abstractmethod
    async def get_positions() -> List[Position]

    @abstractmethod
    async def get_account() -> Dict

    @abstractmethod
    async def subscribe_quotes(symbols: List[str])
```

**设计特点**:
- 异步接口 (async/await)
- 统一错误类型 (OrderRejectedException/BrokerConnectionError)
- 支持实时行情订阅
- 账户/持仓查询

### 2. LiveTradingEngine 实盘引擎

核心运行时引擎 (`src/trading/live_engine.py`):

**核心机制**:

1. **事件循环** (`_event_loop`)
   - 从队列获取事件 (MarketData/Signal/Fill)
   - 路由到对应处理器
   - 异常隔离 (单个策略异常不影响全局)

2. **心跳循环** (`_heartbeat_loop`)
   - 定期检查券商连接 (默认30秒)
   - 监控待处理订单数量
   - 自动重连机制

3. **状态同步** (`_state_sync_loop`)
   - 每分钟同步持仓
   - 同步账户资金
   - 确保本地与券商状态一致

4. **限流保护**
   - 订单限流 (默认10单/秒)
   - 防止超限触发券商风控

**配置项**:
```python
LiveEngineConfig:
    initial_capital: 初始资金
    enable_trading: 是否真实下单 (False=纸上交易)
    max_orders_per_second: 订单限流
    heartbeat_interval: 心跳间隔
```

### 3. OrderManager 订单管理

订单全生命周期管理 (`src/trading/order_manager.py`):

**状态机**:
```
CREATED → VALIDATED → SUBMITTED → ACCEPTED → FILLED
              ↓                           ↓
          REJECTED                   CANCELED
```

**核心功能**:
1. **订单校验**
   - 必填字段检查
   - 数量合法性 (>0, 100的倍数)
   - 订单类型支持 (MARKET/LIMIT)
   - 限价单价格检查

2. **订单持久化**
   - 提交前写入数据库 (orders表)
   - 状态变更时更新
   - 重启后恢复待处理订单

3. **订单监控**
   - 后台异步监控订单状态
   - 轮询券商获取最新状态 (1秒间隔)
   - 自动更新本地状态

### 4. SignalExecutor 信号执行

将策略信号转换为可执行订单 (`src/trading/signal_executor.py`):

**处理流程**:
1. 获取账户可用资金
2. 获取当前持仓
3. 根据信号类型路由 (BUY/SELL/HOLD)
4. 计算仓位大小 (signal.strength × max_position_pct)
5. 获取当前报价
6. 创建订单对象
7. 提交到OrderManager

**仓位计算**:
- 买入: `可用资金 × 10% × 信号强度 / 当前价格`
- 卖出: `当前持仓 × 信号强度`
- 自动取整到100股 (A股最小单位)

---

## 💼 券商对接

详细券商对接指南请参考 [BROKER_INTEGRATION.md](./BROKER_INTEGRATION.md)

### 支持的券商

- **华泰证券** - HuataiAdapter (OpenAPI)
- **easytrader** - 多券商支持 (华泰/银河/广发/中信等)
- 更多券商接口开发中...

### 实现自定义适配器

```python
from src.trading.broker_adapter import BrokerAdapter

class MyBrokerAdapter(BrokerAdapter):
    async def connect(self) -> bool:
        # Implement connection logic
        pass

    async def place_order(self, order: Order) -> str:
        # Implement order placement
        pass

    # Implement other required methods...
```

---

## ⚠️ 风险控制

### 1. 订单限流

```python
config = LiveEngineConfig(
    max_orders_per_second=10  # Limit to 10 orders/sec
)
```

### 2. 仓位控制

```python
# In SignalExecutor
max_position_pct = 0.1  # Max 10% per position
```

### 3. 异常处理

```python
# All exceptions are logged and isolated
# Strategy errors won't crash the entire engine
```

### 4. 已知限制

1. **数据库持久化可选**
   - 当前数据库连接失败时会降级为内存模式
   - 生产环境建议确保数据库可用

2. **行情推送未集成**
   - 需要实现WebSocket行情订阅
   - 当前依赖外部调用`on_market_data()`

3. **风控规则简单**
   - 仅有订单限流和基础校验
   - 缺少动态风控 (亏损熔断/波动检测)

---

## 🐛 故障排查

### 常见问题

**问题1: 订单未执行**
- 检查 `enable_trading` 是否为 True
- 检查券商连接状态
- 查看日志中的错误信息

**问题2: 策略不生成信号**
- 确认策略参数配置正确
- 检查行情数据是否正常
- 添加调试日志

**问题3: 连接断开**
- 检查网络连接
- 查看心跳日志
- 确认券商API凭证有效

### 调试模式

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📊 性能指标

| 指标 | 目标 | 实际 |
|------|------|------|
| 订单延迟 | <100ms | ~10ms (Mock) |
| 订单限流 | 10单/秒 | ✅ 支持 |
| 引擎启动 | <1秒 | ~200ms |
| 策略隔离 | ✅ | ✅ 异常不互相影响 |
| 状态同步 | 60秒 | ✅ 定时同步 |

---

## 📁 相关文档

- [策略开发指南](./STRATEGY_GUIDE.md)
- [券商对接文档](./BROKER_INTEGRATION.md)
- [系统架构文档](../ARCHITECTURE.md)
- [API文档](../API.md)

---

**最后更新**: 2025-11-22
**测试状态**: ✅ 11/11 通过
