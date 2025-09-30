# 股票量化交易系统

一个高度可移植的现代化股票量化交易系统，集成数据分析、策略回测、实盘交易全流程。

## ✨ 核心功能

### 📊 数据分析
- 🚀 **多数据源集成** - 新浪财经、Yahoo Finance、Tushare，支持自动降级
- 📈 **深度技术分析** - 20+专业指标：MA、RSI、MACD、布林带等
- 💼 **基本面分析** - 估值、盈利能力、成长性、财务健康度评估
- 😊 **情绪分析** - 新闻舆情、社交媒体情绪、分析师观点

### 🎯 量化交易 (NEW)
- 📈 **策略回测引擎** - 事件驱动架构，支持多策略并行
- 🤖 **实盘交易框架** - 完整的订单管理、仓位跟踪、风控系统
- 💡 **内置策略库** - 双均线、均值回归、动量策略等经典策略
- ⚙️ **灵活配置系统** - YAML配置，支持策略组合
- 📊 **性能分析** - 夏普比率、最大回撤、收益归因等完整指标

### 🛡️ 系统特性
- ⚡ **高性能架构** - 异步处理，支持批量分析
- 🔒 **风控保护** - 订单限流、仓位限制、熔断机制
- 🎨 **健壮性设计** - 故障转移、自动降级、离线模式

## 🎯 便携性亮点

- 🌐 **跨平台支持** - Linux/macOS/Windows，Docker/裸机部署
- 📦 **分层依赖** - 最小/基础/完整三套依赖，支持渐进式安装
- 🔌 **可选组件** - Redis/PostgreSQL可选，自动降级到SQLite/内存
- 🚫 **离线模式** - 完整的模拟数据服务，无网络依赖
- 🏗️ **零配置启动** - 开箱即用，智能默认配置

## ⚡ 快速启动

### 🚀 数据分析API (< 1分钟)
```bash
# 安装依赖
pip install -r requirements.txt

# 启动API服务
export OFFLINE_MODE=true DATABASE_URL=sqlite:///dev.db
python src/app.py

# 测试股票查询
curl http://localhost:5000/api/stocks/600900.SH
```

### 📈 量化策略回测 (NEW)
```bash
# 回测双均线策略
python examples/backtest_strategies.py --strategy moving_average --symbol 600036.SH --days 60

# 回测策略组合
python examples/backtest_strategies.py --combination balanced --days 90

# 查看所有策略
python examples/backtest_strategies.py --help
```

### 🐳 Docker启动 (< 2分钟)
```bash
# 最小镜像
./scripts/build.sh --type minimal
docker run -p 5000:5000 -e OFFLINE_MODE=true stock-analysis:minimal

# 完整部署
docker-compose -f build/docker/docker-compose.yml up -d
```

### 🔧 开发环境
```bash
git clone <repo-url> && cd stock
pip install -r build/requirements/dev.txt
cp .env.example .env  # 编辑配置
python src/app.py
```

## 🧪 系统验证

```bash
# 自动验证所有功能
./scripts/validate.sh

# 查看详细健康状态
curl http://localhost:5000/metrics/health

# 测试股票查询 (长江电力)
curl http://localhost:5000/api/stocks/600900.SH/analysis
```

## 📊 API 示例

### 股票基础信息
```bash
curl http://localhost:5000/api/stocks/600900.SH
```

### 综合分析
```bash
curl http://localhost:5000/api/stocks/600900.SH/analysis?analysis_type=all
```

### 批量分析
```bash
curl -X POST http://localhost:5000/api/stocks/batch_analysis \
  -H "Content-Type: application/json" \
  -d '{"stock_codes": ["600900.SH", "600036.SH"], "analysis_types": ["technical"]}'
```

## 🛠️ 环境配置

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `DATABASE_URL` | PostgreSQL连接 | 数据库连接，支持SQLite |
| `OFFLINE_MODE` | false | 离线模式，使用模拟数据 |
| `USE_REDIS` | true | 是否使用Redis缓存 |
| `LOG_TO_FILE` | true | 是否记录文件日志 |
| `CORS_ORIGINS` | localhost:3000 | 允许的跨域源 |

完整配置请参考 [.env.example](.env.example)

## 📖 文档导航

### 量化交易文档 (NEW)
- 🎯 [策略使用指南](STRATEGY_GUIDE.md) - 策略开发、回测、实盘完整教程
- 🔴 [实盘交易文档](LIVE_TRADING_IMPLEMENTATION.md) - 实盘系统架构与使用
- 📋 [项目TODO](docs/TODO.md) - 开发路线图与进度

### 用户文档
- 📚 [快速启动指南](docs/QUICK_START.md) - 多种启动方式详解
- 🔧 [API接口文档](docs/API.md) - 完整API参考
- 🌐 [便携性指南](docs/PORTABILITY.md) - 跨平台部署最佳实践
- 🚨 [故障排查指南](docs/TROUBLESHOOTING.md) - 常见问题解决

### 开发文档
- 🏗️ [系统架构说明](docs/ARCHITECTURE.md) - 技术架构详解
- 🚀 [部署指南](docs/DEPLOYMENT.md) - 生产环境部署
- 📈 [性能优化](docs/PERFORMANCE.md) - 性能调优建议

## 🗂️ 项目结构

```
stock/
├── src/                    # 源代码
│   ├── api/               # API接口层
│   ├── services/          # 业务服务
│   ├── trading/           # ⚡ 实盘交易 (NEW)
│   ├── strategies/        # 📈 策略库 (NEW)
│   ├── backtest/          # 🧪 回测引擎 (NEW)
│   ├── database/          # 数据库管理
│   ├── models/            # 数据模型 (含trading/market_data)
│   ├── middleware/        # 中间件
│   └── utils/             # 工具函数
├── config/                # ⚙️ 配置文件
│   └── strategies.yaml   # 策略配置 (NEW)
├── docs/                  # 文档
├── examples/              # 📚 示例代码
│   └── backtest_strategies.py  # 回测示例 (NEW)
├── tests/                 # 🧪 测试
│   ├── test_live_trading.py   # 实盘测试 (NEW)
│   └── test_strategies.py      # 策略测试 (NEW)
├── scripts/               # 脚本工具
├── build/                 # 构建相关文件
├── STRATEGY_GUIDE.md      # 📖 策略指南 (NEW)
├── LIVE_TRADING_IMPLEMENTATION.md  # 🔴 实盘文档 (NEW)
└── pyproject.toml        # 项目配置
```

## 🔄 运行模式

| 模式 | 依赖 | 启动时间 | 适用场景 |
|------|------|----------|----------|
| **数据分析模式** | 最小 | <1分钟 | API服务、数据查询 |
| **策略回测模式** | 中等 | <1分钟 | 策略开发、历史验证 |
| **纸上交易模式** | 完整 | <2分钟 | 实时模拟、策略验证 |
| **实盘交易模式** | 完整+券商 | <3分钟 | 真实交易 (需券商接口) |

## 📊 量化系统进度

| 阶段 | 状态 | 模块 | 测试 |
|------|------|------|------|
| **阶段1: 实盘基础** | ✅ 完成 | 5个核心模块 | 11/11通过 |
| **阶段2: 策略库** | ✅ 完成 | 3个经典策略 | 13/16通过 |
| **阶段3: 风控增强** | 📋 计划中 | 动态风控/仓位管理 | - |
| **阶段4: 生产化** | 📋 计划中 | 监控/告警/优化 | - |

详见: [项目TODO](docs/TODO.md)

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出改进建议！

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 支持

- 📧 问题反馈：通过 GitHub Issues
- 📖 文档：查看 `docs/` 目录
- 🔧 故障排查：参考 [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
