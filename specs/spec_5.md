# Spec 5：功能测试引擎 — REST API 测试 + 数据库性能测试

## 1. 概述

本 Spec 实现框架七大测试引擎中的两个功能测试引擎：  
- **③ REST API 测试引擎**：提供 Python/Node.js 双引擎，支持接口自动构建、权限认证、限流控制、契约校验、Schema 验证  
- **④ 数据库性能测试引擎**：支持 MySQL/PostgreSQL/MongoDB/Redis，内置连接池、SQL 执行器、执行计划分析、索引优化建议

**依赖**：Spec 1, Spec 2, Spec 3  
**被依赖**：无（叶子模块）

---

## 2. 目标目录结构

```
uniplore-test-framework/
└── engines/
    ├── rest_api/                # ③ REST API 测试
    │   ├── __init__.py
    │   ├── engine.py            # Python 引擎
    │   ├── engine.js            # Node.js 引擎
    │   ├── request_builder.py   # 请求构建器（建造者模式）
    │   ├── response_validator.py # 响应验证器（策略模式）
    │   ├── auth_handler.py      # 认证处理器
    │   ├── rate_limiter.py      # 限流器
    │   ├── contract_tester.py   # 契约测试
    │   ├── schema_validator.py  # Schema 验证
    │   └── config_schema.py
    │
    └── database/                # ④ 数据库性能测试
        ├── __init__.py
        ├── engine.py            # 引擎主类
        ├── connection_pool.py   # 连接池管理（对象池模式）
        ├── query_executor.py    # 查询执行器
        ├── explain_analyzer.py  # 执行计划分析
        ├── index_advisor.py     # 索引建议
        ├── dialect/             # 数据库方言（策略模式）
        │   ├── __init__.py
        │   ├── base.py
        │   ├── postgresql.py
        │   ├── mysql.py
        │   ├── mongodb.py
        │   └── redis.py
        └── config_schema.py
```

---

## 3. 详细设计

### 3.1 REST API 测试引擎

#### rest_api/engine.py — Python 引擎

```python
"""
职责：REST API 测试主引擎，基于 httpx 实现异步请求
支持：单接口测试、接口批量测试、接口压测
"""
class RestAPIEngine(BaseEngine):
    engine_type = TestType.REST_API

    def __init__(self, config, container):
        super().__init__(config, container)
        self._auth_handler = AuthHandler(config.get("auth", {}))
        self._rate_limiter = RateLimiter(config.get("rate_limit", {}))
        self._schema_validator = SchemaValidator()
        self._contract_tester = ContractTester()

    async def setup(self, target: TargetSystem) -> None:
        self._client = httpx.AsyncClient(
            base_url=target.base_url,
            timeout=self._config.get("timeout", 30),
            verify=self._config.get("verify_ssl", True)
        )
        await self._auth_handler.initialize(target.auth)

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        request = RequestBuilder.from_config(case.config).build()
        headers = await self._auth_handler.get_auth_headers()
        await self._rate_limiter.acquire()

        start = time.monotonic()
        response = await self._client.request(
            method=request.method,
            url=request.path,
            headers={**headers, **request.headers},
            params=request.params,
            json=request.body,
        )
        duration = time.monotonic() - start

        # 验证响应
        validation_result = await ResponseValidator(self._config).validate(response, case.config)
        status = TestStatus.PASS if validation_result.passed else TestStatus.FAIL

        return TestResult(
            case_id=case.id, status=status, duration=duration,
            message=validation_result.message,
            details={"status_code": response.status_code, "response_body": response.json()},
            metrics=TestMetrics(latency_avg=duration, throughput=1/duration),
            timestamp=datetime.now()
        )

    async def teardown(self) -> None:
        await self._client.aclose()
```

#### rest_api/engine.js — Node.js 引擎

```javascript
/**
 * 职责：Node.js 高并发 API 测试引擎
 * 使用 axios + 并发控制实现高吞吐量接口压测
 * 被 Python 通过 LanguageBridge 调度
 */
class NodeRestAPIEngine {
    constructor(config) {
        this.config = config;
        this.results = [];
    }

    async execute({ url, method, headers, body, concurrency, totalRequests, duration }) {
        const semaphore = new Semaphore(concurrency);
        const tasks = [];
        let completed = 0;
        const startTime = Date.now();

        while (completed < totalRequests && (Date.now() - startTime) < duration * 1000) {
            await semaphore.acquire();
            tasks.push(
                this._sendRequest(url, method, headers, body)
                    .finally(() => { semaphore.release(); completed++; })
            );
        }
        const results = await Promise.allSettled(tasks);
        return this._aggregate(results, startTime);
    }

    async _sendRequest(url, method, headers, body) { ... }
    _aggregate(results, startTime) { ... }
}

module.exports = NodeRestAPIEngine;
```

#### rest_api/request_builder.py（建造者模式）

```python
"""
设计模式：建造者模式
职责：链式构建 HTTP 请求，支持参数、请求头、Body、文件上传
"""
class RequestBuilder:
    def __init__(self):
        self._method = "GET"
        self._path = "/"
        self._headers = {}
        self._params = {}
        self._body = None
        self._files = None

    def method(self, m: str) -> 'RequestBuilder': ...
    def path(self, p: str) -> 'RequestBuilder': ...
    def header(self, key: str, value: str) -> 'RequestBuilder': ...
    def headers(self, h: Dict) -> 'RequestBuilder': ...
    def param(self, key: str, value: Any) -> 'RequestBuilder': ...
    def params(self, p: Dict) -> 'RequestBuilder': ...
    def json_body(self, body: Dict) -> 'RequestBuilder': ...
    def form_body(self, body: Dict) -> 'RequestBuilder': ...
    def file(self, field: str, path: str) -> 'RequestBuilder': ...

    def build(self) -> 'Request': ...

    @classmethod
    def from_config(cls, config: Dict) -> 'RequestBuilder':
        """从配置字典快速构建"""

@dataclass
class Request:
    method: str
    path: str
    headers: Dict[str, str]
    params: Dict[str, Any]
    body: Any
    files: Dict[str, str]
```

#### rest_api/response_validator.py（策略模式）

```python
"""
设计模式：策略模式
职责：根据配置的验证策略组合验证响应
"""
class ResponseValidator:
    def __init__(self, config: Dict):
        self._strategies: List[ValidationStrategy] = []
        if config.get("validation", {}).get("schema_check"):
            self._strategies.append(SchemaCheckStrategy())
        if config.get("validation", {}).get("contract_check"):
            self._strategies.append(ContractCheckStrategy())
        self._strategies.append(StatusCodeStrategy())  # 始终验证状态码

    async def validate(self, response, case_config: Dict) -> ValidationResult:
        errors = []
        for strategy in self._strategies:
            result = await strategy.validate(response, case_config)
            errors.extend(result.errors)
        return ValidationResult(
            passed=len(errors) == 0,
            message="; ".join(errors) if errors else "OK",
            errors=errors
        )

class ValidationStrategy(ABC):
    @abstractmethod
    async def validate(self, response, case_config: Dict) -> ValidationResult: ...
```

#### rest_api/auth_handler.py

```python
"""
职责：统一认证处理，支持 Basic / Bearer / OAuth2 / API Key
"""
class AuthHandler:
    def __init__(self, config: Dict): ...

    async def initialize(self, auth_config: Dict) -> None: ...
    async def get_auth_headers(self) -> Dict[str, str]: ...
    async def refresh_token(self) -> None: ...  # OAuth2 token 刷新
```

#### rest_api/rate_limiter.py

```python
"""
职责：请求限流，控制每秒请求数（令牌桶算法）
"""
class RateLimiter:
    def __init__(self, config: Dict): ...
    async def acquire(self) -> None: ...
    def set_rate(self, rps: int) -> None: ...
```

#### rest_api/contract_tester.py

```python
"""
职责：契约测试，对比实际响应与预定义契约（OpenAPI / JSON Schema）
"""
class ContractTester:
    def load_contract(self, contract_path: str) -> None: ...
    async def validate(self, response, endpoint: str) -> ValidationResult: ...
```

#### rest_api/schema_validator.py

```python
"""
职责：基于 JSON Schema 验证响应体结构
"""
class SchemaValidator:
    def validate(self, data: Any, schema: Dict) -> ValidationResult: ...
    def validate_from_file(self, data: Any, schema_path: str) -> ValidationResult: ...
```

---

### 3.2 数据库性能测试引擎

#### database/engine.py

```python
"""
职责：数据库性能测试主引擎
流程：建立连接池 → 执行查询 → 分析执行计划 → 生成索引建议 → 采集指标
"""
class DatabaseEngine(BaseEngine):
    engine_type = TestType.DATABASE

    async def setup(self, target: TargetSystem) -> None:
        dialect = DialectFactory.create(target.config.get("db_type", "postgresql"))
        self._pool = ConnectionPool(dialect, self._config.get("pool", {}))
        await self._pool.initialize(target)
        self._executor = QueryExecutor(self._pool, dialect)
        self._explain = ExplainAnalyzer(self._pool, dialect)
        self._advisor = IndexAdvisor(dialect, self._config.get("index_advisor", {}))

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        query = case.config["query"]
        iterations = case.config.get("iterations", 100)

        # 执行查询
        exec_result = await self._executor.execute_benchmark(query, iterations)
        # 执行计划分析
        explain = await self._explain.analyze(query) if self._config.get("query", {}).get("explain") else None
        # 索引建议
        suggestions = self._advisor.analyze(explain) if explain else []

        return TestResult(
            case_id=case.id,
            status=TestStatus.PASS,
            duration=exec_result.total_time,
            details={"explain": explain, "suggestions": suggestions},
            metrics=TestMetrics(
                latency_avg=exec_result.avg_time,
                latency_p50=exec_result.p50,
                latency_p95=exec_result.p95,
                latency_p99=exec_result.p99,
                throughput=exec_result.qps
            ),
            timestamp=datetime.now()
        )

    async def teardown(self) -> None:
        await self._pool.close()
```

#### database/connection_pool.py（对象池模式）

```python
"""
设计模式：对象池模式
职责：管理数据库连接复用，支持连接数上下限、空闲超时
"""
class ConnectionPool:
    def __init__(self, dialect: 'Dialect', config: Dict):
        self._min_size = config.get("min_size", 5)
        self._max_size = config.get("max_size", 20)
        self._idle_timeout = config.get("idle_timeout", 300)
        self._pool: asyncio.Queue = None

    async def initialize(self, target: TargetSystem) -> None: ...
    async def acquire(self) -> Any: ...
    async def release(self, conn: Any) -> None: ...
    async def close(self) -> None: ...
    def stats(self) -> Dict[str, int]: ...
```

#### database/query_executor.py

```python
"""
职责：执行 SQL 查询并统计性能指标
"""
@dataclass
class BenchmarkResult:
    total_time: float
    avg_time: float
    p50: float
    p95: float
    p99: float
    qps: float
    errors: int

class QueryExecutor:
    def __init__(self, pool: ConnectionPool, dialect: 'Dialect'): ...

    async def execute(self, query: str, params: tuple = None) -> Any: ...

    async def execute_benchmark(self, query: str, iterations: int = 100,
                                concurrency: int = 1) -> BenchmarkResult: ...
```

#### database/explain_analyzer.py

```python
"""
职责：分析 SQL 执行计划，识别全表扫描、低效 JOIN、缺失索引等问题
"""
class ExplainAnalyzer:
    async def analyze(self, query: str) -> Dict[str, Any]: ...
    def detect_issues(self, plan: Dict) -> List[str]: ...
```

#### database/index_advisor.py

```python
"""
职责：基于执行计划分析结果，生成索引优化建议
"""
class IndexAdvisor:
    def analyze(self, explain_result: Dict) -> List[Dict[str, Any]]:
        """返回建议列表：[{table, columns, type, estimated_improvement}]"""
```

#### database/dialect/base.py

```python
"""
职责：数据库方言抽象基类，屏蔽不同数据库的 SQL 差异
"""
class Dialect(ABC):
    @abstractmethod
    def build_explain_query(self, sql: str) -> str: ...

    @abstractmethod
    def parse_explain_result(self, result: Any) -> Dict[str, Any]: ...

    @abstractmethod
    def get_connection_string(self, target: 'TargetSystem') -> str: ...

    @abstractmethod
    async def create_connection(self, conn_str: str) -> Any: ...
```

#### database/dialect/postgresql.py

```python
class PostgreSQLDialect(Dialect):
    def build_explain_query(self, sql: str) -> str:
        return f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"
    # ... 实现其余抽象方法，使用 asyncpg
```

#### database/dialect/mysql.py

```python
class MySQLDialect(Dialect):
    def build_explain_query(self, sql: str) -> str:
        return f"EXPLAIN FORMAT=JSON {sql}"
    # ... 使用 aiomysql
```

#### database/dialect/mongodb.py

```python
class MongoDBDialect(Dialect):
    def build_explain_query(self, query: str) -> str:
        # MongoDB 使用 explain() 方法
        ...
    # ... 使用 motor
```

#### database/dialect/redis.py

```python
class RedisDialect(Dialect):
    # Redis 使用 INFO / SLOWLOG / LATENCY 命令
    ...
```

---

## 4. 验收标准

- [ ] REST API Python 引擎可发送 HTTP 请求并验证响应
- [ ] REST API Node.js 引擎可高并发压测并聚合结果
- [ ] `RequestBuilder` 可链式构建各类 HTTP 请求
- [ ] `ResponseValidator` 可按策略组合验证
- [ ] `AuthHandler` 支持 Basic/Bearer/OAuth2/API Key 四种认证
- [ ] `RateLimiter` 可控制请求速率
- [ ] 数据库引擎可建立连接池并执行查询
- [ ] `ExplainAnalyzer` 可分析执行计划并识别性能问题
- [ ] `IndexAdvisor` 可生成索引优化建议
- [ ] 四种数据库方言（PG/MySQL/MongoDB/Redis）均可正确工作
- [ ] 全模块有完整单元测试覆盖
