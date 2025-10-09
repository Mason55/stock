# src/services/etl_tasks.py - ETL tasks for historical data and indicators
import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session

from config.stock_symbols import STOCK_SYMBOLS
from src.data_sources.data_source_manager import data_source_manager
from src.models.market_data import AdjustType, Frequency, HistoricalPrice
from src.services.indicators_calculator import IndicatorsCalculator

logger = logging.getLogger(__name__)


class ETLTasks:
    """Batch ETL tasks for historical data collection and processing"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.indicators_calc = IndicatorsCalculator(db_session)

    async def fetch_and_store_historical_prices(
        self, symbol: str, start_date: date, end_date: date
    ) -> int:
        """Fetch historical prices from data source and store to database"""
        try:
            # Fetch data from data source manager
            data = await data_source_manager.get_historical_data(symbol, start_date, end_date)

            if data is None or data.empty:
                logger.warning(f"No data fetched for {symbol}")
                return 0

            stored_count = 0
            for idx, row in data.iterrows():
                try:
                    trade_date = row.get("date") or idx
                    if isinstance(trade_date, str):
                        trade_date = datetime.strptime(trade_date, "%Y-%m-%d").date()
                    elif isinstance(trade_date, datetime):
                        trade_date = trade_date.date()

                    # Check if record exists
                    existing = (
                        self.db.query(HistoricalPrice)
                        .filter_by(
                            symbol=symbol,
                            trade_date=trade_date,
                            frequency=Frequency.DAILY,
                            adjust_type=AdjustType.NONE,
                        )
                        .first()
                    )

                    if existing:
                        # Update existing record
                        price_record = existing
                    else:
                        price_record = HistoricalPrice(
                            symbol=symbol,
                            trade_date=trade_date,
                            frequency=Frequency.DAILY,
                            adjust_type=AdjustType.NONE,
                        )
                        self.db.add(price_record)

                    # Update price data
                    price_record.open_price = Decimal(str(row["open"]))
                    price_record.high_price = Decimal(str(row["high"]))
                    price_record.low_price = Decimal(str(row["low"]))
                    price_record.close_price = Decimal(str(row["close"]))
                    price_record.volume = int(row["volume"])

                    if "amount" in row and row["amount"]:
                        price_record.amount = Decimal(str(row["amount"]))
                    if "pre_close" in row and row["pre_close"]:
                        price_record.pre_close = Decimal(str(row["pre_close"]))
                    if "change" in row and row["change"]:
                        price_record.change = Decimal(str(row["change"]))
                    if "change_pct" in row and row["change_pct"]:
                        price_record.change_pct = Decimal(str(row["change_pct"]))

                    price_record.updated_at = datetime.utcnow()
                    stored_count += 1

                except Exception as e:
                    logger.error(f"Failed to store price for {symbol} on {trade_date}: {e}")
                    continue

            self.db.commit()
            logger.info(f"Stored {stored_count} price records for {symbol}")
            return stored_count

        except Exception as e:
            logger.error(f"Failed to fetch/store historical prices for {symbol}: {e}")
            self.db.rollback()
            return 0

    async def run_daily_etl(self, symbols: List[str] = None, lookback_days: int = 90) -> dict:
        """Run daily ETL for multiple stocks"""
        if symbols is None:
            symbols = list(STOCK_SYMBOLS.keys())[:50]  # Process top 50 stocks

        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)

        results = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "prices_stored": 0,
            "indicators_stored": 0,
        }

        logger.info(f"Starting daily ETL for {len(symbols)} symbols")

        for symbol in symbols:
            try:
                results["processed"] += 1

                # Step 1: Fetch and store historical prices
                price_count = await self.fetch_and_store_historical_prices(
                    symbol, start_date, end_date
                )
                results["prices_stored"] += price_count

                # Step 2: Calculate and store indicators
                if price_count > 0:
                    success = self.indicators_calc.process_stock(symbol, lookback_days)
                    if success:
                        results["succeeded"] += 1
                    else:
                        results["failed"] += 1
                else:
                    results["failed"] += 1

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"ETL failed for {symbol}: {e}")
                results["failed"] += 1
                continue

        logger.info(
            f"Daily ETL completed: {results['succeeded']}/{results['processed']} succeeded, "
            f"{results['prices_stored']} prices, {results['indicators_stored']} indicators"
        )

        return results

    async def run_incremental_update(self, symbols: List[str] = None) -> dict:
        """Run incremental update for recent data only"""
        if symbols is None:
            symbols = list(STOCK_SYMBOLS.keys())[:50]

        # Only fetch last 7 days
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        return await self.run_daily_etl(symbols, lookback_days=7)

    def cleanup_old_data(self, retention_days: int = 730) -> dict:
        """Clean up historical data older than retention period"""
        cutoff_date = date.today() - timedelta(days=retention_days)

        try:
            # Clean up old prices
            prices_deleted = (
                self.db.query(HistoricalPrice)
                .filter(HistoricalPrice.trade_date < cutoff_date)
                .delete()
            )

            self.db.commit()

            logger.info(f"Cleaned up {prices_deleted} old price records before {cutoff_date}")

            return {"prices_deleted": prices_deleted}

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            self.db.rollback()
            return {"prices_deleted": 0}


class CacheWarmer:
    """Pre-warm cache for frequently accessed stocks"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.hot_stocks = list(STOCK_SYMBOLS.keys())[:20]  # Top 20 most popular

    async def warm_cache(self) -> dict:
        """Pre-fetch and cache hot stocks data"""
        logger.info(f"Warming cache for {len(self.hot_stocks)} hot stocks")

        warmed = 0
        for symbol in self.hot_stocks:
            try:
                # Fetch recent data (will be cached by cache manager)
                await data_source_manager.get_realtime_data([symbol])
                warmed += 1
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Failed to warm cache for {symbol}: {e}")
                continue

        logger.info(f"Cache warmed for {warmed} stocks")
        return {"warmed": warmed, "total": len(self.hot_stocks)}