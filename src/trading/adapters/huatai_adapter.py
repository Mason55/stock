"""华泰证券 OpenAPI Adapter

Requirements:
    pip install xtquant

Setup:
    1. 在华泰证券开户
    2. 申请量化交易权限
    3. 下载SDK: https://quantapi.htsc.com.cn/
    4. 配置账号信息

Usage:
    adapter = HuataiAdapter(account_id='12345678')
    await adapter.connect()
    order_id = await adapter.place_order(order)
"""
import asyncio
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from src.trading.broker_adapter import BrokerAdapter, OrderRejectedException, BrokerConnectionError
from src.models.trading import Order, Position, OrderStatus, OrderSide

logger = logging.getLogger(__name__)

try:
    from xtquant import xtdata, xttrader
    XTQUANT_AVAILABLE = True
except ImportError:
    XTQUANT_AVAILABLE = False
    logger.warning("xtquant not installed. Install with: pip install xtquant")


class HuataiAdapter(BrokerAdapter):
    """华泰证券 OpenAPI 适配器

    支持功能:
    - A股、ETF交易
    - 实时行情订阅
    - 持仓、资金查询
    - 委托查询和撤单
    """

    def __init__(self, account_id: str, account_type: str = 'STOCK',
                 data_dir: str = './userdata_mini'):
        """
        初始化华泰适配器

        Args:
            account_id: 资金账号
            account_type: 账户类型 ('STOCK' | 'CREDIT')
            data_dir: 数据存储目录
        """
        if not XTQUANT_AVAILABLE:
            raise ImportError("xtquant not installed")

        self.account_id = account_id
        self.account_type = account_type
        self.data_dir = data_dir
        self.session = None
        self._connected = False

        logger.info(f"HuataiAdapter initialized: account={account_id}, type={account_type}")

    async def connect(self) -> bool:
        """连接华泰服务器"""
        try:
            # 创建交易会话
            self.session = xttrader.XtQuantTrader(
                path=self.data_dir,
                session_id=self.account_id
            )

            # 启动会话
            self.session.start()
            logger.info("Huatai session started")

            # 连接交易账户
            connect_result = self.session.connect()
            if connect_result != 0:
                raise BrokerConnectionError(f"Connection failed with code: {connect_result}")

            # 订阅账户
            account = xttrader.StockAccount(self.account_id, self.account_type)
            subscribe_result = self.session.subscribe(account)

            if subscribe_result != 0:
                raise BrokerConnectionError(f"Subscribe failed with code: {subscribe_result}")

            self._connected = True
            logger.info(f"Connected to Huatai: account={self.account_id}")
            return True

        except Exception as e:
            logger.error(f"Huatai connection error: {e}")
            raise BrokerConnectionError(f"Huatai API connection failed: {e}")

    async def disconnect(self) -> None:
        """断开连接"""
        if self.session:
            self.session.stop()
        self._connected = False
        logger.info("Disconnected from Huatai")

    async def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    async def place_order(self, order: Order) -> str:
        """下单

        Args:
            order: 订单对象

        Returns:
            broker_order_id: 券商订单号

        Raises:
            ConnectionError: 未连接
            OrderRejectedException: 订单被拒绝
        """
        if not self._connected:
            raise ConnectionError("Not connected to broker")

        # 订单类型映射
        order_type_map = {
            'LIMIT': xttrader.XtOrderType.LIMIT_ORDER,
            'MARKET': xttrader.XtOrderType.MARKET_ORDER
        }
        xt_order_type = order_type_map.get(order.order_type, xttrader.XtOrderType.LIMIT_ORDER)

        # 买卖方向映射
        if order.side == OrderSide.BUY:
            xt_side = xttrader.XtBusinessType.STOCK_BUY
        else:
            xt_side = xttrader.XtBusinessType.STOCK_SELL

        try:
            # 提交订单
            order_id = self.session.order_stock(
                account=xttrader.StockAccount(self.account_id, self.account_type),
                stock_code=order.symbol,
                order_type=xt_side,
                order_volume=order.quantity,
                price_type=xttrader.XtPriceType.FIX_PRICE,
                price=float(order.price) if order.price else 0,
                strategy_name="ETF_T_Trading",
                order_remark=order.metadata.get('t_type', '') if order.metadata else ''
            )

            if order_id <= 0:
                raise OrderRejectedException(f"Order rejected with code: {order_id}")

            logger.info(f"Order placed: {order_id} {order.side.value} {order.quantity} {order.symbol} @ {order.price}")
            return str(order_id)

        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            raise OrderRejectedException(f"Failed to place order: {e}")

    async def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        try:
            result = self.session.cancel_order_stock(
                account=xttrader.StockAccount(self.account_id, self.account_type),
                order_id=int(order_id)
            )

            success = result == 0
            if success:
                logger.info(f"Order canceled: {order_id}")
            else:
                logger.warning(f"Cancel order failed: {order_id}, code: {result}")

            return success

        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            return False

    async def get_order_status(self, order_id: str) -> Dict:
        """查询订单状态"""
        try:
            orders = self.session.query_stock_orders(
                account=xttrader.StockAccount(self.account_id, self.account_type),
                order_id=int(order_id)
            )

            if not orders:
                raise ValueError(f"Order not found: {order_id}")

            xt_order = orders[0]

            # 状态映射
            status_map = {
                48: OrderStatus.NEW,           # 未报
                49: OrderStatus.PARTIALLY_FILLED,  # 部分成交
                50: OrderStatus.FILLED,        # 全部成交
                51: OrderStatus.CANCELED,      # 已撤单
                52: OrderStatus.REJECTED       # 废单
            }

            return {
                'order_id': str(xt_order.order_sysid),
                'symbol': xt_order.stock_code,
                'side': 'BUY' if xt_order.order_type == xttrader.XtBusinessType.STOCK_BUY else 'SELL',
                'quantity': xt_order.order_volume,
                'filled_quantity': xt_order.traded_volume,
                'status': status_map.get(xt_order.order_status, OrderStatus.NEW).value,
                'avg_fill_price': float(xt_order.traded_price) if xt_order.traded_price else 0,
                'submitted_at': datetime.fromtimestamp(xt_order.order_time / 1000) if xt_order.order_time else None,
                'filled_at': datetime.fromtimestamp(xt_order.traded_time / 1000) if xt_order.traded_time else None
            }

        except Exception as e:
            logger.error(f"Query order status error: {e}")
            raise

    async def get_positions(self) -> List[Position]:
        """查询持仓"""
        try:
            positions = self.session.query_stock_positions(
                account=xttrader.StockAccount(self.account_id, self.account_type)
            )

            result = []
            for pos in positions:
                result.append(Position(
                    account_id=self.account_id,
                    symbol=pos.stock_code,
                    quantity=pos.volume,
                    available_quantity=pos.can_use_volume,  # 可用数量（考虑T+1）
                    avg_cost=Decimal(str(pos.avg_price)),
                    last_price=Decimal(str(pos.market_value / pos.volume)) if pos.volume > 0 else Decimal("0"),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ))

            logger.debug(f"Queried {len(result)} positions")
            return result

        except Exception as e:
            logger.error(f"Query positions error: {e}")
            return []

    async def get_account(self) -> Dict:
        """查询资金账户"""
        try:
            assets = self.session.query_stock_asset(
                account=xttrader.StockAccount(self.account_id, self.account_type)
            )

            account_info = {
                'account_id': self.account_id,
                'total_assets': assets.total_asset,
                'cash_balance': assets.cash,
                'stock_value': assets.market_value,
                'available_cash': assets.cash - assets.frozen_cash  # 可用资金 = 现金 - 冻结
            }

            logger.debug(f"Account info: total={account_info['total_assets']:.2f}, "
                        f"cash={account_info['cash_balance']:.2f}")
            return account_info

        except Exception as e:
            logger.error(f"Query account error: {e}")
            raise

    async def subscribe_quotes(self, symbols: List[str]) -> None:
        """订阅行情"""
        try:
            xtdata.subscribe_quote(symbols, period='tick', count=-1)
            logger.info(f"Subscribed to {len(symbols)} symbols")
        except Exception as e:
            logger.error(f"Subscribe quotes error: {e}")

    async def unsubscribe_quotes(self, symbols: List[str]) -> None:
        """取消订阅"""
        try:
            xtdata.unsubscribe_quote(symbols, period='tick')
            logger.info(f"Unsubscribed from {len(symbols)} symbols")
        except Exception as e:
            logger.error(f"Unsubscribe quotes error: {e}")

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """获取最新行情"""
        try:
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

        except Exception as e:
            logger.error(f"Get quote error: {e}")
            return None
