# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.stock import Base
from src.app import create_app


@pytest.fixture(scope='session')
def test_db():
    """Create test database"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    """Create test Flask client"""
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_stock_data():
    """Sample stock data for testing"""
    return {
        'code': '000001.SZ',
        'name': '平安银行',
        'exchange': 'SZ',
        'industry': '银行'
    }