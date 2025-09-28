# 掌握本工程的系统学习计划

本计划面向需要全面掌握本仓库（股票分析系统）的工程师，覆盖 Web 后端、数据持久化、缓存与限流、异步采集、量化与建模、工程化与部署等关键能力，并提供按周（前两周细化到天）的学习与实践路径，可直接作为团队入职/自学的执行清单。

## 学习重点

- Web API 架构与中间件：Flask 蓝图、请求生命周期、CORS、全局错误处理、依赖注入。
- 数据持久化：SQLAlchemy 2.x ORM、Session 作用域与连接池、迁移策略、PostgreSQL 基础。
- 缓存与限流：Redis 基础、二级缓存策略（L1/L2）、令牌桶限流、故障降级。
- 异步采集：asyncio/aiohttp 并发模型、外部行情源访问与容错（Sina/Yahoo/Mock）。
- 量化与建模：pandas/numpy 指标计算、scikit‑learn 训练/验证、SHAP 可解释。
- 工程化与部署：pytest 测试与 Mock、Docker/docker-compose、日志与配置管理、任务调度。

## 前置要求

- Python 3.10+ 熟练；虚拟环境与 pip 基本操作。
- 基础 SQL，能读写常见查询与简单索引使用。
- Git 与命令行基本操作。

## 总览路线（8 周）

- 第 1 周：Flask 基础与仓库结构解读，补齐依赖注入与错误链路。
- 第 2 周：SQLAlchemy 会话管理与数据访问层实践，Postgres/SQLite 双环境可运行。
- 第 3 周：Redis 缓存与限流，中间件封装与降级策略。
- 第 4 周：asyncio/aiohttp 并发采集与外部数据容错，批量采集。
- 第 5 周：技术指标与特征工程，sklearn 训练与持久化，SHAP 解释。
- 第 6 周：API 端点完善（analysis/batch/realtime/history），通过现有/新增测试。
- 第 7 周：调度与部署（Docker、docker-compose），运行监控与日志。
- 第 8 周：性能与健壮性（缓存命中、连接池、熔断回退），补齐文档与运维脚本。

## 详细计划（第 1–2 周按天，3–8 周按任务）

### 第 1 周（Flask + 错误处理）

- 第 1 天：请求链路与中间件
  - 阅读与梳理请求生命周期：before_request → 视图 → after_request → 全局异常。
  - 关注文件：`src/app.py`（应用工厂/蓝图注册/计时日志）、`src/utils/error_handler.py`（统一异常）、`src/middleware/auth.py`（请求 ID 与鉴权）。
  - 产出：一张请求生命周期图与中间件顺序说明。
- 第 2 天：依赖注入与会话
  - 分析蓝图与依赖注入：`src/api/stock_api.py` 中 `db_session` 为空的问题；设计 request-scoped Session 注入（在 `before_request` 创建，在 `teardown_request` 关闭/回滚）。
  - 产出：注入方案设计文档与伪代码。
- 第 3 天：统一错误响应
  - 从自定义异常到 JSON 输出规范（400/401/403/429/500/503）。
  - 为参数校验失败返回结构补充 `request_id` 与可定位信息。
  - 产出：错误码对照表与响应模板。
- 第 4 天：CORS/Headers/日志
  - 确保所有响应包含 `X-Request-ID`、`X-Response-Time`。
  - 产出：本地调用验证截图或日志片段。
- 第 5 天：对齐测试与文档
  - 梳理 `tests/test_enhanced_api.py` 的端点期望与现状缺口（如 `/analysis`、`/realtime`、`/history`）。
  - 产出：缺口清单与实现顺序（先 Session 注入与 `/health` 细化，再 `/analysis`）。

### 第 2 周（SQLAlchemy + 数据访问）

- 第 1 天：模型与元数据
  - 阅读 `src/models/stock.py`，编写基础 CRUD（按代码查 Stock、按时间窗口查价格、最近一条价格）。
  - 产出：示例查询函数与单测。
- 第 2 天：连接池与健康检查
  - 阅读 `src/database/session.py`，理解连接池参数与 `health_check()` 实现。
  - 为测试环境提供 SQLite 后备（通过 `.env` 或环境变量切换），数据库不可用时应用可“降级启动”。
  - 产出：`/api/stocks/health` 返回 `degraded` 路径验证。
- 第 3 天：Session 生命周期
  - 选择 scoped_session 或 request-scoped Session 实现；确保异常回滚与关闭。
  - 产出：连接泄漏检测脚本或日志规则。
- 第 4 天：时间序列与分页
  - 完善 `/timeline` 查询窗口与分页；处理空数据与边界值。
  - 产出：覆盖这些路径的单测。
- 第 5 天：复盘与测试
  - 跑 `pytest`，记录失败用例与修复计划。

### 第 3 周（Redis 缓存/限流）

- 学习要点
  - L1（本地）+ L2（Redis）缓存策略、TTL、键设计与失效（`src/middleware/cache.py`）。
  - 令牌桶限流与响应头（`src/middleware/rate_limiter.py`）。
- 实践
  - 为热点接口加缓存装饰器与失效方法（按 pattern 失效）。
  - 设计 Redis 不可用时的无损降级（仅 L1，记录告警）。
  - 验证 429 响应头与对应测试。

### 第 4 周（异步采集与容错）

- 学习要点
  - `asyncio`/`aiohttp` 并发、超时与重试、批量聚合。
  - 多数据源回退策略：Sina → Yahoo → Mock（`src/services/enhanced_data_collector.py`）。
- 实践
  - 完成 `fetch_batch_prices()` 的异常收敛与日志标准；写库路径幂等与回滚。
  - 增加“模拟数据模式”开关，便于本地/CI。

### 第 5 周（特征工程与推荐引擎）

- 学习要点
  - 技术指标实现（MA/RSI/MACD/BOLL/量比）与波动性度量（`src/services/recommendation_engine.py`）。
  - sklearn 训练/评估/持久化；SHAP 解释与 TopN 因子。
- 实践
  - 构造小样本训练集（可用合成标签），训练 GBDT；持久化模型与 scaler（避免“未训练”）。
  - 产出：人类可读解释摘要与存库；基础精度与过拟合检查报告。

### 第 6 周（API 补全与测试）

- 端点实现
  - `/analysis`（按 `docs/API.md` 参数）；`/batch_analysis`（体量/速率限制）；`/realtime`、`/history`（days 参数校验）。
- 校验层
  - 扩展 `InputValidator` 覆盖现有测试；必要时新增 `StockValidator` 适配。
- 测试
  - 跑 `pytest`，逐个击破：请求头断言、429 场景、JSON 解析错误 400。

### 第 7 周（调度与部署）

- 调度器修复
  - 为 `src/scheduler.py` 补 `timedelta` 与 `StockPrice` 导入；完善市场时段、断点续跑、告警。
- 部署
  - 构建镜像，`docker-compose` 启动（Postgres/Redis + API）。
  - 健康检查、降级页面；日志卷与轮转校验。

### 第 8 周（性能与健壮性）

- 连接池参数与慢查询日志；缓存命中率观测。
- API 超时与熔断（超时返回、部分数据可用）与重试策略。
- 文档
  - 更新 `docs/API.md` 与 `docs/ARCHITECTURE.md` 已实现与 TODO；补本地开发指南与故障排查。

## 每周交付与检查点

- 第 1 周：请求链路图与中间件顺序；request‑scoped Session 注入设计。
- 第 2 周：SQLite 可启动与 `/health` degraded；关键查询单测；`pytest` 报告。
- 第 3 周：热点接口命中缓存；Redis 挂掉时服务不崩；429 头验证。
- 第 4 周：批量采集可运行（mock/真实开关）；写库幂等验证。
- 第 5 周：基础模型与 SHAP 解释；推荐结果可入库。
- 第 6 周：文档中的核心端点可用；主要测试通过。
- 第 7 周：Docker 一键启动（API+DB+Redis）；调度可运行。
- 第 8 周：性能与稳定性基线报告；更新文档与运维手册。

## 与仓库强关联的实践清单

- 注入会话：在 `src/app.py` 为蓝图提供 request‑scoped `db_session` 并 `teardown_request` 关闭；修正 `src/api/stock_api.py` 的空引用。
- 健康检查：数据库不可用时 `/api/stocks/health` 返回 `degraded`，而非启动失败。
- 调度器导入缺失：修复 `src/scheduler.py` 的 `timedelta` 与 `StockPrice` 导入。
- 端点补全：实现 `/analysis`、`/realtime`、`/history`、`/batch_analysis` 以满足现有测试。
- 校验层：补 `StockValidator` 适配或调整测试使用；统一错误响应结构与 `request_id`。
- 模型持久化：为 `RecommendationEngine` 增加加载/保存，避免“未训练”。
- 日志与目录：创建 `logs/` 可写目录或支持仅控制台日志的降级。

## 建议的练习与验证命令

- 运行测试：`pytest -q`
- 本地启动（SQLite）：`DATABASE_URL=sqlite:///dev.db python src/app.py`
- 采集演示（mock/真实）：`python -m src.scheduler`
- Docker 化：`docker build -t stock-api .`；`docker-compose up -d`

## Issue/TODO 清单（可复制到任务管理）

以下条目为可执行的任务清单（勾选项）。每项包含验收标准与产出要求，建议以 GitHub Issues 或项目管理工具分解追踪。

### 第 1 周（Flask + 错误处理）

- [ ] Day 1｜梳理请求链路与中间件顺序
  - 验收：形成一张请求生命周期图（before→view→after→error handler），标注 `X-Request-ID`、`X-Response-Time` 注入点。
  - 产出：架构图（PNG/MD）与说明（1 页）。
- [ ] Day 2｜设计并实现 request-scoped Session 注入
  - 验收：`src/api/stock_api.py` 不再出现 `db_session` 空引用；请求结束释放连接；异常时回滚。
  - 产出：代码变更 + 设计记录（创建/回收时机、示例伪代码）。
- [ ] Day 3｜统一错误响应与可观测信息
  - 验收：常见错误（400/401/403/429/500/503）均为统一 JSON，含 `request_id`；新增或完善对应测试。
  - 产出：错误码对照表（MD）+ 测试用例。
- [ ] Day 4｜完善 CORS/Headers/日志
  - 验收：所有响应含 `X-Request-ID` 与 `X-Response-Time`；日志包含请求方法、路径、耗时、状态码。
  - 产出：配置说明 + 日志示例片段。
- [ ] Day 5｜对齐文档与测试缺口
  - 验收：列出 `/analysis`、`/realtime`、`/history` 等缺口与实现优先级；获得评审确认。
  - 产出：缺口清单（MD/Issue 列表）。

### 第 2 周（SQLAlchemy + 数据访问）

- [ ] Day 1｜CRUD 与时间序列查询
  - 验收：封装获取最新价格、按窗口查询价格、分页列表等方法，并通过单测。
  - 产出：查询函数 + 测试。
- [ ] Day 2｜健康检查与降级策略
  - 验收：数据库不可用时应用可“降级启动”；`/health` 返回 `degraded`；文档化环境切换（Postgres/SQLite）。
  - 产出：环境说明 + 健康检查行为定义。
- [ ] Day 3｜Session 生命周期治理
  - 验收：异常回滚、连接释放；提供连接泄漏监控规则（日志/metrics）。
  - 产出：治理说明 + 验证脚本或操作指引。
- [ ] Day 4｜时间窗口与分页边界测试
  - 验收：覆盖空数据、边界日期、非法参数的单测。
  - 产出：测试用例。
- [ ] Day 5｜一轮测试复盘
  - 验收：`pytest` 报告清晰，列出失败用例与修复计划。
  - 产出：测试报告与改进清单。

### 第 3 周（Redis 缓存/限流）

- [ ] 为热点接口增加缓存与失效
  - 验收：命中率可观测（日志/metrics），可按 pattern 失效；Redis 不可用自动降级到 L1。
  - 产出：实现说明 + 验证手册。
- [ ] 限流与响应头对齐
  - 验收：达到上限返回 429，带 `X-RateLimit-*` 头；新增/完善相关测试。
  - 产出：测试用例与运行截图。

### 第 4 周（异步采集与容错）

- [ ] 批量并发采集 + 回退策略
  - 验收：Sina→Yahoo→Mock 回退链路生效；批量异常不影响全局；写库幂等。
  - 产出：并发/回退策略说明 + 日志样例。
- [ ] 本地/CI 模拟数据模式
  - 验收：一键切换真实/模拟；CI 默认使用模拟模式跑测。
  - 产出：环境变量约定与 README 片段。

### 第 5 周（特征工程与推荐引擎）

- [ ] 特征提取与空值治理
  - 验收：技术指标与统计特征齐备；缺失值策略稳定；单测覆盖基础统计。
  - 产出：特征字典（字段、含义、单位、范围）。
- [ ] 训练/持久化/解释
  - 验收：可训练 GBDT；持久化模型与 scaler；SHAP TopN 因子可读化并存库。
  - 产出：训练脚本 + 评估报告（精度、过拟合、可解释示例）。

### 第 6 周（API 补全与测试）

- [ ] 实现 `/analysis`、`/batch_analysis`、`/realtime`、`/history`
  - 验收：参数校验与速率限制齐备；与 `docs/API.md` 一致；主要测试通过。
  - 产出：接口说明更新 + 测试用例。
- [ ] 校验层适配
  - 验收：补 `StockValidator` 或扩展 `InputValidator` 以满足测试期望；统一错误结构。
  - 产出：实现与迁移说明。

### 第 7 周（调度与部署）

- [ ] 修复调度器与清理任务
  - 验收：补齐缺失导入（`timedelta`、`StockPrice`）；市场时段策略生效；异常告警。
  - 产出：调度策略文档与运行日志。
- [ ] Docker 化与 compose 编排
  - 验收：一键启动 API+DB+Redis；健康检查通过；日志卷与轮转正常。
  - 产出：部署指南与故障排查条目。

### 第 8 周（性能与健壮性）

- [ ] 连接池与慢查询治理
  - 验收：可观测连接池状态与慢查询；提出优化建议并落地。
  - 产出：性能基线报告。
- [ ] 缓存命中/超时/熔断策略
  - 验收：超时返回与部分可用；缓存策略验证；降级流程清晰。
  - 产出：策略文档与演示记录。
- [ ] 文档与运维手册完善
  - 验收：更新 `docs/API.md`、`docs/ARCHITECTURE.md` 与本学习文档；新增本地开发与故障排查指南。
  - 产出：完整文档集。

## 推荐学习资料（书籍与论文）

### 书籍（工程与基础）
- Flask Web Development（Miguel Grinberg）
- Essential SQLAlchemy（O’Reilly）
- Designing Data-Intensive Applications（Martin Kleppmann）
- Redis in Action（Josiah L. Carlson）
- High Performance Python（Micha Gorelick, Ian Ozsvald）
- Fluent Python（Luciano Ramalho）
- Effective Python（Brett Slatkin）
- Hands-On Machine Learning with Scikit-Learn, Keras & TensorFlow（Aurélien Géron）

### 书籍（量化与金融）
- Advances in Financial Machine Learning（Marcos López de Prado）
- Machine Trading（Ernest P. Chan）

### 论文/经典文献（模型与可解释、金融因子）
- A Unified Approach to Interpreting Model Predictions（Lundberg & Lee, 2017）— SHAP 原始论文
- XGBoost: A Scalable Tree Boosting System（Chen & Guestrin, 2016）
- LightGBM: A Highly Efficient Gradient Boosting Decision Tree（Ke et al., 2017）
- Common risk factors in the returns on stocks and bonds（Fama & French, 1993）
- Returns to Buying Winners and Selling Losers（Jegadeesh & Titman, 1993）

### 主题/关键词（速查）
- Flask：请求生命周期、Blueprint、应用工厂、错误处理
- SQLAlchemy 2.x：ORM/Session/连接池/事务
- Redis：令牌桶/漏桶、缓存失效策略
- asyncio/aiohttp：并发、超时、重试、会话
- pandas/sklearn/SHAP：指标、训练评估、可解释性
- pytest：fixture/mocking、参数化测试、覆盖率
