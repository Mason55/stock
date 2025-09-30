# 监控与告警使用指南

## 概述

本文档介绍量化交易系统的监控与告警功能，包括策略监控、告警管理、实时数据流和K线生成。

## 📊 策略监控 (StrategyMonitor)

### 功能特性

- **实时收益追踪**: 总回报、日回报、年化回报
- **风险指标**: 夏普比率、波动率、最大回撤
- **交易统计**: 胜率、盈亏比、利润因子
- **健康度评分**: 0-100分，基于多维度指标
- **Prometheus集成**: 指标导出支持

### 快速开始

```python
from src.monitoring import StrategyMonitor

# 初始化监控器
monitor = StrategyMonitor(config={
    'min_trades_for_stats': 10,
    'health_check_interval': 300,
    'performance_window': 30
})

# 注册策略
monitor.register_strategy('moving_average')

# 记录交易
monitor.record_trade(
    strategy_name='moving_average',
    symbol='000001.SZ',
    side='BUY',
    quantity=1000,
    entry_price=10.0,
    exit_price=10.5,
    pnl=500,
    entry_time=datetime(2025, 1, 1, 9, 30),
    exit_time=datetime(2025, 1, 2, 15, 0)
)

# 更新权益曲线
monitor.update_equity('moving_average', equity=1050000)

# 获取指标
metrics = monitor.get_metrics('moving_average')
print(f"胜率: {metrics.win_rate:.2%}")
print(f"夏普比率: {metrics.sharpe_ratio:.2f}")
print(f"健康度: {metrics.health_score}")

# 获取汇总统计
summary = monitor.get_summary()
print(f"活跃策略: {summary['active_strategies']}")
print(f"总盈亏: ¥{summary['total_pnl']:,.2f}")
```

### 健康度评分

健康度评分 (0-100) 基于以下因素:

| 指标 | 权重 | 评分标准 |
|------|------|----------|
| 胜率 | 20% | ≥70%=20分, ≥60%=15分, ≥50%=10分 |
| 利润因子 | 20% | ≥2.0=20分, ≥1.5=15分, ≥1.0=10分 |
| 夏普比率 | 20% | ≥2.0=20分, ≥1.0=15分, ≥0.5=10分 |
| 最大回撤 | 20% | <5%=20分, <10%=15分, <20%=10分 |
| 活跃度 | 20% | <24h=20分, <72h=15分, <7d=10分 |

### Prometheus集成

```python
# 导出Prometheus指标
metrics_text = monitor.export_prometheus_metrics()

# 在Flask中暴露
@app.route('/metrics/strategies')
def strategy_metrics():
    return monitor.export_prometheus_metrics(), 200, {'Content-Type': 'text/plain'}
```

指标格式:
```
strategy_moving_average_total_return 0.050000
strategy_moving_average_sharpe_ratio 1.250000
strategy_moving_average_win_rate 0.600000
strategy_moving_average_health_score 85
strategy_moving_average_total_trades 100
```

## 🚨 告警管理 (AlertManager)

### 功能特性

- **多渠道推送**: 日志、邮件、Webhook、钉钉、企业微信
- **告警分级**: INFO, WARNING, ERROR, CRITICAL
- **去重与限流**: 5分钟冷却，每小时最多50条
- **自定义处理器**: 注册自定义告警逻辑
- **历史记录**: 24小时告警历史

### 配置示例

```python
from src.monitoring import AlertManager, AlertLevel, AlertChannel

# 初始化告警管理器
alert_mgr = AlertManager(config={
    'channels': ['log', 'email', 'dingtalk'],
    'alert_cooldown': 300,  # 5分钟
    'max_alerts_per_hour': 50,

    # 邮件配置
    'smtp_host': 'smtp.gmail.com',
    'smtp_port': 587,
    'smtp_user': 'your_email@gmail.com',
    'smtp_password': 'your_password',
    'email_to': ['admin@example.com'],

    # 钉钉Webhook
    'dingtalk_webhook': 'https://oapi.dingtalk.com/robot/send?access_token=xxx',

    # 企业微信Webhook
    'wechat_work_webhook': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx'
})

# 发送告警
alert_mgr.send_alert(
    level=AlertLevel.WARNING,
    title='策略亏损预警',
    message='moving_average策略当日亏损达到2.5%',
    source='risk_monitor',
    metadata={
        'strategy': 'moving_average',
        'loss_pct': -2.5,
        'current_capital': 975000
    }
)
```

### 告警渠道

#### 1. 邮件告警

```python
alert_mgr.send_alert(
    level=AlertLevel.CRITICAL,
    title='交易熔断',
    message='单日亏损超过3%，已暂停交易',
    channels=[AlertChannel.EMAIL]
)
```

#### 2. 钉钉推送

```python
# 钉钉Markdown格式
alert_mgr.send_alert(
    level=AlertLevel.ERROR,
    title='下单失败',
    message='订单 #12345 提交失败：余额不足',
    channels=[AlertChannel.DINGTALK]
)
```

#### 3. 企业微信推送

```python
alert_mgr.send_alert(
    level=AlertLevel.INFO,
    title='策略启动',
    message='moving_average策略已启动',
    channels=[AlertChannel.WECHAT_WORK]
)
```

#### 4. 自定义处理器

```python
def slack_handler(alert):
    """发送到Slack"""
    import requests
    requests.post('https://hooks.slack.com/services/xxx', json={
        'text': f"{alert.title}: {alert.message}"
    })

alert_mgr.register_handler('slack', slack_handler)
```

### 告警历史查询

```python
# 查询最近24小时告警
history = alert_mgr.get_alert_history(hours=24)

# 按来源过滤
risk_alerts = alert_mgr.get_alert_history(source='risk_monitor', hours=12)

# 按级别过滤
critical_alerts = alert_mgr.get_alert_history(level=AlertLevel.CRITICAL)

# 统计汇总
summary = alert_mgr.get_alert_summary()
print(f"24小时告警数: {summary['total_alerts_24h']}")
print(f"按级别: {summary['by_level']}")
print(f"按来源: {summary['by_source']}")
```

## 📡 实时行情订阅 (RealtimeFeed)

### 新浪实时Feed

```python
from src.data_sources.realtime_feed import SinaRealtimeFeed

# 创建Feed
feed = SinaRealtimeFeed(config={
    'update_interval': 1.0,  # 1秒更新
    'max_retries': 5
})

# 注册回调
async def on_quote(symbol, data):
    print(f"{symbol}: ¥{data['price']:.2f} ({data['change']:+.2%})")

feed.register_callback(on_quote)

# 连接与订阅
await feed.connect()
await feed.subscribe(['000001.SZ', '600000.SH', '000002.SZ'])

# 获取最新数据
quote = feed.get_latest('000001.SZ')
print(f"价格: {quote['price']}")
print(f"成交量: {quote['volume']}")

# 断开
await feed.disconnect()
```

### 与实盘引擎集成

```python
from src.trading import LiveTradingEngine

engine = LiveTradingEngine(...)

# 连接实时数据
feed = SinaRealtimeFeed()
await feed.connect()

# 订阅策略所需标的
symbols = strategy.get_symbols()
await feed.subscribe(symbols)

# 将行情推送到引擎
async def push_to_engine(symbol, data):
    event = MarketDataEvent(
        symbol=symbol,
        timestamp=data['timestamp'],
        data=data
    )
    await engine.event_queue.put(event)

feed.register_callback(push_to_engine)
```

## 📈 K线生成器 (KLineGenerator)

### 功能特性

- **多周期支持**: 1m, 5m, 15m, 30m, 1h
- **实时聚合**: Tick自动聚合为K线
- **指标计算**: MA, EMA, Volume MA
- **历史管理**: 每标的每周期最多1000根
- **完成回调**: K线完成时触发

### 基础使用

```python
from src.data_sources.kline_generator import KLineGenerator

# 创建生成器
generator = KLineGenerator(
    intervals=['1m', '5m', '15m'],
    config={
        'save_to_db': True,
        'max_history': 1000
    }
)

# 处理Tick
generator.process_tick(
    symbol='000001.SZ',
    price=10.50,
    volume=1000,
    timestamp=datetime.now()
)

# 获取当前K线 (未完成)
current = generator.get_current_kline('000001.SZ', '1m')
print(f"开: {current.open}, 高: {current.high}, 收: {current.close}")

# 获取历史K线
history = generator.get_history('000001.SZ', '5m', count=50)

# 最新完成的K线
latest = generator.get_latest_kline('000001.SZ', '1m')
```

### K线完成回调

```python
def on_kline_complete(kline):
    """K线完成回调"""
    print(f"{kline.symbol} {kline.interval} 完成")
    print(f"OHLC: {kline.open}/{kline.high}/{kline.low}/{kline.close}")

    # 可以在这里触发策略信号
    if kline.close > kline.open:
        print("阳线，可能做多")

# 注册回调
generator.register_callback('1m', on_kline_complete)
generator.register_callback('5m', on_kline_complete)
```

### 技术指标计算

```python
# 计算指标
indicators = generator.calculate_indicators(
    symbol='000001.SZ',
    interval='5m',
    period=20
)

print(f"MA(20): {indicators['ma']:.2f}")
print(f"EMA(20): {indicators['ema']:.2f}")
print(f"成交量MA: {indicators['volume_ma']:.0f}")
```

### 与实时Feed集成

```python
# 创建Feed和Generator
feed = SinaRealtimeFeed()
generator = KLineGenerator(intervals=['1m', '5m'])

# Feed回调推送到Generator
async def feed_to_generator(symbol, data):
    generator.process_tick(
        symbol=symbol,
        price=data['price'],
        volume=data['volume'],
        timestamp=data['timestamp']
    )

feed.register_callback(feed_to_generator)

# Generator回调触发策略
def kline_to_strategy(kline):
    if kline.interval == '5m':
        # 计算指标
        indicators = generator.calculate_indicators(
            kline.symbol, '5m', 20
        )

        # 生成信号
        if kline.close > indicators['ma']:
            strategy.generate_signal(kline.symbol, 'BUY')

generator.register_callback('5m', kline_to_strategy)

# 启动
await feed.connect()
await feed.subscribe(['000001.SZ'])
```

## 🔗 完整示例：实盘监控系统

```python
import asyncio
from src.monitoring import StrategyMonitor, AlertManager, AlertLevel
from src.data_sources.realtime_feed import SinaRealtimeFeed
from src.data_sources.kline_generator import KLineGenerator
from src.trading import LiveTradingEngine

async def main():
    # 1. 初始化组件
    monitor = StrategyMonitor()
    alert_mgr = AlertManager(config={'channels': ['log', 'dingtalk']})
    feed = SinaRealtimeFeed()
    generator = KLineGenerator(intervals=['1m', '5m'])
    engine = LiveTradingEngine(...)

    # 2. 注册策略
    monitor.register_strategy('moving_average')

    # 3. 实时数据流: Feed -> Generator -> Engine
    async def on_quote(symbol, data):
        # 生成K线
        generator.process_tick(symbol, data['price'], data['volume'])

        # 推送到引擎
        await engine.process_market_data(symbol, data)

    feed.register_callback(on_quote)

    # 4. K线完成触发策略
    def on_kline(kline):
        # 策略逻辑...
        pass

    generator.register_callback('5m', on_kline)

    # 5. 监控策略性能
    async def monitor_loop():
        while True:
            await asyncio.sleep(60)

            metrics = monitor.get_metrics('moving_average')
            health = monitor.calculate_health_score('moving_average')

            # 健康度过低告警
            if health < 60:
                alert_mgr.send_alert(
                    level=AlertLevel.WARNING,
                    title='策略健康度下降',
                    message=f'健康度: {health}, 胜率: {metrics.win_rate:.2%}',
                    source='monitor'
                )

            # 回撤过大告警
            if metrics.max_drawdown > 0.10:
                alert_mgr.send_alert(
                    level=AlertLevel.ERROR,
                    title='最大回撤告警',
                    message=f'回撤达到 {metrics.max_drawdown:.2%}',
                    source='risk'
                )

    # 6. 启动系统
    await feed.connect()
    await feed.subscribe(['000001.SZ', '600000.SH'])
    await engine.start()

    # 7. 运行监控
    await monitor_loop()

if __name__ == '__main__':
    asyncio.run(main())
```

## 📝 最佳实践

### 1. 告警配置

- 设置合理的冷却时间，避免告警风暴
- 按重要性配置不同渠道 (CRITICAL→邮件, WARNING→钉钉)
- 定期检查告警历史，调整阈值

### 2. 策略监控

- 至少10笔交易后才计算统计指标
- 关注健康度趋势而非单次数值
- 结合多个指标综合评估 (不只看胜率)

### 3. 实时数据

- 使用合理的更新间隔 (1-3秒)
- 实现断线重连机制
- 监控数据延迟

### 4. K线生成

- 选择合适的时间周期 (1m适合日内，5m适合短线)
- 注意K线对齐 (整分钟边界)
- 及时清理历史数据

## ⚠️ 注意事项

1. **邮件告警**: 需要SMTP服务器，Gmail需开启"应用专用密码"
2. **钉钉/企微**: 需要创建自定义机器人获取Webhook
3. **实时数据**: 新浪接口有频率限制，建议间隔≥1秒
4. **K线数据**: 未来考虑持久化到数据库

## 🔮 未来计划

- [ ] WebSocket真实推送 (替代轮询)
- [ ] Level-2逐笔数据
- [ ] 高级性能分析 (因子归因/IC分析)
- [ ] 机器学习异常检测
- [ ] 分布式监控 (多策略/多实例)

---

*文档版本: v1.0*
*最后更新: 2025-09-30*