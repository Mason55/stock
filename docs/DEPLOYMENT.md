# 部署指南

## 部署方案概览

本系统支持多种部署方式，从开发环境到生产环境都有相应的解决方案。

## 本地开发环境

### 前置要求
- Python 3.8+
- Redis 6.0+ (可选)
- Git

### 快速启动
```bash
# 1. 克隆项目
git clone <repository-url>
cd stock

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境
cp .env.example .env
# 编辑 .env 文件配置数据库等信息

# 5. 启动服务
python src/app.py
```

## Docker部署 (推荐)

### 单容器部署
```bash
# 构建镜像
docker build -t stock-analysis .

# 运行容器
docker run -d \
  --name stock-analysis \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL=sqlite:///data/stock.db \
  stock-analysis
```

### Docker Compose部署
```bash
# 开发环境
docker-compose up -d

# 生产环境
docker-compose -f docker-compose.prod.yml up -d
```

**docker-compose.yml 配置**:
```yaml
version: '3.8'

services:
  stock-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/stock_db
      - REDIS_HOST=redis
    depends_on:
      - db
      - redis
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: stock_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - stock-api
    restart: unless-stopped

volumes:
  postgres_data:
```

## 云服务部署

### AWS部署

#### 使用 AWS ECS
```bash
# 1. 推送镜像到 ECR
aws ecr create-repository --repository-name stock-analysis
docker tag stock-analysis:latest <account-id>.dkr.ecr.<region>.amazonaws.com/stock-analysis:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/stock-analysis:latest

# 2. 创建 ECS 任务定义
aws ecs register-task-definition --cli-input-json file://task-definition.json

# 3. 创建服务
aws ecs create-service \
  --cluster stock-cluster \
  --service-name stock-service \
  --task-definition stock-analysis \
  --desired-count 2
```

**task-definition.json**:
```json
{
  "family": "stock-analysis",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "stock-api",
      "image": "<account-id>.dkr.ecr.<region>.amazonaws.com/stock-analysis:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://user:pass@rds-endpoint:5432/stock_db"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/stock-analysis",
          "awslogs-region": "us-west-2"
        }
      }
    }
  ]
}
```

#### 使用 AWS Lambda (无服务器)
```python
# lambda_handler.py
import json
from src.app import create_app
from mangum import Mangum

app = create_app()
handler = Mangum(app)

def lambda_handler(event, context):
    return handler(event, context)
```

### 阿里云部署

#### 使用容器服务 ACK
```bash
# 1. 创建命名空间
kubectl create namespace stock-system

# 2. 部署应用
kubectl apply -f k8s/

# 3. 检查状态
kubectl get pods -n stock-system
kubectl get svc -n stock-system
```

**k8s/deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: stock-api
  namespace: stock-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: stock-api
  template:
    metadata:
      labels:
        app: stock-api
    spec:
      containers:
      - name: stock-api
        image: registry.cn-hangzhou.aliyuncs.com/your-namespace/stock-analysis:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: stock-api-service
  namespace: stock-system
spec:
  selector:
    app: stock-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### 腾讯云部署

#### 使用云函数 SCF
```bash
# 1. 安装 Serverless Framework
npm install -g serverless

# 2. 配置 serverless.yml
serverless deploy
```

**serverless.yml**:
```yaml
service: stock-analysis

provider:
  name: tencent
  runtime: Python3.8
  region: ap-guangzhou

functions:
  stock-api:
    handler: lambda_handler.main
    events:
      - apigw:
          path: /{proxy+}
          method: ANY
    environment:
      DATABASE_URL: ${env:DATABASE_URL}
    timeout: 30

plugins:
  - serverless-tencent-scf
```

## 监控和日志

### 健康检查
```bash
# API健康检查
curl http://localhost:8000/api/stocks/health

# 容器健康检查
docker exec stock-analysis curl -f http://localhost:8000/api/stocks/health || exit 1
```

### 日志配置
```yaml
# docker-compose.yml 中的日志配置
services:
  stock-api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Prometheus监控
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'stock-api'
    static_configs:
      - targets: ['stock-api:8000']
    metrics_path: '/metrics'
```

## 性能优化

### 数据库优化
```sql
-- 创建索引
CREATE INDEX idx_stock_code ON stock_analysis(stock_code);
CREATE INDEX idx_analysis_date ON stock_analysis(analysis_date);
CREATE INDEX idx_stock_price_date ON stock_prices(stock_code, date);
```

### Redis缓存配置
```bash
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### Nginx负载均衡
```nginx
upstream stock_api {
    least_conn;
    server stock-api-1:8000 weight=1;
    server stock-api-2:8000 weight=1;
    server stock-api-3:8000 weight=1;
}

server {
    listen 80;
    server_name api.stock-analysis.com;

    location / {
        proxy_pass http://stock_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    location /health {
        access_log off;
        proxy_pass http://stock_api/api/stocks/health;
    }
}
```

## 安全配置

### SSL/TLS配置
```bash
# 使用 Let's Encrypt 获取证书
certbot --nginx -d api.stock-analysis.com

# 或者使用自签名证书 (仅开发环境)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/server.key -out ssl/server.crt
```

### 环境变量安全
```bash
# 使用 Docker secrets (生产环境)
echo "your_secret_key" | docker secret create db_password -
```

### 防火墙配置
```bash
# 仅开放必要端口
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw deny 8000/tcp   # 直接访问 API 端口
```

## 自动化部署

### GitHub Actions CI/CD
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Build and push Docker image
      run: |
        docker build -t stock-analysis:${{ github.sha }} .
        docker tag stock-analysis:${{ github.sha }} stock-analysis:latest
        docker push your-registry/stock-analysis:${{ github.sha }}
        docker push your-registry/stock-analysis:latest
    
    - name: Deploy to production
      run: |
        kubectl set image deployment/stock-api \
          stock-api=your-registry/stock-analysis:${{ github.sha }}
        kubectl rollout status deployment/stock-api
```

### 回滚策略
```bash
# Kubernetes 回滚
kubectl rollout undo deployment/stock-api

# Docker 回滚
docker-compose down
docker-compose up -d --scale stock-api=0
docker-compose up -d --scale stock-api=3
```

## 故障排除

### 常见问题
1. **数据库连接失败**: 检查数据库服务状态和连接字符串
2. **Redis连接超时**: 检查Redis配置和网络连接
3. **API响应慢**: 检查数据源可用性和缓存配置
4. **内存不足**: 调整容器资源限制或优化代码

### 调试工具
```bash
# 查看容器日志
docker logs stock-analysis -f

# 进入容器调试
docker exec -it stock-analysis /bin/bash

# 检查系统资源
docker stats

# 检查网络连接
docker network ls
docker network inspect bridge
```