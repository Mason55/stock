#!/usr/bin/env python3
# scripts/create_indexes.py - Database index creation script
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from src.models.stock import Base
from config.settings import Settings

settings = Settings()
# 在开发环境中使用SQLite
DATABASE_URL = "sqlite:///stock_dev.db"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_database_indexes():
    """创建数据库索引"""
    
    try:
        # 创建数据库引擎
        engine = create_engine(DATABASE_URL)
        
        # 创建所有表（包含索引定义）
        Base.metadata.create_all(engine)
        logger.info("✅ All tables and indexes created successfully")
        
        # 创建额外的性能索引
        additional_indexes = [
            # StockPrice表的额外索引
            """
            CREATE INDEX IF NOT EXISTS idx_stock_prices_composite
            ON stock_prices(stock_code, timestamp DESC, close_price);
            """,
            
            # 分区索引（如果支持）
            """
            CREATE INDEX IF NOT EXISTS idx_stock_prices_recent
            ON stock_prices(timestamp DESC)
            WHERE timestamp > NOW() - INTERVAL '1 year';
            """,
            
            # 推荐表的复合索引
            """
            CREATE INDEX IF NOT EXISTS idx_recommendations_latest
            ON stock_recommendations(stock_code, confidence DESC, timestamp DESC);
            """,
            
            # 统计查询优化索引
            """
            CREATE INDEX IF NOT EXISTS idx_stock_prices_stats
            ON stock_prices(stock_code, volume, change_pct)
            WHERE volume > 0;
            """
        ]
        
        with engine.connect() as conn:
            for i, index_sql in enumerate(additional_indexes):
                try:
                    conn.execute(text(index_sql))
                    conn.commit()
                    logger.info(f"✅ Additional index {i+1} created successfully")
                except OperationalError as e:
                    if "already exists" in str(e).lower():
                        logger.info(f"⚠️ Additional index {i+1} already exists")
                    elif "syntax error" in str(e).lower():
                        logger.warning(f"⚠️ Index {i+1} skipped (PostgreSQL-specific syntax)")
                    else:
                        logger.error(f"❌ Failed to create additional index {i+1}: {e}")
                except Exception as e:
                    logger.error(f"❌ Unexpected error with index {i+1}: {e}")
        
        logger.info("🎉 Database index optimization completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database optimization failed: {e}")
        return False


def verify_indexes():
    """验证索引是否创建成功"""
    
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # 查询现有索引
            if engine.dialect.name == 'postgresql':
                indexes_query = """
                SELECT 
                    t.tablename,
                    i.indexname,
                    i.indexdef
                FROM pg_catalog.pg_indexes i
                JOIN pg_catalog.pg_tables t ON i.tablename = t.tablename
                WHERE t.schemaname = 'public'
                AND t.tablename IN ('stocks', 'stock_prices', 'stock_recommendations')
                ORDER BY t.tablename, i.indexname;
                """
            else:
                # SQLite
                indexes_query = """
                SELECT 
                    tbl_name as tablename,
                    name as indexname,
                    sql as indexdef
                FROM sqlite_master 
                WHERE type = 'index' 
                AND tbl_name IN ('stocks', 'stock_prices', 'stock_recommendations')
                AND sql IS NOT NULL
                ORDER BY tbl_name, name;
                """
            
            result = conn.execute(text(indexes_query))
            indexes = result.fetchall()
            
            logger.info("📋 Current Database Indexes:")
            current_table = None
            for row in indexes:
                if row.tablename != current_table:
                    current_table = row.tablename
                    logger.info(f"  📊 Table: {current_table}")
                
                logger.info(f"    ├── {row.indexname}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to verify indexes: {e}")
        return False


def main():
    """主函数"""
    
    logger.info("🚀 Starting database index optimization...")
    
    # 创建索引
    if create_database_indexes():
        logger.info("✅ Index creation completed")
    else:
        logger.error("❌ Index creation failed")
        return 1
    
    # 验证索引
    if verify_indexes():
        logger.info("✅ Index verification completed")
    else:
        logger.error("❌ Index verification failed")
        return 1
    
    logger.info("🎉 Database optimization successful!")
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)