"""easytrader Adapter - 通用券商接口

基于 easytrader 开源项目，支持多家券商客户端模拟交易

Supported Brokers:
    - 华泰证券 (ht)
    - 佣金宝 (yjb)
    - 银河证券 (yh)
    - 广发证券 (gf)
    - 中信证券 (zx)
    - 招商证券 (zs)

Requirements:
    pip install easytrader

Setup:
    1. 创建配置文件 config.json:
    {
        "user": "your_account",
        "password": "your_password",
        "exe_path": "C:/交易软件/client.exe"  # 可选
    }

    2. 打开券商交易软件并登录

Usage:
    adapter = EasytraderAdapter(broker='ht')
    await adapter.connect()
"""
import asyncio
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from src.trading.broker_adapter import BrokerAdapter, OrderRejectedException, BrokerConnectionError
from src.models.trading import Order, Position, OrderSide, OrderStatus

logger = logging.getLogger(__name__)

try:
    import easytrader
    EASYTRADER_AVAILABLE = True
except ImportError:
    EASYTRADER_AVAILABLE = False
    logger.warning("easytrader not installed. Install with: pip install easytrader")


class EasytraderAdapter(BrokerAdapter):
    """基于 easytrader 的通用券商适配器

    优点:
    - 支持多家券商
    - 纯Python实现，无需C++编译
    - 适合个人投资者快速上手

    缺点:
    - 基于客户端模拟，稳定性依赖客户端
    - 延迟较高（200-500ms）
    - 需要保持交易软件开启
    """

    BROKER_CODES = {
        '华泰': 'ht',
        '佣金宝': 'yjb',
        '银河': 'yh',
        '广发': 'gf',
        '中信': 'zx',
        '招商': 'zs'
    }

    def __init__(self, broker: str = 'ht', config_file: str = 'config/easytrader_config.json'):
        """
        初始化 easytrader 适配器

        Args:
            broker: 券商代码 ('ht', 'yjb', 'yh', 'gf', 'zx', 'zs')
            config_file: 配置文件路径
        """
        if not EASYTRADER_AVAILABLE:
            raise ImportError("easytrader not installed. Run: pip install easytrader")

        self.broker = broker
        self.config_file = config_file
        self.user = None
        self._connected = False

        logger.info(f"EasytraderAdapter initialized: broker={broker}")

    async def connect(self) -> bool:
        """连接券商（使用客户端）"""
        try:
            # 创建用户实例
            self.user = easytrader.use(self.broker)

            # 加载配置并准备
            self.user.prepare(self.config_file)

            # 验证连接（尝试查询资金）
            balance = self.user.balance
            if not balance:
                raise BrokerConnectionError("Failed to query account balance")

            self._connected = True
            logger.info(f"Connected to {self.broker} via easytrader")
            return True

        except FileNotFoundError:
            raise BrokerConnectionError(f"Config file not found: {self.config_file}")
        except Exception as e:
            logger.error(f"easytrader connection error: {e}")
            raise BrokerConnectionError(f"Connection failed: {e}")

    async def disconnect(self) -> None:
        """断开连接"""
        self._connected = False
        self.user = None
        logger.info("Disconnected from easytrader")

    async def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected and self.user is not None

    async def place_order(self, order: Order) -> str:
        """下单

        Args:
            order: 订单对象

        Returns:
            entrust_no: 委托编号
        """
        if not self._connected:
            raise ConnectionError("Not connected to broker")

        try:
            # 确定操作类型
            action = 'buy' if order.side == OrderSide.BUY else 'sell'

            # 执行下单（同步调用）
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.user.__getattribute__(action)(
                    security=order.symbol,
                    price=float(order.price) if order.price else None,
                    amount=order.quantity
                )
            )

            # 检查结果
            # result 示例: {'entrust_no': '12345', 'msg': 'success'}
            if 'entrust_no' not in result:
                error_msg = result.get('msg', 'Unknown error')
                raise OrderRejectedException(f"Order failed: {error_msg}")

            entrust_no = str(result['entrust_no'])
            logger.info(f"Order placed: {entrust_no} {order.side.value} {order.quantity} {order.symbol} @ {order.price}")

            return entrust_no

        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            raise OrderRejectedException(f"Failed to place order: {e}")

    async def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        if not self._connected:
            return False

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.user.cancel_entrust(entrust_no=order_id)
            )

            success = 'success' in str(result.get('msg', '')).lower()

            if success:
                logger.info(f"Order canceled: {order_id}")
            else:
                logger.warning(f"Cancel failed: {order_id}, result: {result}")

            return success

        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            return False

    async def get_order_status(self, order_id: str) -> Dict:
        """查询委托状态"""
        if not self._connected:
            raise ConnectionError("Not connected")

        try:
            # 查询当日委托
            entrusts = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.user.today_entrusts
            )

            # 查找对应委托
            for e in entrusts:
                if str(e.get('entrust_no', '')) == order_id:
                    return {
                        'order_id': str(e['entrust_no']),
                        'symbol': e['stock_code'],
                        'side': self._parse_side(e.get('entrust_bs', '')),
                        'quantity': int(e.get('entrust_amount', 0)),
                        'filled_quantity': int(e.get('business_amount', 0)),
                        'status': self._parse_status(e.get('entrust_status', '')),
                        'avg_fill_price': float(e.get('business_price', 0)) if e.get('business_price') else 0,
                        'submitted_at': self._parse_time(e.get('entrust_time'))
                    }

            raise ValueError(f"Order not found: {order_id}")

        except Exception as e:
            logger.error(f"Query order error: {e}")
            raise

    def _parse_side(self, entrust_bs: str) -> str:
        """解析买卖方向"""
        return 'BUY' if '买' in entrust_bs else 'SELL'

    def _parse_status(self, status_text: str) -> str:
        """解析委托状态"""
        if '已成' in status_text or '成交' in status_text:
            return OrderStatus.FILLED.value
        elif '部分成交' in status_text or '部成' in status_text:
            return OrderStatus.PARTIALLY_FILLED.value
        elif '已撤' in status_text or '撤单' in status_text:
            return OrderStatus.CANCELED.value
        elif '废单' in status_text or '失败' in status_text:
            return OrderStatus.REJECTED.value
        else:
            return OrderStatus.NEW.value

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """解析时间字符串"""
        if not time_str:
            return None
        try:
            # 尝试解析 HH:MM:SS 格式
            from datetime import date, time as dt_time
            today = date.today()
            parts = time_str.split(':')
            if len(parts) == 3:
                t = dt_time(int(parts[0]), int(parts[1]), int(parts[2]))
                return datetime.combine(today, t)
        except:
            pass
        return None

    async def get_positions(self) -> List[Position]:
        """查询持仓"""
        if not self._connected:
            return []

        try:
            positions = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.user.position
            )

            result = []
            for pos in positions:
                result.append(Position(
                    account_id='easytrader',
                    symbol=pos.get('stock_code', ''),
                    quantity=int(pos.get('current_amount', 0)),
                    available_quantity=int(pos.get('enable_amount', 0)),  # T+1可卖数量
                    avg_cost=Decimal(str(pos.get('cost_price', 0))),
                    last_price=Decimal(str(pos.get('last_price', 0))),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ))

            logger.debug(f"Queried {len(result)} positions")
            return result

        except Exception as e:
            logger.error(f"Query positions error: {e}")
            return []

    async def get_account(self) -> Dict:
        """查询资金"""
        if not self._connected:
            raise ConnectionError("Not connected")

        try:
            balance_list = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.user.balance
            )

            # 通常返回列表，取第一个
            if not balance_list:
                raise ValueError("Failed to get balance")

            balance = balance_list[0] if isinstance(balance_list, list) else balance_list

            account_info = {
                'account_id': 'easytrader',
                'total_assets': float(balance.get('asset_balance', 0)),
                'cash_balance': float(balance.get('current_balance', 0)),
                'stock_value': float(balance.get('market_value', 0)),
                'available_cash': float(balance.get('enable_balance', 0))
            }

            logger.debug(f"Account info: total={account_info['total_assets']:.2f}")
            return account_info

        except Exception as e:
            logger.error(f"Query account error: {e}")
            raise

    async def subscribe_quotes(self, symbols: List[str]) -> None:
        """订阅行情（easytrader不支持主动订阅）"""
        logger.info(f"easytrader does not support active quote subscription")
        pass

    async def unsubscribe_quotes(self, symbols: List[str]) -> None:
        """取消订阅"""
        pass

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """获取行情（需要配合其他数据源，如akshare）"""
        logger.warning("easytrader does not provide real-time quotes, use external data source")
        return None
