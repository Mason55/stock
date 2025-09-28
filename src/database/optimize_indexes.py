# src/database/optimize_indexes.py - Database index optimization
import logging
from sqlalchemy import text, Index
from sqlalchemy.exc import OperationalError
from src.database.session import get_session
from src.models.stock import Base, StockPrice, StockRecommendation

logger = logging.getLogger(__name__)


class DatabaseIndexOptimizer:
    """Database index optimization manager"""
    
    def __init__(self):
        self.session = get_session()
    
    def create_performance_indexes(self):
        """Create performance-critical indexes"""
        
        indexes_to_create = [
            # StockPrice优化索引
            {
                'name': 'idx_stock_prices_code_timestamp_desc',
                'table': 'stock_prices',
                'sql': '''
                CREATE INDEX IF NOT EXISTS idx_stock_prices_code_timestamp_desc 
                ON stock_prices(stock_code, timestamp DESC)
                '''
            },
            {
                'name': 'idx_stock_prices_timestamp_desc',
                'table': 'stock_prices', 
                'sql': '''
                CREATE INDEX IF NOT EXISTS idx_stock_prices_timestamp_desc 
                ON stock_prices(timestamp DESC)
                '''
            },
            {
                'name': 'idx_stock_prices_volume_price',
                'table': 'stock_prices',
                'sql': '''
                CREATE INDEX IF NOT EXISTS idx_stock_prices_volume_price 
                ON stock_prices(volume, close_price) 
                WHERE volume > 0
                '''
            },
            
            # StockRecommendation优化索引
            {
                'name': 'idx_recommendations_code_timestamp_desc',
                'table': 'stock_recommendations',
                'sql': '''
                CREATE INDEX IF NOT EXISTS idx_recommendations_code_timestamp_desc 
                ON stock_recommendations(stock_code, timestamp DESC)
                '''
            },
            {
                'name': 'idx_recommendations_action_confidence',
                'table': 'stock_recommendations',
                'sql': '''
                CREATE INDEX IF NOT EXISTS idx_recommendations_action_confidence 
                ON stock_recommendations(action, confidence) 
                WHERE confidence > 0
                '''
            },
            
            # Stock表优化索引
            {
                'name': 'idx_stocks_industry_exchange',
                'table': 'stocks',
                'sql': '''
                CREATE INDEX IF NOT EXISTS idx_stocks_industry_exchange 
                ON stocks(industry, exchange)
                '''
            },
            {
                'name': 'idx_stocks_market_cap',
                'table': 'stocks',
                'sql': '''
                CREATE INDEX IF NOT EXISTS idx_stocks_market_cap 
                ON stocks(market_cap) 
                WHERE market_cap IS NOT NULL
                '''
            }
        ]
        
        created_count = 0
        failed_count = 0
        
        for idx_info in indexes_to_create:
            try:
                logger.info(f"Creating index: {idx_info['name']} on table {idx_info['table']}")
                self.session.execute(text(idx_info['sql']))
                self.session.commit()
                created_count += 1
                logger.info(f"✅ Index {idx_info['name']} created successfully")
                
            except OperationalError as e:
                if "already exists" in str(e).lower():
                    logger.info(f"⚠️ Index {idx_info['name']} already exists, skipping")
                else:
                    logger.error(f"❌ Failed to create index {idx_info['name']}: {e}")
                    failed_count += 1
                    self.session.rollback()
            except Exception as e:
                logger.error(f"❌ Unexpected error creating index {idx_info['name']}: {e}")
                failed_count += 1
                self.session.rollback()
        
        logger.info(f"Index creation summary: {created_count} created, {failed_count} failed")
        return created_count, failed_count
    
    def analyze_table_statistics(self):
        """Analyze table statistics for query optimization"""
        
        try:
            # PostgreSQL statistics
            if self.session.bind.dialect.name == 'postgresql':
                stats_queries = [
                    "ANALYZE stocks;",
                    "ANALYZE stock_prices;", 
                    "ANALYZE stock_recommendations;"
                ]
                
                for query in stats_queries:
                    self.session.execute(text(query))
                    logger.info(f"✅ Executed: {query}")
                
                self.session.commit()
                
                # Get table statistics
                stats_query = '''
                SELECT 
                    schemaname,
                    tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_rows,
                    n_dead_tup as dead_rows
                FROM pg_stat_user_tables 
                WHERE schemaname = 'public'
                ORDER BY n_live_tup DESC
                '''
                
                result = self.session.execute(text(stats_query))
                logger.info("📊 Table Statistics:")
                for row in result:
                    logger.info(f"  {row.tablename}: {row.live_rows:,} live rows, {row.dead_rows:,} dead rows")
            
            # SQLite optimization
            elif self.session.bind.dialect.name == 'sqlite':
                analyze_queries = [
                    "ANALYZE;",
                    "PRAGMA optimize;"
                ]
                
                for query in analyze_queries:
                    self.session.execute(text(query))
                    logger.info(f"✅ Executed: {query}")
                
                self.session.commit()
                
        except Exception as e:
            logger.error(f"❌ Failed to analyze table statistics: {e}")
            self.session.rollback()
    
    def check_index_usage(self):
        """Check index usage statistics"""
        
        try:
            if self.session.bind.dialect.name == 'postgresql':
                # PostgreSQL index usage stats
                usage_query = '''
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_tup_read,
                    idx_tup_fetch,
                    idx_scan
                FROM pg_stat_user_indexes 
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
                '''
                
                result = self.session.execute(text(usage_query))
                logger.info("📈 Index Usage Statistics:")
                for row in result:
                    logger.info(f"  {row.tablename}.{row.indexname}: {row.idx_scan:,} scans")
                    
            elif self.session.bind.dialect.name == 'sqlite':
                # SQLite doesn't have detailed index stats, but we can check if indexes exist
                indexes_query = '''
                SELECT name, tbl_name, sql 
                FROM sqlite_master 
                WHERE type = 'index' AND tbl_name IN ('stocks', 'stock_prices', 'stock_recommendations')
                ORDER BY tbl_name, name
                '''
                
                result = self.session.execute(text(indexes_query))
                logger.info("📋 Existing Indexes:")
                for row in result:
                    if row.sql:  # Skip auto indexes
                        logger.info(f"  {row.tbl_name}.{row.name}")
                        
        except Exception as e:
            logger.error(f"❌ Failed to check index usage: {e}")
    
    def optimize_database(self):
        """Run complete database optimization"""
        
        logger.info("🚀 Starting database optimization...")
        
        # Create performance indexes
        created, failed = self.create_performance_indexes()
        
        # Analyze table statistics
        self.analyze_table_statistics()
        
        # Check index usage
        self.check_index_usage()
        
        logger.info("✅ Database optimization completed")
        return {
            'indexes_created': created,
            'indexes_failed': failed,
            'status': 'completed'
        }
    
    def __del__(self):
        """Clean up database session"""
        if hasattr(self, 'session') and self.session:
            self.session.close()


def optimize_database_indexes():
    """Convenience function to run database optimization"""
    optimizer = DatabaseIndexOptimizer()
    return optimizer.optimize_database()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run optimization
    result = optimize_database_indexes()
    print(f"Optimization result: {result}")