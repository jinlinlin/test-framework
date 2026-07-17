# 配置管理

## 配置层次

框架采用 **多层配置 + 环境覆盖** 机制，优先级从高到低：

```
命令行参数 > 环境变量(.env) > 环境配置(dev.yaml) > 引擎默认配置(defaults/) > 基础配置(base.yaml)
```

---

## 配置文件结构

```
test_framework/config/
├── manager.py              # ConfigManager 单例
├── loader.py               # 配置加载器工厂（YAML/JSON/TOML/ENV）
├── validator.py            # 配置校验器
├── schema/                 # JSON Schema 定义
│   ├── global.json
│   ├── test_type.json
│   ├── adapter.json
│   └── strategy.json
├── environments/           # 环境配置
│   ├── base.yaml           # 基础配置（所有环境共享）
│   ├── dev.yaml            # 开发环境覆盖
│   ├── test.yaml           # 测试环境覆盖
│   ├── staging.yaml        # 预发环境覆盖
│   └── production.yaml     # 生产环境覆盖
├── defaults/               # 引擎默认配置
│   ├── web.yaml
│   ├── backend.yaml
│   ├── api.yaml
│   ├── database.yaml
│   ├── knowledge.yaml
│   ├── penetration.yaml
│   └── auth_bypass.yaml
└── targets/                # 被测系统配置
    └── *.yaml
```

---

## 基础配置（base.yaml）

所有环境共享的默认配置：

```yaml
framework:
  name: uniplore-test-framework
  version: "1.0.0"
  debug: false

logging:
  level: INFO
  file: logs/framework.log
  max_size_mb: 50
  backup_count: 5

output:
  reports_dir: reports
  results_dir: results

concurrency:
  max_workers: 8
  max_async_tasks: 100

adapters:
  http:
    backend: httpx
    timeout: 30
  browser:
    backend: playwright
    headless: true

reporters:
  default_format: html
  auto_generate: true
```

---

## 环境覆盖

通过 `TF_ENV` 环境变量选择环境，自动加载对应配置：

```bash
TF_ENV=dev      # → base.yaml + dev.yaml
TF_ENV=test     # → base.yaml + test.yaml
TF_ENV=staging  # → base.yaml + staging.yaml
TF_ENV=production # → base.yaml + production.yaml
```

覆盖规则为 **深度合并（deep merge）**：环境配置中的值会覆盖 base 中对应路径的值。

---

## ConfigManager API

```python
from test_framework.config.manager import ConfigManager

# 获取单例
config = ConfigManager()

# 加载配置
config.load(environment="dev")

# 获取配置值（支持点号路径）
level = config.get("logging.level")          # "INFO"
timeout = config.get("adapters.http.timeout") # 30

# 设置配置值
config.set("logging.level", "DEBUG")

# 验证配置
result = config.validate()
if not result.is_valid:
    print(result.errors)

# 导出配置
config.export("config_snapshot.yaml")

# 重新加载
config.reload()
```

---

## 测试配置文件格式

### REST API 测试

```yaml
test:
  name: "用户 API 测试"
  type: rest_api
  target:
    base_url: https://api.example.com/v1
    auth:
      type: bearer
      token_env: API_TOKEN
  endpoints:
    - path: /users
      method: GET
      expected_status: 200
    - path: /users
      method: POST
      body:
        name: "新用户"
        email: "user@example.com"
      expected_status: 201
  timeout: 15
  retry:
    max_retries: 3
```

### 数据库测试

```yaml
test:
  name: "数据库性能测试"
  type: database
  target:
    dialect: postgresql
    host: localhost
    port: 5432
    database: test_db
    user_env: DB_USER
    password_env: DB_PASSWORD
  queries:
    - name: "用户查询"
      sql: "SELECT * FROM users LIMIT 100"
      expected_max_ms: 50
      explain: true
```

### Web 性能测试

```yaml
test:
  name: "首页性能测试"
  type: web_performance
  target:
    url: https://example.com
    pages: ["/", "/login", "/dashboard"]
  browser:
    type: chromium
    headless: true
  thresholds:
    lcp_ms: 2500
    fid_ms: 100
    cls: 0.1
```

---

## Schema 验证

框架使用 JSON Schema 对配置文件进行严格验证：

- `schema/global.json` — 全局配置结构
- `schema/test_type.json` — 测试类型配置
- `schema/adapter.json` — 适配器配置
- `schema/strategy.json` — 策略配置

验证在 `ConfigManager.load()` 时自动执行，无效配置会抛出 `ConfigException`。
