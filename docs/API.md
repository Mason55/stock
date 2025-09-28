# API接口文档

## 基础信息

- **基础URL**: `http://localhost:8000`
- **数据格式**: JSON
- **认证方式**: 暂无 (后续可添加API Key)

## 接口列表

### 1. 系统健康检查

**接口地址**: `GET /api/stocks/health`

**描述**: 检查系统状态和各组件健康状况

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2025-09-28T11:15:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "data_sources": {
      "sina": "available",
      "eastmoney": "available"
    }
  },
  "performance": {
    "response_time_ms": 45.2,
    "cache_hit_rate": 0.85
  }
}
```

### 2. 股票分析

**接口地址**: `GET /api/stocks/{stock_code}/analysis`

**描述**: 获取指定股票的综合分析结果

**路径参数**:
- `stock_code` (string, required): 股票代码，格式如 `000001.SZ` 或 `600036.SH`

**查询参数**:
- `analysis_type` (string, optional): 分析类型
  - `technical`: 技术分析
  - `fundamental`: 基本面分析  
  - `sentiment`: 情绪分析
  - `all`: 全部分析 (默认)
- `period` (string, optional): 分析周期
  - `1d`: 日线 (默认)
  - `1w`: 周线
  - `1m`: 月线
- `indicators` (string, optional): 指定技术指标，用逗号分隔
  - 例: `rsi,macd,kdj`

**请求示例**:
```bash
GET /api/stocks/000001.SZ/analysis?analysis_type=all&period=1d
```

**响应示例**:
```json
{
  "stock_code": "000001.SZ",
  "company_name": "平安银行",
  "current_price": 12.34,
  "price_change": 0.25,
  "price_change_percent": 2.07,
  "market_cap": 239800000000,
  "analysis_timestamp": "2025-09-28T11:15:00Z",
  
  "technical_analysis": {
    "overall_trend": "bullish",
    "trend_strength": 0.75,
    "support_levels": [11.80, 12.00],
    "resistance_levels": [12.80, 13.20],
    "indicators": {
      "ma": {
        "ma5": 12.15,
        "ma10": 11.95,
        "ma20": 11.70,
        "ma60": 11.20
      },
      "rsi": {
        "value": 65.2,
        "signal": "overbought_warning"
      },
      "macd": {
        "macd": 0.12,
        "signal": 0.08,
        "histogram": 0.04,
        "trend": "bullish"
      },
      "kdj": {
        "k": 80.1,
        "d": 75.3,
        "j": 89.7,
        "signal": "overbought"
      },
      "bollinger_bands": {
        "upper": 12.80,
        "middle": 12.20,
        "lower": 11.60,
        "position": "upper_zone"
      }
    }
  },
  
  "fundamental_analysis": {
    "valuation": {
      "pe_ratio": 5.8,
      "pb_ratio": 0.9,
      "ps_ratio": 2.1,
      "peg_ratio": 0.8
    },
    "profitability": {
      "roe": 0.122,
      "roa": 0.015,
      "net_margin": 0.32,
      "gross_margin": 0.68
    },
    "growth": {
      "revenue_growth": 0.08,
      "profit_growth": 0.12,
      "eps_growth": 0.15
    },
    "financial_health": {
      "debt_ratio": 0.85,
      "current_ratio": 1.2,
      "quick_ratio": 1.1,
      "cash_ratio": 0.8
    }
  },
  
  "sentiment_analysis": {
    "overall_sentiment": 0.6,
    "sentiment_level": "positive",
    "news_sentiment": {
      "score": 0.65,
      "article_count": 15,
      "keywords": ["业绩", "增长", "银行"]
    },
    "social_sentiment": {
      "score": 0.55,
      "mention_count": 1250,
      "platforms": ["weibo", "guba", "xueqiu"]
    },
    "analyst_sentiment": {
      "buy_count": 8,
      "hold_count": 3,
      "sell_count": 1,
      "average_rating": "买入"
    }
  },
  
  "recommendation": {
    "action": "买入",
    "confidence": 0.82,
    "score": 8.2,
    "risk_level": "中等",
    "target_price": 13.50,
    "stop_loss": 11.50,
    "holding_period": "3-6个月",
    "reasons": [
      "技术指标显示上涨趋势",
      "基本面估值合理",
      "市场情绪积极"
    ]
  }
}
```

### 3. 批量分析

**接口地址**: `POST /api/stocks/batch_analysis`

**描述**: 批量分析多只股票

**请求体**:
```json
{
  "stock_codes": ["000001.SZ", "600036.SH", "000002.SZ"],
  "analysis_types": ["technical", "fundamental"],
  "period": "1d"
}
```

**响应示例**:
```json
{
  "batch_id": "batch_20250928_111500",
  "total_stocks": 3,
  "completed": 3,
  "failed": 0,
  "results": [
    {
      "stock_code": "000001.SZ",
      "status": "success",
      "analysis": {
        // 完整分析结果
      }
    }
    // ... 其他股票结果
  ],
  "summary": {
    "bullish_count": 2,
    "bearish_count": 1,
    "neutral_count": 0,
    "average_score": 7.5
  }
}
```

### 4. 历史数据

**接口地址**: `GET /api/stocks/{stock_code}/history`

**描述**: 获取股票历史价格数据

**查询参数**:
- `period` (string, optional): 时间周期，默认 `1d`
- `start_date` (string, optional): 开始日期，格式 `YYYY-MM-DD`
- `end_date` (string, optional): 结束日期，格式 `YYYY-MM-DD`
- `limit` (integer, optional): 数据条数限制，默认 100

**响应示例**:
```json
{
  "stock_code": "000001.SZ",
  "period": "1d",
  "data_count": 100,
  "data": [
    {
      "date": "2025-09-28",
      "open": 12.10,
      "high": 12.45,
      "low": 12.05,
      "close": 12.34,
      "volume": 15680000,
      "turnover": 193420000
    }
    // ... 更多历史数据
  ]
}
```

### 5. 实时行情

**接口地址**: `GET /api/stocks/{stock_code}/realtime`

**描述**: 获取股票实时行情数据

**响应示例**:
```json
{
  "stock_code": "000001.SZ",
  "company_name": "平安银行",
  "current_price": 12.34,
  "price_change": 0.25,
  "price_change_percent": 2.07,
  "volume": 15680000,
  "turnover": 193420000,
  "market_cap": 239800000000,
  "pe_ratio": 5.8,
  "timestamp": "2025-09-28T11:15:00Z",
  "market_status": "open",
  "bid_ask": {
    "bid_price": 12.33,
    "bid_volume": 12000,
    "ask_price": 12.35,
    "ask_volume": 8000
  }
}
```

## 错误处理

### 错误响应格式
```json
{
  "error": "error_type",
  "message": "错误描述",
  "code": 400,
  "timestamp": "2025-09-28T11:15:00Z",
  "request_id": "req_123456789"
}
```

### 常见错误码

| 状态码 | 错误类型 | 描述 |
|--------|----------|------|
| 400 | invalid_stock_code | 股票代码格式错误 |
| 404 | stock_not_found | 股票不存在 |
| 429 | rate_limit_exceeded | 请求频率超限 |
| 500 | data_source_error | 数据源不可用 |
| 503 | service_unavailable | 服务暂不可用 |

### 错误示例
```json
{
  "error": "invalid_stock_code",
  "message": "股票代码格式错误，请使用 XXXXXX.SZ 或 XXXXXX.SH 格式",
  "code": 400,
  "timestamp": "2025-09-28T11:15:00Z",
  "request_id": "req_123456789"
}
```

## 限流说明

- **频率限制**: 每分钟最多 60 次请求
- **并发限制**: 单IP最多 10 个并发连接
- **响应头**: 
  - `X-RateLimit-Limit`: 限制次数
  - `X-RateLimit-Remaining`: 剩余次数
  - `X-RateLimit-Reset`: 重置时间

## WebSocket接口 (实时推送)

**连接地址**: `ws://localhost:8000/ws/stocks/{stock_code}`

**消息格式**:
```json
{
  "type": "price_update",
  "stock_code": "000001.SZ",
  "data": {
    "price": 12.34,
    "change": 0.25,
    "volume": 15680000,
    "timestamp": "2025-09-28T11:15:00Z"
  }
}
```

## SDK使用示例

### Python
```python
import requests

class StockAPI:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def get_analysis(self, stock_code, analysis_type="all"):
        url = f"{self.base_url}/api/stocks/{stock_code}/analysis"
        params = {"analysis_type": analysis_type}
        response = requests.get(url, params=params)
        return response.json()

# 使用示例
api = StockAPI()
result = api.get_analysis("000001.SZ")
print(f"投资建议: {result['recommendation']['action']}")
```

### JavaScript
```javascript
class StockAPI {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
    }
    
    async getAnalysis(stockCode, analysisType = 'all') {
        const url = `${this.baseUrl}/api/stocks/${stockCode}/analysis`;
        const params = new URLSearchParams({ analysis_type: analysisType });
        const response = await fetch(`${url}?${params}`);
        return await response.json();
    }
}

// 使用示例
const api = new StockAPI();
api.getAnalysis('000001.SZ').then(result => {
    console.log('投资建议:', result.recommendation.action);
});
```