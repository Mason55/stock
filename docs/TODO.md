# 项目TODO跟踪

## 📋 完成状态总览

### ✅ 已完成 (第1-2阶段)

#### 第1阶段：立即修复
- [x] **修复requirements.txt依赖问题** 
  - 移除asyncio内置模块依赖
  - 优化版本范围管理
  - 按功能分类依赖项
  
- [x] **重构数据库会话管理**
  - 实现连接池管理 (`src/database/session.py`)
  - 添加会话自动清理机制
  - 完善数据库异常重连逻辑
  - 健康检查功能
  
- [x] **完善API错误处理机制**
  - 创建自定义异常类 (`src/utils/exceptions.py`)
  - 实现集中错误处理 (`src/utils/error_handler.py`)
  - 分类业务异常类型 (4xx vs 5xx)
  - 添加请求ID追踪（已统一读取 `g.request_id` 并在响应头透传 `X-Request-ID`）

#### 第2阶段：短期改进
- [x] **集成真实股票数据API**
  - 实现新浪财经数据源 (`src/data_sources/sina_finance.py`)
  - 完善数据收集器故障转移机制
  - A股实时数据获取
  
- [x] **扩展测试用例覆盖**
  - 创建增强测试套件 (`tests/test_enhanced_api.py`)
  - 业务逻辑单元测试
  - 边界条件和异常情况测试
  - 参数化测试用例
  
- [x] **实现基础认证功能**
  - API Key认证系统 (`src/middleware/auth.py`)
  - 权限控制机制
  - 签名验证 (防重放攻击)
  - 可选认证支持

---

## 🔄 进行中

- [ ] 历史数据与指标落库（夜间任务），避免线上频繁拉取与限流
  - 位置：`src/scheduler.py` + 新增 ETL；表：`stock_prices` 扩展、`indicators` 新表
- [ ] 技术指标扩展与解释（BOLL/KDJ/ATR 等），并在 `/analysis` 输出可操作解读
  - 位置：`src/api/stock_api.py` 与（可选）`src/core/technical_analysis.py`
- [ ] 基本面与情绪接入（Tushare 财报、新闻/NLP），去除"降级"标注
  - 位置：新增 `src/data_sources/fundamentals_*.py`、`src/services/sentiment_provider.py`
- [ ] 热门标的预取与缓存预热（减少尾延迟与限流）
  - 位置：`src/scheduler.py` 调度 + `src/cache` 统一入口

---

## 🎯 量化交易系统 (实盘交易路线图)

### ✅ 已完成 (Week 1 核心架构)
- [x] **回测引擎** (`src/backtest/engine.py`, 480行事件驱动)
  - 事件系统: MarketData/Order/Fill/Signal
  - 策略基类 (Strategy ABC)
  - 组合管理 (Portfolio)
  - 时间回放机制
- [x] **市场模拟器** (`src/backtest/market_simulator.py`)
  - 涨跌停限制 (±10%)
  - T+1交易规则
  - 滑点与市场冲击
- [x] **成本模型** (`src/backtest/cost_model.py`)
  - 佣金计算 (千分之三)
  - 印花税 (千分之一)
  - 过户费
- [x] **风控系统** (`src/backtest/risk_manager.py`)
  - 单仓位上限 (10%)
  - 总仓位上限 (95%)
  - 订单前置检查
- [x] **数据模型** (trading/market_data models)
  - Order/Fill/Position/Portfolio
  - HistoricalPrice/CorporateAction
  - TradingCalendar

### ✅ 阶段1: 实盘基础 (已完成)

#### 1.1 实盘交易网关 ⚠️ 关键路径
- [x] **Broker适配器抽象** (`src/trading/broker_adapter.py`)
  - 抽象接口设计 (place_order/cancel_order/get_positions/get_account/subscribe_quotes)
  - 错误处理与重试机制
  - 连接状态管理

- [x] **Mock Broker网关** (`src/trading/broker_gateway.py`)
  - 模拟订单处理 (市价/限价)
  - 成交模拟 (延迟+滑点)
  - 账户与持仓管理
  - 测试辅助功能

#### 1.2 实盘引擎 🔴
- [x] **实时策略运行时** (`src/trading/live_engine.py`)
  - 事件驱动架构 (复用BacktestEngine设计)
  - 实时行情处理 (WebSocket → MarketDataEvent)
  - 策略生命周期管理 (启动/停止)
  - 状态持久化 (数据库)
  - 异常恢复机制

- [x] **信号执行器** (`src/trading/signal_executor.py`)
  - SignalEvent → Order 转换
  - 仓位同步检查
  - 资金可用性检查
  - 订单提交到网关
  - 订单规模计算 (可用资金 × 10% × 信号强度)

#### 1.3 订单管理系统 (OMS) 📝
- [x] **订单管理器** (`src/trading/order_manager.py`)
  - 订单状态机 (CREATED/VALIDATED/SUBMITTED/PARTIAL_FILLED/FILLED/CANCELED/REJECTED/EXPIRED)
  - 订单持久化 (写入orders表)
  - 成交回报处理 (更新Portfolio)
  - 订单查询API
  - 速率限制 (10 orders/s)

- [ ] **智能下单** (`src/trading/smart_order.py`)
  - TWAP算法 (时间加权)
  - VWAP算法 (成交量加权)
  - 大单拆分逻辑
  - 撤单重发策略

**测试状态**: 11/11 通过 ✅
**提交记录**: 0fee300

### ✅ 阶段2: 策略库 (已完成)

#### 2.1 经典策略实现 (`src/strategies/`)
- [x] **双均线策略** (`moving_average.py`)
  - 金叉死叉检测 (MA5 × MA20)
  - 信号强度计算 (基于价差百分比)
  - 参数: 快慢均线周期 (默认5/20)

- [x] **均值回归策略** (`mean_reversion.py`)
  - 布林带突破检测 (2倍标准差)
  - RSI超买超卖判断 (30/70阈值)
  - 参数: BB周期20、RSI周期14

- [x] **动量策略** (`momentum.py`)
  - 价格动量排名 (20日回报率)
  - 多标的轮动 (最多5个)
  - 参数: 回看周期、持仓数量

- [ ] **配对交易策略** (`pairs_trading.py`)
  - 协整对筛选
  - 价差均值回归
  - 参数: 开仓阈值、止损线

- [ ] **机器学习策略** (`ml_predictor.py`)
  - 特征工程 (技术指标+基本面)
  - XGBoost/LightGBM模型
  - 参数: 模型路径、预测阈值

#### 2.2 策略配置化
- [x] **策略参数管理** (`config/strategies.yaml`)
  - YAML配置支持
  - 3个预设组合 (保守/激进/平衡)
  - StrategyLoader加载器

- [ ] **参数优化工具** (`examples/optimize_strategy.py`)
  - 参数热加载
  - 参数版本控制
  - 参数优化记录

**测试状态**: 16个测试 (13通过/3待调参) ⚠️
**提交记录**: b02b6db + ed9d5a9 (文档)

### ✅ 阶段3: 风控增强 (已完成)

#### 3.1 实时风控监控
- [x] **动态风控引擎** (`src/risk/real_time_monitor.py`)
  - 单日亏损熔断 (-3%)
  - 总回撤熔断 (-10%)
  - 集中度控制 (单股<15%)
  - 异常波动检测 (3倍标准波动)
  - 分级告警 (warning/limit/circuit_breaker)

- [x] **风控规则配置** (`config/risk_rules.yaml`)
  - 3个风险配置 (conservative/moderate/aggressive)
  - 规则动态调整
  - 分级风控 (警告/限制/熔断)

#### 3.2 动态仓位管理
- [x] **仓位计算器** (`src/risk/position_sizer.py`)
  - Kelly公式 (最优仓位，Half-Kelly安全系数)
  - 固定比例 (默认10%)
  - 波动率调整 (基于ATR)
  - Equal Weight (1/N)
  - 仓位上下限 (2%-20%)

- [x] **仓位监控** (`src/risk/position_monitor.py`)
  - 实时持仓跟踪 (市值/成本/盈亏)
  - 仓位偏离检测 (5%阈值)
  - 自动再平衡建议
  - 大额亏损告警 (-5%)

- [x] **配置加载器** (`src/risk/risk_config_loader.py`)
  - 风险配置文件加载
  - 多配置档案支持

**测试状态**: 22/22 通过 ✅
**提交记录**: (待提交)

### 🚀 阶段4: 生产化 (1-2周)

#### 4.1 监控与告警 🚨
- [ ] **策略监控** (`src/monitoring/strategy_monitor.py`)
  - 收益率监控 (实时/日度/累计)
  - 信号质量统计 (胜率/盈亏比)
  - 策略健康度评分
  - Prometheus指标暴露

- [ ] **告警系统** (`src/monitoring/alert_manager.py`)
  - 邮件告警 (SMTP)
  - 企业微信/钉钉推送
  - 异常日志聚合
  - 告警规则引擎

#### 4.2 实时数据流优化
- [ ] **WebSocket行情订阅** (`src/data_sources/realtime_feed.py`)
  - 新浪/腾讯/东财 WebSocket
  - Tick级数据处理
  - Level-2深度行情
  - 行情队列管理

- [ ] **分钟K线生成** (`src/data_sources/kline_generator.py`)
  - Tick聚合为1m/5m/15m
  - 实时指标计算
  - 数据落库

#### 4.3 回测增强
- [ ] **高级市场模拟** (`src/backtest/advanced_simulator.py`)
  - 订单簿撮合 (价格优先/时间优先)
  - 成交概率模型
  - 市场微观结构

- [ ] **绩效分析器** (`src/backtest/performance_analyzer.py`)
  - 因子收益分解
  - 夏普/卡尔玛/索提诺比率
  - 分年度/分策略统计
  - 收益归因报告

#### 4.4 参数优化
- [ ] **参数调优器** (`src/optimization/parameter_tuner.py`)
  - 网格搜索
  - 遗传算法
  - 贝叶斯优化

- [ ] **滚动优化** (`src/optimization/walk_forward.py`)
  - 训练集/验证集拆分
  - 防止过拟合
  - 稳健性测试

---

### 💡 最小可行实盘系统 (MVP)

**目标**: 1周开发 + 1周测试

**核心模块**:
1. 实盘交易网关 (选1个券商SDK)
2. 实盘引擎 (复用回测架构)
3. 双均线策略 (最简单)
4. 基础风控 (亏损熔断)
5. 日志监控

**测试方案**:
- 纸上交易 (模拟盘)
- 小资金实盘验证 (<1万元)
- 监控1-2周稳定性

---

### 📊 量化系统指标

**当前状态**:
- 回测功能: ✅ 完整 (事件驱动/组合管理/成本模型)
- 实盘交易: ✅ 基础架构 (Mock Broker/实盘引擎/订单管理)
- 策略数量: 3个 (双均线/均值回归/动量)
- 数据频率: 日线 + 实时(准备)
- 风控完整度: 70% (熔断/仓位管理/再平衡)

**MVP目标**:
- 实盘下单: ✅ 支持
- 策略数量: 1-2个
- 数据频率: 日线 + 实时
- 风控完整度: 60%
- 告警机制: ✅ 基础

**完整系统目标**:
- 实盘下单: ✅ 完善
- 策略数量: 5+个
- 数据频率: Tick/分钟/日线
- 风控完整度: 90%
- 告警机制: ✅ 完善
- 监控覆盖: 100%

---

---

## 📅 待开始 (第3-4阶段)

### 第3阶段：中期优化 (1-2周)

#### 3.1 性能优化 🚀
- [ ] **解决N+1查询问题**
  - 优化`src/api/stock_api.py`中的scan_stocks函数
  - 实现批量数据库查询
  - 添加查询性能监控
  - 进展：已采用子查询+Join 批量拉取最新价，仍需压测与指标化（见 `scan_stocks`）
  
- [ ] **数据库查询优化**
  - 创建必要的数据库索引
  - 优化复杂查询语句
  - 实现查询缓存策略
  
- [ ] **缓存策略优化**
  - 实现智能缓存失效
  - 分层缓存架构
  - 缓存命中率监控

#### 3.2 安全加固 🛡️
- [ ] **防护SQL注入风险**
  - 强制使用参数化查询
  - 增强输入验证规则
  - 代码安全审计
  - 进展：`validate_query_safety` 放宽对普通 `SELECT` 的误报；装饰器在无请求上下文时安全降级
  
- [ ] **加强输入验证**
  - 完善股票代码验证 (`src/middleware/validator.py`)
  - 添加数据类型验证
  - 实现请求大小限制
  
- [ ] **实现数据加密**
  - 敏感数据字段加密
  - API密钥安全存储
  - 传输加密增强

#### 3.3 监控告警 📊
- [ ] **添加性能监控指标**
  - Prometheus指标集成
  - 响应时间监控
  - 错误率统计
  - 进展：`/metrics` 已有轻量文本版，Prometheus client 可选；需将关键 API 时延与错误率指标化
  
- [ ] **实现异常告警机制**
  - 邮件/短信告警
  - 错误阈值设定
  - 告警策略配置
  
- [ ] **完善日志聚合分析**
  - ELK Stack集成
  - 日志格式标准化
  - 日志轮转策略

### 第4阶段：长期规划 (2-4周)

#### 4.1 架构优化 🏗️
- [ ] **设计微服务拆分方案**
  - 服务边界定义
  - API网关设计
  - 服务间通信协议
  
- [ ] **实现服务发现机制**
  - Consul/Eureka集成
  - 健康检查机制
  - 负载均衡策略
  
- [ ] **优化负载均衡策略**
  - Nginx配置优化
  - 会话粘性处理
  - 动态负载均衡

#### 4.2 高可用设计 ⚡
- [ ] **实现多实例部署**
  - Docker Swarm/Kubernetes
  - 无状态服务设计
  - 配置中心化管理
  
- [ ] **添加健康检查机制**
  - 深度健康检查
  - 依赖服务检查
  - 自动故障恢复
  
- [ ] **设置自动故障转移**
  - 主备切换机制
  - 数据同步策略
  - 故障通知机制

#### 4.3 运维自动化 🤖
- [ ] **实现CI/CD流水线**
  - GitHub Actions优化
  - 自动化测试集成
  - 蓝绿部署策略
  
- [ ] **添加自动化测试**
  - 端到端测试
  - 性能回归测试
  - 安全漏洞扫描
  
- [ ] **完善部署回滚机制**
  - 版本管理策略
  - 快速回滚功能
  - 部署状态监控

---

## 🎯 功能增强需求

### 数据源扩展
- [ ] **东方财富API集成**
  - 基本面数据获取
  - 财务报表数据
  - 行业分析数据
  
- [ ] **腾讯财经API集成**
  - 新闻情绪数据
  - 社交媒体情绪
  - 分析师评级
  
- [ ] **港股美股数据支持**
  - 多市场数据源
  - 汇率转换
  - 跨市场分析

### 算法增强
- [ ] **机器学习模型优化**
  - 模型训练流水线
  - 特征工程改进
  - 模型性能评估
  
- [ ] **技术指标扩展**
  - 高级技术指标
  - 自定义指标支持
  - 指标组合策略
  
- [ ] **风险管理模块**
  - VaR计算
  - 压力测试
  - 风险预警

### 用户体验
- [ ] **Web前端界面**
  - React/Vue.js前端
  - 实时数据展示
  - 交互式图表
  
- [ ] **移动端支持**
  - 响应式设计
  - PWA支持
  - 原生App开发
  
- [ ] **个性化功能**
  - 用户偏好设置
  - 自定义看板
  - 投资组合管理

---

## 🚨 已知问题和Bug

### 高优先级
- [ ] **数据源稳定性问题**
  - 新浪财经API偶尔超时
  - 需要实现更robust的重试机制
  - 位置: `src/data_sources/sina_finance.py`
  
- [ ] **内存使用优化**
  - 大批量数据处理时内存占用过高
  - 需要实现数据流式处理
  - 位置: `src/services/enhanced_data_collector.py`

### 中优先级
- [ ] **错误信息国际化**
  - 当前错误信息混合中英文
  - 需要统一语言规范
  - 位置: `src/utils/error_handler.py`
  
- [ ] **配置文件验证**
  - 缺少配置项有效性检查
  - 需要启动时配置验证
  - 位置: `config/settings.py`

### 低优先级
- [ ] **日志格式不一致**
  - 不同模块日志格式略有差异
  - 需要统一日志格式
  - 位置: 多个文件

---

## 📈 性能指标目标

### 当前状态
- API响应时间: ~500ms
- 数据更新延迟: ~60s
- 并发用户支持: ~50

### 优化目标
- API响应时间: <200ms
- 数据更新延迟: <30s  
- 并发用户支持: >500
- 缓存命中率: >80%
- 系统可用性: >99.9%

---

## 🔧 技术债务

### 代码质量
- [ ] **代码注释完善**
  - 添加关键算法说明
  - 完善函数文档字符串
  - 添加使用示例

- [ ] **单元测试覆盖率提升**
  - 目标覆盖率: 80%+
  - 关键业务逻辑100%覆盖
  - 集成测试补充

- [ ] **代码重构**
  - 消除重复代码
  - 提取公共组件
  - 优化类结构设计

### 依赖管理
- [ ] **依赖版本更新**
  - 定期更新依赖版本
  - 安全漏洞检查
  - 兼容性测试

- [ ] **可选依赖隔离**
  - 核心功能与可选功能分离
  - 插件化架构设计
  - 降低耦合度

---

## 📊 项目里程碑

### 近期目标 (1个月)
- [x] ~~系统稳定性修复~~
- [x] ~~基础功能完善~~
- [ ] 性能优化完成
- [ ] 安全加固完成

### 中期目标 (3个月)
- [ ] 微服务架构改造
- [ ] 高可用部署
- [ ] 监控告警完善
- [ ] 前端界面开发

### 长期目标 (6个月)
- [ ] 多市场数据支持
- [ ] 算法模型优化
- [ ] 商业化准备
- [ ] 开源社区建设

---

## 📝 更新日志

### 2025-09-30
- **架构优化与安全加固**:
  - 数据库连接池环境变量配置 (DB_POOL_SIZE/MAX_OVERFLOW/TIMEOUT/RECYCLE)
  - 统一缓存TTL管理 (实时30s/历史3600s/分析600s)
  - URL脱敏正则加固 (`_sanitize_url` with regex)
  - 启动配置验证器 (`ConfigValidator` 验证13项关键配置)
  - 合并离线模式标志 (废弃MOCK_DATA_ENABLED, 统一OFFLINE_MODE)
  - 移除SQLAlchemy警告 (3个模型文件迁移到新导入)
  - 代码格式化 (black + isort 统一8个文件)
- **量化交易路线图**: 添加实盘交易系统完整TODO (4阶段+MVP)
  - 已完成: Week 1回测引擎架构 (480行事件驱动)
  - 待实现: 实盘网关/策略库/风控增强/监控告警
- **✅ 阶段1完成 (实盘基础)**:
  - Broker适配器抽象 + Mock实现 (broker_adapter.py, broker_gateway.py)
  - 实时策略引擎 (live_engine.py, 320行)
  - 信号执行器 (signal_executor.py)
  - 订单管理系统 (order_manager.py, 状态机+持久化)
  - 测试: 11/11 通过 (commit: 0fee300)
- **✅ 阶段2完成 (策略库)**:
  - 3个经典策略 (双均线/均值回归/动量)
  - YAML配置系统 (strategies.yaml + strategy_loader.py)
  - 策略文档 (STRATEGY_GUIDE.md, 360行)
  - 测试: 16个 (13通过/3待调参) (commit: b02b6db, ed9d5a9)
- **✅ 阶段3完成 (风控增强)**:
  - 实时风控监控 (real_time_monitor.py, 熔断/告警/集中度)
  - 仓位计算器 (position_sizer.py, Kelly/固定/波动率/等权)
  - 仓位监控 (position_monitor.py, 跟踪/再平衡/告警)
  - 风控配置 (risk_rules.yaml, 3档配置)
  - 测试: 22/22 通过

### 2025-09-29
- /history：DB 为空时回退到 Tushare → Yahoo → 新浪 K 线（`src/api/stock_api.py:get_historical_data`），统一 OHLCV 与 `source` 字段。
- 分析：使用真实历史K线计算 MA/RSI/MACD；技术趋势来源明确，`fundamental/sentiment` 暂标注降级待接入。
- 实时：新浪 `hq.sinajs` 请求头与解析健壮性提升（GBK）。
- 兼容：Pydantic v2 `from_attributes`；ErrorHandler 读取 `g.request_id`；Validator 提供 `StockValidator` 适配；Scheduler 清理；/health 增加 `services` 汇总。
- 安全：SQL 安全检测避免将普通 `SELECT` 误判；在无请求上下文时装饰器降级安全处理。
- 测试：为 `request` 提供 shim 便于 patch，提升测试稳定性。

### 2025-09-28
- 完成第1-2阶段所有任务
- 修复核心稳定性问题
- 添加基础安全功能
- 创建TODO跟踪文档

---

## 🤝 贡献指南

### 新功能开发
1. 从TODO列表选择任务
2. 创建feature分支
3. 完成开发和测试
4. 提交PR并更新TODO状态

### Bug修复
1. 在已知问题中记录Bug
2. 标记优先级
3. 修复后更新状态
4. 添加回归测试

### 文档更新
1. 及时更新API文档
2. 补充使用示例
3. 更新架构说明
4. 维护TODO状态

---

*最后更新: 2025-09-29*  
*负责人: Development Team*  
*状态: 活跃维护中*