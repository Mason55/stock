# Developer Guide

## 🚀 Quick Start for Developers

### Prerequisites
```bash
# Python 3.8+
python --version

# Git
git --version
```

### Development Setup
```bash
# Clone repository
git clone <repo-url>
cd stock

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r build/requirements/dev.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Initialize database
python -c "from src.database import init_database; init_database()"

# Run tests
pytest tests/

# Start development server
python src/app.py
```

---

## 📁 Project Structure

```
stock/
├── src/                    # Source code
│   ├── api/               # REST API endpoints (Flask blueprints)
│   │   ├── stock_api.py          # Stock query endpoints
│   │   ├── indicators_api.py     # Technical indicators API
│   │   └── metrics.py            # Prometheus metrics endpoint
│   │
│   ├── backtest/          # Backtesting engine
│   │   ├── engine.py             # Event-driven backtest engine
│   │   ├── market_simulator.py  # Market rules and simulation
│   │   └── cost_model.py         # Trading costs calculation
│   │
│   ├── trading/           # Live trading framework
│   │   ├── engine.py             # Live trading engine
│   │   ├── broker_gateway.py    # Broker interface
│   │   ├── order_manager.py     # Order management
│   │   └── signal_executor.py   # Signal execution logic
│   │
│   ├── strategies/        # Strategy library
│   │   ├── base.py               # Base strategy class
│   │   ├── moving_average.py    # MA crossover strategy
│   │   ├── mean_reversion.py    # Mean reversion strategy
│   │   └── momentum.py          # Momentum strategy
│   │
│   ├── data_sources/      # Data providers
│   │   ├── data_source_manager.py  # Multi-source manager
│   │   ├── sina_finance.py         # Sina Finance provider
│   │   └── realtime_feed.py        # Real-time data feed
│   │
│   ├── database/          # Database layer
│   │   ├── __init__.py           # DB manager and initialization
│   │   └── session.py            # Session management
│   │
│   ├── models/            # Data models (SQLAlchemy ORM)
│   │   ├── trading.py            # Trading models (Order, Position)
│   │   ├── market_data.py        # Market data models
│   │   └── indicators.py         # Technical indicators models
│   │
│   ├── services/          # Business logic
│   │   ├── indicators_calculator.py  # Technical indicators
│   │   ├── etl_tasks.py             # ETL and cache warming
│   │   └── data_collector.py        # Data collection service
│   │
│   ├── monitoring/        # Observability
│   │   └── enhanced_metrics.py   # Prometheus metrics collector
│   │
│   ├── risk/              # Risk management
│   │   ├── real_time_monitor.py  # Real-time risk monitoring
│   │   └── position_sizer.py     # Position sizing algorithms
│   │
│   ├── middleware/        # Middleware components
│   │   ├── rate_limiter.py       # API rate limiting
│   │   ├── cache.py              # Caching layer
│   │   └── auth.py               # Authentication
│   │
│   ├── utils/             # Utilities
│   │   ├── logger.py             # Logging configuration
│   │   ├── di_container.py       # Dependency injection
│   │   └── error_handler.py      # Error handling
│   │
│   ├── app.py             # Flask application entry point
│   └── scheduler.py       # Background task scheduler
│
├── config/                # Configuration files
│   ├── settings.py               # Application settings
│   ├── stock_symbols.py          # Stock symbol lists
│   └── strategies.yaml           # Strategy configurations
│
├── tests/                 # Test suite (328 tests)
├── docs/                  # Documentation
├── examples/              # Example scripts
└── scripts/               # Build and deployment scripts
```

---

## 🏗️ Architecture Overview

### Dependency Injection Container

The system uses a centralized DI container for managing dependencies:

```python
# src/utils/di_container.py
from src.utils.di_container import get_container

container = get_container()
session_factory = container['session_factory']
cache_manager = container['cache_manager']
rate_limiter = container['rate_limiter']
```

### Database Layer

Uses SQLAlchemy 2.0 with automatic fallback:

```python
from src.database import get_session_factory, db_manager

# Get session
session_factory = get_session_factory()
with session_factory() as session:
    # Use session
    result = session.query(StockInfo).filter_by(symbol='600036.SH').first()
```

### Data Source Manager

Multi-provider with automatic fallback chain:

```python
from src.data_sources import DataSourceManager

manager = DataSourceManager()
# Tries: Tushare → Yahoo Finance → Sina Finance → Mock Data
data = await manager.get_historical_data('600036.SH', days=30)
```

---

## 💻 Development Workflows

### Adding a New API Endpoint

1. **Define endpoint in blueprint** (`src/api/stock_api.py`):

```python
from flask import Blueprint, request, jsonify

stock_bp = Blueprint('stocks', __name__, url_prefix='/api/stocks')

@stock_bp.route('/<stock_code>/my_analysis', methods=['GET'])
def get_my_analysis(stock_code):
    """Custom analysis endpoint"""
    # Validate input
    if not validate_stock_code(stock_code):
        return jsonify({'error': 'Invalid stock code'}), 400

    # Business logic
    result = perform_analysis(stock_code)

    return jsonify({
        'symbol': stock_code,
        'analysis': result,
        'timestamp': datetime.now().isoformat()
    })
```

2. **Add tests** (`tests/test_api.py`):

```python
def test_my_analysis_endpoint(client):
    response = client.get('/api/stocks/600036.SH/my_analysis')
    assert response.status_code == 200
    data = response.get_json()
    assert 'analysis' in data
```

3. **Register blueprint** (already done in `src/app.py`):

```python
app.register_blueprint(stock_bp)
```

### Creating a New Strategy

1. **Extend base strategy** (`src/strategies/my_strategy.py`):

```python
# src/strategies/my_strategy.py
from src.strategies.base import Strategy
from src.backtest.engine import MarketDataEvent, SignalEvent

class MyStrategy(Strategy):
    """Custom trading strategy"""

    def __init__(self, name="my_strategy", param1=10, param2=0.5):
        super().__init__(name)
        self.param1 = param1
        self.param2 = param2
        self.data_buffer = {}

    async def handle_market_data(self, event: MarketDataEvent):
        """Process market data and generate signals"""
        symbol = event.symbol
        price = event.price_data.get('close', 0)

        # Initialize buffer
        if symbol not in self.data_buffer:
            self.data_buffer[symbol] = []

        # Update buffer
        self.data_buffer[symbol].append(price)

        # Keep only recent data
        if len(self.data_buffer[symbol]) > self.param1:
            self.data_buffer[symbol].pop(0)

        # Generate signal based on custom logic
        if len(self.data_buffer[symbol]) >= self.param1:
            avg_price = sum(self.data_buffer[symbol]) / len(self.data_buffer[symbol])

            if price > avg_price * (1 + self.param2):
                return self.generate_signal(symbol, "BUY", 0.8)
            elif price < avg_price * (1 - self.param2):
                return self.generate_signal(symbol, "SELL", 0.8)

    def get_indicators(self):
        """Return calculated indicators"""
        return {
            'param1': self.param1,
            'param2': self.param2,
            'buffer_size': len(self.data_buffer)
        }
```

2. **Add configuration** (`config/strategies.yaml`):

```yaml
strategies:
  my_strategy:
    class: src.strategies.my_strategy.MyStrategy
    params:
      param1: 10
      param2: 0.5
    enabled: true
    description: "My custom strategy"
```

3. **Add tests** (`tests/test_strategies.py`):

```python
class TestMyStrategy:
    @pytest.fixture
    def strategy(self):
        return MyStrategy("test_strategy", param1=5, param2=0.3)

    @pytest.mark.asyncio
    async def test_buy_signal(self, strategy):
        # Send market data
        for price in [10.0, 10.5, 11.0, 11.5, 15.0]:
            event = MarketDataEvent(
                timestamp=datetime.now(),
                symbol="600036.SH",
                price_data={'close': price}
            )
            await strategy.handle_market_data(event)

        # Should generate BUY signal
        assert len(strategy.signals) > 0
        assert strategy.signals[-1].signal_type == "BUY"
```

4. **Backtest your strategy**:

```bash
python examples/backtest_strategies.py \
  --strategy my_strategy \
  --symbol 600036.SH \
  --days 90
```

### Adding a Database Model

1. **Define model** (`src/models/my_model.py`):

```python
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MyModel(Base):
    __tablename__ = 'my_table'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    value = Column(Float)
    timestamp = Column(DateTime, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'value': self.value,
            'timestamp': self.timestamp.isoformat()
        }
```

2. **Create migration**:

```bash
# Create SQL migration file
cat > scripts/create_my_table.sql << EOF
CREATE TABLE IF NOT EXISTS my_table (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    value FLOAT,
    timestamp TIMESTAMP NOT NULL
);

CREATE INDEX idx_my_table_symbol ON my_table(symbol);
CREATE INDEX idx_my_table_timestamp ON my_table(timestamp);
EOF
```

3. **Run migration**:

```bash
# PostgreSQL
psql -U your_user -d stock_db -f scripts/create_my_table.sql

# SQLite
sqlite3 stock_dev.db < scripts/create_my_table.sql

# Or use SQLAlchemy
python -c "from src.models.my_model import Base; \
from src.database import db_manager; \
Base.metadata.create_all(db_manager.engine)"
```

---

## 🧪 Testing Guide

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_backtest_engine.py

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test class
pytest tests/test_strategies.py::TestMovingAverageCrossover

# Run with verbose output
pytest tests/ -v

# Run only failed tests
pytest tests/ --lf

# Run async tests
pytest tests/test_live_trading.py -v
```

### Writing Tests

```python
# tests/test_my_feature.py
import pytest
from datetime import datetime

class TestMyFeature:
    @pytest.fixture
    def setup_data(self):
        """Setup test data"""
        return {'symbol': '600036.SH', 'price': 42.0}

    def test_basic_functionality(self, setup_data):
        """Test basic functionality"""
        result = my_function(setup_data['symbol'])
        assert result is not None
        assert result['price'] > 0

    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test async function"""
        result = await my_async_function('600036.SH')
        assert result is not None

    def test_error_handling(self):
        """Test error handling"""
        with pytest.raises(ValueError):
            my_function('INVALID_CODE')
```

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── test_api.py             # API endpoint tests
├── test_backtest_engine.py # Backtest engine tests
├── test_strategies.py      # Strategy tests
└── test_*.py               # Other test modules
```

---

## 📊 Monitoring and Debugging

### Logging

```python
from src.utils.logger import setup_logger

logger = setup_logger('my_module', 'my_module.log')

logger.debug('Debug message')
logger.info('Info message')
logger.warning('Warning message')
logger.error('Error message')
logger.exception('Exception with traceback')
```

### Prometheus Metrics

```python
from src.monitoring.enhanced_metrics import metrics_collector, track_analysis

# Context manager
with track_analysis('technical'):
    result = analyze_stock('600036.SH')

# Manual recording
metrics_collector.record_stock_analysis(
    analysis_type='technical',
    duration=0.25,
    success=True
)

# Custom metrics
from prometheus_client import Counter, Histogram

my_counter = Counter('my_operation_total', 'Description')
my_counter.inc()

my_histogram = Histogram('my_duration_seconds', 'Description')
my_histogram.observe(0.5)
```

### Debugging Tips

```bash
# Run with debug mode
DEBUG=true python src/app.py

# Use ipdb for interactive debugging
pip install ipdb
# Add in code: import ipdb; ipdb.set_trace()

# Profile performance
pip install py-spy
py-spy record -o profile.svg -- python src/app.py

# Memory profiling
pip install memory-profiler
python -m memory_profiler src/app.py
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/stock_db
# Or SQLite: DATABASE_URL=sqlite:///stock_dev.db

# Redis (optional)
USE_REDIS=true
REDIS_HOST=localhost
REDIS_PORT=6379

# API Settings
API_HOST=0.0.0.0
API_PORT=5000
DEBUG=false

# Data Sources
OFFLINE_MODE=false
TUSHARE_TOKEN=your_token_here

# Monitoring
ENABLE_ETL_SCHEDULER=true
ETL_LOOKBACK_DAYS=90
CACHE_WARMING_ENABLED=true

# Logging
LOG_LEVEL=INFO
LOG_TO_FILE=true
```

### Settings Module

```python
# config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///stock_dev.db"
    USE_REDIS: bool = False
    DEBUG: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 📦 Dependency Management

### Installing Dependencies

```bash
# Minimal (API only)
pip install -e ".[minimal]"

# Base (API + PostgreSQL + Redis)
pip install -e ".[base]"

# Development (includes testing tools)
pip install -e ".[dev]"

# Production (includes ML and monitoring)
pip install -e ".[production]"
```

### Adding New Dependencies

1. Update `pyproject.toml`:

```toml
[project.optional-dependencies]
base = [
    "stock-analysis-system[minimal]",
    "new-package==1.0.0"
]
```

2. Regenerate requirements:

```bash
pip-compile pyproject.toml -o requirements.txt
```

---

## 🚢 Deployment

### Docker Build

```bash
# Build image
docker build -t stock-analysis:latest .

# Run container
docker run -d \
  -p 5000:5000 \
  -e DATABASE_URL=postgresql://... \
  -e USE_REDIS=true \
  stock-analysis:latest
```

### Production Checklist

- [ ] Set `DEBUG=false`
- [ ] Configure PostgreSQL database
- [ ] Set up Redis for caching
- [ ] Configure environment variables
- [ ] Set up Prometheus monitoring
- [ ] Configure log rotation
- [ ] Set up SSL/TLS
- [ ] Configure firewall rules
- [ ] Set up backup strategy
- [ ] Test disaster recovery

---

## 🤝 Contributing Guidelines

### Code Style

```bash
# Format code
black src/ tests/ --line-length 100

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Commit Messages

```
feat: add new strategy for grid trading
fix: resolve position calculation error in backtest
docs: update developer guide with testing section
refactor: simplify data source manager
test: add tests for new API endpoint
chore: update dependencies
```

### Pull Request Process

1. Fork repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Write code and tests
4. Run test suite: `pytest tests/`
5. Format code: `black src/ tests/`
6. Commit changes: `git commit -m "feat: add my feature"`
7. Push to branch: `git push origin feature/my-feature`
8. Create Pull Request

### Code Review Checklist

- [ ] Tests pass locally
- [ ] Code is formatted (black, isort)
- [ ] No linting errors (flake8)
- [ ] Documentation updated
- [ ] Test coverage maintained (>95%)
- [ ] No security vulnerabilities
- [ ] Performance acceptable

---

## 📚 Additional Resources

- [Architecture Documentation](ARCHITECTURE.md)
- [API Reference](API.md)
- [Strategy Guide](../STRATEGY_GUIDE.md)
- [Live Trading Documentation](../LIVE_TRADING_IMPLEMENTATION.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)

---

## 🆘 Getting Help

### Common Issues

**Database connection error**
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Fallback to SQLite
export DATABASE_URL=sqlite:///stock_dev.db
```

**Redis connection error**
```bash
# Disable Redis
export USE_REDIS=false
```

**Import errors**
```bash
# Reinstall in development mode
pip install -e .
```

### Support Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community support
- **Documentation**: Check docs/ directory first

---

**Last Updated**: 2025-10-09
**Version**: 1.0.0
