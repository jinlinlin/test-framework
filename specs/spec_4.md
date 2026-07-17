# Spec 4：性能测试引擎 — 网页性能测试 + 后端性能测试

## 1. 概述

本 Spec 实现框架七大测试引擎中的两个性能测试引擎：  
- **① 网页性能测试引擎**：基于 Playwright 实现网页自动化渲染、资源加载监控、Web Vitals 采集，集成 Lighthouse 完成综合性能评分  
- **② 后端性能测试引擎**：支持多语言后端服务，提供 HTTP/gRPC 负载施压，采集 CPU/内存/JVM/pprof 等多维度运行指标

**依赖**：Spec 1（core/*）, Spec 2（config/*）, Spec 3（languages/*）  
**被依赖**：无（叶子模块）

---

## 2. 目标目录结构

```
uniplore-test-framework/
└── engines/
    ├── __init__.py
    ├── base.py                    # 引擎基类（所有引擎共享）
    ├── engine_factory.py          # 引擎工厂（工厂模式）
    ├── engine_registry.py         # 引擎注册表
    │
    ├── web_performance/           # ① 网页性能测试
    │   ├── __init__.py
    │   ├── engine.py              # 引擎主类（模板模式）
    │   ├── playwright_client.py   # Playwright 客户端（适配器模式）
    │   ├── page_analyzer.py       # 页面分析器
    │   ├── resource_monitor.py    # 资源监控
    │   ├── web_vitals.py          # Web Vitals 采集
    │   ├── lighthouse_integration.py
    │   └── config_schema.py
    │
    └── backend_performance/       # ② 后端性能测试
        ├── __init__.py
        ├── engine.py
        ├── http_loader.py         # HTTP 负载发生器
        ├── grpc_loader.py         # gRPC 负载发生器
        ├── resource_collector.py  # 资源采集器
        ├── jvm_monitor.py
        ├── go_monitor.py
        ├── node_monitor.py
        ├── python_monitor.py
        ├── container_monitor.py
        └── config_schema.py
```

---

## 3. 详细设计

### 3.1 engines/base.py — 引擎基类（模板模式）

```python
"""
设计模式：模板模式
职责：定义所有测试引擎的统一执行骨架，子类仅需实现差异化逻辑
生命周期：validate_config → setup → [execute × N] → collect_metrics → teardown
"""
from abc import ABC, abstractmethod

class BaseEngine(ABC):
    def __init__(self, config: Dict[str, Any], container: 'Container'):
        self._config = config
        self._container = container
        self._event_bus = container.resolve(EventBus)
        self._results: List[TestResult] = []

    @property
    @abstractmethod
    def engine_type(self) -> TestType: ...

    async def run(self, plan: TestPlan, target: TargetSystem) -> TestReport:
        """模板方法：固定执行流程，子类实现各步骤"""
        self.validate_config()
        await self.setup(target)
        try:
            for suite in plan.suites:
                for case in suite.get_all_cases():
                    await self._event_bus.publish(Event(EventTypes.TEST_CASE_STARTED, self, {"case": case}))
                    result = await self.execute_case(case, target)
                    self._results.append(result)
                    await self._event_bus.publish(Event(EventTypes.TEST_CASE_COMPLETED, self, {"result": result}))
            metrics = await self.collect_metrics()
            report = await self.generate_report(plan, metrics)
            return report
        finally:
            await self.teardown()

    def validate_config(self) -> None: ...

    @abstractmethod
    async def setup(self, target: TargetSystem) -> None: ...

    @abstractmethod
    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult: ...

    @abstractmethod
    async def collect_metrics(self) -> TestMetrics: ...

    @abstractmethod
    async def teardown(self) -> None: ...

    async def generate_report(self, plan: TestPlan, metrics: TestMetrics) -> TestReport: ...
```

### 3.2 engine_factory.py — 引擎工厂

```python
"""
设计模式：工厂模式
职责：根据 TestType 创建对应引擎实例
"""
class EngineFactory:
    _registry: Dict[TestType, Type[BaseEngine]] = {}

    @classmethod
    def register(cls, test_type: TestType, engine_cls: Type[BaseEngine]) -> None: ...

    @classmethod
    def create(cls, test_type: TestType, config: Dict, container: 'Container') -> BaseEngine: ...

    @classmethod
    def available_engines(cls) -> List[TestType]: ...
```

### 3.3 engine_registry.py

```python
"""
职责：引擎注册表，支持插件式注册/发现引擎
"""
class EngineRegistry:
    def register(self, engine_type: TestType, metadata: Dict) -> None: ...
    def get_metadata(self, engine_type: TestType) -> Dict: ...
    def list_all(self) -> Dict[TestType, Dict]: ...
```

### 3.4 网页性能测试引擎

#### web_performance/engine.py（模板模式）

```python
"""
职责：网页性能测试引擎主类
执行流程：启动浏览器 → 访问页面 → 采集 Web Vitals → 运行 Lighthouse → 生成报告
"""
class WebPerformanceEngine(BaseEngine):
    engine_type = TestType.WEB_PERFORMANCE

    def __init__(self, config, container):
        super().__init__(config, container)
        self._playwright = None
        self._vitals_collector = WebVitalsCollector(config)
        self._lighthouse = LighthouseIntegration(config)
        self._resource_monitor = ResourceMonitor(config)

    async def setup(self, target: TargetSystem) -> None:
        self._playwright = PlaywrightClient(self._config)
        await self._playwright.launch()

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        url = f"{target.base_url}{case.config.get('path', '/')}"
        page = await self._playwright.new_page()
        try:
            # 1. 资源监控开始
            await self._resource_monitor.start(page)
            # 2. 导航
            response = await page.goto(url, wait_until="networkidle")
            # 3. 采集 Web Vitals
            vitals = await self._vitals_collector.collect(page)
            # 4. 页面分析
            analysis = await PageAnalyzer(page).analyze()
            # 5. 可选：Lighthouse
            lighthouse_score = None
            if self._config.get("lighthouse", {}).get("enabled"):
                lighthouse_score = await self._lighthouse.audit(url)
            return TestResult(
                case_id=case.id,
                status=TestStatus.PASS,
                duration=analysis["load_time"],
                details={"vitals": vitals, "analysis": analysis, "lighthouse": lighthouse_score},
                metrics=TestMetrics(
                    latency_avg=vitals.get("LCP", 0),
                    custom=vitals
                ),
                timestamp=datetime.now()
            )
        finally:
            await page.close()

    async def teardown(self) -> None:
        if self._playwright:
            await self._playwright.close()
```

#### web_performance/playwright_client.py（适配器模式）

```python
"""
设计模式：适配器模式
职责：封装 Playwright API，提供统一的浏览器操作接口
"""
class PlaywrightClient:
    def __init__(self, config: Dict): ...

    async def launch(self, browser_type: str = "chromium", headless: bool = True) -> None: ...
    async def new_page(self, viewport: Dict = None) -> Any: ...
    async def close(self) -> None: ...
    async def screenshot(self, page, path: str) -> str: ...
    async def evaluate(self, page, expression: str) -> Any: ...
```

#### web_performance/web_vitals.py

```python
"""
职责：采集 Web Vitals 指标（LCP、FCP、CLS、FID、INP、TTFB）
"""
class WebVitalsCollector:
    METRICS = ["LCP", "FCP", "CLS", "FID", "INP", "TTFB"]

    def __init__(self, config: Dict): ...

    async def collect(self, page) -> Dict[str, float]:
        """注入 JS 脚本采集各指标"""

    def evaluate_thresholds(self, vitals: Dict[str, float]) -> Dict[str, str]:
        """对比阈值，返回 PASS/WARN/FAIL"""
```

#### web_performance/lighthouse_integration.py

```python
"""
职责：集成 Lighthouse CLI，执行综合性能审计
"""
class LighthouseIntegration:
    def __init__(self, config: Dict): ...

    async def audit(self, url: str, categories: List[str] = None) -> Dict[str, Any]:
        """调用 lighthouse CLI，解析 JSON 报告"""

    def parse_report(self, raw_report: Dict) -> Dict[str, float]:
        """提取各类评分"""
```

#### web_performance/resource_monitor.py

```python
"""
职责：监控页面加载过程中的网络请求、资源大小、请求数
"""
class ResourceMonitor:
    async def start(self, page) -> None: ...
    async def stop(self) -> Dict[str, Any]: ...
    def get_summary(self) -> Dict[str, Any]: ...
```

#### web_performance/page_analyzer.py

```python
"""
职责：分析页面 DOM 结构、加载时间、关键渲染路径
"""
class PageAnalyzer:
    def __init__(self, page): ...
    async def analyze(self) -> Dict[str, Any]: ...
```

#### web_performance/config_schema.py

```python
WEB_PERFORMANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "browser": {"type": "string", "enum": ["chromium", "firefox", "webkit"]},
        "headless": {"type": "boolean"},
        "timeout": {"type": "integer"},
        "viewport": {"type": "object", "properties": {"width": {"type": "integer"}, "height": {"type": "integer"}}},
        "lighthouse": {"type": "object", "properties": {"enabled": {"type": "boolean"}}},
        "web_vitals": {"type": "object", "properties": {
            "metrics": {"type": "array"},
            "thresholds": {"type": "object"}
        }}
    }
}
```

### 3.5 后端性能测试引擎

#### backend_performance/engine.py

```python
"""
职责：后端性能测试引擎，支持 HTTP/gRPC 负载施压
可调度 Node.js 引擎实现高并发（通过 LanguageBridge）
"""
class BackendPerformanceEngine(BaseEngine):
    engine_type = TestType.BACKEND_PERFORMANCE

    async def setup(self, target: TargetSystem) -> None:
        protocol = target.protocol
        if protocol in ("http", "https"):
            self._loader = HTTPLoader(self._config, target)
        elif protocol == "grpc":
            self._loader = GRPCLoader(self._config, target)

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        load_profile = case.config.get("load_profile", "constant")
        strategy = LoadStrategyFactory.create(load_profile, case.config)
        # 执行负载
        raw_results = await self._loader.apply_load(strategy)
        # 采集资源指标
        resources = await self._resource_collector.collect()
        return self._build_result(case, raw_results, resources)
```

#### backend_performance/http_loader.py

```python
"""
职责：HTTP 负载发生器，支持 GET/POST/PUT/DELETE，可配置并发数和持续时间
"""
class HTTPLoader:
    def __init__(self, config: Dict, target: TargetSystem): ...

    async def apply_load(self, strategy: 'LoadStrategy') -> Dict[str, Any]:
        """
        返回：{total_requests, success_count, fail_count,
               latency_avg, latency_p50, latency_p95, latency_p99,
               throughput, error_rate}
        """

    async def _send_request(self, session, method, url, **kwargs) -> Dict: ...
```

#### backend_performance/grpc_loader.py

```python
"""
职责：gRPC 负载发生器，基于 grpcio 实现
"""
class GRPCLoader:
    async def apply_load(self, strategy: 'LoadStrategy') -> Dict[str, Any]: ...
    async def _invoke_rpc(self, channel, method, request) -> Dict: ...
```

#### backend_performance/resource_collector.py

```python
"""
职责：采集被测服务的 CPU、内存、网络 IO 指标
支持直连进程、Docker stats、K8s metrics API 三种采集方式
"""
class ResourceCollector:
    def __init__(self, config: Dict): ...
    async def start(self) -> None: ...
    async def collect(self) -> Dict[str, float]: ...
    async def stop(self) -> None: ...
```

#### backend_performance/jvm_monitor.py

```python
"""
职责：通过 JMX / Jolokia 采集 JVM 指标（堆内存、GC、线程数）
"""
class JVMMonitor:
    async def connect(self, host: str, port: int) -> None: ...
    async def collect(self) -> Dict[str, Any]: ...
    async def disconnect(self) -> None: ...
```

#### backend_performance/go_monitor.py

```python
"""
职责：通过 Go pprof HTTP 端点采集 goroutine、heap、CPU profile
"""
class GoMonitor:
    async def collect(self, pprof_url: str) -> Dict[str, Any]: ...
```

#### backend_performance/node_monitor.py

```python
"""
职责：通过 Node.js process.metrics() 或 clinic.js 采集事件循环延迟、堆内存
"""
class NodeMonitor:
    async def collect(self, metrics_url: str) -> Dict[str, Any]: ...
```

#### backend_performance/python_monitor.py

```python
"""
职责：通过 psutil 或 Prometheus 客户端采集 Python 进程指标
"""
class PythonMonitor:
    async def collect(self, pid: int = None) -> Dict[str, Any]: ...
```

#### backend_performance/container_monitor.py

```python
"""
职责：采集 Docker/K8s 容器的 CPU、内存、网络 IO
"""
class ContainerMonitor:
    async def collect_docker(self, container_id: str) -> Dict[str, Any]: ...
    async def collect_k8s(self, pod_name: str, namespace: str = "default") -> Dict[str, Any]: ...
```

---

## 4. 验收标准

- [ ] `BaseEngine` 模板方法流程正确，子类仅需实现差异步骤
- [ ] `EngineFactory` 可按 TestType 创建对应引擎
- [ ] Web 引擎可启动 Playwright 浏览器、导航、采集 Web Vitals 指标
- [ ] Lighthouse 集成可输出性能评分
- [ ] Backend 引擎可对 HTTP 服务施压并采集延迟百分位指标
- [ ] Backend 引擎可对 gRPC 服务施压
- [ ] JVM/Go/Node/Python/Container 监控可正确采集各自指标
- [ ] 两个引擎均可输出标准化 `TestReport`
- [ ] 全模块有完整单元测试覆盖
