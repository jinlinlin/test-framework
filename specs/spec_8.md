# Spec 8：策略层 + 报告层

## 1. 概述

本 Spec 实现框架的策略层和报告层：  
- **策略层**：封装可替换的负载策略、验证策略、重试策略，通过策略模式实现动态切换  
- **报告层**：通过观察者模式实现事件驱动的报告生成，支持 HTML/JSON/Console/Allure 及外部推送（Grafana/Prometheus/Slack/Email）

**依赖**：Spec 1（core/events/*, core/models/*）, Spec 2（config/）  
**被依赖**：Spec 4 ~ Spec 6（引擎层使用策略），所有层均使用报告

---

## 2. 目标目录结构

```
uniplore-test-framework/
├── strategies/
│   ├── __init__.py
│   ├── base.py                  # 策略基类
│   ├── strategy_factory.py      # 策略工厂
│   ├── load/                    # 负载策略
│   │   ├── __init__.py
│   │   ├── constant.py
│   │   ├── ramp_up.py
│   │   ├── spike.py
│   │   ├── soak.py
│   │   ├── step.py
│   │   └── wave.py
│   ├── validation/              # 验证策略
│   │   ├── __init__.py
│   │   ├── threshold.py
│   │   ├── percentile.py
│   │   ├── trend.py
│   │   └── custom.py
│   └── retry/                   # 重试策略
│       ├── __init__.py
│       ├── fixed.py
│       ├── exponential.py
│       └── custom.py
│
└── reporters/
    ├── __init__.py
    ├── base.py                  # 报告器基类
    ├── reporter_factory.py      # 报告器工厂
    ├── reporter_registry.py     # 报告器注册表
    ├── html/
    │   ├── __init__.py
    │   ├── reporter.py
    │   ├── templates/
    │   │   ├── base.html
    │   │   ├── summary.html
    │   │   ├── detail.html
    │   │   └── security.html
    │   └── assets/
    │       ├── css/
    │       └── js/
    ├── json/
    │   ├── __init__.py
    │   └── reporter.py
    ├── console/
    │   ├── __init__.py
    │   └── reporter.py
    ├── allure/
    │   ├── __init__.py
    │   └── reporter.py
    └── external/
        ├── __init__.py
        ├── grafana.py
        ├── prometheus.py
        ├── slack.py
        └── email.py
```

---

## 3. 详细设计 — 策略层

### 3.1 base.py — 策略基类

```python
"""
设计模式：策略模式
职责：定义所有策略的统一接口
"""
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    @property
    @abstractmethod
    def strategy_type(self) -> str: ...   # "load" / "validation" / "retry"

    @property
    @abstractmethod
    def name(self) -> str: ...
```

### 3.2 strategy_factory.py

```python
class StrategyFactory:
    _registry: Dict[str, Dict[str, Type[BaseStrategy]]] = {}

    @classmethod
    def register(cls, strategy_type: str, name: str, cls_: Type[BaseStrategy]) -> None: ...

    @classmethod
    def create(cls, strategy_type: str, name: str, **kwargs) -> BaseStrategy: ...

    @classmethod
    def create_from_config(cls, config: Dict) -> BaseStrategy:
        """根据配置中的 strategy 字段自动创建"""
```

### 3.3 负载策略

#### load/constant.py

```python
"""恒定负载：固定并发数持续运行"""
class ConstantLoadStrategy(BaseStrategy):
    strategy_type = "load"
    name = "constant"

    def __init__(self, concurrency: int, duration: float): ...
    def get_load_profile(self) -> 'LoadProfile': ...
```

#### load/ramp_up.py

```python
"""逐步上升：并发数线性增长"""
class RampUpLoadStrategy(BaseStrategy):
    name = "ramp_up"
    def __init__(self, start: int, end: int, ramp_duration: float): ...
```

#### load/spike.py

```python
"""尖峰负载：突然大量请求，测试系统恢复能力"""
class SpikeLoadStrategy(BaseStrategy):
    name = "spike"
    def __init__(self, normal: int, spike: int, spike_duration: float): ...
```

#### load/soak.py

```python
"""浸泡负载：中等负载持续长时间，检测内存泄漏"""
class SoakLoadStrategy(BaseStrategy):
    name = "soak"
    def __init__(self, concurrency: int, duration: float): ...
```

#### load/step.py

```python
"""阶梯负载：分阶段递增并发数"""
class StepLoadStrategy(BaseStrategy):
    name = "step"
    def __init__(self, steps: List[Dict]): ...
```

#### load/wave.py

```python
"""波浪负载：周期性波动，模拟真实流量"""
class WaveLoadStrategy(BaseStrategy):
    name = "wave"
    def __init__(self, min_concurrency: int, max_concurrency: int, period: float): ...
```

### 3.4 验证策略

#### validation/threshold.py

```python
"""阈值验证：指标是否超过设定阈值"""
class ThresholdValidationStrategy(BaseStrategy):
    strategy_type = "validation"
    name = "threshold"

    def __init__(self, thresholds: Dict[str, float]): ...
    def validate(self, metrics: TestMetrics) -> ValidationResult:
        """逐指标对比阈值"""
```

#### validation/percentile.py

```python
"""百分位验证：P95/P99 是否达标"""
class PercentileValidationStrategy(BaseStrategy):
    name = "percentile"
```

#### validation/trend.py

```python
"""趋势验证：对比历史数据，检测性能退化"""
class TrendValidationStrategy(BaseStrategy):
    name = "trend"
```

#### validation/custom.py

```python
"""自定义验证：用户自定义验证函数"""
class CustomValidationStrategy(BaseStrategy):
    name = "custom"
    def __init__(self, validate_fn: Callable): ...
```

### 3.5 重试策略

#### retry/fixed.py

```python
"""固定间隔重试"""
class FixedRetryStrategy(BaseStrategy):
    strategy_type = "retry"
    name = "fixed"
    def __init__(self, max_retries: int, interval: float): ...
    async def execute_with_retry(self, fn: Callable) -> Any: ...
```

#### retry/exponential.py

```python
"""指数退避重试"""
class ExponentialRetryStrategy(BaseStrategy):
    name = "exponential"
    def __init__(self, max_retries: int, base_interval: float, max_interval: float): ...
```

#### retry/custom.py

```python
class CustomRetryStrategy(BaseStrategy):
    name = "custom"
```

---

## 4. 详细设计 — 报告层

### 4.1 base.py — 报告器基类

```python
"""
设计模式：观察者模式
职责：报告器订阅事件总线事件，收集结果并在适当时机生成报告
"""
class BaseReporter(ABC):
    @property
    @abstractmethod
    def reporter_type(self) -> str: ...

    @abstractmethod
    async def on_test_completed(self, report: TestReport) -> None: ...

    @abstractmethod
    async def on_plan_completed(self, plan: TestPlan, results: List[TestResult]) -> str:
        """生成最终报告，返回报告路径"""
```

### 4.2 reporter_factory.py

```python
class ReporterFactory:
    @classmethod
    def create(cls, reporter_type: str, **kwargs) -> BaseReporter: ...
    @classmethod
    def create_from_config(cls, config: Dict) -> List[BaseReporter]: ...
```

### 4.3 reporter_registry.py

```python
"""报告器注册表：管理所有活跃报告器"""
class ReporterRegistry:
    def register(self, reporter: BaseReporter) -> None: ...
    def unregister(self, reporter_type: str) -> None: ...
    def get_all(self) -> List[BaseReporter]: ...
    async def notify_all(self, event: str, data: Any) -> None: ...
```

### 4.4 HTML 报告

#### html/reporter.py

```python
class HTMLReporter(BaseReporter):
    reporter_type = "html"

    def __init__(self, output_dir: str, template_dir: str = None): ...

    async def on_plan_completed(self, plan, results) -> str:
        """使用 Jinja2 渲染 HTML 模板，生成独立可浏览的报告文件"""

    def _render_summary(self, report: TestReport) -> str: ...
    def _render_detail(self, results: List[TestResult]) -> str: ...
    def _render_security(self, findings: List) -> str: ...
```

#### 模板文件

- `base.html`：基础布局模板（导航栏、样式框架）
- `summary.html`：测试概览（通过率、耗时、指标汇总）
- `detail.html`：每个用例的详细结果
- `security.html`：安全测试专项报告（漏洞列表、风险分级）

### 4.5 JSON 报告

```python
class JSONReporter(BaseReporter):
    reporter_type = "json"

    async def on_plan_completed(self, plan, results) -> str:
        """将 TestReport 序列化为 JSON 文件"""
```

### 4.6 Console 报告

```python
class ConsoleReporter(BaseReporter):
    reporter_type = "console"

    async def on_test_completed(self, report) -> None:
        """实时打印每个用例的执行结果（彩色输出）"""

    async def on_plan_completed(self, plan, results) -> str:
        """打印汇总统计"""
```

### 4.7 Allure 集成

```python
class AllureReporter(BaseReporter):
    reporter_type = "allure"

    async def on_test_completed(self, report) -> None:
        """写入 allure 结果文件，可被 allure serve 查看"""
```

### 4.8 外部集成

#### external/grafana.py

```python
class GrafanaPusher:
    async def push(self, metrics: TestMetrics, tags: Dict = None) -> None:
        """将指标推送到 Grafana（通过 InfluxDB/Prometheus 数据源）"""
```

#### external/prometheus.py

```python
class PrometheusPusher:
    async def push(self, metrics: TestMetrics, job: str, gateway: str) -> None:
        """推送到 Prometheus Push Gateway"""
```

#### external/slack.py

```python
class SlackNotifier:
    async def notify(self, report: TestReport, webhook_url: str) -> None:
        """发送 Slack 消息通知"""
```

#### external/email.py

```python
class EmailReporter:
    async def send(self, report: TestReport, recipients: List[str],
                   smtp_config: Dict) -> None:
        """发送测试报告邮件"""
```

---

## 5. 验收标准

- [ ] 6 种负载策略均可生成正确的负载曲线
- [ ] 4 种验证策略均可验证 `TestMetrics`
- [ ] 3 种重试策略均可正确重试并处理异常
- [ ] `StrategyFactory` 可按名称和配置创建策略
- [ ] HTML 报告可独立在浏览器打开，含图表和汇总
- [ ] JSON 报告可被程序解析，结构与 `TestReport` 一致
- [ ] Console 报告可彩色实时输出
- [ ] Allure 报告可被 `allure serve` 正确展示
- [ ] Grafana/Prometheus/Slack/Email 外部推送接口完整
- [ ] 报告器注册表可管理多个报告器并行工作
- [ ] 全模块有完整单元测试覆盖
