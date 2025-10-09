# 部署检查清单 - 2025改进

## 📋 部署前准备

### 1. 环境检查
- [ ] Python 3.8+ 已安装
- [ ] PostgreSQL/SQLite 数据库可用
- [ ] Redis 可用（可选，推荐）
- [ ] 磁盘空间充足（至少 5GB 可用）

### 2. 代码同步
```bash
git pull origin main
git checkout <release-tag>  # 或使用特定分支
```

### 3. 依赖安装
```bash
# 基础依赖
pip install -r requirements.txt

# 可选：Prometheus监控
pip install prometheus-client

# 验证安装
python -c "import prometheus_client; print('✅ Prometheus client installed')"
```

---

## 🗄️ 数据库迁移

### PostgreSQL
```bash
# 1. 备份现有数据库
pg_dump -U postgres stock_db > backup_$(date +%Y%m%d).sql

# 2. 创建新表
psql -U postgres -d stock_db -f scripts/create_new_tables.sql

# 3. 验证表结构
psql -U postgres -d stock_db -c "\dt technical_*"
```

### SQLite (开发环境)
```bash
# 1. 备份
cp stock_dev.db stock_dev.db.backup

# 2. 创建新表
sqlite3 stock_dev.db < scripts/create_new_tables.sql

# 3. 验证
sqlite3 stock_dev.db ".tables"
```

---

## ✅ 功能验证

### 运行验证脚本
```bash
python scripts/verify_improvements.py
```

期望输出:
```
Tests Passed: 7/7 (100.0%)
🎉 All improvements verified successfully!
✅ System is ready for deployment
```

### 手动测试

#### 1. 启动应用
```bash
# 设置环境变量
export DATABASE_URL="postgresql://user:pass@localhost/stock_db"
export OFFLINE_MODE=false
export USE_REDIS=true

# 启动API服务
python src/app.py
```

#### 2. 测试新API端点
```bash
# 测试指标API
curl http://localhost:5000/api/indicators/600036.SH

# 测试批量查询
curl -X POST http://localhost:5000/api/stocks/batch_analysis \
  -H "Content-Type: application/json" \
  -d '{"stock_codes": ["600036.SH", "600900.SH"]}'

# 测试健康检查
curl http://localhost:5000/metrics/health
```

#### 3. 测试新策略
```bash
# 回测布林带策略
python examples/backtest_strategies.py \
  --strategy bollinger_breakout \
  --symbol 600036.SH \
  --days 60

# 回测RSI策略
python examples/backtest_strategies.py \
  --strategy rsi_reversal \
  --symbol 600900.SH \
  --days 60
```

---

## 🔄 ETL调度器配置

### 启动方式选择

#### 方式1: 独立进程（推荐生产环境）
```bash
# 使用systemd管理
sudo nano /etc/systemd/system/stock-etl.service
```

```ini
[Unit]
Description=Stock Analysis ETL Scheduler
After=network.target

[Service]
Type=simple
User=stockapp
WorkingDirectory=/opt/stock
ExecStart=/opt/stock/venv/bin/python /opt/stock/src/scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable stock-etl
sudo systemctl start stock-etl
sudo systemctl status stock-etl
```

#### 方式2: Docker容器
```yaml
# docker-compose.yml 添加服务
etl-scheduler:
  build: .
  command: python src/scheduler.py
  environment:
    - DATABASE_URL=${DATABASE_URL}
  depends_on:
    - postgres
    - redis
  restart: unless-stopped
```

#### 方式3: Cron任务
```bash
crontab -e

# 每小时运行一次ETL
0 * * * * cd /opt/stock && python -c "from src.scheduler import DataScheduler; import asyncio; asyncio.run(DataScheduler().run_daily_etl())"
```

---

## 📊 Prometheus配置

### 1. 安装Prometheus
```bash
# Ubuntu/Debian
sudo apt-get install prometheus

# 或使用Docker
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/config/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

### 2. 配置抓取目标
编辑 `config/prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'stock_api'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### 3. 验证Prometheus
```bash
# 访问Prometheus Web UI
open http://localhost:9090

# 查询示例指标
http_requests_total
stock_analysis_duration_seconds
db_queries_total
```

---

## 📈 Grafana仪表盘

### 1. 安装Grafana
```bash
docker run -d \
  --name grafana \
  -p 3000:3000 \
  grafana/grafana
```

### 2. 配置数据源
1. 访问 http://localhost:3000 (admin/admin)
2. Configuration → Data Sources → Add Prometheus
3. URL: http://prometheus:9090

### 3. 导入仪表盘模板
```bash
# 提供预制仪表盘JSON
cp docs/grafana_dashboard.json /tmp/
```

---

## 🚀 生产环境部署

### Nginx反向代理
```nginx
# /etc/nginx/sites-available/stock-api
upstream stock_api {
    server localhost:5000;
    server localhost:5001;  # 多实例负载均衡
}

server {
    listen 80;
    server_name api.stock.example.com;

    location / {
        proxy_pass http://stock_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /metrics {
        # 仅内网访问
        allow 10.0.0.0/8;
        deny all;
        proxy_pass http://stock_api;
    }
}
```

### Gunicorn部署
```bash
pip install gunicorn

gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 4 \
  --timeout 120 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log \
  src.app:create_app()
```

---

## ⚙️ 环境变量配置

### 必需配置
```bash
# 数据库
export DATABASE_URL="postgresql://user:pass@localhost/stock_db"

# Redis
export USE_REDIS=true
export REDIS_HOST=localhost
export REDIS_PORT=6379

# 模式
export OFFLINE_MODE=false
export DEPLOYMENT_MODE=production
```

### 可选配置
```bash
# ETL调度
export ENABLE_ETL_SCHEDULER=true
export ETL_LOOKBACK_DAYS=90

# 缓存预热
export CACHE_WARMING_ENABLED=true

# 批量查询
export BATCH_QUERY_MAX_WORKERS=10

# 监控
export PROMETHEUS_PORT=9090
export METRICS_EXPORT_INTERVAL=15
```

---

## 🔍 监控告警

### 1. 设置告警规则
创建 `alerts/rules.yml`:
```yaml
groups:
  - name: stock_api
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "API错误率过高"

      - alert: SlowQueries
        expr: histogram_quantile(0.99, rate(db_query_duration_seconds_bucket[5m])) > 1
        for: 2m
        annotations:
          summary: "数据库查询缓慢"

      - alert: ETLJobFailed
        expr: increase(etl_runs_total{status="failed"}[1h]) > 3
        annotations:
          summary: "ETL任务频繁失败"
```

### 2. 配置告警通知
- Email
- Slack
- PagerDuty
- 微信企业号

---

## 🧪 压力测试

```bash
# 安装工具
pip install locust

# 运行压力测试
locust -f tests/load_test.py --host=http://localhost:5000
```

预期性能指标:
- QPS: > 100
- P99延迟: < 500ms
- 错误率: < 0.1%

---

## 📝 部署后验证

### 1. 功能完整性
- [ ] API端点全部正常响应
- [ ] 新指标API工作正常
- [ ] 批量查询性能提升明显
- [ ] ETL任务正常运行

### 2. 性能验证
- [ ] 单股查询 < 100ms
- [ ] 批量查询(50只) < 1s
- [ ] 缓存命中率 > 80%
- [ ] CPU使用率 < 60%

### 3. 监控验证
- [ ] Prometheus指标正常采集
- [ ] Grafana仪表盘显示正常
- [ ] 告警规则配置完成
- [ ] 日志正常输出

---

## 🔄 回滚计划

如遇严重问题，按以下步骤回滚:

### 1. 停止服务
```bash
sudo systemctl stop stock-api
sudo systemctl stop stock-etl
```

### 2. 恢复代码
```bash
git checkout <previous-version-tag>
```

### 3. 恢复数据库
```bash
# 删除新表
psql -U postgres -d stock_db -c "DROP TABLE IF EXISTS technical_indicators CASCADE;"
psql -U postgres -d stock_db -c "DROP TABLE IF EXISTS indicator_signals CASCADE;"

# 或恢复备份
psql -U postgres -d stock_db < backup_YYYYMMDD.sql
```

### 4. 重启服务
```bash
sudo systemctl start stock-api
sudo systemctl status stock-api
```

---

## 📞 支持联系

- 🐛 Bug报告: GitHub Issues
- 📧 紧急联系: ops@example.com
- 📱 On-call: +86-xxx-xxxx-xxxx

---

## ✅ 最终检查清单

部署完成后，确认以下所有项:

- [ ] 所有依赖安装成功
- [ ] 数据库迁移完成
- [ ] 验证脚本全部通过
- [ ] API端点全部可访问
- [ ] ETL调度器正常运行
- [ ] Prometheus正常采集指标
- [ ] 日志文件正常写入
- [ ] 性能指标达标
- [ ] 回滚方案已测试
- [ ] 团队已培训

**签署**: _____________
**日期**: _____________

---

*部署清单版本: v1.0*
*更新日期: 2025-09-30*