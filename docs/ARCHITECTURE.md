# 系统架构文档

## 架构概览

股票分析系统采用分层架构设计，具备高性能、高可用、易扩展的特点。系统主要分为数据层、业务逻辑层、API层和前端展示层。

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend Layer                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │   Web UI    │ │  Mobile App │ │    Third-party Tools    │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                        HTTP/WebSocket
                              │
┌─────────────────────────────────────────────────────────────┐
│                         API Layer                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │ RESTful API │ │ WebSocket   │ │     Rate Limiter        │ │
│  │             │ │ Real-time   │ │     Authentication      │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Business Layer                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │ Technical   │ │ Fundamental │ │     Sentiment           │ │
│  │ Analysis    │ │ Analysis    │ │     Analysis            │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │ Data        │ │ Analyzer    │ │  Recommendation         │ │
│  │ Collector   │ │ Factory     │ │  Engine                 │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                        Data Layer                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │  PostgreSQL │ │    Redis    │ │    External APIs        │ │
│  │  (Primary)  │ │  (Cache)    │ │  (Sina, Eastmoney...)   │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. API层 (src/api/)

#### RESTful API服务
- **主要文件**: `src/api/stock_api.py`
- **功能**: 提供HTTP接口，处理客户端请求
- **特性**: 
  - 支持CORS跨域
  - 请求日志记录
  - 错误处理和统一响应格式
  - API版本管理

```python
# API路由设计
GET  /api/stocks/health                    # 健康检查
GET  /api/stocks/{code}/analysis          # 股票分析
POST /api/stocks/batch_analysis           # 批量分析
GET  /api/stocks/{code}/history           # 历史数据
GET  /api/stocks/{code}/realtime          # 实时行情
```

#### 中间件系统 (src/middleware/)
- **限流器**: 基于Redis的分布式限流
- **缓存管理**: 多级缓存策略
- **参数验证**: 请求参数校验和清洗

### 2. 业务逻辑层 (src/core/)

#### 分析器工厂模式
```python
# src/core/analyzer_factory.py
class AnalyzerFactory:
    @staticmethod
    def create_analyzer(analyzer_type: str):
        if analyzer_type == 'technical':
            return TechnicalAnalyzer()
        elif analyzer_type == 'fundamental':
            return FundamentalAnalyzer()
        # ... 其他分析器
```

#### 技术分析模块
- **移动平均线**: MA, EMA, SMA
- **动量指标**: RSI, KDJ, Williams %R
- **趋势指标**: MACD, 布林带
- **成交量指标**: OBV, 成交量移动平均

#### 基本面分析模块
- **估值指标**: PE, PB, PS, PEG
- **盈利能力**: ROE, ROA, 净利润率
- **财务健康**: 负债率, 流动比率
- **成长性**: 营收增长率, 利润增长率

#### 情绪分析模块
- **新闻情绪**: NLP文本分析
- **社交媒体**: 微博、股吧情绪监控
- **分析师观点**: 券商研报评级

### 3. 数据层

#### 数据源管理 (src/core/data_sources.py)
```python
class DataSourceManager:
    def __init__(self):
        self.sources = {
            'sina': SinaDataSource(),
            'eastmoney': EastmoneyDataSource(),
            'tencent': TencentDataSource(),
            'ths': THSDataSource()
        }
    
    async def fetch_with_fallback(self, symbol: str):
        for source_name, source in self.sources.items():
            try:
                return await source.fetch(symbol)
            except Exception as e:
                logger.warning(f"{source_name} failed: {e}")
        raise DataSourceError("All data sources failed")
```

#### 缓存策略
- **L1缓存**: 内存缓存 (30秒TTL)
- **L2缓存**: Redis缓存 (5分钟TTL)
- **L3缓存**: 数据库缓存 (1小时TTL)

#### 数据库设计
```sql
-- 股票基础信息表
CREATE TABLE stocks (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) UNIQUE NOT NULL,
    company_name VARCHAR(100) NOT NULL,
    market VARCHAR(10) NOT NULL,
    industry VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 股票分析结果表
CREATE TABLE stock_analysis (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    analysis_date DATE NOT NULL,
    technical_score DECIMAL(3,2),
    fundamental_score DECIMAL(3,2),
    sentiment_score DECIMAL(3,2),
    overall_score DECIMAL(3,2),
    recommendation VARCHAR(20),
    analysis_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 股票价格历史表
CREATE TABLE stock_prices (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open_price DECIMAL(10,3),
    high_price DECIMAL(10,3),
    low_price DECIMAL(10,3),
    close_price DECIMAL(10,3),
    volume BIGINT,
    turnover DECIMAL(15,2),
    UNIQUE(stock_code, date)
);
```

## 数据流架构

### 实时数据流
```
External APIs → Data Collector → Cache → Business Logic → API Response
     │               │             │           │              │
     │               └─────────────┼───────────┼──────────────┘
     │                             │           │
     └─────────────────────────────┼───────────┼─→ Database
                                   │           │
                              Rate Limiter   Logger
```

### 分析处理流程
```python
async def analyze_stock(stock_code: str) -> AnalysisResult:
    # 1. 数据收集
    data = await data_collector.collect_all_data(stock_code)
    
    # 2. 并行分析
    tasks = [
        technical_analyzer.analyze(data),
        fundamental_analyzer.analyze(data),
        sentiment_analyzer.analyze(data)
    ]
    results = await asyncio.gather(*tasks)
    
    # 3. 综合评分
    final_score = recommendation_engine.calculate_score(results)
    
    # 4. 生成建议
    recommendation = recommendation_engine.generate_advice(final_score)
    
    return AnalysisResult(
        technical=results[0],
        fundamental=results[1],
        sentiment=results[2],
        recommendation=recommendation
    )
```

## 性能架构

### 异步处理
- **协程**: 使用 `asyncio` 处理I/O密集型操作
- **线程池**: CPU密集型计算使用 `ThreadPoolExecutor`
- **连接池**: 数据库和HTTP连接复用

### 缓存架构
```python
class CacheManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.memory_cache = {}
    
    async def get(self, key: str):
        # L1: 内存缓存
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # L2: Redis缓存
        value = await self.redis.get(key)
        if value:
            self.memory_cache[key] = value
            return value
        
        return None
```

### 限流机制
```python
class RateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, window)
        return current <= limit
```

## 扩展性设计

### 水平扩展
- **无状态设计**: API服务器无状态，支持负载均衡
- **数据库分片**: 按股票代码分片存储
- **缓存集群**: Redis集群模式

### 服务注册与发现
```yaml
# consul 配置示例
services:
  - name: stock-api
    id: stock-api-1
    port: 8000
    health_check:
      http: http://localhost:8000/api/stocks/health
      interval: 10s
```

### 消息队列
```python
# 异步任务处理
class TaskQueue:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def enqueue(self, task_type: str, params: dict):
        task = {
            'type': task_type,
            'params': params,
            'created_at': time.time()
        }
        await self.redis.lpush('task_queue', json.dumps(task))
    
    async def process_tasks(self):
        while True:
            task_data = await self.redis.brpop('task_queue', timeout=1)
            if task_data:
                await self.handle_task(json.loads(task_data[1]))
```

## 监控和可观测性

### 指标收集
```python
from prometheus_client import Counter, Histogram, Gauge

# 业务指标
api_requests = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
response_time = Histogram('response_time_seconds', 'Response time')
active_stocks = Gauge('active_stocks_total', 'Number of actively monitored stocks')

# 系统指标
class MetricsCollector:
    def __init__(self):
        self.response_time = Histogram('http_request_duration_seconds', 
                                     'HTTP request duration')
        self.request_count = Counter('http_requests_total',
                                   'Total HTTP requests',
                                   ['method', 'endpoint', 'status'])
```

### 分布式追踪
```python
import opentelemetry.trace as trace

tracer = trace.get_tracer(__name__)

async def analyze_stock_with_tracing(stock_code: str):
    with tracer.start_as_current_span("stock_analysis") as span:
        span.set_attribute("stock.code", stock_code)
        
        with tracer.start_as_current_span("data_collection"):
            data = await collect_data(stock_code)
        
        with tracer.start_as_current_span("analysis"):
            result = await analyze(data)
        
        span.set_attribute("analysis.score", result.score)
        return result
```

### 日志架构
```python
import structlog

logger = structlog.get_logger()

async def process_request(request):
    log = logger.bind(
        request_id=request.headers.get('X-Request-ID'),
        user_ip=request.remote_addr,
        stock_code=request.path_params.get('stock_code')
    )
    
    log.info("Processing stock analysis request")
    
    try:
        result = await analyze_stock(stock_code)
        log.info("Analysis completed", score=result.score)
        return result
    except Exception as e:
        log.error("Analysis failed", error=str(e))
        raise
```

## 安全架构

### 认证和授权
```python
class AuthMiddleware:
    def __init__(self):
        self.secret_key = os.getenv('JWT_SECRET_KEY')
    
    async def authenticate(self, token: str) -> Optional[User]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return User(id=payload['user_id'], role=payload['role'])
        except jwt.InvalidTokenError:
            return None
```

### 数据加密
- **传输加密**: TLS 1.3
- **存储加密**: 敏感数据AES-256加密
- **密钥管理**: AWS KMS / Azure Key Vault

### 输入验证
```python
from pydantic import BaseModel, validator

class AnalysisRequest(BaseModel):
    stock_code: str
    analysis_type: str = 'all'
    
    @validator('stock_code')
    def validate_stock_code(cls, v):
        if not re.match(r'^\d{6}\.(SZ|SH)$', v):
            raise ValueError('Invalid stock code format')
        return v
```

## 容灾和备份

### 数据备份策略
- **实时备份**: WAL日志流复制
- **定时备份**: 每日全量备份 + 增量备份
- **异地备份**: 跨地域数据同步

### 故障转移
```python
class FailoverManager:
    def __init__(self):
        self.primary_db = connect_primary()
        self.replica_db = connect_replica()
    
    async def execute_query(self, query: str):
        try:
            return await self.primary_db.execute(query)
        except DatabaseError:
            logger.warning("Primary database failed, switching to replica")
            return await self.replica_db.execute(query)
```

### 服务熔断
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpenError()
        
        try:
            result = await func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            
            raise e
```

## 部署架构

### 容器化部署
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY config/ config/

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "src.app:create_app()"]
```

### Kubernetes部署
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: stock-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: stock-api
  template:
    spec:
      containers:
      - name: stock-api
        image: stock-analysis:latest
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/stocks/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

## 总结

本系统架构具备以下特点：

1. **高性能**: 异步处理 + 多级缓存 + 连接池
2. **高可用**: 故障转移 + 熔断机制 + 健康检查
3. **可扩展**: 微服务 + 水平扩展 + 负载均衡
4. **可观测**: 指标监控 + 分布式追踪 + 结构化日志
5. **安全性**: 认证授权 + 数据加密 + 输入验证

通过合理的架构设计，系统能够稳定可靠地为用户提供股票分析服务。