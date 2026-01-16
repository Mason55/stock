# src/strategies/hs300_etf_rotation.py - Conservative weekly rotation for HS300 + ETFs
import logging
import statistics
from collections import defaultdict, deque
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config.stock_symbols import A_SHARE_STOCKS
from src.backtest.engine import Strategy, MarketDataEvent
from src.models.trading import OrderSide

logger = logging.getLogger(__name__)

DEFAULT_ETF_UNIVERSE = [
    "510300.SH",  # CSI 300 ETF
    "510500.SH",  # CSI 500 ETF
    "510050.SH",  # SSE 50 ETF
    "159915.SZ",  # ChiNext ETF
    "510880.SH",  # Dividend ETF
]


class HS300EtfRotation(Strategy):
    """Conservative weekly rotation for HS300 stocks and ETFs.

    Core ideas:
    - Weekly rebalance
    - Market regime filter using HS300 index trend
    - Momentum ranking with volatility filter for stocks
    - Defensive allocation when trend weakens or drawdown hits
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        super().__init__("hs300_etf_rotation", config)

        self.market_index_symbol = config.get("market_index_symbol", "000300.SH")
        self.stock_universe = self._resolve_stock_universe(config)
        self.etf_universe = config.get("etf_universe") or list(DEFAULT_ETF_UNIVERSE)
        self.defensive_asset = config.get("defensive_asset", "511010.SH")

        self.stock_allocation = float(config.get("stock_allocation", 0.4))
        self.defensive_stock_allocation = float(config.get("defensive_stock_allocation", 0.0))
        self.top_n_stocks = int(config.get("top_n_stocks", 10))
        self.top_n_etf = int(config.get("top_n_etf", 3))

        self.momentum_lookback = int(config.get("momentum_lookback", 60))
        self.volatility_lookback = int(config.get("volatility_lookback", 20))
        self.trend_ma_short = int(config.get("trend_ma_short", 60))
        self.trend_ma_long = int(config.get("trend_ma_long", 120))

        self.min_stock_momentum = float(config.get("min_stock_momentum", 0.0))
        self.min_etf_momentum = float(config.get("min_etf_momentum", 0.0))
        self.max_stock_volatility = float(config.get("max_stock_volatility", 0.05))
        self.use_vol_adjusted_momentum = bool(config.get("use_vol_adjusted_momentum", True))

        self.max_drawdown_pct = config.get("max_drawdown_pct")
        self.cooldown_weeks = int(config.get("cooldown_weeks", 4))
        self.min_defensive_weeks = int(config.get("min_defensive_weeks", 4))
        default_recover = (
            float(self.max_drawdown_pct) * 0.6 if self.max_drawdown_pct is not None else 0.1
        )
        self.drawdown_recover_pct = float(config.get("drawdown_recover_pct", default_recover))
        self.defensive_only_on_drawdown = bool(config.get("defensive_only_on_drawdown", True))
        self.missing_data_tolerance_days = int(config.get("missing_data_tolerance_days", 5))
        self.max_total_weight = float(config.get("max_total_weight", 0.95))
        self.max_position_weight = float(config.get("max_position_weight", 0.08))
        self.cash_buffer_pct = float(config.get("cash_buffer_pct", 0.05))
        self.min_order_value = float(config.get("min_order_value", 1000.0))
        self.max_order_value = float(config.get("max_order_value", 3000000.0))
        self.use_available_cash_only = bool(config.get("use_available_cash_only", True))
        self.two_phase_rebalance = bool(config.get("two_phase_rebalance", True))

        self.initial_capital = float(config.get("initial_capital", 1000000.0))
        self.cash = self.initial_capital
        self.equity_peak = self.initial_capital
        self.risk_off_until: Optional[date] = None
        self.pending_buy_weights: Optional[Dict[str, float]] = None
        self.last_rebalance_date: Optional[date] = None
        self.portfolio = None

        self.lot_size = int(config.get("lot_size", 100))

        max_lookback = max(self.momentum_lookback, self.volatility_lookback, self.trend_ma_long)
        self.price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_lookback + 1))
        self.last_prices: Dict[str, float] = {}
        self.last_seen_date: Dict[str, date] = {}
        self.last_rebalance_week: Optional[int] = None
        self.date_symbols_seen: Dict[date, set] = defaultdict(set)
        self.drawdown_mode_until: Optional[date] = None

        self.all_symbols = self._build_symbol_set()

        logger.info(
            "HS300 ETF Rotation initialized: stocks=%d, etfs=%d, rebalance=weekly",
            len(self.stock_universe),
            len(self.etf_universe),
        )

    async def handle_market_data(self, event: MarketDataEvent):
        symbol = event.symbol
        close_price = float(event.price_data.get("close", 0))
        if close_price <= 0:
            return

        self.last_prices[symbol] = close_price
        self.price_history[symbol].append(close_price)

        current_date = event.timestamp.date()
        self.date_symbols_seen[current_date].add(symbol)
        self.last_seen_date[symbol] = current_date

        if not self._ready_for_rebalance(current_date):
            return

        await self._rebalance(current_date)

    async def handle_fill(self, event):
        await super().handle_fill(event)

        if self.portfolio is None:
            if event.side == OrderSide.BUY:
                self.cash -= float(event.price * event.quantity + event.commission)
            elif event.side == OrderSide.SELL:
                self.cash += float(event.price * event.quantity - event.commission)

    def _ready_for_rebalance(self, current_date: date) -> bool:
        if not self._all_symbols_seen(current_date):
            return False

        if self.pending_buy_weights is not None:
            if self.last_rebalance_date == current_date:
                return False
            if not self._has_min_history(self.market_index_symbol, self.trend_ma_long):
                return False
            return True

        week_key = self._week_key(current_date)
        if self.last_rebalance_week == week_key:
            return False

        if not self._has_min_history(self.market_index_symbol, self.trend_ma_long):
            return False

        return True

    async def _rebalance(self, current_date: date):
        self.last_rebalance_date = current_date
        week_key = self._week_key(current_date)
        self.last_rebalance_week = week_key
        self.date_symbols_seen.pop(current_date, None)

        equity = self._current_equity()
        drawdown = self._update_drawdown(equity)

        risk_on = self._market_risk_on()
        if self.risk_off_until and current_date < self.risk_off_until:
            risk_on = False

        drawdown_active = self._update_drawdown_mode(current_date, drawdown, risk_on)
        if drawdown_active:
            risk_on = False

        if drawdown_active and self.defensive_only_on_drawdown:
            target_weights = {}
            if self.defensive_asset:
                target_weights[self.defensive_asset] = self.max_total_weight
            self._emit_rebalance_orders(target_weights)
            logger.info(
                "Defensive mode %s | equity=%.2f | drawdown=%.2f%% | target=%s",
                current_date,
                equity,
                drawdown * 100,
                target_weights,
            )
            return

        if self.pending_buy_weights is not None:
            self._emit_rebalance_orders(self.pending_buy_weights, buy_only=True)
            self.pending_buy_weights = None
            return

        etf_ranked = self._rank_assets(self.etf_universe, self.min_etf_momentum, require_trend=False)
        stock_ranked = self._rank_assets(
            self.stock_universe,
            self.min_stock_momentum,
            require_trend=True,
            volatility_cap=self.max_stock_volatility,
        )

        top_etfs = [symbol for symbol, _score in etf_ranked[: self.top_n_etf]]
        top_stocks = [symbol for symbol, _score in stock_ranked[: self.top_n_stocks]]

        stock_weight_total = self.stock_allocation if risk_on else self.defensive_stock_allocation
        etf_weight_total = max(0.0, 1.0 - stock_weight_total)

        if not top_stocks or stock_weight_total <= 0:
            etf_weight_total += stock_weight_total
            stock_weight_total = 0.0

        target_weights: Dict[str, float] = {}
        if top_stocks and stock_weight_total > 0:
            per_stock = stock_weight_total / len(top_stocks)
            for symbol in top_stocks:
                target_weights[symbol] = per_stock

        if top_etfs and etf_weight_total > 0:
            per_etf = etf_weight_total / len(top_etfs)
            for symbol in top_etfs:
                target_weights[symbol] = target_weights.get(symbol, 0.0) + per_etf
        elif etf_weight_total > 0 and self.defensive_asset:
            target_weights[self.defensive_asset] = etf_weight_total

        self._emit_rebalance_orders(target_weights)

        logger.info(
            "Rebalance %s | risk_on=%s | equity=%.2f | drawdown=%.2f%% | targets=%s",
            current_date,
            risk_on,
            equity,
            drawdown * 100,
            target_weights,
        )

    def _emit_rebalance_orders(self, target_weights: Dict[str, float], buy_only: bool = False):
        equity = self._current_equity()
        if equity <= 0:
            return

        target_weights = self._apply_position_caps(target_weights)
        if target_weights:
            total_weight = sum(target_weights.values())
            if total_weight > self.max_total_weight > 0:
                scale = self.max_total_weight / total_weight
                target_weights = {symbol: weight * scale for symbol, weight in target_weights.items()}

        current_positions = {symbol: qty for symbol, qty in self.position.items() if qty > 0}
        target_qty_map: Dict[str, int] = {}
        for symbol, weight in target_weights.items():
            price = self.last_prices.get(symbol)
            if not price or price <= 0:
                continue
            target_value = equity * weight
            target_qty = int(target_value / price / self.lot_size) * self.lot_size
            if target_qty > 0:
                target_qty_map[symbol] = target_qty

        sell_orders = []
        if not buy_only:
            for symbol, qty in current_positions.items():
                if symbol not in target_qty_map:
                    if self._order_value(symbol, qty) >= self.min_order_value:
                        sell_orders.append((symbol, qty, "rebalance_exit"))
                    continue

                target_qty = target_qty_map[symbol]
                delta = target_qty - qty
                if delta < -self.lot_size:
                    sell_qty = abs(delta)
                    if self._order_value(symbol, sell_qty) >= self.min_order_value:
                        sell_orders.append((symbol, sell_qty, "rebalance_trim"))

        if self.two_phase_rebalance and sell_orders and not buy_only:
            for symbol, qty, reason in sell_orders:
                for chunk in self._split_quantity(symbol, qty):
                    self.generate_signal(
                        symbol,
                        "SELL",
                        strength=1.0,
                        metadata={"quantity": chunk, "reason": reason},
                    )
            self.pending_buy_weights = target_weights
            return

        if not buy_only:
            for symbol, qty, reason in sell_orders:
                for chunk in self._split_quantity(symbol, qty):
                    self.generate_signal(
                        symbol,
                        "SELL",
                        strength=1.0,
                        metadata={"quantity": chunk, "reason": reason},
                    )

        if self.use_available_cash_only:
            if self.portfolio is not None and hasattr(self.portfolio, "available_cash"):
                available_cash = max(0.0, self.portfolio.available_cash())
            else:
                available_cash = max(0.0, self.cash * (1.0 - self.cash_buffer_pct))
        else:
            if self.portfolio is not None:
                available_cash = max(0.0, self.portfolio.cash)
            else:
                available_cash = max(0.0, self.cash)

        for symbol, target_qty in target_qty_map.items():
            price = self.last_prices.get(symbol)
            if not price or price <= 0:
                continue

            current_qty = self.position.get(symbol, 0)
            delta = target_qty - current_qty
            if delta < self.lot_size:
                continue

            remaining = delta
            for chunk in self._split_quantity(symbol, remaining):
                buy_value = chunk * price
                if buy_value < self.min_order_value:
                    continue

                if self.use_available_cash_only and buy_value > available_cash:
                    max_qty = int(available_cash / price / self.lot_size) * self.lot_size
                    if max_qty < self.lot_size:
                        break
                    chunk = min(chunk, max_qty)
                    buy_value = chunk * price

                if buy_value < self.min_order_value:
                    continue

                self.generate_signal(
                    symbol,
                    "BUY",
                    strength=1.0,
                    metadata={
                        "quantity": chunk,
                        "target_weight": target_weights.get(symbol, 0.0),
                        "reason": "rebalance_buy",
                        "min_order_value": self.min_order_value,
                    },
                )

                remaining -= chunk
                if self.use_available_cash_only:
                    available_cash = max(0.0, available_cash - buy_value)
                if remaining < self.lot_size:
                    break

    def _order_value(self, symbol: str, quantity: int) -> float:
        price = self.last_prices.get(symbol)
        if not price:
            return 0.0
        return float(price * quantity)

    def _apply_position_caps(self, target_weights: Dict[str, float]) -> Dict[str, float]:
        if self.max_position_weight <= 0:
            return target_weights
        capped = {}
        for symbol, weight in target_weights.items():
            capped[symbol] = min(weight, self.max_position_weight)
        return capped

    def _max_qty_by_order_value(self, price: float) -> int:
        if self.max_order_value <= 0 or price <= 0:
            return 0
        return int(self.max_order_value / price / self.lot_size) * self.lot_size

    def _split_quantity(self, symbol: str, quantity: int) -> List[int]:
        price = self.last_prices.get(symbol)
        if not price or price <= 0:
            return []

        max_qty = self._max_qty_by_order_value(price)
        if max_qty <= 0:
            return [quantity]

        chunks = []
        remaining = quantity
        while remaining >= self.lot_size:
            chunk = min(remaining, max_qty)
            if chunk < self.lot_size:
                break
            if self._order_value(symbol, chunk) < self.min_order_value:
                break
            chunks.append(chunk)
            remaining -= chunk
        return chunks

    def _rank_assets(
        self,
        universe: List[str],
        min_momentum: float,
        require_trend: bool,
        volatility_cap: Optional[float] = None,
    ) -> List[Tuple[str, float]]:
        ranked = []
        for symbol in universe:
            if not self._has_min_history(symbol, self.momentum_lookback):
                continue

            price = self.last_prices.get(symbol)
            if not price:
                continue

            if require_trend and not self._trend_filter(symbol):
                continue

            momentum = self._momentum(symbol)
            if momentum is None or momentum < min_momentum:
                continue

            volatility = self._volatility(symbol)
            if volatility_cap is not None and volatility is not None and volatility > volatility_cap:
                continue

            score = momentum
            if self.use_vol_adjusted_momentum and volatility:
                score = momentum / volatility

            ranked.append((symbol, score))

        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked

    def _momentum(self, symbol: str) -> Optional[float]:
        history = self.price_history.get(symbol)
        if not history or len(history) <= self.momentum_lookback:
            return None
        start_price = history[-self.momentum_lookback]
        end_price = history[-1]
        if start_price <= 0:
            return None
        return (end_price / start_price) - 1.0

    def _volatility(self, symbol: str) -> Optional[float]:
        history = self.price_history.get(symbol)
        if not history or len(history) <= self.volatility_lookback:
            return None
        prices = list(history)[-self.volatility_lookback :]
        returns = []
        for i in range(1, len(prices)):
            prev = prices[i - 1]
            if prev <= 0:
                continue
            returns.append((prices[i] / prev) - 1.0)
        if len(returns) < 2:
            return None
        return statistics.pstdev(returns)

    def _trend_filter(self, symbol: str) -> bool:
        history = self.price_history.get(symbol)
        if not history or len(history) < self.trend_ma_long:
            return False
        prices = list(history)
        ma_long = sum(prices[-self.trend_ma_long :]) / self.trend_ma_long
        return prices[-1] > ma_long

    def _market_risk_on(self) -> bool:
        history = self.price_history.get(self.market_index_symbol)
        if not history or len(history) < self.trend_ma_long:
            return False
        prices = list(history)
        ma_short = sum(prices[-self.trend_ma_short :]) / self.trend_ma_short
        ma_long = sum(prices[-self.trend_ma_long :]) / self.trend_ma_long
        return prices[-1] > ma_long and ma_short >= ma_long

    def _current_equity(self) -> float:
        if self.portfolio is not None:
            return float(self.portfolio.total_value)

        total = self.cash
        for symbol, qty in self.position.items():
            price = self.last_prices.get(symbol)
            if price:
                total += qty * price
        return total

    def _update_drawdown(self, equity: float) -> float:
        if equity > self.equity_peak:
            self.equity_peak = equity
        if self.equity_peak <= 0:
            return 0.0
        return (self.equity_peak - equity) / self.equity_peak

    def _update_risk_off(self, current_date: date, drawdown: float):
        if self.max_drawdown_pct is None:
            return
        if drawdown >= float(self.max_drawdown_pct):
            self.risk_off_until = current_date + timedelta(weeks=self.cooldown_weeks)

    def _update_drawdown_mode(self, current_date: date, drawdown: float, market_risk_on: bool) -> bool:
        if self.max_drawdown_pct is None:
            return False

        if drawdown >= float(self.max_drawdown_pct):
            self.drawdown_mode_until = current_date + timedelta(weeks=self.min_defensive_weeks)
            self.risk_off_until = current_date + timedelta(weeks=self.cooldown_weeks)
            return True

        if self.drawdown_mode_until and current_date < self.drawdown_mode_until:
            return True

        if self.drawdown_mode_until and current_date >= self.drawdown_mode_until:
            if drawdown <= self.drawdown_recover_pct and market_risk_on:
                self.drawdown_mode_until = None
                return False
            return True

        return False

    def _has_min_history(self, symbol: str, min_len: int) -> bool:
        history = self.price_history.get(symbol)
        return history is not None and len(history) >= min_len

    def _week_key(self, current_date: date) -> int:
        year, week, _ = current_date.isocalendar()
        return year * 100 + week

    def _all_symbols_seen(self, current_date: date) -> bool:
        active_symbols = {
            symbol
            for symbol, seen_date in self.last_seen_date.items()
            if symbol in self.all_symbols
            if (current_date - seen_date).days <= self.missing_data_tolerance_days
        }
        if not active_symbols:
            return False
        return self.date_symbols_seen[current_date].issuperset(active_symbols)

    def _build_symbol_set(self) -> set:
        symbols = set(self.stock_universe + self.etf_universe + [self.market_index_symbol])
        if self.defensive_asset:
            symbols.add(self.defensive_asset)
        return {s for s in symbols if s}

    def _resolve_stock_universe(self, config: Dict) -> List[str]:
        stock_universe = config.get("stock_universe") or []
        if stock_universe:
            return list(stock_universe)

        stock_universe_path = config.get("stock_universe_path")
        if stock_universe_path:
            path = Path(stock_universe_path)
            if path.is_file():
                symbols = []
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    symbols.append(line.split(",")[0].strip())
                if symbols:
                    return symbols

        return [item["code"] for item in A_SHARE_STOCKS]
