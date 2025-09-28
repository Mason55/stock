# src/database/session.py - Database session management with lazy loading
import logging
from contextlib import contextmanager
from typing import Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from config.settings import settings
from src.models.stock import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, auto_init=False):
        self.engine = None
        self.Session = None
        self._initialized = False
        self._fallback_mode = False
        # Lazy initialization by default to improve portability
    
    def _setup_database(self):
        """Setup database engine with connection pool"""
        try:
            self.engine = create_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                pool_pre_ping=True,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_recycle=3600,
                pool_timeout=30
            )
            
            # Add connection event listeners
            event.listen(self.engine, 'connect', self._on_connect)
            event.listen(self.engine, 'checkout', self._on_checkout)
            
            # Create tables
            Base.metadata.create_all(self.engine)
            
            # Create session factory
            self.Session = sessionmaker(bind=self.engine)
            self._initialized = True
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
            # Initialize in degraded mode
            self._initialize_mock_mode()
    
    def _initialize_mock_mode(self):
        """Initialize in mock mode when database is unavailable"""
        try:
            # Use SQLite in-memory database as fallback
            fallback_url = "sqlite:///:memory:"
            logger.info(f"Initializing fallback database: {fallback_url}")
            
            self.engine = create_engine(
                fallback_url,
                echo=settings.DEBUG,
                pool_pre_ping=True
            )
            
            # Create tables in memory
            Base.metadata.create_all(self.engine)
            
            # Create session factory
            self.Session = sessionmaker(bind=self.engine)
            self._initialized = True
            self._fallback_mode = True
            
            logger.warning("Database initialized in fallback mode (SQLite in-memory)")
            
        except Exception as e:
            logger.error(f"Fallback database initialization failed: {e}")
            self._initialized = False
            self._fallback_mode = False
    
    def _on_connect(self, dbapi_connection, connection_record):
        """Called when a new database connection is created"""
        logger.debug("New database connection created")
    
    def _on_checkout(self, dbapi_connection, connection_record, connection_proxy):
        """Called when a connection is checked out from the pool"""
        logger.debug("Database connection checked out from pool")
    
    def ensure_initialized(self):
        """Ensure database is initialized (lazy loading)"""
        if not self._initialized:
            self._setup_database()
        return self._initialized
    
    @contextmanager
    def get_session(self):
        """Get a database session with automatic cleanup"""
        if not self.ensure_initialized():
            raise RuntimeError("Database not available")
            
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_session_factory(self):
        """Get session factory for dependency injection"""
        if not self.ensure_initialized():
            return None
        return self.Session
    
    def health_check(self) -> dict:
        """Check database connection health with detailed status"""
        # Try to initialize if not done yet
        initialized = self.ensure_initialized()
        
        if not initialized:
            return {
                'status': 'unavailable',
                'initialized': False,
                'fallback_mode': False,
                'error': 'Failed to initialize database'
            }
            
        try:
            with self.get_session() as session:
                from sqlalchemy import text
                session.execute(text("SELECT 1"))
            status = 'degraded' if self._fallback_mode else 'healthy'
            return {
                'status': status,
                'initialized': True,
                'fallback_mode': self._fallback_mode,
                'database_url': str(self.engine.url).split('@')[0] + '@***' if self.engine else None
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'initialized': True,
                'fallback_mode': self._fallback_mode,
                'error': str(e)
            }
    
    def is_initialized(self) -> bool:
        """Check if database is initialized"""
        return self._initialized
    
    def is_fallback_mode(self) -> bool:
        """Check if running in fallback mode"""
        return self._fallback_mode
    
    def close(self):
        """Close database engine"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")


# Global database manager instance (lazy initialization)
db_manager = DatabaseManager(auto_init=False)


def get_db_session():
    """Dependency function for getting database session"""
    return db_manager.get_session()


def get_session_factory():
    """Get session factory"""
    return db_manager.get_session_factory()


def init_database():
    """Explicitly initialize database (for app startup)"""
    return db_manager.ensure_initialized()