# src/services/batch_optimizer.py - Batch query optimization utilities
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.models.indicators import TechnicalIndicators
from src.models.market_data import HistoricalPrice

logger = logging.getLogger(__name__)


class BatchQueryOptimizer:
    """Optimize batch queries with connection pooling and parallel execution"""

    def __init__(self, db_session: Session, max_workers: int = 10):
        self.db = db_session
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def batch_fetch_indicators(
        self, symbols: List[str], date_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch indicators for multiple symbols in one query"""
        try:
            query = self.db.query(TechnicalIndicators).filter(
                TechnicalIndicators.symbol.in_(symbols)
            )

            if date_filter:
                query = query.filter(TechnicalIndicators.calc_date == date_filter)
            else:
                # Get latest for each symbol using subquery
                from sqlalchemy import func
                from sqlalchemy.orm import aliased

                subq = (
                    self.db.query(
                        TechnicalIndicators.symbol,
                        func.max(TechnicalIndicators.calc_date).label("max_date"),
                    )
                    .filter(TechnicalIndicators.symbol.in_(symbols))
                    .group_by(TechnicalIndicators.symbol)
                    .subquery()
                )

                query = self.db.query(TechnicalIndicators).join(
                    subq,
                    and_(
                        TechnicalIndicators.symbol == subq.c.symbol,
                        TechnicalIndicators.calc_date == subq.c.max_date,
                    ),
                )

            results = query.all()

            # Organize by symbol
            indicators_map = {}
            for indicator in results:
                indicators_map[indicator.symbol] = {
                    "symbol": indicator.symbol,
                    "calc_date": indicator.calc_date.isoformat(),
                    "ma_5": float(indicator.ma_5) if indicator.ma_5 else None,
                    "ma_20": float(indicator.ma_20) if indicator.ma_20 else None,
                    "rsi_12": float(indicator.rsi_12) if indicator.rsi_12 else None,
                    "macd_dif": float(indicator.macd_dif) if indicator.macd_dif else None,
                    "boll_upper": float(indicator.boll_upper) if indicator.boll_upper else None,
                    "boll_lower": float(indicator.boll_lower) if indicator.boll_lower else None,
                    "kdj_k": float(indicator.kdj_k) if indicator.kdj_k else None,
                    "kdj_d": float(indicator.kdj_d) if indicator.kdj_d else None,
                }

            return indicators_map

        except Exception as e:
            logger.error(f"Batch fetch indicators failed: {e}")
            return {}

    async def batch_fetch_prices(
        self, symbols: List[str], limit: int = 1
    ) -> Dict[str, List[Dict]]:
        """Fetch recent prices for multiple symbols in one query"""
        try:
            from sqlalchemy import func

            # Get latest N prices for each symbol using window function
            subq = (
                self.db.query(
                    HistoricalPrice,
                    func.row_number()
                    .over(
                        partition_by=HistoricalPrice.symbol,
                        order_by=HistoricalPrice.trade_date.desc(),
                    )
                    .label("row_num"),
                )
                .filter(HistoricalPrice.symbol.in_(symbols))
                .subquery()
            )

            query = self.db.query(
                subq.c.symbol,
                subq.c.trade_date,
                subq.c.open_price,
                subq.c.high_price,
                subq.c.low_price,
                subq.c.close_price,
                subq.c.volume,
            ).filter(subq.c.row_num <= limit)

            results = query.all()

            # Organize by symbol
            prices_map = {}
            for row in results:
                symbol = row.symbol
                if symbol not in prices_map:
                    prices_map[symbol] = []

                prices_map[symbol].append(
                    {
                        "date": row.trade_date.isoformat(),
                        "open": float(row.open_price),
                        "high": float(row.high_price),
                        "low": float(row.low_price),
                        "close": float(row.close_price),
                        "volume": int(row.volume),
                    }
                )

            return prices_map

        except Exception as e:
            logger.error(f"Batch fetch prices failed: {e}")
            return {}

    async def parallel_process(
        self, items: List[Any], process_func: Callable, batch_size: int = 10
    ) -> List[Any]:
        """Process items in parallel with batching"""
        results = []

        # Split into batches
        batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

        for batch in batches:
            # Create async tasks for each item in batch
            tasks = [asyncio.create_task(process_func(item)) for item in batch]

            # Wait for all tasks in batch to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and collect results
            for result in batch_results:
                if not isinstance(result, Exception):
                    results.append(result)
                else:
                    logger.error(f"Batch processing error: {result}")

        return results

    def batch_insert(self, model_class, data_list: List[Dict], batch_size: int = 100):
        """Bulk insert with batching for better performance"""
        try:
            total_inserted = 0

            # Split into batches
            for i in range(0, len(data_list), batch_size):
                batch = data_list[i : i + batch_size]

                # Use bulk_insert_mappings for better performance
                self.db.bulk_insert_mappings(model_class, batch)
                total_inserted += len(batch)

                # Commit every N batches to avoid long transactions
                if total_inserted % (batch_size * 10) == 0:
                    self.db.commit()

            # Final commit
            self.db.commit()
            logger.info(f"Batch inserted {total_inserted} records")

            return total_inserted

        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            self.db.rollback()
            return 0

    def batch_update(
        self, model_class, updates: List[Dict], key_field: str = "id", batch_size: int = 100
    ):
        """Bulk update with batching"""
        try:
            total_updated = 0

            for i in range(0, len(updates), batch_size):
                batch = updates[i : i + batch_size]

                # Use bulk_update_mappings for better performance
                self.db.bulk_update_mappings(model_class, batch)
                total_updated += len(batch)

                # Commit periodically
                if total_updated % (batch_size * 10) == 0:
                    self.db.commit()

            self.db.commit()
            logger.info(f"Batch updated {total_updated} records")

            return total_updated

        except Exception as e:
            logger.error(f"Batch update failed: {e}")
            self.db.rollback()
            return 0

    def prefetch_related(
        self, query, relationships: List[str], strategy: str = "selectinload"
    ):
        """Prefetch related data to avoid N+1 queries"""
        from sqlalchemy.orm import selectinload, joinedload, subqueryload

        strategy_map = {
            "selectinload": selectinload,
            "joinedload": joinedload,
            "subqueryload": subqueryload,
        }

        load_func = strategy_map.get(strategy, selectinload)

        for rel in relationships:
            query = query.options(load_func(rel))

        return query

    async def cached_batch_query(
        self, cache_manager, cache_key_prefix: str, symbols: List[str], query_func: Callable
    ) -> Dict[str, Any]:
        """Execute batch query with caching"""
        results = {}
        uncached_symbols = []

        # Check cache for each symbol
        if cache_manager:
            for symbol in symbols:
                cache_key = f"{cache_key_prefix}:{symbol}"
                cached = await cache_manager.get(cache_key)
                if cached:
                    results[symbol] = cached
                else:
                    uncached_symbols.append(symbol)
        else:
            uncached_symbols = symbols

        # Query uncached symbols
        if uncached_symbols:
            fresh_results = await query_func(uncached_symbols)

            # Update cache
            if cache_manager:
                for symbol, data in fresh_results.items():
                    cache_key = f"{cache_key_prefix}:{symbol}"
                    await cache_manager.set(cache_key, data, ttl=300)  # 5 min cache

            results.update(fresh_results)

        return results


class QueryOptimizationMixin:
    """Mixin class to add query optimization methods to services"""

    def __init__(self):
        self._batch_optimizer = None

    def get_batch_optimizer(self, db_session: Session) -> BatchQueryOptimizer:
        """Get or create batch optimizer"""
        if self._batch_optimizer is None:
            self._batch_optimizer = BatchQueryOptimizer(db_session)
        return self._batch_optimizer

    async def batch_analyze_stocks(
        self, db_session: Session, symbols: List[str], analysis_types: List[str]
    ) -> Dict[str, Any]:
        """Optimized batch analysis of multiple stocks"""
        optimizer = self.get_batch_optimizer(db_session)

        # Fetch all data in parallel
        indicators_task = optimizer.batch_fetch_indicators(symbols)
        prices_task = optimizer.batch_fetch_prices(symbols, limit=60)

        indicators_map, prices_map = await asyncio.gather(indicators_task, prices_task)

        # Build results
        results = {}
        for symbol in symbols:
            results[symbol] = {
                "symbol": symbol,
                "indicators": indicators_map.get(symbol, {}),
                "recent_prices": prices_map.get(symbol, []),
                "analysis": {},
            }

            # Add quick analysis based on indicators
            if symbol in indicators_map:
                ind = indicators_map[symbol]
                results[symbol]["analysis"] = self._quick_analysis(ind)

        return results

    def _quick_analysis(self, indicators: Dict) -> Dict:
        """Quick technical analysis from indicators"""
        analysis = {"signals": [], "overall": "NEUTRAL"}

        # MA analysis
        ma_5 = indicators.get("ma_5")
        ma_20 = indicators.get("ma_20")
        if ma_5 and ma_20:
            if ma_5 > ma_20:
                analysis["signals"].append("MA_BULLISH")
            else:
                analysis["signals"].append("MA_BEARISH")

        # RSI analysis
        rsi = indicators.get("rsi_12")
        if rsi:
            if rsi < 30:
                analysis["signals"].append("RSI_OVERSOLD")
            elif rsi > 70:
                analysis["signals"].append("RSI_OVERBOUGHT")

        # MACD analysis
        macd = indicators.get("macd_dif")
        if macd:
            if macd > 0:
                analysis["signals"].append("MACD_BULLISH")
            else:
                analysis["signals"].append("MACD_BEARISH")

        # Overall signal
        bullish = sum(1 for s in analysis["signals"] if "BULLISH" in s or "OVERSOLD" in s)
        bearish = sum(1 for s in analysis["signals"] if "BEARISH" in s or "OVERBOUGHT" in s)

        if bullish > bearish:
            analysis["overall"] = "BUY"
        elif bearish > bullish:
            analysis["overall"] = "SELL"

        return analysis