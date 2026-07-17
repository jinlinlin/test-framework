# 适配器

## 适配器模式

所有适配器实现统一的 `IAdaptable` 接口，通过 `AdapterFactory` 统一创建：

```python
from test_framework.adapters import AdapterFactory

factory = AdapterFactory()
http_adapter = factory.create("http")
db_adapter = factory.create("database")
```

---

## 适配器类型

### 1. HTTP 适配器

**目录**：`adapters/http/`

| 实现 | 文件 | 特点 |
|------|------|------|
| requests | `requests_impl.py` | 同步、简单、广泛使用 |
| httpx | `httpx_impl.py` | 异步、HTTP/2 支持 |
| aiohttp | `aiohttp_impl.py` | 纯异步、高性能 |

```yaml
adapters:
  http:
    backend: httpx       # requests / httpx / aiohttp
    timeout: 30
    max_retries: 3
    pool_connections: 10
    verify_ssl: true
```

### 2. 浏览器适配器

**目录**：`adapters/browser/`

| 实现 | 文件 | 特点 |
|------|------|------|
| Playwright | `playwright_impl.py` | 现代、异步、多浏览器 |
| Selenium | `selenium_impl.py` | 经典、广泛支持 |

```yaml
adapters:
  browser:
    backend: playwright   # playwright / selenium
    headless: true
    browser_type: chromium # chromium / firefox / webkit
```

### 3. 数据库适配器

**目录**：`adapters/database/`

| 实现 | 文件 | 数据库 |
|------|------|-------|
| asyncpg | `asyncpg_impl.py` | PostgreSQL |
| aiomysql | `aiomysql_impl.py` | MySQL |
| motor | `motor_impl.py` | MongoDB |
| redis | `redis_impl.py` | Redis |

```yaml
adapters:
  database:
    pool_min: 5
    pool_max: 20
    timeout: 10
```

### 4. 消息队列适配器

**目录**：`adapters/messaging/`

| 实现 | 文件 | 特点 |
|------|------|------|
| Kafka | `kafka_impl.py` | 高吞吐、分区 |
| RabbitMQ | `rabbitmq_impl.py` | 灵活路由 |

### 5. 负载生成器适配器

**目录**：`adapters/load_generator/`

| 实现 | 文件 | 特点 |
|------|------|------|
| JMeter | `jmeter_impl.py` | 功能全面、GUI |
| Locust | `locust_impl.py` | Python 脚本化 |
| k6 | `k6_impl.py` | 轻量、JavaScript |

---

## 自定义适配器

### 1. 创建适配器类

```python
from test_framework.adapters.base import BaseAdapter

class MyCustomAdapter(BaseAdapter):
    """自定义适配器示例。"""

    @property
    def adapter_type(self) -> str:
        return "my_custom"

    async def connect(self, config: dict):
        """建立连接。"""
        self._client = MyClient(config["host"], config["port"])
        await self._client.connect()

    async def execute(self, operation: str, **kwargs):
        """执行操作。"""
        method = getattr(self._client, operation)
        return await method(**kwargs)

    async def disconnect(self):
        """断开连接。"""
        if self._client:
            await self._client.close()

    async def health_check(self) -> bool:
        """健康检查。"""
        try:
            return await self._client.ping()
        except Exception:
            return False
```

### 2. 注册到工厂

```python
from test_framework.adapters import AdapterFactory

AdapterFactory.register("my_custom", MyCustomAdapter)

# 使用
adapter = AdapterFactory.create("my_custom")
await adapter.connect({"host": "localhost", "port": 9090})
```

---

## 适配器生命周期

```
创建 → connect(config) → execute(op) → ... → disconnect()
```

所有适配器遵循统一生命周期：
1. **创建**：通过工厂或构造函数实例化
2. **连接**：`connect(config)` 初始化底层连接
3. **执行**：`execute(operation, **kwargs)` 执行操作
4. **断开**：`disconnect()` 释放资源

适配器在异常时应通过 `health_check()` 报告状态。
