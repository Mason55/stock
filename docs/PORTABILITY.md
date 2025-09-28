# 系统便携性指南

本文档详细说明系统的便携性特性和跨平台部署最佳实践。

## 🎯 便携性概览

### 支持的运行模式

| 模式 | 依赖要求 | 适用场景 | 数据来源 |
|------|----------|----------|----------|
| **离线模式** | 最小 | 无网络/演示/测试 | 模拟数据 |
| **基础模式** | 中等 | 开发/小规模部署 | 数据库+模拟 |
| **完整模式** | 完整 | 生产环境 | 数据库+外部API |

### 跨平台支持

| 平台 | Docker | 本地安装 | 备注 |
|------|--------|----------|------|
| **Linux** | ✅ 完全支持 | ✅ 完全支持 | 推荐平台 |
| **macOS** | ✅ 完全支持 | ✅ 完全支持 | M1/Intel均支持 |
| **Windows** | ✅ 完全支持 | ⚠️ 部分限制 | WSL2推荐 |

## 🔧 配置层次

系统采用多层次配置，按优先级从高到低：

1. **环境变量** - 运行时覆盖
2. **配置文件** (.env) - 项目配置  
3. **默认值** - 代码中的合理默认

### 关键配置项

```bash
# 便携性相关的关键配置
OFFLINE_MODE=true/false          # 离线模式开关
MOCK_DATA_ENABLED=true/false     # 模拟数据开关
USE_REDIS=true/false             # Redis使用开关
LOG_TO_FILE=true/false           # 文件日志开关
DATABASE_URL=sqlite:///stock.db  # 数据库连接
CORS_ORIGINS=http://localhost:3000 # CORS设置
```

## 📦 依赖管理策略

### 分层依赖文件

```
requirements-minimal.txt    # 最小依赖 (~15个包)
requirements-base.txt       # 基础依赖 (~25个包)
requirements-ml.txt         # ML相关依赖 (~15个包)
requirements-dev.txt        # 开发工具依赖
requirements.txt            # 完整依赖 (组合上述)
constraints.txt             # 版本约束
```

### 依赖安装策略

```bash
# 1. 最小安装 (快速启动)
pip install -r requirements-minimal.txt

# 2. 渐进式安装
pip install -r requirements-base.txt
pip install -r requirements-ml.txt  # 可选

# 3. 受约束安装 (保证兼容性)
pip install -r requirements.txt -c constraints.txt

# 4. 离线安装
cd wheels/
./install.sh
```

## 🐳 容器化部署

### 多阶段构建

```dockerfile
# 构建阶段 - 包含构建工具
FROM python:3.11-slim-bookworm as builder
# ... 安装依赖

# 运行阶段 - 最小运行时
FROM python:3.11-slim-bookworm as runtime
# ... 复制文件和依赖
```

### 构建选项

```bash
# 完整镜像 (包含ML)
docker build --build-arg INSTALL_ML=true -t stock:full .

# 最小镜像 (无ML)
docker build -f Dockerfile.minimal -t stock:minimal .

# 跨平台构建
docker buildx build --platform linux/amd64,linux/arm64 .
```

## 🗄️ 数据库适配

### 支持的数据库

| 数据库 | 使用场景 | 配置示例 |
|--------|----------|----------|
| **SQLite** | 开发/测试/小规模 | `sqlite:///stock.db` |
| **PostgreSQL** | 生产环境 | `postgresql://user:pass@host/db` |
| **内存数据库** | 临时/测试 | `sqlite:///:memory:` |

### 数据库降级策略

1. **尝试配置的数据库**
2. **降级到SQLite文件**
3. **最终降级到内存数据库**

```python
# 自动降级逻辑
try:
    # 使用配置的数据库
    engine = create_engine(DATABASE_URL)
except:
    # 降级到SQLite
    engine = create_engine("sqlite:///fallback.db")
```

## 🌐 网络和外部服务

### 外部依赖处理

| 服务 | 必需性 | 降级策略 |
|------|--------|----------|
| **PostgreSQL** | 可选 | → SQLite |
| **Redis** | 可选 | → 内存缓存 |
| **外部API** | 可选 | → 模拟数据 |
| **网络访问** | 可选 | → 离线模式 |

### 离线模式特性

```bash
# 启用离线模式
export OFFLINE_MODE=true

# 自动效果:
# - 禁用外部API调用
# - 使用模拟数据服务
# - 禁用Redis (可选)
# - 使用本地数据库
```

## 🔧 环境适配

### 开发环境

```bash
# 最小开发环境
DATABASE_URL=sqlite:///dev.db
OFFLINE_MODE=true
USE_REDIS=false
LOG_TO_FILE=false
DEBUG=true
```

### CI/CD环境

```bash
# CI测试配置
DATABASE_URL=sqlite:///:memory:
OFFLINE_MODE=true
USE_REDIS=false
LOG_TO_FILE=false
LOG_LEVEL=WARNING
```

### 生产环境

```bash
# 生产配置
DATABASE_URL=postgresql://...
OFFLINE_MODE=false
USE_REDIS=true
LOG_TO_FILE=true
LOG_LEVEL=INFO
DEPLOYMENT_MODE=production
```

### 边缘/受限环境

```bash
# 资源受限环境
DATABASE_URL=sqlite:///stock.db
OFFLINE_MODE=true
USE_REDIS=false
LOG_TO_FILE=false
API_TIMEOUT=10.0
BATCH_SIZE=100
```

## 🚀 启动模式

### 模式1: 极简启动 (< 1分钟)

```bash
pip install -r requirements-minimal.txt
export DATABASE_URL=sqlite:///dev.db OFFLINE_MODE=true
python src/app.py
```

### 模式2: 容器启动 (< 2分钟)

```bash
docker run -p 5000:5000 -e OFFLINE_MODE=true stock:minimal
```

### 模式3: 完整启动 (< 5分钟)

```bash
docker-compose up -d
```

## 🧪 验证清单

### 基础功能验证

```bash
# 1. 服务启动
curl -f http://localhost:5000/api/stocks/health

# 2. 模拟数据查询
curl http://localhost:5000/api/stocks/600900.SH

# 3. 分析功能
curl http://localhost:5000/api/stocks/600900.SH/analysis

# 4. 批量处理
curl -X POST http://localhost:5000/api/stocks/batch_analysis \
  -H "Content-Type: application/json" \
  -d '{"stock_codes": ["600900.SH"]}'
```

### 跨平台验证

```bash
# 在不同操作系统上验证
scripts/test-platform.sh

# Docker跨架构测试
docker buildx build --platform linux/amd64,linux/arm64 .
```

### 网络隔离验证

```bash
# 断网测试
export OFFLINE_MODE=true
python src/app.py
# 验证所有API仍然工作
```

## ⚠️ 已知限制

### Windows平台

- **ML依赖**: LightGBM/XGBoost可能需要Visual Studio构建工具
- **解决方案**: 使用Docker或WSL2

### 受限网络

- **外部API**: 无法获取实时数据
- **解决方案**: 启用OFFLINE_MODE

### 资源受限环境

- **内存**: ML模型可能消耗大量内存
- **解决方案**: 使用requirements-minimal.txt

### 权限受限环境

- **文件写入**: 日志和数据库文件创建可能失败
- **解决方案**: 设置LOG_TO_FILE=false和内存数据库

## 🔧 故障排查

### 依赖问题

```bash
# 检查依赖兼容性
pip check

# 使用约束安装
pip install -r requirements.txt -c constraints.txt

# 最小化安装
pip install -r requirements-minimal.txt
```

### 网络问题

```bash
# 测试网络连接
curl -I https://api.example.com

# 启用离线模式
export OFFLINE_MODE=true
```

### 权限问题

```bash
# 检查文件权限
ls -la logs/

# 禁用文件写入
export LOG_TO_FILE=false
```

## 📈 性能调优

### 内存优化

```bash
# 减少批处理大小
export BATCH_SIZE=100

# 禁用非必需服务
export USE_REDIS=false
```

### 启动优化

```bash
# 跳过数据库初始化
export DATABASE_URL=sqlite:///:memory:

# 使用预构建镜像
docker pull stock:minimal
```

## 🔗 相关资源

- [快速启动指南](QUICK_START.md)
- [Docker部署指南](DEPLOYMENT.md)
- [API文档](API.md)
- [故障排查指南](TROUBLESHOOTING.md)