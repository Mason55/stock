# Stock Analysis System - 部署指南

## 快速部署

### 1. 环境要求
- Docker 20.10+
- Docker Compose 2.0+
- 至少 4GB RAM
- 至少 10GB 磁盘空间

### 2. 部署步骤

```bash
# 1. 克隆或复制项目文件到目标服务器
# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置数据库密码等

# 3. 运行部署脚本
./deploy.sh

# 或者手动部署
docker-compose -f docker-compose.prod.yml up -d
```

### 3. 验证部署
访问 http://localhost:5000 检查应用是否正常运行

## 详细配置

### 环境变量说明
```bash
# 数据库配置
DATABASE_URL=postgresql://postgres:password@db:5432/stockdb
POSTGRES_DB=stockdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-password

# Redis配置
REDIS_URL=redis://redis:6379

# Kafka配置
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# API配置
API_HOST=0.0.0.0
API_PORT=5000
DEBUG=False

# 外部数据源
STOCK_DATA_API_KEY=your_api_key_here
STOCK_DATA_BASE_URL=https://api.example.com
```

### 生产环境优化

#### 1. 安全配置
- 修改默认密码
- 使用 HTTPS（需要反向代理）
- 限制网络访问

#### 2. 性能优化
- 根据服务器配置调整容器资源限制
- 配置数据库连接池
- 启用 Redis 持久化

#### 3. 监控
- 查看日志：`docker-compose -f docker-compose.prod.yml logs -f`
- 监控资源：`docker stats`

## 常用命令

```bash
# 启动服务
./deploy.sh

# 停止服务
docker-compose -f docker-compose.prod.yml down

# 重启服务
docker-compose -f docker-compose.prod.yml restart

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f

# 进入应用容器
docker-compose -f docker-compose.prod.yml exec app bash

# 备份数据库
docker-compose -f docker-compose.prod.yml exec db pg_dump -U postgres stockdb > backup.sql

# 清理未使用的镜像
docker system prune -a
```

## 故障排除

### 常见问题

1. **端口冲突**
   - 检查 5000、5432、6379、9092 端口是否被占用
   - 修改 docker-compose.prod.yml 中的端口映射

2. **内存不足**
   - 增加服务器内存
   - 减少容器数量或调整资源限制

3. **数据库连接失败**
   - 检查 .env 文件中的数据库配置
   - 确认数据库容器正常启动

4. **Kafka 连接问题**
   - 检查 Zookeeper 是否正常启动
   - 确认网络连接

### 日志分析
```bash
# 查看所有服务日志
docker-compose -f docker-compose.prod.yml logs

# 查看特定服务日志
docker-compose -f docker-compose.prod.yml logs app
docker-compose -f docker-compose.prod.yml logs db
```

## 更新部署

1. 停止现有服务
2. 拉取新代码
3. 重新构建镜像
4. 启动服务

```bash
docker-compose -f docker-compose.prod.yml down
git pull  # 如果使用 git
./build.sh
./deploy.sh
```