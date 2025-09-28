# src/database/session.py - Database session management
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from config.settings import settings
from src.models.stock import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, auto_init=True):
        self.engine = None
        self.Session = None
        self._initialized = False
        if auto_init:
            self._setup_database()
    
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
            
            logger.warning("Database initialized in fallback mode (SQLite in-memory)")
            
        except Exception as e:
            logger.error(f"Fallback database initialization failed: {e}")
            self._initialized = False
    
    def _on_connect(self, dbapi_connection, connection_record):
        """Called when a new database connection is created"""
        logger.debug("New database connection created")
    
    def _on_checkout(self, dbapi_connection, connection_record, connection_proxy):
        """Called when a connection is checked out from the pool"""
        logger.debug("Database connection checked out from pool")
    
    @contextmanager
    def get_session(self):
        """Get a database session with automatic cleanup"""
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
        return self.Session
    
    def health_check(self) -> bool:
        """Check database connection health"""
        if not self._initialized:
            return False
            
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def is_initialized(self) -> bool:
        """Check if database is initialized"""
        return self._initialized
    
    def is_fallback_mode(self) -> bool:
        """Check if running in fallback mode"""
        if not self._initialized:
            return False
        return "sqlite:///:memory:" in str(self.engine.url)
    
    def close(self):
        """Close database engine"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


def get_db_session():
    """Dependency function for getting database session"""
    return db_manager.get_session()


def get_session_factory():
    """Get session factory"""
    return db_manager.get_session_factory()