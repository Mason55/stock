# 股票分析系统使用文档

## 概述

这是一个功能强大的股票分析系统，集成了技术分析、基本面分析和情绪分析等多种分析方法，支持A股市场的深度数据分析。

## 核心功能

### 🚀 多数据源集成
- **新浪财经**: 实时股价和成交量数据
- **东方财富**: 基本面财务数据
- **腾讯财经**: 补充数据源
- **同花顺**: 技术指标数据

### 📊 深度技术分析
支持20+专业技术指标：
- **趋势指标**: MA、EMA、MACD、布林带
- **动量指标**: RSI、KDJ、威廉指标、随机指标
- **成交量指标**: OBV、成交量移动平均
- **波动率指标**: ATR、布林带宽度

### 💼 基本面分析
- **估值分析**: PE、PB、PS、PEG比率
- **盈利能力**: ROE、ROA、净利润率
- **成长性**: 营收增长率、净利润增长率
- **财务健康**: 资产负债率、流动比率

### 😊 情绪分析
- **新闻情绪**: 基于新闻标题的情绪倾向
- **社交媒体**: 微博、股吧等平台情绪
- **分析师态度**: 券商研报推荐等级

### 🎯 智能投资建议
- 多维度综合评分系统
- 个性化风险等级评估
- 基于历史数据的预测模型

## 快速开始

### 环境要求
- Python 3.8+
- Redis (可选，用于缓存)
- SQLite/PostgreSQL

### 安装依赖
```bash
pip install -r requirements.txt
```

### 基本配置
1. 复制配置模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，配置数据库和Redis连接

### 运行方式

#### 1. API服务模式
```bash
python src/app.py
```
服务将在 `http://localhost:8000` 启动

#### 2. 命令行分析模式
```bash
# 分析单只股票
python -m src.services.jac_analyzer 000001.SZ

# 批量分析
python -m src.services.jac_analyzer 000001.SZ 000002.SZ 600036.SH
```

#### 3. 交互式Web界面
```bash
python demo_app.py
```
在浏览器访问 `http://localhost:5000`

## API接口文档

### 获取股票分析
```
GET /api/stocks/{stock_code}/analysis
```

**参数:**
- `stock_code`: 股票代码 (如: 000001.SZ, 600036.SH)
- `analysis_type`: 分析类型 [technical|fundamental|sentiment|all]

**响应示例:**
```json
{
  "stock_code": "000001.SZ",
  "company_name": "平安银行",
  "current_price": 12.34,
  "technical_analysis": {
    "trend": "upward",
    "strength": 0.75,
    "indicators": {
      "rsi": 65.2,
      "macd": "bullish",
      "kdj": {"k": 80.1, "d": 75.3, "j": 89.7}
    }
  },
  "fundamental_analysis": {
    "pe_ratio": 5.8,
    "pb_ratio": 0.9,
    "roe": 0.12,
    "debt_ratio": 0.85
  },
  "sentiment_analysis": {
    "overall_sentiment": "positive",
    "news_sentiment": 0.6,
    "social_sentiment": 0.4
  },
  "recommendation": {
    "action": "买入",
    "score": 8.2,
    "risk_level": "中等",
    "target_price": 13.50
  }
}
```

### 健康检查
```
GET /api/stocks/health
```

### 批量分析
```
POST /api/stocks/batch_analysis
Content-Type: application/json

{
  "stock_codes": ["000001.SZ", "600036.SH"],
  "analysis_types": ["technical", "fundamental"]
}
```

## 配置说明

### 环境变量配置 (.env)
```bash
# 数据库配置
DATABASE_URL=sqlite:///stock_analysis.db

# Redis配置 (可选)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# API配置
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# 数据源API密钥 (可选)
SINA_API_KEY=your_api_key
EASTMONEY_API_KEY=your_api_key
```

### 高级配置 (config/settings.py)
```python
# 缓存设置
CACHE_TTL = 300  # 5分钟

# 限流设置
RATE_LIMIT_PER_MINUTE = 60

# 数据更新频率
DATA_UPDATE_INTERVAL = 60  # 秒

# 技术指标参数
TECHNICAL_INDICATORS = {
    'ma_periods': [5, 10, 20, 60],
    'rsi_period': 14,
    'macd_params': (12, 26, 9)
}
```

## 使用示例

### Python SDK使用
```python
from src.core.analyzer_factory import AnalyzerFactory
from src.services.data_collector import DataCollector

# 初始化分析器
analyzer = AnalyzerFactory.create_analyzer('comprehensive')
data_collector = DataCollector()

# 获取股票数据
stock_data = data_collector.collect_stock_data('000001.SZ')

# 执行分析
result = analyzer.analyze(stock_data)

print(f"股票: {result['company_name']}")
print(f"当前价格: {result['current_price']}")
print(f"技术分析评分: {result['technical_score']}")
print(f"投资建议: {result['recommendation']['action']}")
```

### 命令行工具
```bash
# 查看帮助
python -m src.services.jac_analyzer --help

# 分析指定股票并保存结果
python -m src.services.jac_analyzer 000001.SZ --output analysis_result.json

# 生成图表
python -m src.services.jac_analyzer 000001.SZ --charts --output-dir ./charts/

# 实时监控模式
python -m src.services.jac_analyzer 000001.SZ --monitor --interval 60
```

## 性能优化

### 缓存策略
- **Redis缓存**: 股票基础数据缓存5分钟
- **内存缓存**: 计算结果缓存30秒
- **数据库**: 历史数据本地存储

### 并发处理
- **异步请求**: 使用aiohttp进行数据获取
- **线程池**: CPU密集型计算使用多线程
- **连接池**: 数据库连接复用

### 监控指标
- API响应时间 < 200ms
- 数据更新延迟 < 30s
- 缓存命中率 > 80%

## 故障排除

### 常见问题

**1. 数据获取失败**
```bash
# 检查网络连接
curl -I https://finance.sina.com.cn

# 检查API限制
tail -f logs/app.log | grep "rate_limit"
```

**2. Redis连接失败**
```bash
# 检查Redis服务
redis-cli ping

# 或禁用Redis
export REDIS_HOST=""
```

**3. 股票代码格式错误**
- 深交所: 000001.SZ
- 上交所: 600036.SH
- 创业板: 300001.SZ

### 日志分析
```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误日志
grep "ERROR" logs/app.log

# 性能分析
grep "Response-Time" logs/app.log | awk '{print $NF}' | sort -n
```

## 开发指南

### 项目结构
```
stock/
├── src/
│   ├── core/           # 核心分析模块
│   ├── api/            # API接口
│   ├── services/       # 业务服务
│   ├── models/         # 数据模型
│   ├── middleware/     # 中间件
│   └── utils/          # 工具类
├── config/             # 配置文件
├── tests/              # 测试用例
├── docs/               # 文档
└── frontend/           # 前端界面
```

### 添加新的技术指标
1. 在 `src/core/technical_analysis.py` 中添加计算函数
2. 在配置中注册新指标
3. 更新API文档

### 添加新的数据源
1. 在 `src/core/data_sources.py` 中实现数据源类
2. 注册到工厂类中
3. 添加相应的测试用例

## 许可证

MIT License - 详见 LICENSE 文件