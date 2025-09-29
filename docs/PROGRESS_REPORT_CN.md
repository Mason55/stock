# 项目进展与下一步计划（中文）

本文汇总当前仓库的工程分析、学习路径、可移植性评估、商业化差距、向量化系统演进建议，以及本轮完成项与待办。配合 docs/study 与 todo/ 目录的执行清单，便于团队协作推进。

## 当前工程概览
- 架构：Flask API + SQLAlchemy ORM，支持 Mock/离线模式；监控/指标模块独立（/metrics），统一错误处理与请求日志。
- 数据源：
  - 实时行情：优先调用新浪 `hq.sinajs`（带 Referer/User-Agent 头避免 403），失败回退到数据库/Mock。
  - 历史K线：优先 Tushare（需 `TUSHARE_TOKEN`）→ Yahoo Finance（`yfinance`）→ 新浪 OpenAPI（日线）。
  - 技术指标：基于真实K线计算 MA/RSI/MACD；趋势综合由价格- MA20 与 MACD 判断，支持/阻力以当前价的相对区间给出。
  - 基本面/情绪：当前标记为降级状态，等待接入真实来源（财报、资讯、NLP）。
- 缓存：`@cached` 装饰器（内存 L1，可选 Redis L2），TTL 可配置；`nocache=1` 强制绕过。
- 健壮性：数据库懒加载，失败回退到内存 SQLite；`/health` 报告健康/降级；配置项支持 OFFLINE_MODE/USE_REDIS/LOG_TO_FILE/CORS_ORIGINS。

## 学习路径与资料
- 学习目录：`docs/study/`（学习计划、Issue 导入模板）。
- 关键资料：
  - 工程：Flask Web Development、Designing Data-Intensive Applications、High Performance Python 等。
  - 量化：Advances in Financial Machine Learning（Lopez de Prado）、Machine Trading（Ernest Chan）。
  - 论文：Fama-French(1993)、Momentum(Jegadeesh & Titman, 1993)、SHAP/XGBoost/LightGBM 等。
- 导入 Issues：见 `docs/study/ISSUE_IMPORT_GUIDE.md` 与 `docs/study/issues_import.csv|json`。

## 可移植性/便携性评估
- 已有：
  - Dockerfile.minimal / compose（见 `docs/PORTABILITY.md`、`docs/DEPLOYMENT.md`）。
  - Redis/Prometheus 可选启用；离线/Mock 模式支持。
- 改进建议：
  - 统一缓存管理入口（避免多处初始化）；
  - 增加平台探测与 wheels 预装，缩短安装时间（numpy/scipy 版本匹配）。
  - 提供 ARM/AMD 多架构镜像（buildx），明确运行内存/CPU 最低要求。

## 商业化差距清单（高优先）
- 交易链路：OMS/订单风控前置（价格/敞口/信用/自成交/黑白名单）、券商/Broker 接入、执行算法（TWAP/VWAP/POV）。
- 数据治理：稳定的历史落库与增量 ETL、CA/停牌/交易日历、复权因子、指标持久化与再利用。
- 实盘观测：统一监控面板、告警、A/B 实验、风控审计日志与合规留痕。
- 安全与权限：多租户、Key/签名、速率限制、配额与成本控制。

## 向量化系统演进（从分析到交易）
- 事件驱动回测引擎：撮合规则（涨跌停、撮合粒度）、费用模型、T+1/卖出可用量、成交与持仓模型（SQLAlchemy 已有骨架）。
- 策略接口：信号→订单→执行，统一回测/仿真/实盘 3 环境。
- 作业编排：夜间数据更新（价格/财报/资讯），指标与特征离线计算落库；热股票预取与缓存预热。

## 本轮完成项（代码路径）
- 历史回退：`src/api/stock_api.py:get_historical_data` 在 DB 无数据时回退到 Tushare→Yahoo→新浪，统一返回 OHLCV；返回 `source` 字段。
- 技术分析：`get_stock_analysis` 使用真实K线计算 MA/RSI/MACD；情绪/基本面保持降级标注。
- 实时行情：`fetch_sina_realtime_sync` 增强请求头，容错解析（GBK）。
- 兼容与健壮：
  - Pydantic v2 兼容：`src/models/stock.py` 采用 `from_attributes`（保留 v1 兼容）。
  - 错误处理携带 request_id：`src/utils/error_handler.py` 读取 `g.request_id`；`src/middleware/auth.py` 生成与透传 X-Request-ID。
  - /health 对齐测试：增加 `services` 汇总字段。
  - Validator 适配：在 `src/middleware/validator.py` 提供 `StockValidator` 适配旧测试；统一 `ValidationError`。
  - Scheduler 小修：移除无效 `self.db_session.close()`。
  - SQL 安全：`validate_query_safety` 不再把普通 `SELECT` 视为注入；装饰器在无请求上下文时安全降级。
  - 测试易用：为 `request` 提供 shim，便于 `patch('src.api.stock_api.request')`。

## 验证（卧龙电驱 600580.SH）
- Realtime：/api/stocks/600580.SH/realtime → 来自新浪，含涨跌幅/成交量。
- Analysis：/api/stocks/600580.SH/analysis?analysis_type=technical → 使用真实K线计算指标；`fundamental/sentiment` 暂降级。
- History：/api/stocks/600580.SH/history?days=30 → DB 无数据时回退到网络，`source=tushare/yahoo/sina`，`data_count≈30`。

结论：情绪与“购入风向标”在未接入真实来源前为占位/降级；技术面基于真实数据并可解释。离线模式下数据来自 `src/services/mock_data.py`，用于演示与断网可用性。

## 仍待办（映射到 todo/ 与 docs/TODO.md）
1) 数据持久化与一致性
- 历史K线与指标落库，避免反复拉取与限流；加 nightly 任务与热股票预取。
- 表结构：`stock_prices` 扩展（复权因子、昨收、是否停牌）、新增 `indicators` 表。

2) 指标扩展与解释
- 增加 BOLL/KDJ/ATR 等；在 `technical_analysis` 中补充解释字段与阈值提示。

3) 基本面与情绪
- 接入 Tushare 财务、新闻/公告渠道与 NLP 管线；去掉“降级”标注。

4) 回测与撮合细节
- 交易日历、涨跌停/撮合、T+1 卖出可用、流动性约束；单元测试补齐。

5) 性能与限流
- 背景预取 + 缓存预热；外部数据调用做熔断/退避；热点队列；限流与配额落库。

6) API/测试对齐
- 局部测试仍有兼容项（性能模拟/SQL 安全阈值等），后续在不影响生产正确性的前提下再对齐。

## 下一步建议（短期可执行）
- [ ] `/history` 数据与指标 nightly 落库 + 简单增量同步脚本（避免线上限流）。
- [ ] 扩展技术指标并在 `/analysis` 给出可操作解读（阈值、背离、形态）。
- [ ] 起草最小 OMS（下单/撤单 API + 订单校验），为纸上实盘做准备。
- [ ] Prometheus 依赖生产可选启用；补全 /metrics 文档与示例 Dashboard。

