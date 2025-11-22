# 股票量化交易系统文档中心

> 一个专业、完整、开箱即用的股票量化交易系统

---

## 📚 文档导航

### 🚀 快速上手
- **[快速启动指南](QUICK_START.md)** - 5分钟快速开始使用系统
- **[API接口文档](API.md)** - 完整的REST API参考
- **[开发者指南](DEVELOPER_GUIDE.md)** - 系统开发和扩展指南

### 📈 量化交易
- **[策略开发指南](trading/STRATEGY_GUIDE.md)** - 策略开发、回测、实盘完整教程
- **[实盘交易指南](trading/LIVE_TRADING.md)** - 实盘交易系统架构与使用
- **[券商对接文档](trading/BROKER_INTEGRATION.md)** - 券商API对接指南

### 🏗️ 系统架构
- **[系统架构说明](ARCHITECTURE.md)** - 技术架构详解
- **[产品路线图](ROADMAP.md)** - 功能规划和发展方向
- **[部署指南](DEPLOYMENT.md)** - 生产环境部署
- **[监控指南](MONITORING_GUIDE.md)** - 系统监控和告警
- **[故障排查指南](TROUBLESHOOTING.md)** - 常见问题解决

---

## 🎯 核心功能

### 📊 数据分析能力
- ✅ **多数据源集成** - 新浪/东方财富/腾讯财经，自动降级
- ✅ **20+技术指标** - MA、RSI、MACD、KDJ、布林带、ATR等
- ✅ **支撑/压力位** - 自动识别关键价位
- ✅ **基本面分析** - PE、PB、ROE、负债率等
- ✅ **ETF专项分析** - 溢价率/跟踪误差/持仓分析

### 📈 量化交易能力
- ✅ **策略回测引擎** - 事件驱动架构，真实历史数据
- ✅ **多种内置策略** - 双均线、均值回归、动量等
- ✅ **参数自动优化** - 网格搜索自动寻找最佳参数
- ✅ **性能分析** - 15项专业指标（Sharpe、Sortino、Calmar等）
- ✅ **成本模型** - 佣金、印花税、滑点精确计算

### 🛡️ 风险管理能力
- ✅ **价格预警系统** - 支撑/压力位、技术指标预警
- ✅ **实时监控工具** - 命令行价格监控，自动提醒
- ✅ **仓位管理器** - 科学计算仓位 + Kelly公式优化
- ✅ **风险预设** - 保守/稳健/激进三套方案
- ✅ **止损止盈计算** - 自动计算目标价位

### 🤖 实盘交易能力
- ✅ **实盘交易引擎** - 完整的事件驱动实时引擎
- ✅ **订单管理** - 下单、撤单、状态跟踪
- ✅ **仓位跟踪** - 实时持仓监控
- ✅ **券商接口** - 支持主流券商API对接

---

## 🚀 快速开始

### 环境要求
- Python 3.11+
- SQLite/PostgreSQL
- Redis (可选，用于缓存)

### 安装系统
```bash
git clone <repo-url>
cd stock
pip install -r requirements.txt
```

### 启动API服务
```bash
export DATABASE_URL=sqlite:///stock_dev.db
export OFFLINE_MODE=false
python src/app.py
```

### 分析第一只股票
```bash
curl http://localhost:5000/api/stocks/603993.SH/analysis?analysis_type=all
```

详细教程请查看 **[快速启动指南](QUICK_START.md)**

---

## 📖 学习路径

### 初学者路径
1. 阅读 [快速启动指南](QUICK_START.md)
2. 了解 [API接口文档](API.md)
3. 运行第一个回测 - 参考 [策略开发指南](trading/STRATEGY_GUIDE.md)

### 策略开发者路径
1. 学习 [策略开发指南](trading/STRATEGY_GUIDE.md)
2. 了解 [系统架构说明](ARCHITECTURE.md)
3. 阅读 [开发者指南](DEVELOPER_GUIDE.md)
4. 开发自定义策略

### 实盘交易者路径
1. 完成回测验证 - [策略开发指南](trading/STRATEGY_GUIDE.md)
2. 学习 [实盘交易指南](trading/LIVE_TRADING.md)
3. 对接券商API - [券商对接文档](trading/BROKER_INTEGRATION.md)
4. 配置监控告警 - [监控指南](MONITORING_GUIDE.md)

### 系统管理员路径
1. 学习 [部署指南](DEPLOYMENT.md)
2. 配置 [监控告警](MONITORING_GUIDE.md)
3. 掌握 [故障排查](TROUBLESHOOTING.md)

---

## 🔗 外部资源

### 学习资料
- [量化交易基础](study/README.md)
- [Python量化学习计划](study/LEARNING_PLAN_CN.md)

### 社区与支持
- 📧 GitHub Issues - 问题反馈
- 💬 GitHub Discussions - 讨论交流
- 📝 Pull Requests - 贡献代码

---

## 📊 版本信息

**文档版本**: v2.1
**系统版本**: v2.1
**最后更新**: 2025-11-22

查看完整 [产品路线图](ROADMAP.md) 了解未来规划。

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](../LICENSE) 文件了解详情
