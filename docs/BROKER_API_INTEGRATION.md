# 券商API接入指南

**更新日期:** 2025-11-21

本文档介绍如何将量化交易系统接入券商API，实现实盘自动交易。

---

## 目录
- [1. 国内主流券商API](#1-国内主流券商api)
- [2. 技术架构](#2-技术架构)
- [3. 接入流程](#3-接入流程)
- [4. 代码实现](#4-代码实现)
- [5. 安全与风控](#5-安全与风控)
- [6. 实施建议](#6-实施建议)

---

## 1. 国内主流券商API

### 1.1 主流券商接口对比

| 券商 | API类型 | 开发难度 | 费用 | 推荐度 |
|------|---------|----------|------|--------|
| **华泰证券** | OpenAPI | ★★★ | 免费 | ⭐⭐⭐⭐⭐ |
| **国金证券** | TradeX API | ★★★ | 免费 | ⭐⭐⭐⭐⭐ |
| **东方财富** | EMT XTP | ★★★★ | 付费 | ⭐⭐⭐⭐ |
| **中信证券** | CITIC API | ★★★★★ | 付费 | ⭐⭐⭐ |
| **同花顺** | i问财 | ★★ | 付费 | ⭐⭐⭐⭐ |

### 1.2 华泰证券 OpenAPI（推荐）

**优点:**
- 完全免费，只需开通交易权限
- 支持Python、C++、C# 等多语言
- 文档完善，社区活跃
- 支持A股、港股、期权等多市场

**申请流程:**
1. 在华泰证券开户
2. 联系客户经理申请 "量化交易权限"
3. 签署《量化交易协议》
4. 获取API账号和密钥
5. 下载SDK和文档

**官方资源:**
- API文档: https://quantapi.htsc.com.cn/
- SDK下载: Python、C++ SDK
- 测试环境: 提供仿真交易环境

### 1.3 国金证券 TradeX

**特点:**
- 基于XTP协议
- 低延迟（微秒级）
- 适合高频交易
- 支持期权、期货

### 1.4 开源方案：easytrader

**特点:**
- 支持多家券商（华泰、银河、广发等）
- 纯Python实现
- 通过同花顺客户端接口模拟
- 适合个人投资者快速上手

**安装:**
```bash
pip install easytrader
```

---

## 2. 技术架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────┐
│         Trading System (你的系统)            │
│                                             │
│  ┌─────────────┐      ┌─────────────┐      │
│  │  Strategy   │─────>│ Live Engine │      │
│  │  (做T策略)   │      │             │      │
│  └─────────────┘      └──────┬──────┘      │
│                              │              │
│                      ┌───────▼────────┐     │
│                      │ BrokerAdapter  │     │ <- 抽象接口层
│                      │   (Interface)  │     │
│                      └───────┬────────┘     │
└──────────────────────────────┼──────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼─────────┐   ┌────────▼────────┐   ┌────────▼─────────┐
│ HuataiAdapter   │   │ GuojinAdapter   │   │ EasytraderAdapter│
│ (华泰OpenAPI)    │   │ (国金TradeX)     │   │  (开源方案)       │
└───────┬─────────┘   └────────┬────────┘   └────────┬─────────┘
        │                      │                      │
        │                      │                      │
┌───────▼─────────┐   ┌────────▼────────┐   ┌────────▼─────────┐
│  华泰服务器      │   │  国金服务器      │   │  同花顺客户端     │
└─────────────────┘   └─────────────────┘   └──────────────────┘
```

### 2.2 核心接口

系统已定义 `BrokerAdapter` 抽象类：

```python
# src/trading/broker_adapter.py
class BrokerAdapter(ABC):
    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def place_order(self, order: Order) -> str: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def get_positions(self) -> List[Position]: ...

    @abstractmethod
    async def get_account(self) -> Dict: ...
```

---

## 3. 接入流程

### 3.1 开通流程

**Step 1: 选择券商**
- 资金量 < 50万: 选择华泰/国金 免费API
- 资金量 > 50万: 可选择东方财富XTP（更低延迟）
- 新手: 先用 easytrader 测试

**Step 2: 申请权限**
```
1. 联系券商客户经理
2. 填写《量化交易申请表》
3. 签署风险揭示书
4. 提供策略说明文档
5. 等待审批（3-7个工作日）
```

**Step 3: 获取凭证**
- 账号ID
- API密钥/Token
- 服务器地址
- SDK文件

**Step 4: 测试环境**
- 先在仿真环境测试
- 验证下单、撤单、查询功能
- 测试异常处理

---

## 4. 代码实现

### 4.1 华泰证券 OpenAPI 实现

```python
# src/trading/adapters/huatai_adapter.py
import asyncio
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from xtquant import xtdata, xttrader
from src.trading.broker_adapter import BrokerAdapter, OrderRejectedException
from src.models.trading import Order, Position, OrderStatus, OrderSide

class HuataiAdapter(BrokerAdapter):
    """华泰证券 OpenAPI 适配器"""

    def __init__(self, account_id: str, account_type: str = 'STOCK'):
        """
        Args:
            account_id: 资金账号
            account_type: 账户类型 (STOCK/CREDIT)
        """
        self.account_id = account_id
        self.account_type = account_type
        self.session = None
        self._connected = False

    async def connect(self) -> bool:
        """连接华泰服务器"""
        try:
            # 创建交易会话
            self.session = xttrader.XtQuantTrader(
                path='./userdata',  # 配置目录
                session_id=self.account_id
            )

            # 启动会话
            self.session.start()

            # 连接交易账户
            connect_result = self.session.connect()
            if connect_result != 0:
                raise ConnectionError(f"Connection failed: {connect_result}")

            # 订阅账户
            account = xttrader.StockAccount(self.account_id, self.account_type)
            subscribe_result = self.session.subscribe(account)

            self._connected = True
            return True

        except Exception as e:
            raise ConnectionError(f"Huatai API connection error: {e}")

    async def disconnect(self) -> None:
        """断开连接"""
        if self.session:
            self.session.stop()
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def place_order(self, order: Order) -> str:
        """下单"""
        if not self._connected:
            raise ConnectionError("Not connected to broker")

        # 转换订单类型
        xt_order_type = 23  # 限价单
        if order.order_type == 'MARKET':
            xt_order_type = 11  # 市价单

        # 转换买卖方向
        xt_side = xttrader.XtBusinessType.STOCK_BUY if order.side == OrderSide.BUY else xttrader.XtBusinessType.STOCK_SELL

        # 提交订单
        try:
            order_id = self.session.order_stock(
                account=xttrader.StockAccount(self.account_id, self.account_type),
                stock_code=order.symbol,
                order_type=xt_order_type,
                order_volume=order.quantity,
                price_type=xttrader.XtPriceType.FIX_PRICE,
                price=float(order.price) if order.price else 0,
                strategy_name="ETF_T_Trading",
                order_remark=order.metadata.get('t_type', '')
            )

            if order_id <= 0:
                raise OrderRejectedException(f"Order rejected: {order_id}")

            return str(order_id)

        except Exception as e:
            raise OrderRejectedException(f"Order placement failed: {e}")

    async def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        try:
            result = self.session.cancel_order_stock(
                account=xttrader.StockAccount(self.account_id, self.account_type),
                order_id=int(order_id)
            )
            return result == 0
        except:
            return False

    async def get_order_status(self, order_id: str) -> Dict:
        """查询订单状态"""
        orders = self.session.query_stock_orders(
            account=xttrader.StockAccount(self.account_id, self.account_type),
            order_id=int(order_id)
        )

        if not orders:
            raise ValueError(f"Order not found: {order_id}")

        xt_order = orders[0]

        # 状态映射
        status_map = {
            48: OrderStatus.NEW,
            49: OrderStatus.PARTIALLY_FILLED,
            50: OrderStatus.FILLED,
            51: OrderStatus.CANCELED,
            52: OrderStatus.REJECTED
        }

        return {
            'order_id': str(xt_order.order_sysid),
            'symbol': xt_order.stock_code,
            'side': 'BUY' if xt_order.order_type == 23 else 'SELL',
            'quantity': xt_order.order_volume,
            'filled_quantity': xt_order.traded_volume,
            'status': status_map.get(xt_order.order_status, OrderStatus.NEW).value,
            'avg_fill_price': float(xt_order.traded_price),
            'submitted_at': datetime.fromtimestamp(xt_order.order_time / 1000)
        }

    async def get_positions(self) -> List[Position]:
        """查询持仓"""
        positions = self.session.query_stock_positions(
            account=xttrader.StockAccount(self.account_id, self.account_type)
        )

        result = []
        for pos in positions:
            result.append(Position(
                account_id=self.account_id,
                symbol=pos.stock_code,
                quantity=pos.volume,
                available_quantity=pos.can_use_volume,  # 可用数量（T+1）
                avg_cost=Decimal(str(pos.avg_price)),
                last_price=Decimal(str(pos.market_value / pos.volume)) if pos.volume > 0 else Decimal("0"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            ))

        return result

    async def get_account(self) -> Dict:
        """查询资金账户"""
        assets = self.session.query_stock_asset(
            account=xttrader.StockAccount(self.account_id, self.account_type)
        )

        return {
            'account_id': self.account_id,
            'total_assets': assets.total_asset,
            'cash_balance': assets.cash,
            'stock_value': assets.market_value,
            'available_cash': assets.frozen_cash  # 可用资金
        }

    async def subscribe_quotes(self, symbols: List[str]) -> None:
        """订阅行情"""
        xtdata.subscribe_quote(symbols, period='tick', count=-1)

    async def unsubscribe_quotes(self, symbols: List[str]) -> None:
        """取消订阅"""
        xtdata.unsubscribe_quote(symbols, period='tick')

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """获取最新行情"""
        tick = xtdata.get_full_tick([symbol])
        if not tick or symbol not in tick:
            return None

        t = tick[symbol]
        return {
            'symbol': symbol,
            'price': t['lastPrice'],
            'bid_price': t['bidPrice'][0] if t['bidPrice'] else 0,
            'ask_price': t['askPrice'][0] if t['askPrice'] else 0,
            'volume': t['volume'],
            'timestamp': datetime.fromtimestamp(t['time'] / 1000)
        }
```

### 4.2 easytrader 实现（快速方案）

```python
# src/trading/adapters/easytrader_adapter.py
import asyncio
import easytrader
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from src.trading.broker_adapter import BrokerAdapter
from src.models.trading import Order, Position, OrderSide

class EasytraderAdapter(BrokerAdapter):
    """基于 easytrader 的通用券商适配器"""

    def __init__(self, broker: str = 'ht'):
        """
        Args:
            broker: 券商代码 ('ht'=华泰, 'yjb'=佣金宝, 'gf'=广发等)
        """
        self.broker = broker
        self.user = None
        self._connected = False

    async def connect(self) -> bool:
        """连接券商（使用客户端）"""
        try:
            # 使用客户端模式（需要打开券商交易软件）
            self.user = easytrader.use(self.broker)

            # 准备账户配置文件 config.json:
            # {
            #   "user": "your_account",
            #   "password": "your_password",
            #   "exe_path": "C:/华泰证券/xiadan.exe"  # 交易软件路径
            # }
            self.user.prepare('config.json')

            self._connected = True
            return True

        except Exception as e:
            raise ConnectionError(f"easytrader connection failed: {e}")

    async def disconnect(self) -> None:
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def place_order(self, order: Order) -> str:
        """下单"""
        if not self._connected:
            raise ConnectionError("Not connected")

        # easytrader 使用同步方法
        action = 'buy' if order.side == OrderSide.BUY else 'sell'

        result = self.user.__getattribute__(action)(
            security=order.symbol,
            price=float(order.price) if order.price else None,
            amount=order.quantity
        )

        # result: {'entrust_no': '12345', 'msg': 'success'}
        if 'entrust_no' not in result:
            raise OrderRejectedException(f"Order failed: {result}")

        return str(result['entrust_no'])

    async def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        try:
            result = self.user.cancel_entrust(entrust_no=order_id)
            return 'success' in result.get('msg', '').lower()
        except:
            return False

    async def get_order_status(self, order_id: str) -> Dict:
        """查询委托"""
        entrusts = self.user.today_entrusts

        for e in entrusts:
            if str(e['entrust_no']) == order_id:
                return {
                    'order_id': str(e['entrust_no']),
                    'symbol': e['stock_code'],
                    'side': 'BUY' if '买' in e['entrust_bs'] else 'SELL',
                    'quantity': int(e['entrust_amount']),
                    'filled_quantity': int(e['business_amount']),
                    'status': self._parse_status(e['entrust_status']),
                    'avg_fill_price': float(e['business_price']) if e['business_price'] else 0
                }

        raise ValueError(f"Order not found: {order_id}")

    def _parse_status(self, status_text: str) -> str:
        """解析委托状态"""
        if '已成' in status_text:
            return 'FILLED'
        elif '部分成交' in status_text:
            return 'PARTIALLY_FILLED'
        elif '已撤' in status_text:
            return 'CANCELED'
        elif '废单' in status_text:
            return 'REJECTED'
        else:
            return 'NEW'

    async def get_positions(self) -> List[Position]:
        """查询持仓"""
        positions = self.user.position

        result = []
        for pos in positions:
            result.append(Position(
                account_id='easytrader',
                symbol=pos['stock_code'],
                quantity=int(pos['current_amount']),
                available_quantity=int(pos['enable_amount']),
                avg_cost=Decimal(str(pos['cost_price'])),
                last_price=Decimal(str(pos['last_price'])),
                created_at=datetime.now(),
                updated_at=datetime.now()
            ))

        return result

    async def get_account(self) -> Dict:
        """查询资金"""
        balance = self.user.balance[0]  # 通常返回列表

        return {
            'account_id': 'easytrader',
            'total_assets': float(balance['asset_balance']),
            'cash_balance': float(balance['current_balance']),
            'stock_value': float(balance['market_value']),
            'available_cash': float(balance['enable_balance'])
        }

    async def subscribe_quotes(self, symbols: List[str]) -> None:
        pass  # easytrader 不支持主动订阅

    async def unsubscribe_quotes(self, symbols: List[str]) -> None:
        pass
```

### 4.3 配置文件

```yaml
# config/broker_config.yaml
broker:
  # 选择适配器类型: 'huatai' | 'easytrader' | 'mock'
  adapter: 'huatai'

  # 华泰配置
  huatai:
    account_id: '12345678'
    account_type: 'STOCK'
    data_dir: './userdata_mini'

  # easytrader配置
  easytrader:
    broker: 'ht'  # 券商代码
    config_file: './config/easytrader_config.json'

  # 风控参数
  risk_control:
    max_order_value: 100000  # 单笔最大金额
    max_daily_trades: 50     # 每日最大交易次数
    max_position_pct: 0.3    # 单股最大仓位比例
    enable_pre_check: true   # 启用下单前检查
```

---

## 5. 安全与风控

### 5.1 API安全

**凭证管理:**
```python
# 使用环境变量存储敏感信息
import os

BROKER_ACCOUNT = os.getenv('BROKER_ACCOUNT')
BROKER_PASSWORD = os.getenv('BROKER_PASSWORD')

# 或使用加密配置文件
from cryptography.fernet import Fernet

def load_encrypted_config(key_file, config_file):
    with open(key_file, 'rb') as f:
        key = f.read()

    cipher = Fernet(key)
    with open(config_file, 'rb') as f:
        encrypted = f.read()

    return cipher.decrypt(encrypted).decode()
```

**连接安全:**
- 使用SSL/TLS加密连接
- 验证服务器证书
- 定期更新密钥

### 5.2 风控系统

```python
# src/risk/risk_checker.py
class RiskChecker:
    """交易风控检查"""

    def __init__(self, config: Dict):
        self.max_order_value = config.get('max_order_value', 100000)
        self.max_daily_trades = config.get('max_daily_trades', 50)
        self.daily_trade_count = 0
        self.last_reset_date = datetime.now().date()

    def pre_order_check(self, order: Order, account: Dict) -> bool:
        """下单前检查"""
        # 重置每日计数
        if datetime.now().date() > self.last_reset_date:
            self.daily_trade_count = 0
            self.last_reset_date = datetime.now().date()

        # 检查交易次数
        if self.daily_trade_count >= self.max_daily_trades:
            raise RiskException("Daily trade limit exceeded")

        # 检查订单金额
        order_value = float(order.price or 0) * order.quantity
        if order_value > self.max_order_value:
            raise RiskException(f"Order value {order_value} exceeds limit {self.max_order_value}")

        # 检查可用资金
        if order.side == OrderSide.BUY:
            if order_value > account['available_cash']:
                raise RiskException("Insufficient cash")

        # 检查可用持仓
        if order.side == OrderSide.SELL:
            positions = account.get('positions', {})
            available = positions.get(order.symbol, {}).get('available_quantity', 0)
            if order.quantity > available:
                raise RiskException("Insufficient available shares")

        self.daily_trade_count += 1
        return True

class RiskException(Exception):
    pass
```

### 5.3 异常处理

```python
# 订单重试机制
async def place_order_with_retry(broker, order, max_retries=3):
    """带重试的下单"""
    for i in range(max_retries):
        try:
            order_id = await broker.place_order(order)
            return order_id
        except OrderRejectedException as e:
            if '资金不足' in str(e) or '持仓不足' in str(e):
                # 不可恢复错误，直接抛出
                raise
            elif i < max_retries - 1:
                # 可重试错误，等待后重试
                await asyncio.sleep(1)
            else:
                raise
```

---

## 6. 实施建议

### 6.1 测试流程

**Phase 1: 离线测试（1-2周）**
```bash
# 使用Mock Broker测试策略逻辑
python live_trading_513090.py --mode paper
```

**Phase 2: 仿真交易（2-4周）**
```bash
# 使用券商仿真环境
python live_trading_513090.py --mode paper --broker huatai_sim
```

**Phase 3: 小资金实盘（1个月）**
```bash
# 使用少量资金测试（如1-5万）
python live_trading_513090.py --mode live --capital 10000
```

**Phase 4: 正式运行**
```bash
# 使用完整资金
python live_trading_513090.py --mode live --capital 100000
```

### 6.2 监控与报警

```python
# 监控指标
- 订单成功率
- 平均成交时间
- 滑点统计
- 每日盈亏
- 系统错误日志

# 报警机制
- 订单被拒绝 -> 微信/邮件通知
- 账户余额不足 -> 暂停交易
- 连接断开 -> 自动重连
- 异常波动 -> 人工介入
```

### 6.3 日常运维

**每日检查清单:**
- [ ] 检查系统连接状态
- [ ] 查看昨日交易记录
- [ ] 核对持仓和资金
- [ ] 检查日志异常
- [ ] 查看策略表现

**每周任务:**
- [ ] 分析做T成功率
- [ ] 优化策略参数
- [ ] 检查风控规则
- [ ] 备份交易数据

---

## 7. 快速开始

### 7.1 使用 easytrader（最简单）

```bash
# 1. 安装
pip install easytrader

# 2. 创建配置文件 config/easytrader_config.json
{
  "user": "your_account",
  "password": "your_password"
}

# 3. 运行
python live_trading_513090.py --mode live --broker easytrader
```

### 7.2 使用华泰OpenAPI（推荐）

```bash
# 1. 申请华泰量化权限（联系客户经理）

# 2. 下载SDK
# 访问 https://quantapi.htsc.com.cn/
# 下载 Python SDK

# 3. 安装
pip install xtquant

# 4. 配置
# 编辑 config/broker_config.yaml

# 5. 运行
python live_trading_513090.py --mode live --broker huatai
```

---

## 8. 常见问题

**Q1: 需要多少资金才能开通量化API?**
A: 大部分券商无资金门槛，但建议至少5-10万以获得更好的服务。

**Q2: API费用多少?**
A: 华泰、国金等免费，东财XTP按交易量收费（约万1-万2）。

**Q3: 交易延迟有多大?**
A: 华泰OpenAPI约50-200ms，XTP可达10ms以内。

**Q4: 支持T+0吗?**
A: A股是T+1，但ETF支持当日买卖（T+0），适合做T。

**Q5: 如何保证系统稳定?**
A:
- 使用VPS运行（避免断网断电）
- 部署监控和自动重启
- 设置风控和止损
- 定期备份数据

---

## 9. 参考资源

**官方文档:**
- 华泰证券: https://quantapi.htsc.com.cn/
- 东方财富XTP: http://xtp.zts.com.cn/
- easytrader: https://github.com/shidenggui/easytrader

**社区:**
- 聚宽社区: https://www.joinquant.com/
- 优矿社区: https://uqer.datayes.com/
- 雪球: https://xueqiu.com/

**书籍:**
- 《Python量化交易实战》
- 《量化交易之路》

---

*最后更新: 2025-11-21*
