# 股票量化系统改进计划 v2.1

**制定日期**: 2025-11-18
**目标版本**: v2.1.0
**预计完成**: 2025-12-15 (4周)

---

## 📋 改进概览

本次改进聚焦于以下几个方面：
1. **ETF专项分析** - 新增ETF特定的分析功能
2. **数据持久化** - 解决数据缓存和限流问题
3. **可视化增强** - 添加图表和仪表板
4. **风控优化** - 动态止损和风险监控
5. **代码质量** - 异常处理和测试覆盖

---

## 🎯 第一阶段: 基础设施完善 (Week 1)

### 任务1.1: 持久化缓存系统 ⭐⭐⭐
**优先级**: 🔥 最高
**预计时间**: 1天
**负责模块**: `src/cache/persistent_cache.py`

#### 目标
解决数据重复爬取和限流问题，提升系统性能

#### 实现内容
```python
# src/cache/persistent_cache.py
class PersistentCacheManager:
    """SQLite-based persistent cache for crawled data"""

    def __init__(self, db_path: str = "cache.db"):
        """Initialize persistent cache with SQLite backend"""
        pass

    def get(self, key: str, max_age: int = 3600) -> Optional[Any]:
        """Get cached value if not expired"""
        pass

    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set cache value with TTL"""
        pass

    def invalidate(self, pattern: str = None):
        """Invalidate cache by pattern"""
        pass
```

#### 集成点
- `src/services/fundamental_provider.py` - 基本面数据缓存(24h)
- `src/services/sentiment_provider.py` - 情绪数据缓存(1h)
- `src/api/stock_api.py` - 历史数据缓存(6h)

#### 数据库结构
```sql
CREATE TABLE cache_store (
    cache_key TEXT PRIMARY KEY,
    cache_value TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    data_type TEXT,
    stock_code TEXT
);

CREATE INDEX idx_expires ON cache_store(expires_at);
CREATE INDEX idx_stock_code ON cache_store(stock_code);
```

#### 验收标准
- [x] 支持设置TTL
- [x] 自动清理过期数据
- [x] 支持按股票代码批量失效
- [x] 性能测试: 10000次读取 < 1秒

---

### 任务1.2: ETF专项分析模块 ⭐⭐⭐
**优先级**: 🔥 高
**预计时间**: 2天
**负责模块**: `src/services/etf_analyzer.py`

#### 目标
为ETF提供专业的分析维度，补充现有技术分析

#### 实现功能

##### 1. ETF基本信息
```python
def get_etf_info(self, etf_code: str) -> Dict:
    """获取ETF基本信息

    Returns:
        {
            'etf_code': '159920.SZ',
            'etf_name': '恒生ETF',
            'tracking_index': '恒生指数',
            'fund_company': '华夏基金',
            'establishment_date': '2012-08-09',
            'fund_size': 15.8,  # 亿元
            'management_fee': 0.006,  # 0.6%
            'tracking_error': 0.0023  # 年化跟踪误差
        }
    """
```

##### 2. 溢价率/折价率
```python
def get_premium_discount(self, etf_code: str) -> Dict:
    """计算ETF溢价率/折价率

    Returns:
        {
            'nav': 1.612,  # 单位净值
            'market_price': 1.610,  # 市场价格
            'premium_rate': -0.12,  # 折价0.12%
            'status': 'discount',  # discount/premium/fair
            'timestamp': '2025-11-18 15:00:00'
        }
    """
```

##### 3. 持仓分析
```python
def get_holdings(self, etf_code: str, top_n: int = 10) -> Dict:
    """获取ETF持仓构成

    Returns:
        {
            'update_date': '2025-10-31',
            'total_stocks': 50,
            'top_holdings': [
                {'stock_code': '00700.HK', 'stock_name': '腾讯控股', 'weight': 0.125},
                {'stock_code': '09988.HK', 'stock_name': '阿里巴巴', 'weight': 0.089},
                ...
            ],
            'sector_distribution': {
                '科技': 0.35,
                '金融': 0.25,
                '消费': 0.20,
                ...
            }
        }
    """
```

##### 4. 跟踪误差分析
```python
def get_tracking_performance(self, etf_code: str, days: int = 30) -> Dict:
    """分析ETF跟踪指数的效果

    Returns:
        {
            'tracking_error': 0.0023,  # 年化跟踪误差
            'correlation': 0.998,  # 与指数相关性
            'beta': 0.995,  # β系数
            'daily_deviation': 0.0012,  # 日均偏离度
            'max_deviation': 0.0089,  # 最大偏离
            'performance_chart': [  # 收益对比
                {'date': '2025-11-01', 'etf_return': 0.012, 'index_return': 0.013},
                ...
            ]
        }
    """
```

##### 5. 资金流向
```python
def get_fund_flow(self, etf_code: str, days: int = 5) -> Dict:
    """分析ETF资金流入流出

    Returns:
        {
            'net_inflow_5d': 125000000,  # 5日净流入(元)
            'net_inflow_20d': 450000000,  # 20日净流入
            'daily_flow': [
                {'date': '2025-11-18', 'inflow': 50000000, 'outflow': 30000000},
                ...
            ],
            'trend': 'inflow'  # inflow/outflow/neutral
        }
    """
```

#### 数据源
- 天天基金网 (http://fund.eastmoney.com/)
- 集思录 ETF (https://www.jisilu.cn/data/etf/)
- Tushare Pro (fund_portfolio, fund_nav)

#### 集成到analyze_stock.py
```python
# 新增 --type etf 参数
if is_etf(stock_code):
    etf_analyzer = ETFAnalyzer()
    etf_info = etf_analyzer.get_etf_info(stock_code)
    premium = etf_analyzer.get_premium_discount(stock_code)
    holdings = etf_analyzer.get_holdings(stock_code)
    # 展示ETF专项分析
```

#### 验收标准
- [x] 支持主流ETF (股票ETF、债券ETF、跨境ETF)
- [x] 溢价率计算准确(与天天基金对比误差<0.1%)
- [x] 持仓数据完整(top 10持仓)
- [x] 集成到API和CLI工具

---

### 任务1.3: 异常处理改进 ⭐⭐
**优先级**: 🔶 中
**预计时间**: 1天
**影响范围**: 全局

#### 目标
提升系统稳定性和可维护性

#### 改进点

##### 1. 分类异常处理
```python
# src/utils/exceptions.py (新增)
class DataSourceError(Exception):
    """数据源相关错误"""
    pass

class RateLimitError(DataSourceError):
    """限流错误"""
    def __init__(self, source: str, retry_after: int = None):
        self.source = source
        self.retry_after = retry_after

class DataNotFoundError(DataSourceError):
    """数据不存在"""
    pass

class ValidationError(Exception):
    """数据验证错误"""
    pass
```

##### 2. 重试装饰器
```python
# src/utils/retry.py (新增)
def retry_on_rate_limit(max_retries=3, backoff=2.0):
    """遇到限流自动重试"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except RateLimitError as e:
                    if i == max_retries - 1:
                        raise
                    wait_time = backoff ** i
                    logger.warning(f"Rate limited, retry in {wait_time}s")
                    time.sleep(wait_time)
        return wrapper
    return decorator
```

##### 3. 改进位置
- `src/services/fundamental_provider.py:78-100` - Sina financial fetch
- `src/services/sentiment_provider.py:329-399` - Guba crawler
- `src/api/stock_api.py:91-140` - Sina realtime fetch

#### 验收标准
- [x] 所有外部API调用有异常处理
- [x] 限流错误自动重试
- [x] 日志记录完整(包含调用栈)

---

## 🎨 第二阶段: 可视化增强 (Week 2)

### 任务2.1: K线图表生成 ⭐⭐⭐
**优先级**: 🔥 高
**预计时间**: 1天
**负责模块**: `src/visualization/chart_generator.py`

#### 目标
为股票分析生成专业的技术分析图表

#### 实现功能

##### 1. K线图 + 指标
```python
def generate_stock_chart(
    stock_code: str,
    df: pd.DataFrame,
    indicators: Dict = None,
    save_path: str = None
) -> str:
    """生成K线图

    Args:
        df: 包含OHLCV的DataFrame
        indicators: {'ma5': [...], 'ma20': [...], 'rsi': [...]}

    Returns:
        图表文件路径
    """
```

**图表内容**:
- 主图: K线 + MA5/MA20/MA60
- 副图1: MACD
- 副图2: RSI
- 成交量柱状图

##### 2. 回测报告图表
```python
def generate_backtest_report(
    equity_curve: List,
    trades: List,
    metrics: Dict,
    save_path: str = None
) -> str:
    """生成回测可视化报告

    包含:
    - 资金曲线
    - 回撤曲线
    - 月度收益热力图
    - 交易分布
    """
```

##### 3. 组合对比图
```python
def generate_comparison_chart(
    results: Dict[str, Dict],
    save_path: str = None
) -> str:
    """生成策略/股票对比图"""
```

#### 技术选型
```python
import mplfinance as mpf
import matplotlib.pyplot as plt
import seaborn as sns
```

#### 集成点
```python
# analyze_stock.py 新增 --chart 参数
python analyze_stock.py 159920.SZ --chart

# 生成图表保存到 reports/159920_SZ_20251118.png
```

#### 验收标准
- [x] 支持中文显示
- [x] 图表清晰美观(300 DPI)
- [x] 可配置颜色主题(涨红跌绿 / 涨绿跌红)
- [x] 支持多种输出格式(PNG/SVG/PDF)

---

### 任务2.2: Web仪表板(可选) ⭐⭐
**优先级**: 🔶 中
**预计时间**: 2天
**技术栈**: Streamlit

#### 功能页面

##### 1. 股票分析页
- 输入股票代码
- 展示实时行情
- 技术指标图表
- 基本面数据表格
- 情绪分析雷达图

##### 2. 回测页
- 选择策略和股票
- 设置回测参数
- 运行回测并展示结果
- 下载回测报告

##### 3. 监控页
- 监控列表
- 价格预警
- 持仓监控

#### 快速启动
```bash
pip install streamlit plotly
streamlit run src/web/app.py
```

#### 验收标准
- [x] 响应式布局
- [x] 实时数据更新
- [x] 交互式图表
- [x] 支持导出数据

---

## 🛡️ 第三阶段: 风控优化 (Week 3)

### 任务3.1: 动态止损机制 ⭐⭐⭐
**优先级**: 🔥 高
**预计时间**: 2天
**负责模块**: `src/risk/dynamic_stop_loss.py`

#### 实现策略

##### 1. ATR追踪止损
```python
class ATRTrailingStop:
    """基于ATR的移动止损

    止损价 = 最高价 - ATR * multiplier
    """
    def __init__(self, atr_period: int = 14, multiplier: float = 2.0):
        pass

    def calculate_stop_price(
        self,
        entry_price: float,
        current_price: float,
        df: pd.DataFrame
    ) -> float:
        """计算当前止损价"""
        pass
```

##### 2. 百分比追踪止损
```python
class PercentageTrailingStop:
    """固定百分比追踪止损

    当浮盈超过trigger_pct时激活，回撤trailing_pct时止损
    """
    def __init__(self, trigger_pct: float = 0.1, trailing_pct: float = 0.05):
        pass
```

##### 3. 时间止损
```python
class TimeBasedStop:
    """时间止损

    持仓超过N天未达盈利目标则平仓
    """
    def __init__(self, max_holding_days: int = 30):
        pass
```

##### 4. 支撑位止损
```python
class SupportLevelStop:
    """基于支撑位的止损

    跌破关键支撑位时止损
    """
    def __init__(self, lookback_period: int = 20):
        pass
```

#### 集成到Portfolio
```python
# src/backtest/portfolio.py
class Portfolio:
    def __init__(self, ..., stop_loss_strategy: StopLossStrategy = None):
        self.stop_loss = stop_loss_strategy or ATRTrailingStop()

    def check_stop_loss(self, symbol: str) -> bool:
        """检查是否触发止损"""
        pass
```

#### 验收标准
- [x] 4种止损策略可配置
- [x] 回测中自动触发止损
- [x] 止损日志完整记录
- [x] 与现有系统无缝集成

---

### 任务3.2: 风险监控模块 ⭐⭐
**优先级**: 🔶 中
**预计时间**: 2天
**负责模块**: `src/risk/risk_monitor.py`

#### 监控指标

##### 1. VaR (风险价值)
```python
def calculate_var(
    portfolio_value: float,
    returns: List[float],
    confidence_level: float = 0.95,
    method: str = 'historical'  # historical/parametric/monte_carlo
) -> float:
    """计算投资组合的VaR

    Returns:
        在95%置信水平下，未来1天最大可能损失
    """
```

##### 2. 相关性检查
```python
def check_concentration_risk(
    holdings: Dict[str, float],  # {stock_code: weight}
    correlation_matrix: pd.DataFrame,
    max_correlation: float = 0.7
) -> Dict:
    """检查持仓相关性风险

    Returns:
        {
            'high_correlation_pairs': [('600036.SH', '600519.SH', 0.85)],
            'concentration_score': 0.65,  # 0-1，越高越集中
            'warnings': [...]
        }
    """
```

##### 3. 杠杆监控
```python
def calculate_leverage(
    total_position_value: float,
    account_equity: float
) -> Dict:
    """计算当前杠杆率

    Returns:
        {
            'leverage_ratio': 1.5,
            'margin_usage': 0.75,
            'available_margin': 250000,
            'status': 'normal'  # normal/warning/danger
        }
    """
```

##### 4. 异常检测
```python
def detect_anomaly(
    stock_code: str,
    current_price: float,
    volume: int,
    df: pd.DataFrame
) -> Dict:
    """检测价格/成交量异常

    Returns:
        {
            'price_anomaly': False,
            'volume_anomaly': True,
            'z_score_price': 1.2,
            'z_score_volume': 3.5,
            'alert_level': 'medium'
        }
    """
```

#### 实时监控
```python
# examples/risk_monitor.py (新建)
from src.risk.risk_monitor import RiskMonitor

monitor = RiskMonitor()
monitor.add_position('600036.SH', quantity=1000, entry_price=45.5)
monitor.add_position('000977.SZ', quantity=500, entry_price=75.0)

# 实时监控
while True:
    alerts = monitor.check_all_risks()
    if alerts:
        for alert in alerts:
            print(f"⚠️ {alert['level']}: {alert['message']}")
    time.sleep(60)
```

#### 验收标准
- [x] 支持多种风险指标
- [x] 实时异常检测
- [x] 可配置预警阈值
- [x] 生成风险报告

---

## 🚀 第四阶段: 高级功能 (Week 4)

### 任务4.1: 多资产组合优化 ⭐⭐
**优先级**: 🔶 中
**预计时间**: 3天
**负责模块**: `src/portfolio/optimizer.py`

#### 实现算法

##### 1. 马科维茨均值-方差优化
```python
def markowitz_optimization(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_aversion: float = 1.0,
    constraints: Dict = None
) -> Dict:
    """马科维茨优化

    Returns:
        {
            'weights': {'600036.SH': 0.3, '000977.SZ': 0.7},
            'expected_return': 0.15,
            'expected_risk': 0.12,
            'sharpe_ratio': 1.25
        }
    """
```

##### 2. 风险平价
```python
def risk_parity(
    cov_matrix: pd.DataFrame,
    target_risk: float = None
) -> Dict:
    """风险平价组合

    每个资产贡献相同的风险
    """
```

##### 3. 最大夏普比率
```python
def max_sharpe_portfolio(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float = 0.03
) -> Dict:
    """最大化夏普比率的组合"""
```

##### 4. 最小波动率
```python
def min_volatility_portfolio(
    cov_matrix: pd.DataFrame,
    constraints: Dict = None
) -> Dict:
    """最小化波动率的组合"""
```

#### 使用示例
```python
# examples/portfolio_optimization.py (新建)
from src.portfolio.optimizer import PortfolioOptimizer

stocks = ['600036.SH', '000977.SZ', '600519.SH', '000858.SZ']
optimizer = PortfolioOptimizer(stocks, lookback_days=120)

# 最大夏普比率组合
result = optimizer.optimize(method='max_sharpe')
print(f"Optimal weights: {result['weights']}")
print(f"Expected return: {result['expected_return']:.2%}")
print(f"Expected risk: {result['expected_risk']:.2%}")

# 绘制有效前沿
optimizer.plot_efficient_frontier()
```

#### 验收标准
- [x] 支持4种优化方法
- [x] 考虑约束条件(权重上下限、禁止做空等)
- [x] 可视化有效前沿
- [x] 输出可直接用于交易的权重

---

### 任务4.2: 策略性能归因分析 ⭐
**优先级**: 🔷 低
**预计时间**: 2天
**负责模块**: `src/analytics/attribution.py`

#### 分析维度

##### 1. 收益来源拆解
```python
def decompose_returns(
    trades: List[Dict],
    benchmark_returns: pd.Series
) -> Dict:
    """拆解收益来源

    Returns:
        {
            'stock_selection': 0.05,  # 选股贡献
            'market_timing': 0.03,     # 择时贡献
            'interaction': 0.01,       # 交互效应
            'total_alpha': 0.09        # 超额收益
        }
    """
```

##### 2. 交易胜率分析
```python
def analyze_win_rate_by_condition(
    trades: List[Dict],
    df: pd.DataFrame
) -> Dict:
    """按条件分析胜率

    Returns:
        {
            'by_hour': {9: 0.65, 10: 0.58, ...},  # 按小时
            'by_rsi': {'<30': 0.72, '30-50': 0.55, ...},  # 按RSI区间
            'by_volatility': {'low': 0.68, 'medium': 0.55, 'high': 0.45},
            'by_trend': {'uptrend': 0.75, 'downtrend': 0.45, 'sideways': 0.50}
        }
    """
```

##### 3. 最佳/最差交易分析
```python
def analyze_extreme_trades(
    trades: List[Dict],
    top_n: int = 10
) -> Dict:
    """分析极端交易

    找出表现最好和最差的交易，总结共性
    """
```

#### 验收标准
- [x] 生成详细的归因报告
- [x] 识别策略优势和弱点
- [x] 提供优化建议

---

## 📊 测试和文档 (贯穿全程)

### 任务5.1: 单元测试 ⭐⭐
**目标覆盖率**: >80%

#### 关键测试
```python
# tests/test_persistent_cache.py
def test_cache_set_and_get()
def test_cache_expiration()
def test_cache_invalidation()

# tests/test_etf_analyzer.py
def test_premium_discount_calculation()
def test_holdings_parsing()
def test_tracking_error()

# tests/test_dynamic_stop_loss.py
def test_atr_trailing_stop()
def test_time_based_stop()

# tests/test_portfolio_optimizer.py
def test_markowitz_optimization()
def test_risk_parity()
```

#### 运行测试
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

---

### 任务5.2: 文档更新 ⭐
**更新文档**:
- `README.md` - 新功能介绍
- `CHANGELOG.md` - 版本变更记录
- `docs/ETF_ANALYSIS.md` - ETF分析使用指南
- `docs/VISUALIZATION.md` - 可视化功能说明
- `docs/RISK_MANAGEMENT.md` - 风控系统文档
- `docs/PORTFOLIO_OPTIMIZATION.md` - 组合优化指南

---

## 📅 时间表

### Week 1: 基础设施
- **Day 1-2**: 持久化缓存 + 异常处理改进
- **Day 3-4**: ETF分析模块
- **Day 5**: 测试和集成

### Week 2: 可视化
- **Day 1-2**: K线图表生成
- **Day 3-4**: 回测报告可视化
- **Day 5**: Web仪表板(可选)

### Week 3: 风控
- **Day 1-2**: 动态止损机制
- **Day 3-4**: 风险监控模块
- **Day 5**: 集成测试

### Week 4: 高级功能
- **Day 1-3**: 组合优化
- **Day 4-5**: 性能归因 + 文档完善

---

## 🎯 成功标准

### 技术指标
- [x] 所有单元测试通过
- [x] 代码覆盖率 >80%
- [x] 无 critical/high 级别的代码问题
- [x] API响应时间 <500ms (95th percentile)

### 功能指标
- [x] 支持分析至少10个主流ETF
- [x] 生成专业级的可视化报告
- [x] 动态止损在回测中生效
- [x] 组合优化输出合理权重

### 用户体验
- [x] 文档完整清晰
- [x] 错误信息友好
- [x] 命令行工具易用

---

## 📞 风险和缓解

### 风险1: 数据源不稳定
**缓解**: 多数据源降级 + 持久化缓存

### 风险2: 开发时间超期
**缓解**: 优先完成P0/P1任务，P2任务可延后

### 风险3: 性能问题
**缓解**: 早期进行性能测试，优化热点代码

---

## 📈 后续版本规划

### v2.2 (2026 Q1)
- 机器学习预测模型
- 实盘交易券商对接
- 移动端App

### v3.0 (2026 Q2)
- 期货期权支持
- 高频策略框架
- 云端部署方案

---

**文档版本**: v1.0
**最后更新**: 2025-11-18
**维护者**: 开发团队
