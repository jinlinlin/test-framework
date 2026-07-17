# Spec 7：适配器层

## 1. 概述

本 Spec 实现框架的适配器层，通过适配器模式屏蔽不同中间件、工具、协议的接口差异，对外提供统一调用规范。  
涵盖 HTTP、浏览器、数据库、消息队列、负载发生器五大类适配器，每类提供多种具体实现。

**依赖**：Spec 1（core/interfaces/adaptable.py, core/exceptions/adapter.py）, Spec 2（config/）  
**被依赖**：Spec 4 ~ Spec 6（引擎层）

---

## 2. 目标目录结构

```
uniplore-test-framework/
└── adapters/
    ├── __init__.py
    ├── base.py                  # 适配器基类
    ├── adapter_factory.py       # 适配器工厂（工厂模式）
    │
    ├── http/                    # HTTP 适配器
    │   ├── __init__.py
    │   ├── adapter.py
    │   ├── requests_impl.py     # Requests 实现
    │   ├── httpx_impl.py        # HTTPX 实现（异步）
    │   └── aiohttp_impl.py      # aiohttp 实现
    │
    ├── browser/                 # 浏览器适配器
    │   ├── __init__.py
    │   ├── adapter.py
    │   ├── playwright_impl.py   # Playwright 实现
    │   └── selenium_impl.py     # Selenium 实现（备用）
    │
    ├── database/                # 数据库适配器
    │   ├── __init__.py
    │   ├── adapter.py
    │   ├── asyncpg_impl.py      # PostgreSQL
    │   ├── aiomysql_impl.py     # MySQL
    │   ├── motor_impl.py        # MongoDB
    │   └── redis_impl.py        # Redis
    │
    ├── messaging/               # 消息队列适配器
    │   ├── __init__.py
    │   ├── adapter.py
    │   ├── kafka_impl.py
    │   └── rabbitmq_impl.py
    │
    └── load_generator/          # 负载发生器适配器
        ├── __init__.py
        ├── adapter.py
        ├── jmeter_impl.py       # JMeter 集成
        ├── locust_impl.py       # Locust 集成
        └── k6_impl.py           # K6 集成
```

---

## 3. 详细设计

### 3.1 base.py — 适配器基类

```python
"""
设计模式：适配器模式 — 统一抽象接口
"""
from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    """所有适配器的基类"""

    @property
    @abstractmethod
    def adapter_type(self) -> str: ...

    @property
    @abstractmethod
    def implementation_name(self) -> str: ...

    @abstractmethod
    async def connect(self, config: Dict[str, Any]) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def is_connected(self) -> bool: ...

    async def __aenter__(self): ...
    async def __aexit__(self, *args): ...
```

### 3.2 adapter_factory.py — 适配器工厂

```python
"""
设计模式：工厂模式
职责：根据类型和实现名创建适配器实例
"""
class AdapterFactory:
    _registry: Dict[str, Dict[str, Type[BaseAdapter]]] = {}

    @classmethod
    def register(cls, adapter_type: str, impl_name: str, adapter_cls: Type[BaseAdapter]) -> None: ...

    @classmethod
    def create(cls, adapter_type: str, impl_name: str = None, **kwargs) -> BaseAdapter:
        """impl_name 为空时返回该类型的默认实现"""

    @classmethod
    def available(cls, adapter_type: str) -> List[str]: ...
```

### 3.3 HTTP 适配器

#### http/adapter.py

```python
"""HTTP 适配器统一接口"""
class HTTPAdapter(BaseAdapter):
    adapter_type = "http"

    @abstractmethod
    async def request(self, method: str, url: str, **kwargs) -> 'HTTPResponse': ...

    @abstractmethod
    async def get(self, url: str, **kwargs) -> 'HTTPResponse': ...

    @abstractmethod
    async def post(self, url: str, **kwargs) -> 'HTTPResponse': ...

    @abstractmethod
    async def put(self, url: str, **kwargs) -> 'HTTPResponse': ...

    @abstractmethod
    async def delete(self, url: str, **kwargs) -> 'HTTPResponse': ...

@dataclass
class HTTPResponse:
    status_code: int
    headers: Dict[str, str]
    body: Any
    elapsed: float
    url: str

    def json(self) -> Dict: ...
    def text(self) -> str: ...
    def raise_for_status(self) -> None: ...
```

#### http/httpx_impl.py（推荐默认）

```python
"""基于 httpx 的异步 HTTP 实现"""
class HttpxAdapter(HTTPAdapter):
    implementation_name = "httpx"

    async def connect(self, config: Dict) -> None:
        self._client = httpx.AsyncClient(
            timeout=config.get("timeout", 30),
            verify=config.get("verify_ssl", True),
            limits=httpx.Limits(max_connections=config.get("max_connections", 100))
        )

    async def request(self, method, url, **kwargs) -> HTTPResponse: ...
    async def disconnect(self) -> None:
        await self._client.aclose()
```

#### http/requests_impl.py

```python
"""基于 requests 的同步实现（包装为异步）"""
class RequestsAdapter(HTTPAdapter):
    implementation_name = "requests"
```

#### http/aiohttp_impl.py

```python
"""基于 aiohttp 的异步实现"""
class AiohttpAdapter(HTTPAdapter):
    implementation_name = "aiohttp"
```

### 3.4 浏览器适配器

#### browser/adapter.py

```python
"""浏览器适配器统一接口"""
class BrowserAdapter(BaseAdapter):
    adapter_type = "browser"

    @abstractmethod
    async def new_page(self, **kwargs) -> Any: ...

    @abstractmethod
    async def navigate(self, page, url: str) -> None: ...

    @abstractmethod
    async def click(self, page, selector: str) -> None: ...

    @abstractmethod
    async def type_text(self, page, selector: str, text: str) -> None: ...

    @abstractmethod
    async def screenshot(self, page, path: str) -> str: ...

    @abstractmethod
    async def evaluate(self, page, expression: str) -> Any: ...

    @abstractmethod
    async def wait_for_selector(self, page, selector: str, timeout: float = 30) -> None: ...
```

#### browser/playwright_impl.py

```python
class PlaywrightAdapter(BrowserAdapter):
    implementation_name = "playwright"
    # 封装 playwright.async_api
```

#### browser/selenium_impl.py

```python
class SeleniumAdapter(BrowserAdapter):
    implementation_name = "selenium"
    # 封装 selenium webdriver（备用）
```

### 3.5 数据库适配器

#### database/adapter.py

```python
"""数据库适配器统一接口"""
class DatabaseAdapter(BaseAdapter):
    adapter_type = "database"

    @abstractmethod
    async def execute(self, query: str, params: tuple = None) -> Any: ...

    @abstractmethod
    async def execute_many(self, query: str, params_list: List[tuple]) -> None: ...

    @abstractmethod
    async def fetch_one(self, query: str, params: tuple = None) -> Any: ...

    @abstractmethod
    async def fetch_all(self, query: str, params: tuple = None) -> List[Any]: ...

    @abstractmethod
    async def begin_transaction(self) -> Any: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
```

#### database/asyncpg_impl.py

```python
class AsyncpgAdapter(DatabaseAdapter):
    implementation_name = "asyncpg"
    # PostgreSQL 异步驱动
```

#### database/aiomysql_impl.py

```python
class AiomysqlAdapter(DatabaseAdapter):
    implementation_name = "aiomysql"
    # MySQL 异步驱动
```

#### database/motor_impl.py

```python
class MotorAdapter(DatabaseAdapter):
    implementation_name = "motor"
    # MongoDB 异步驱动
```

#### database/redis_impl.py

```python
class RedisAdapter(DatabaseAdapter):
    implementation_name = "redis"
    # redis.asyncio 驱动
```

### 3.6 消息队列适配器

#### messaging/adapter.py

```python
"""消息队列适配器统一接口"""
class MessagingAdapter(BaseAdapter):
    adapter_type = "messaging"

    @abstractmethod
    async def publish(self, topic: str, message: Any, **kwargs) -> None: ...

    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable) -> None: ...

    @abstractmethod
    async def unsubscribe(self, topic: str) -> None: ...
```

#### messaging/kafka_impl.py

```python
class KafkaAdapter(MessagingAdapter):
    implementation_name = "kafka"
    # 基于 aiokafka
```

#### messaging/rabbitmq_impl.py

```python
class RabbitMQAdapter(MessagingAdapter):
    implementation_name = "rabbitmq"
    # 基于 aio-pika
```

### 3.7 负载发生器适配器

#### load_generator/adapter.py

```python
"""负载发生器适配器统一接口"""
class LoadGeneratorAdapter(BaseAdapter):
    adapter_type = "load_generator"

    @abstractmethod
    async def start_load(self, scenario: Dict[str, Any]) -> str:
        """启动负载测试，返回任务 ID"""

    @abstractmethod
    async def stop_load(self, task_id: str) -> None: ...

    @abstractmethod
    async def get_results(self, task_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def get_status(self, task_id: str) -> str: ...
```

#### load_generator/jmeter_impl.py

```python
class JMeterAdapter(LoadGeneratorAdapter):
    implementation_name = "jmeter"
    # 通过 subprocess 调用 JMeter CLI
```

#### load_generator/locust_impl.py

```python
class LocustAdapter(LoadGeneratorAdapter):
    implementation_name = "locust"
    # 通过 Locust API 或 Python 嵌入调用
```

#### load_generator/k6_impl.py

```python
class K6Adapter(LoadGeneratorAdapter):
    implementation_name = "k6"
    # 通过 subprocess 调用 k6 run，解析 JSON 输出
```

---

## 4. 验收标准

- [ ] `BaseAdapter` 支持 async context manager（`async with`）
- [ ] `AdapterFactory` 可按类型和实现名创建适配器
- [ ] HTTP 适配器三种实现（httpx/requests/aiohttp）接口一致，可互换
- [ ] 浏览器适配器 Playwright/Selenium 接口一致
- [ ] 数据库适配器四种实现均可执行 CRUD
- [ ] 消息队列适配器可发布/订阅消息
- [ ] 负载发生器适配器可启动/停止/获取结果
- [ ] 所有适配器连接失败时抛出 `AdapterException`
- [ ] 全模块有完整单元测试覆盖
