# Spec 1：基础架构层 — Bootstrap 启动引导 + Core 核心抽象层

## 1. 概述

本 Spec 实现框架最底层的基础设施，包含启动引导层（`bootstrap/`）和核心抽象层（`core/`）。  
所有上层模块（引擎、适配器、策略、报告器等）均依赖本层提供的 IoC 容器、接口契约、领域模型、事件总线、管道引擎和异常体系。

**依赖**：无（本层为最底层，无外部框架依赖）  
**被依赖**：Spec 2 ~ Spec 10 全部依赖本层

---

## 2. 目标目录结构

```
uniplore-test-framework/
├── bootstrap/
│   ├── __init__.py
│   ├── bootstrapper.py          # 启动器（单例模式）
│   ├── environment.py           # 环境检测与初始化
│   ├── dependency_checker.py    # 依赖检查（Python/Node/Playwright）
│   └── classpath_loader.py      # 动态类加载器
│
├── core/
│   ├── __init__.py
│   ├── container/
│   │   ├── __init__.py
│   │   ├── container.py         # IoC 容器（单例）
│   │   ├── service_registry.py  # 服务注册
│   │   └── dependency_resolver.py
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── testable.py          # 可测试接口（模板模式）
│   │   ├── adaptable.py         # 可适配接口
│   │   ├── reportable.py        # 可报告接口
│   │   ├── configurable.py      # 可配置接口
│   │   ├── executable.py        # 可执行接口（命令模式）
│   │   ├── observable.py        # 可观察接口（观察者模式）
│   │   ├── lifecycle.py         # 生命周期接口
│   │   └── pluggable.py         # 可插拔接口
│   ├── models/
│   │   ├── __init__.py
│   │   ├── test_case.py
│   │   ├── test_suite.py        # 组合模式
│   │   ├── test_plan.py
│   │   ├── test_result.py
│   │   ├── test_metrics.py
│   │   ├── test_report.py
│   │   ├── target_system.py
│   │   ├── execution_context.py
│   │   └── enums.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── pipeline.py          # 责任链模式
│   │   ├── stage.py
│   │   ├── context.py
│   │   ├── filter.py
│   │   └── hooks.py
│   ├── events/
│   │   ├── __init__.py
│   │   ├── event_bus.py         # 事件总线（单例）
│   │   ├── event.py
│   │   ├── listeners.py
│   │   └── event_types.py
│   └── exceptions/
│       ├── __init__.py
│       ├── base.py
│       ├── config.py
│       ├── execution.py
│       ├── adapter.py
│       └── plugin.py
```

---

## 3. 详细设计

### 3.1 Bootstrap 启动引导层

#### 3.1.1 bootstrapper.py — 启动器（单例模式）

```python
"""
职责：框架总启动器，负责按顺序初始化所有子系统
设计模式：单例模式（全局唯一实例）
"""
class Bootstrapper:
    _instance: Optional['Bootstrapper'] = None

    def __new__(cls) -> 'Bootstrapper':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = False
        self._stages: List[BootstrapStage] = []

    def register_stage(self, stage: 'BootstrapStage') -> None:
        """注册启动阶段"""

    async def boot(self, config_path: str) -> None:
        """执行全部启动阶段：环境检测 → 依赖检查 → 容器初始化 → 插件加载 → 就绪"""

    async def shutdown(self) -> None:
        """优雅关闭，逆序执行各阶段 cleanup"""
```

#### 3.1.2 environment.py — 环境检测与初始化

```python
"""
职责：检测运行环境（OS、Python版本、Node版本、环境变量），输出 EnvironmentInfo 数据类
"""
@dataclass
class EnvironmentInfo:
    os: str
    python_version: str
    node_version: Optional[str]
    shell: str
    env_vars: Dict[str, str]
    is_ci: bool

class EnvironmentDetector:
    def detect(self) -> EnvironmentInfo: ...
    def validate(self, info: EnvironmentInfo) -> List[str]: ...  # 返回警告列表
```

#### 3.1.3 dependency_checker.py — 依赖检查

```python
"""
职责：检查 Python 包、Node 包、系统工具（Playwright、Docker）是否已安装
"""
@dataclass
class DependencyStatus:
    name: str
    required: bool
    installed: bool
    version: Optional[str]
    message: str

class DependencyChecker:
    def check_python_packages(self, packages: List[str]) -> List[DependencyStatus]: ...
    def check_node_packages(self, packages: List[str]) -> List[DependencyStatus]: ...
    def check_system_tools(self, tools: List[str]) -> List[DependencyStatus]: ...
    def check_all(self) -> List[DependencyStatus]: ...
    def ensure_or_raise(self, statuses: List[DependencyStatus]) -> None: ...
```

#### 3.1.4 classpath_loader.py — 动态类加载器

```python
"""
职责：根据字符串路径（如 'engines.web_performance.engine.WebPerformanceEngine'）动态导入并实例化类
用途：插件加载、引擎工厂、适配器工厂均依赖此模块
"""
class ClasspathLoader:
    _cache: Dict[str, Type] = {}

    @classmethod
    def load_class(cls, classpath: str) -> Type: ...

    @classmethod
    def instantiate(cls, classpath: str, **kwargs) -> Any: ...

    @classmethod
    def scan_package(cls, package_path: str) -> List[Type]: ...  # 扫描包下所有类
```

---

### 3.2 Core — IoC 容器（依赖注入）

#### 3.2.1 container.py — 核心容器（单例）

```python
"""
设计模式：单例模式
职责：全局服务容器，管理所有服务的注册与解析，支持单例/瞬态两种生命周期
"""
class Container:
    _instance: Optional['Container'] = None

    def __new__(cls) -> 'Container':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._services = {}
            cls._instance._singletons = {}
        return cls._instance

    def register(self, interface: Type, implementation: Type,
                 lifecycle: Lifecycle = Lifecycle.SINGLETON) -> None: ...

    def resolve(self, interface: Type) -> Any: ...

    def has(self, interface: Type) -> bool: ...

    def unregister(self, interface: Type) -> None: ...

    def reset(self) -> None: ...  # 仅测试用
```

#### 3.2.2 service_registry.py — 服务注册

```python
"""
职责：维护接口→实现的映射表，支持命名注册、标签注册
"""
class ServiceRegistry:
    def register(self, name: str, service: Any, tags: List[str] = None) -> None: ...
    def get(self, name: str) -> Any: ...
    def get_by_tag(self, tag: str) -> List[Any]: ...
    def list_all(self) -> Dict[str, Any]: ...
```

#### 3.2.3 dependency_resolver.py — 依赖解析器

```python
"""
职责：分析类的构造函数参数，自动从容器解析依赖并注入
"""
class DependencyResolver:
    def __init__(self, container: Container): ...
    def resolve(self, cls: Type) -> Any: ...  # 自动注入构造参数
    def resolve_method(self, obj: Any, method_name: str) -> Any: ...  # 方法注入
```

---

### 3.3 Core — 接口定义（面向接口编程）

所有接口均使用 Python `abc.ABC` + `abc.abstractmethod` 定义，禁止直接实例化。

| 接口文件 | 接口名 | 核心方法 |
|---|---|---|
| testable.py | `ITestable` | `setup()`, `execute()`, `teardown()`, `get_result()` |
| adaptable.py | `IAdaptable` | `adapt(target_type)`, `get_adapter_name()` |
| reportable.py | `IReportable` | `generate_report()`, `get_report_data()` |
| configurable.py | `IConfigurable` | `load_config()`, `validate_config()`, `get_config()` |
| executable.py | `IExecutable` | `execute(context)`, `cancel()`, `get_status()` |
| observable.py | `IObservable` | `subscribe()`, `unsubscribe()`, `notify()` |
| lifecycle.py | `ILifecycle` | `init()`, `start()`, `stop()`, `destroy()` |
| pluggable.py | `IPluggable` | `get_plugin_info()`, `activate()`, `deactivate()` |

---

### 3.4 Core — 领域模型

#### test_case.py

```python
@dataclass
class TestCase:
    id: str
    name: str
    test_type: TestType          # 枚举
    target: str                  # 被测目标标识
    config: Dict[str, Any]       # 用例私有配置
    tags: List[str]
    priority: Priority
    timeout: float
    retries: int
    metadata: Dict[str, Any]
```

#### test_suite.py（组合模式）

```python
@dataclass
class TestSuite:
    id: str
    name: str
    children: List[Union['TestSuite', TestCase]]  # 支持嵌套

    def add(self, child: Union['TestSuite', TestCase]) -> None: ...
    def remove(self, child_id: str) -> None: ...
    def get_all_cases(self) -> List[TestCase]: ...  # 递归展平
    def count(self) -> int: ...
```

#### test_plan.py

```python
@dataclass
class TestPlan:
    id: str
    name: str
    suites: List[TestSuite]
    global_config: Dict[str, Any]
    schedule: Optional[str]       # cron 表达式
    parallel: bool
    environment: str
```

#### test_result.py

```python
@dataclass
class TestResult:
    case_id: str
    status: TestStatus            # PASS / FAIL / ERROR / SKIP
    duration: float
    message: str
    details: Dict[str, Any]
    metrics: Optional['TestMetrics']
    timestamp: datetime
    attachments: List[str]        # 附件路径列表
```

#### test_metrics.py

```python
@dataclass
class TestMetrics:
    throughput: float
    latency_avg: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    error_rate: float
    cpu_usage: Optional[float]
    memory_usage: Optional[float]
    custom: Dict[str, float]
```

#### test_report.py

```python
@dataclass
class TestReport:
    id: str
    plan_id: str
    generated_at: datetime
    summary: Dict[str, Any]
    results: List[TestResult]
    metrics: TestMetrics
    verdict: Verdict              # PASS / FAIL / WARN
```

#### target_system.py

```python
@dataclass
class TargetSystem:
    id: str
    name: str
    base_url: Optional[str]
    host: str
    port: int
    protocol: str
    auth: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
```

#### execution_context.py

```python
@dataclass
class ExecutionContext:
    plan: TestPlan
    target: TargetSystem
    config: Dict[str, Any]
    env: EnvironmentInfo
    start_time: datetime
    variables: Dict[str, Any]     # 运行时共享变量
```

#### enums.py

```python
from enum import Enum

class TestType(Enum):
    WEB_PERFORMANCE = "web_performance"
    BACKEND_PERFORMANCE = "backend_performance"
    REST_API = "rest_api"
    DATABASE = "database"
    KNOWLEDGE_QA = "knowledge_qa"
    PENETRATION = "penetration"
    AUTH_BYPASS = "auth_bypass"

class TestStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"

class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class Lifecycle(Enum):
    SINGLETON = "singleton"
    TRANSIENT = "transient"

class Verdict(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
```

---

### 3.5 Core — 管道执行引擎（责任链模式）

#### pipeline.py

```python
"""
设计模式：责任链模式
职责：将测试执行拆分为多个有序阶段（Stage），每个阶段可拦截、跳过、重试
"""
class Pipeline:
    def __init__(self):
        self._stages: List[Stage] = []
        self._filters: List[Filter] = []
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)

    def add_stage(self, stage: 'Stage', priority: int = 0) -> 'Pipeline': ...
    def add_filter(self, filter_: 'Filter') -> 'Pipeline': ...
    def on(self, event: str, callback: Callable) -> 'Pipeline': ...

    async def execute(self, context: 'PipelineContext') -> 'PipelineContext':
        """按优先级依次执行 filters → stages，触发 hooks"""
```

#### stage.py

```python
from abc import ABC, abstractmethod

class Stage(ABC):
    name: str

    @abstractmethod
    async def process(self, context: 'PipelineContext') -> 'PipelineContext': ...

    async def on_error(self, context: 'PipelineContext', error: Exception) -> 'PipelineContext': ...
```

#### context.py

```python
@dataclass
class PipelineContext:
    execution_context: ExecutionContext
    current_stage: str
    data: Dict[str, Any]          # 阶段间传递数据
    errors: List[Exception]
    is_aborted: bool
```

#### filter.py

```python
class Filter(ABC):
    @abstractmethod
    def should_execute(self, context: PipelineContext, stage: Stage) -> bool: ...
```

#### hooks.py

```python
"""
钩子系统：支持 before_stage / after_stage / on_error / on_complete 四类钩子
"""
class HookManager:
    def register(self, event: str, callback: Callable, priority: int = 0) -> None: ...
    async def trigger(self, event: str, context: PipelineContext) -> None: ...
```

---

### 3.6 Core — 事件系统（观察者模式）

#### event_bus.py（单例）

```python
"""
设计模式：单例 + 观察者
"""
class EventBus:
    _instance: Optional['EventBus'] = None

    def __new__(cls) -> 'EventBus':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = defaultdict(list)
        return cls._instance

    def subscribe(self, event_type: str, listener: Callable, priority: int = 0) -> None: ...
    def unsubscribe(self, event_type: str, listener: Callable) -> None: ...
    async def publish(self, event: 'Event') -> None: ...
    def publish_sync(self, event: 'Event') -> None: ...
```

#### event.py

```python
@dataclass
class Event:
    type: str
    source: Any
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
```

#### event_types.py

```python
# 框架标准事件类型
class EventTypes:
    TEST_PLAN_STARTED = "test_plan.started"
    TEST_PLAN_COMPLETED = "test_plan.completed"
    TEST_SUITE_STARTED = "test_suite.started"
    TEST_SUITE_COMPLETED = "test_suite.completed"
    TEST_CASE_STARTED = "test_case.started"
    TEST_CASE_COMPLETED = "test_case.completed"
    TEST_CASE_FAILED = "test_case.failed"
    ENGINE_INITIALIZED = "engine.initialized"
    ENGINE_ERROR = "engine.error"
    REPORT_GENERATED = "report.generated"
```

#### listeners.py

```python
class ListenerRegistry:
    def auto_discover(self, package: str) -> None: ...  # 扫描并注册所有 @listener 装饰器
    def register(self, event_type: str, handler: Callable) -> None: ...
```

---

### 3.7 Core — 异常体系

```python
# base.py
class FrameworkException(Exception):
    def __init__(self, message: str, code: str = "FRAMEWORK_ERROR", details: Dict = None): ...

# config.py
class ConfigException(FrameworkException):
    """配置加载/验证失败"""

# execution.py
class ExecutionException(FrameworkException):
    """测试执行异常，包含引擎错误、超时、断言失败"""

class TimeoutException(ExecutionException): ...
class AssertionException(ExecutionException): ...

# adapter.py
class AdapterException(FrameworkException):
    """适配器连接/调用失败"""

# plugin.py
class PluginException(FrameworkException):
    """插件加载/激活失败"""
```

---

## 4. 验收标准

- [ ] 所有 `core/interfaces/` 接口均可被继承，无法直接实例化
- [ ] `Container` 单例可正确注册/解析服务，支持单例和瞬态生命周期
- [ ] `EventBus` 单例可正确订阅/发布事件，支持同步和异步
- [ ] `Pipeline` 可按优先级顺序执行 Stage，Filter 可拦截执行
- [ ] `Bootstrapper` 可完成完整启动流程并在容器注册核心服务
- [ ] `DependencyChecker` 可正确检测 Python/Node/系统工具依赖
- [ ] 所有领域模型可通过 Pydantic/dataclass 序列化/反序列化
- [ ] 异常体系层级清晰，可被上层精确捕获
- [ ] 全模块有完整单元测试覆盖
