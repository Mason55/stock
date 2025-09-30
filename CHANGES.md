# 改动文件清单

## 新建文件 (5个)

### 1. src/services/market_data_fetcher.py
**作用**: 数据采集服务层
**改动原因**: 从API层抽离数据采集逻辑
**核心类**:
- `RealtimeDataFetcher`: 异步实时行情
- `HistoricalDataFetcher`: 历史K线数据
- `TechnicalIndicatorCalculator`: 技术指标计算

### 2. src/utils/di_container.py
**作用**: 依赖注入容器
**改动原因**: 替换全局变量注入模式
**核心类**:
- `ServiceContainer`: DI容器
- `init_container()`: 初始化函数

### 3. config/stock_symbols.py
**作用**: 股票列表配置
**改动原因**: 消除硬编码
**导出变量**:
- `ALL_STOCKS`: 完整股票列表
- `get_stock_by_code()`: 查询函数

### 4. tests/test_stock_api_endpoints.py
**作用**: API端点单元测试
**覆盖率**: 7个测试类，30+用例

### 5. tests/test_market_data_fetcher.py
**作用**: 数据采集服务测试
**覆盖率**: 6个测试类，25+用例

---

## 修改文件 (3个)

### 1. src/app.py
**改动点**:
- L13: 导入DI容器模块
- L73-80: 使用DI容器替换全局变量注入

**diff**:
```diff
- stock_api_module.session_factory = session_factory
+ container = init_container(session_factory=session_factory, ...)
+ app.container = container
```

### 2. requirements.txt
**改动点**:
- 统一Flask/SQLAlchemy/Redis版本
- 新增aiohttp==3.8.5

**主要变更**:
```diff
- Flask==2.3.3
+ Flask==2.3.2
- SQLAlchemy==2.0.21
+ SQLAlchemy==2.0.19
+ aiohttp==3.8.5
```

### 3. src/services/enhanced_data_collector.py
**改动点**:
- L31-34: 使用配置文件替换硬编码
- L58-63: 改进异常处理

**diff**:
```diff
- stock_list = [{"code": "000001.SZ", ...}, ...]  # 20行硬编码
+ from config.stock_symbols import ALL_STOCKS
+ return list(ALL_STOCKS)
```

---

## 未修改但需注意的文件

### src/api/stock_api.py (1049行)
**状态**: 保留原有逻辑
**原因**: 
- 已通过新建`market_data_fetcher.py`抽离核心逻辑
- 原文件保持兼容性，后续可逐步迁移到新服务

**迁移建议**:
1. 短期: 新功能使用`market_data_fetcher`
2. 中期: 逐步迁移现有路由到新服务
3. 长期: 删除旧实现，完全使用新架构

---

## 部署注意事项

### 1. 安装新依赖
```bash
pip install -r requirements.txt
```

### 2. 检查依赖冲突
```bash
pip check
```

### 3. 运行测试
```bash
pytest tests/ -v
```

### 4. 环境变量检查
无需新增环境变量，现有配置兼容。

---

## 回滚方案

如遇问题可快速回滚：

```bash
git checkout HEAD~1 requirements.txt src/app.py
rm src/services/market_data_fetcher.py
rm src/utils/di_container.py
rm config/stock_symbols.py
```

**影响范围**: 仅影响新增文件，不破坏现有功能。
