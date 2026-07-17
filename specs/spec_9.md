# Spec 9：插件系统 + 调度器 + 装饰器 + 工具层

## 1. 概述

本 Spec 实现框架的横切支撑能力：  
- **插件系统**：可插拔架构，支持内置插件和用户自定义插件  
- **调度器**：顺序/并行/分布式/定时四种调度模式，命令模式封装  
- **装饰器**：计时/重试/限流/熔断/缓存/验证/日志/指标 8 个通用装饰器  
- **工具层**：日志/指标/数据工厂/文件处理/网络/异步/线程/时间/加密/验证等通用工具

**依赖**：Spec 1（core/*）, Spec 2（config/）  
**被依赖**：Spec 4 ~ Spec 6（引擎层使用装饰器和工具），Spec 8（报告层使用调度器）

---

## 2. 目标目录结构

```
uniplore-test-framework/
├── plugins/
│   ├── __init__.py
│   ├── manager.py               # 插件管理器
│   ├── loader.py                # 插件加载器
│   ├── hook.py                  # 插件钩子
│   ├── discovery.py             # 插件发现
│   ├── builtin/
│   │   ├── __init__.py
│   │   ├── web_plugin.py
│   │   ├── api_plugin.py
│   │   └── security_plugin.py
│   └── custom/
│       └── .keep
│
├── schedulers/
│   ├── __init__.py
│   ├── base.py                  # 调度器基类
│   ├── scheduler_factory.py     # 调度器工厂
│   ├── sequential.py            # 顺序调度
│   ├── parallel.py              # 并行调度
│   ├── distributed.py           # 分布式调度
│   └── cron.py                  # 定时调度
│
├── decorators/
│   ├── __init__.py
│   ├── timing.py                # @timing
│   ├── retry.py                 # @retry
│   ├── rate_limit.py            # @rate_limit
│   ├── circuit_breaker.py       # @circuit_breaker
│   ├── cache.py                 # @cache
│   ├── validate.py              # @validate
│   ├── log.py                   # @log
│   └── metrics.py               # @metrics
│
└── utils/
    ├── __init__.py
    ├── logger.py                # 日志工具
    ├── logger.js                # Node 日志
    ├── metrics.py               # 指标工具
    ├── data_factory.py          # 数据工厂
    ├── file_handler.py          # 文件处理
    ├── network.py               # 网络工具
    ├── async_utils.py           # 异步工具
    ├── threading.py             # 线程/协程工具
    ├── time_utils.py            # 时间工具
    ├── crypto.py                # 加密工具
    ├── validation.py            # 验证工具
    └── shell_utils.sh           # Shell 工具函数
```

---

## 3. 详细设计 — 插件系统

### 3.1 manager.py — 插件管理器

```python
"""
职责：管理插件生命周期：发现 → 加载 → 注册 → 激活 → 停用
"""
class PluginManager:
    def __init__(self, container: 'Container'):
        self._container = container
        self._plugins: Dict[str, 'PluginInfo'] = {}
        self._hooks = PluginHookSystem()

    def discover(self, plugin_dirs: List[str]) -> List['PluginInfo']:
        """扫描目录发现可用插件"""

    def load(self, plugin_id: str) -> None: ...
    def unload(self, plugin_id: str) -> None: ...
    def activate(self, plugin_id: str) -> None: ...
    def deactivate(self, plugin_id: str) -> None: ...
    def get_plugin(self, plugin_id: str) -> 'IPluggable': ...
    def list_plugins(self) -> List['PluginInfo']: ...
    def get_hooks(self) -> 'PluginHookSystem': ...
```

### 3.2 loader.py — 插件加载器

```python
"""职责：从文件/包动态加载插件类"""
class PluginLoader:
    def load_from_file(self, file_path: str) -> Type['IPluggable']: ...
    def load_from_package(self, package_path: str) -> List[Type['IPluggable']]: ...
    def load_from_entry_points(self, group: str = "uniplore-test-framework.plugins") -> List[Type['IPluggable']]: ...
```

### 3.3 hook.py — 插件钩子

```python
"""
职责：插件钩子系统，允许插件在框架关键节点注入逻辑
钩子类型：before_engine_run / after_engine_run / before_report / after_report / on_error
"""
class PluginHookSystem:
    def register_hook(self, hook_name: str, callback: Callable, priority: int = 0) -> None: ...
    def unregister_hook(self, hook_name: str, callback: Callable) -> None: ...
    async def trigger(self, hook_name: str, **kwargs) -> None: ...
    def list_hooks(self) -> Dict[str, List[Callable]]: ...
```

### 3.4 discovery.py — 插件发现

```python
"""职责：自动发现 plugins/builtin/ 和 plugins/custom/ 下的插件"""
class PluginDiscovery:
    def scan_directory(self, directory: str) -> List['PluginInfo']: ...
    def scan_entry_points(self) -> List['PluginInfo']: ...

@dataclass
class PluginInfo:
    id: str
    name: str
    version: str
    description: str
    author: str
    entry_class: str
    dependencies: List[str]
    enabled: bool = True
```

### 3.5 内置插件

#### builtin/web_plugin.py

```python
class WebPerformancePlugin(IPluggable):
    """网页性能测试插件：注册 WebPerformanceEngine，提供默认配置"""
    def get_plugin_info(self) -> PluginInfo: ...
    def activate(self) -> None: ...
    def deactivate(self) -> None: ...
```

#### builtin/api_plugin.py

```python
class APIPlugin(IPluggable):
    """REST API 测试插件"""
```

#### builtin/security_plugin.py

```python
class SecurityPlugin(IPluggable):
    """安全测试插件（渗透 + 越权）"""
```

---

## 4. 详细设计 — 调度器

### 4.1 base.py — 调度器基类（命令模式）

```python
"""
设计模式：命令模式
职责：将测试计划封装为命令对象，支持排队、取消、重试
"""
class BaseScheduler(ABC):
    @abstractmethod
    async def schedule(self, plan: TestPlan) -> TestReport: ...

    @abstractmethod
    async def cancel(self, plan_id: str) -> None: ...

    @abstractmethod
    def get_status(self, plan_id: str) -> str: ...
```

### 4.2 scheduler_factory.py

```python
class SchedulerFactory:
    @classmethod
    def create(cls, mode: str, **kwargs) -> BaseScheduler:
        """mode: sequential / parallel / distributed / cron"""
```

### 4.3 sequential.py — 顺序调度

```python
class SequentialScheduler(BaseScheduler):
    async def schedule(self, plan: TestPlan) -> TestReport:
        """按 suite 顺序逐一执行"""
```

### 4.4 parallel.py — 并行调度

```python
class ParallelScheduler(BaseScheduler):
    def __init__(self, max_workers: int = 4): ...
    async def schedule(self, plan: TestPlan) -> TestReport:
        """使用 asyncio.gather 并行执行多个 suite"""
```

### 4.5 distributed.py — 分布式调度

```python
class DistributedScheduler(BaseScheduler):
    """分布式调度：将任务分发到多个 worker 节点"""
    async def schedule(self, plan: TestPlan) -> TestReport: ...
    async def _dispatch(self, task: Dict, workers: List[str]) -> Any: ...
    async def _collect_results(self, task_ids: List[str]) -> List[TestResult]: ...
```

### 4.6 cron.py — 定时调度

```python
class CronScheduler(BaseScheduler):
    """定时调度：基于 cron 表达式周期性执行测试计划"""
    async def schedule(self, plan: TestPlan) -> TestReport: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def list_jobs(self) -> List[Dict]: ...
```

---

## 5. 详细设计 — 装饰器

### 5.1 timing.py

```python
"""@timing — 计时装饰器，记录函数执行时间并发布事件"""
def timing(func=None, *, event_name: str = None):
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
                return result
            finally:
                elapsed = time.monotonic() - start
                logger.debug(f"{fn.__name__} took {elapsed:.3f}s")
        return wrapper
    return decorator(func) if func else decorator
```

### 5.2 retry.py

```python
"""@retry — 重试装饰器，支持固定间隔/指数退避"""
def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0,
          exceptions: Tuple = (Exception,)):
    ...
```

### 5.3 rate_limit.py

```python
"""@rate_limit — 限流装饰器"""
def rate_limit(rps: int = 100):
    ...
```

### 5.4 circuit_breaker.py

```python
"""@circuit_breaker — 熔断装饰器（三态：关闭/打开/半开）"""
def circuit_breaker(failure_threshold: int = 5, recovery_timeout: float = 60):
    ...
```

### 5.5 cache.py

```python
"""@cache — 缓存装饰器（内存 / Redis）"""
def cache(ttl: float = 300, backend: str = "memory"):
    ...
```

### 5.6 validate.py

```python
"""@validate — 参数验证装饰器"""
def validate(**schemas):
    ...
```

### 5.7 log.py

```python
"""@log — 日志装饰器，自动记录入参/出参/异常"""
def log(level: str = "DEBUG", log_args: bool = True, log_result: bool = True):
    ...
```

### 5.8 metrics.py

```python
"""@metrics — 指标装饰器，采集调用次数/耗时/错误率"""
def metrics(name: str = None):
    ...
```

---

## 6. 详细设计 — 工具层

### 6.1 logger.py

```python
"""统一日志工具，支持文件+控制台+结构化 JSON 日志"""
class FrameworkLogger:
    def __init__(self, config: Dict): ...
    def get_logger(self, name: str) -> logging.Logger: ...
    def setup_from_config(self, config: Dict) -> None: ...

def get_logger(name: str) -> logging.Logger:
    """模块级快捷函数"""
```

### 6.2 metrics.py

```python
"""指标收集工具"""
class MetricsCollector:
    _instance = None
    def record(self, name: str, value: float, tags: Dict = None) -> None: ...
    def get(self, name: str) -> List[float]: ...
    def summary(self, name: str) -> Dict[str, float]: ...
    def reset(self) -> None: ...
```

### 6.3 data_factory.py（工厂模式）

```python
"""测试数据工厂"""
class DataFactory:
    @staticmethod
    def random_string(length: int = 10) -> str: ...
    @staticmethod
    def random_int(min_val: int = 0, max_val: int = 10000) -> int: ...
    @staticmethod
    def random_email() -> str: ...
    @staticmethod
    def random_uuid() -> str: ...
    @staticmethod
    def random_json(schema: Dict = None) -> Dict: ...
    @staticmethod
    def from_csv(file_path: str) -> List[Dict]: ...
    @staticmethod
    def from_json(file_path: str) -> List[Dict]: ...
```

### 6.4 ~ 6.12 其他工具（简要说明）

| 文件 | 职责 |
|---|---|
| file_handler.py | 文件读写、目录创建、临时文件管理、YAML/JSON 读写 |
| network.py | 端口检测、HTTP 连通性检测、DNS 解析 |
| async_utils.py | asyncio 工具：run_sync、gather_with_concurrency、timeout |
| threading.py | 线程池管理、协程池、并发控制信号量 |
| time_utils.py | 时间格式化、时区转换、cron 表达式解析 |
| crypto.py | MD5/SHA256、JWT 编解码、AES 加解密 |
| validation.py | JSON Schema 验证、类型检查、数据格式校验 |
| shell_utils.sh | Shell 公共函数（日志、端口等待、进程管理） |
| logger.js | Node.js 侧统一日志，与 Python 日志格式对齐 |

---

## 7. 验收标准

- [ ] 插件管理器可发现/加载/激活/停用插件
- [ ] 内置插件可正确注册对应引擎
- [ ] 自定义插件放入 `plugins/custom/` 后可被自动发现
- [ ] 插件钩子可在引擎执行前后注入逻辑
- [ ] 顺序调度器可逐 suite 执行
- [ ] 并行调度器可并发执行多个 suite
- [ ] 定时调度器可按 cron 表达式周期执行
- [ ] 8 个装饰器均可独立使用，支持组合
- [ ] 熔断器三态转换正确
- [ ] 工具层各模块功能正常
- [ ] 全模块有完整单元测试覆盖
