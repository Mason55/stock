# src/scheduler.py - Background data collection scheduler
import asyncio
import logging
import schedule
import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from src.services.data_collector import DataCollector
from src.services.recommendation_engine import RecommendationEngine
from src.models.stock import Stock, StockPrice
from src.database import db_manager, get_db_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataScheduler:
    """Background scheduler for data collection and model updates"""
    
    def __init__(self):
        # Use managed database instance
        if not db_manager.is_initialized():
            raise RuntimeError("Database not initialized")
        
        self.session_factory = db_manager.get_session_factory()
        
        # Initialize services will be created per operation
        self.data_collector = None
    
    async def run_data_collection(self):
        """Execute data collection cycle"""
        logger.info("Starting scheduled data collection...")
        
        try:
            with db_manager.get_session() as db_session:
                async with DataCollector(db_session) as collector:
                    await collector.run_data_collection()
            logger.info("Data collection completed successfully")
        except Exception as e:
            logger.error(f"Data collection failed: {e}")
    
    def run_model_update(self):
        """Update recommendation models"""
        logger.info("Starting model update...")
        
        try:
            with db_manager.get_session() as db_session:
                recommendation_engine = RecommendationEngine(db_session)
                # This would normally load training data from database
                # For now, we'll skip actual training due to lack of labeled data
                logger.info("Model update completed (placeholder)")
        except Exception as e:
            logger.error(f"Model update failed: {e}")
    
    def setup_schedule(self):
        """Configure scheduled tasks"""
        # Market hours data collection (every 30 seconds during trading)
        schedule.every(30).seconds.do(lambda: asyncio.run(self.run_data_collection()))
        
        # Model update (every hour)
        schedule.every().hour.do(self.run_model_update)
        
        # Daily cleanup at 2 AM
        schedule.every().day.at("02:00").do(self.cleanup_old_data)
        
        logger.info("Scheduler configured with the following tasks:")
        logger.info("- Data collection: Every 30 seconds")
        logger.info("- Model update: Every hour")
        logger.info("- Data cleanup: Daily at 2:00 AM")
    
    def cleanup_old_data(self):
        """Clean up old data beyond retention period"""
        logger.info("Running data cleanup...")
        
        try:
            with db_manager.get_session() as db_session:
                # Clean up old price data (keep 2 years)
                cutoff_date = datetime.now() - timedelta(days=730)
                
                deleted_count = db_session.query(StockPrice).filter(
                    StockPrice.timestamp < cutoff_date
                ).delete()
                
                logger.info(f"Cleaned up {deleted_count} old price records")
            
        except Exception as e:
            logger.error(f"Data cleanup failed: {e}")
    
    def run_forever(self):
        """Run the scheduler continuously"""
        logger.info("Starting Stock Analysis System Scheduler...")
        
        self.setup_schedule()
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        finally:
            # Sessions are managed via db_manager context managers per task
            pass


if __name__ == "__main__":
    scheduler = DataScheduler()
    scheduler.run_forever()
