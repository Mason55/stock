# 快速启动指南

本指南提供多种启动方式，从最简单的离线模式到完整的生产部署。

## 🚀 最小启动 (推荐新手)

无需安装数据库和Redis，使用内存数据库和模拟数据：

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd stock

# 2. 安装最小依赖
pip install -r build/requirements/minimal.txt

# 3. 设置环境变量
export DATABASE_URL="sqlite:///dev.db"
export OFFLINE_MODE=true
export USE_REDIS=false
export LOG_TO_FILE=false

# 4. 启动应用
python src/app.py

# 5. 测试API
curl http://localhost:5000/api/stocks/health
```

## 🐳 Docker 快速启动

### 最小镜像 (无ML依赖)
```bash
# 构建最小镜像
./scripts/build.sh --type minimal

# 运行
docker run -p 5000:5000 -e OFFLINE_MODE=true stock-analysis:minimal

# 测试
curl http://localhost:5000/api/stocks/health
```

### 完整镜像
```bash
# 构建完整镜像
./scripts/build.sh --type full

# 运行
docker run -p 5000:5000 \
  -e DATABASE_URL="sqlite:///stock.db" \
  -e OFFLINE_MODE=true \
  stock-analysis:latest
```

## 🔧 开发环境启动

### 使用虚拟环境
```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 2. 安装开发依赖
pip install -r build/requirements/dev.txt

# 3. 复制环境配置
cp .env.example .env

# 4. 编辑.env文件设置数据库等配置

# 5. 启动应用
python src/app.py
```

### 使用Docker Compose
```bash
# 启动所有服务 (PostgreSQL + Redis + API)
docker-compose -f build/docker/docker-compose.yml up -d

# 查看日志
docker-compose logs -f api

# 停止服务
docker-compose -f build/docker/docker-compose.yml down
```

## 🧪 测试系统

### 健康检查
```bash
# 基础健康检查
curl http://localhost:5000/api/stocks/health

# 详细健康检查
curl http://localhost:5000/metrics/health

# 查看度量
curl http://localhost:5000/metrics/
```

### 股票查询测试
```bash
# 查询长江电力 (离线模式会返回模拟数据)
curl http://localhost:5000/api/stocks/600900.SH

# 综合分析
curl http://localhost:5000/api/stocks/600900.SH/analysis

# 实时数据
curl http://localhost:5000/api/stocks/600900.SH/realtime

# 批量分析
curl -X POST http://localhost:5000/api/stocks/batch_analysis \
  -H "Content-Type: application/json" \
  -d '{"stock_codes": ["600900.SH", "600036.SH"], "analysis_types": ["technical"]}'
```

### 运行测试脚本
```bash
# 简化测试
python simple_test.py

# API测试
python test_query.py
```

## 🌍 不同环境配置

### 离线/受限网络环境
```bash
# 设置离线模式
export OFFLINE_MODE=true
export MOCK_DATA_ENABLED=true
export USE_REDIS=false
export LOG_TO_FILE=false

# 使用SQLite数据库
export DATABASE_URL="sqlite:///stock.db"

# 启动
python src/app.py
```

### 仅基础功能 (无ML)
```bash
# 安装基础依赖
pip install -r build/requirements/base.txt

# 设置配置
export DATABASE_URL="sqlite:///stock.db"
export OFFLINE_MODE=false
export USE_REDIS=true

# 启动 (某些ML相关功能会降级)
python src/app.py
```

### 生产环境
```bash
# 设置生产配置
export DEPLOYMENT_MODE=production
export LOG_LEVEL=WARNING
export LOG_TO_FILE=true
export DEBUG=false

# 使用生产数据库
export DATABASE_URL="postgresql://user:pass@host:5432/stockdb"

# 启动
python src/app.py
```

## 🔍 故障排查

### 常见问题

1. **数据库连接失败**
   ```bash
   # 检查连接
   export DATABASE_URL="sqlite:///test.db"
   python -c "from src.database import db_manager; print(db_manager.health_check())"
   ```

2. **依赖安装失败**
   ```bash
   # 使用最小依赖
   pip install -r build/requirements/minimal.txt
   
   # 或使用约束版本
   pip install -r build/requirements/base.txt -c build/requirements/constraints.txt
   ```

3. **端口冲突**
   ```bash
   # 更改端口
   export API_PORT=8080
   python src/app.py
   ```

4. **权限问题**
   ```bash
   # 禁用文件日志
   export LOG_TO_FILE=false
   python src/app.py
   ```

### 调试模式
```bash
# 启用调试
export DEBUG=true
export LOG_LEVEL=DEBUG

# 查看调试信息
curl http://localhost:5000/metrics/debug
```

## 📋 验证清单

启动后验证以下功能：

- [ ] 健康检查返回200: `curl http://localhost:5000/api/stocks/health`
- [ ] 根端点可访问: `curl http://localhost:5000/`
- [ ] 股票查询正常: `curl http://localhost:5000/api/stocks/600900.SH`
- [ ] 分析功能正常: `curl http://localhost:5000/api/stocks/600900.SH/analysis`
- [ ] 度量端点可用: `curl http://localhost:5000/metrics/`
- [ ] 批量分析正常: 参考上述批量分析curl命令

## 🔗 相关链接

- [API文档](API.md)
- [部署指南](DEPLOYMENT.md)
- [故障排查](TROUBLESHOOTING.md)
- [性能优化](PERFORMANCE.md)