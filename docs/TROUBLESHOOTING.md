# 故障排查指南

本指南收录常见问题及解决方案，帮助快速诊断和修复系统问题。

## 🩺 快速诊断

### 系统健康检查

```bash
# 1. 基础健康检查
curl http://localhost:5000/api/stocks/health

# 2. 详细健康检查  
curl http://localhost:5000/metrics/health

# 3. 系统度量
curl http://localhost:5000/metrics/

# 4. 调试信息 (开发环境)
curl http://localhost:5000/metrics/debug
```

### 日志查看

```bash
# 查看应用日志
tail -f logs/app.log

# Docker日志
docker logs stock-api

# Docker Compose日志
docker-compose logs -f api
```

## ❌ 常见启动问题

### 问题1: 数据库连接失败

**错误信息:**
```
DatabaseError: Database session not available
FATAL: password authentication failed for user "postgres"
```

**解决方案:**

```bash
# 方案1: 使用SQLite
export DATABASE_URL="sqlite:///stock.db"
python src/app.py

# 方案2: 检查PostgreSQL连接
pg_isready -h localhost -p 5432

# 方案3: 使用Docker Compose启动数据库
docker-compose up -d postgres

# 方案4: 降级到内存数据库
export DATABASE_URL="sqlite:///:memory:"
```

### 问题2: Redis连接失败

**错误信息:**
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**解决方案:**

```bash
# 方案1: 禁用Redis
export USE_REDIS=false
python src/app.py

# 方案2: 启动Redis
docker run -d -p 6379:6379 redis:alpine

# 方案3: 启用离线模式 (自动禁用Redis)
export OFFLINE_MODE=true
```

### 问题3: 依赖安装失败

**错误信息:**
```
ERROR: Could not build wheels for lightgbm
Microsoft Visual C++ 14.0 is required
```

**解决方案:**

```bash
# 方案1: 使用最小依赖
pip install -r requirements-minimal.txt

# 方案2: 使用约束安装
pip install -r requirements-base.txt -c constraints.txt

# 方案3: 跳过ML依赖
pip install -r requirements-base.txt

# 方案4: 使用Docker
docker build -f Dockerfile.minimal -t stock:minimal .

# 方案5: Windows用户使用WSL2
wsl --install
```

### 问题4: 端口冲突

**错误信息:**
```
OSError: [Errno 98] Address already in use
```

**解决方案:**

```bash
# 查找占用端口的进程
lsof -i :5000
netstat -tulpn | grep 5000

# 杀死进程
kill -9 <PID>

# 或使用不同端口
export API_PORT=8080
python src/app.py
```

## 🔧 运行时问题

### 问题5: 权限错误

**错误信息:**
```
PermissionError: [Errno 13] Permission denied: 'logs/app.log'
```

**解决方案:**

```bash
# 方案1: 禁用文件日志
export LOG_TO_FILE=false
python src/app.py

# 方案2: 创建日志目录
mkdir -p logs
chmod 755 logs

# 方案3: 使用Docker非root用户
docker run --user $(id -u):$(id -g) stock:minimal
```

### 问题6: 内存不足

**错误信息:**
```
MemoryError: Unable to allocate array
```

**解决方案:**

```bash
# 方案1: 减少批处理大小
export BATCH_SIZE=100

# 方案2: 使用最小依赖 (跳过ML)
pip install -r requirements-minimal.txt

# 方案3: 增加虚拟内存
# Linux: 
sudo swapon --show
sudo fallocate -l 2G /swapfile

# 方案4: 优化Docker内存
docker run -m 512m stock:minimal
```

### 问题7: API响应慢

**症状:** 请求超时或响应时间过长

**诊断:**

```bash
# 检查响应时间
curl -w "@curl-format.txt" http://localhost:5000/api/stocks/health

# 查看系统资源
top
htop
docker stats
```

**解决方案:**

```bash
# 方案1: 启用离线模式 (避免外部API调用)
export OFFLINE_MODE=true

# 方案2: 调整超时设置
export API_TIMEOUT=10.0
export EXTERNAL_API_TIMEOUT=10.0

# 方案3: 启用缓存
export USE_REDIS=true

# 方案4: 减少批处理大小
export BATCH_SIZE=50
```

## 🌐 网络相关问题

### 问题8: 外部API访问失败

**错误信息:**
```
requests.exceptions.ConnectionError: HTTPSConnectionPool
```

**解决方案:**

```bash
# 方案1: 启用离线模式
export OFFLINE_MODE=true

# 方案2: 检查网络连接
ping 8.8.8.8
curl -I https://www.google.com

# 方案3: 配置代理 (如需要)
export HTTP_PROXY=http://proxy:8080
export HTTPS_PROXY=http://proxy:8080

# 方案4: 增加重试次数
export EXTERNAL_API_RETRIES=5
```

### 问题9: CORS错误

**错误信息:**
```
Access to fetch at 'http://localhost:5000' has been blocked by CORS policy
```

**解决方案:**

```bash
# 方案1: 配置CORS源
export CORS_ORIGINS="http://localhost:3000,http://localhost:8080"

# 方案2: 允许所有源 (仅开发环境)
export CORS_ORIGINS="*"

# 方案3: 检查前端请求URL
# 确保使用正确的端口和协议
```

## 🐳 Docker相关问题

### 问题10: Docker构建失败

**错误信息:**
```
ERROR: failed to solve: process "/bin/sh -c pip install" did not complete
```

**解决方案:**

```bash
# 方案1: 使用最小镜像
docker build -f Dockerfile.minimal -t stock:minimal .

# 方案2: 增加构建内存
docker build --memory=2g -t stock:app .

# 方案3: 清理Docker缓存
docker system prune -a

# 方案4: 分步构建
docker build --target builder -t stock:builder .
docker build --target runtime -t stock:runtime .
```

### 问题11: 容器启动失败

**错误信息:**
```
docker: Error response from daemon: failed to create shim
```

**解决方案:**

```bash
# 方案1: 检查Docker守护进程
sudo systemctl status docker
sudo systemctl restart docker

# 方案2: 清理容器
docker container prune

# 方案3: 检查磁盘空间
df -h
docker system df

# 方案4: 重启Docker
sudo systemctl restart docker
```

## 🔍 调试技巧

### 启用详细日志

```bash
# 应用级别调试
export LOG_LEVEL=DEBUG
export DEBUG=true

# SQL查询日志
export DATABASE_URL="postgresql://user:pass@host/db?echo=true"

# 网络请求日志
export PYTHONPATH=. python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# 然后启动应用
"
```

### 使用Python调试器

```python
# 在代码中添加断点
import pdb; pdb.set_trace()

# 或使用ipdb (更好的调试器)
import ipdb; ipdb.set_trace()
```

### 性能分析

```bash
# CPU性能分析
pip install py-spy
py-spy top --pid $(pgrep python)

# 内存分析
pip install memory-profiler
python -m memory_profiler src/app.py

# 请求分析
curl -w "@curl-format.txt" http://localhost:5000/api/stocks/health
```

## 📊 监控和度量

### 实时监控

```bash
# 查看实时度量
watch -n 1 'curl -s http://localhost:5000/metrics/ | grep stock_api'

# 系统资源监控
htop
iotop
nethogs

# Docker资源监控
docker stats
```

### 日志分析

```bash
# 错误日志统计
grep ERROR logs/app.log | wc -l

# 响应时间分析
grep "Response:" logs/app.log | awk '{print $NF}' | sort -n

# 请求路径统计
grep "Request:" logs/app.log | awk '{print $4}' | sort | uniq -c
```

## 🔄 数据恢复

### 数据库恢复

```bash
# SQLite备份
cp stock.db stock.db.backup

# PostgreSQL备份
pg_dump stockdb > backup.sql

# 恢复
psql stockdb < backup.sql
```

### 重置系统状态

```bash
# 清理所有数据
rm -f stock.db logs/*.log

# 重建数据库
export DATABASE_URL="sqlite:///stock.db"
python -c "from src.database import db_manager; db_manager._setup_database()"

# 重启服务
docker-compose restart
```

## 📞 获取帮助

### 诊断信息收集

运行以下命令收集诊断信息：

```bash
#!/bin/bash
# 诊断信息收集脚本

echo "=== 系统信息 ==="
uname -a
python --version
pip --version

echo "=== Docker信息 ==="
docker --version
docker-compose --version

echo "=== 网络连接 ==="
curl -I http://localhost:5000/api/stocks/health

echo "=== 日志 (最近50行) ==="
tail -50 logs/app.log

echo "=== 进程信息 ==="
ps aux | grep python

echo "=== 磁盘空间 ==="
df -h

echo "=== 内存使用 ==="
free -h
```

### 常用检查清单

启动问题检查清单：

- [ ] Python版本 >= 3.8
- [ ] 依赖安装完成
- [ ] 环境变量配置正确
- [ ] 端口5000未被占用
- [ ] 数据库连接可用
- [ ] 磁盘空间充足
- [ ] 权限设置正确

性能问题检查清单：

- [ ] 系统资源充足 (CPU/内存)
- [ ] 网络连接正常
- [ ] 数据库性能正常
- [ ] 缓存服务可用
- [ ] 日志级别合理

## 🔗 相关资源

- [快速启动指南](QUICK_START.md)
- [便携性指南](PORTABILITY.md)
- [API文档](API.md)
- [部署指南](DEPLOYMENT.md)