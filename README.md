# 股票分析系统

一个高度可移植的现代化股票分析系统，支持技术分析、基本面分析和情绪分析。

## ✨ 功能特性

- 🚀 **多数据源集成** - 新浪财经、Yahoo Finance，支持自动降级
- 📊 **深度技术分析** - 20+专业指标：KDJ、布林带、威廉指标等
- 💼 **基本面分析** - 估值、盈利能力、成长性、财务健康度评估
- 😊 **情绪分析** - 新闻舆情、社交媒体情绪、分析师观点
- 🎯 **智能投资建议** - 多维度综合评分与风险评估
- ⚡ **高性能架构** - 异步处理，支持批量分析
- 🛡️ **健壮性设计** - 故障转移、自动降级、离线模式

## 🎯 便携性亮点

- 🌐 **跨平台支持** - Linux/macOS/Windows，Docker/裸机部署
- 📦 **分层依赖** - 最小/基础/完整三套依赖，支持渐进式安装
- 🔌 **可选组件** - Redis/PostgreSQL可选，自动降级到SQLite/内存
- 🚫 **离线模式** - 完整的模拟数据服务，无网络依赖
- 🏗️ **零配置启动** - 开箱即用，智能默认配置

## ⚡ 快速启动

### 🚀 最简启动 (< 1分钟)
```bash
# 无需数据库，使用模拟数据
pip install -r build/requirements/minimal.txt
export OFFLINE_MODE=true DATABASE_URL=sqlite:///dev.db
python src/app.py

# 测试
curl http://localhost:5000/api/stocks/600900.SH
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
│   ├── database/          # 数据库管理
│   ├── models/            # 数据模型
│   ├── middleware/        # 中间件
│   └── utils/             # 工具函数
├── docs/                  # 文档
├── scripts/               # 脚本工具
├── build/                 # 构建相关文件
│   ├── docker/           # Docker相关文件
│   └── requirements/     # 分层依赖文件
├── pyproject.toml        # 项目配置
└── examples/             # 示例代码
```

## 🔄 运行模式

| 模式 | 依赖 | 启动时间 | 适用场景 |
|------|------|----------|----------|
| **离线模式** | 最小 | <1分钟 | 演示、测试、离线环境 |
| **基础模式** | 中等 | <3分钟 | 开发、小规模部署 |
| **完整模式** | 完整 | <5分钟 | 生产环境、大规模部署 |

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
