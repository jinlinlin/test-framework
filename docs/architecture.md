# 架构设计

## 总体架构

Uniplore Test Framework 采用 **分层 + 模块化** 架构，自底向上分为 11 层：

```
┌──────────────────────────────────────────────────┐
│                  运维脚本层 (Shell)                │
├──────────────────────────────────────────────────┤
│               插件 + 调度 + 装饰器层               │
├──────────────────────────────────────────────────┤
│              策略层 + 报告层 + 扩展层              │
├──────────────────────────────────────────────────┤
│                   适配器层                        │
├──────────────────────────────────────────────────┤
│               七大测试引擎层                       │
├──────────────────────────────────────────────────┤
│               多语言桥接层                        │
├──────────────────────────────────────────────────┤
│               配置管理层                          │
├──────────────────────────────────────────────────┤
│   IoC 容器  │  接口契约  │  领域模型  │  事件总线  │
├──────────────────────────────────────────────────┤
│                  启动引导层                        │
└──────────────────────────────────────────────────┘
```

---

## 设计模式

框架深度应用十余种经典设计模式：

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **单例** | Container、EventBus、Bootstrapper | 全局唯一实例 |
| **工厂** | EngineFactory、AdapterFactory、ReporterFactory | 按类型创建实例 |
| **策略** | LoadStrategy、ValidationStrategy、RetryStrategy | 可替换的算法族 |
| **模板** | BaseEngine | 统一引擎执行流程骨架 |
| **观察者** | EventBus | 发布/订阅事件驱动 |
| **责任链** | Pipeline + Stage | 阶段链式处理 |
| **命令** | SchedulePlan | 调度计划封装 |
| **建造者** | RequestBuilder | 链式构建 HTTP 请求 |
| **组合** | TestSuite → TestCase | 树形组合 |
| **适配器** | HTTP/Browser/Database/... | 统一中间件接口 |
| **桥接** | PythonBridge / NodeBridge | 多语言互操作 |
| **装饰器** | timing/retry/rate_limit/... | 横切关注点 |
| **对象池** | ConnectionPool | 数据库连接复用 |

---

## 核心模块关系

```
Bootstrapper
    ├── EnvironmentDetector    环境检测
    ├── DependencyChecker      依赖检查
    ├── Container (IoC)        服务注册/解析
    │     ├── EventBus         事件总线
    │     ├── ConfigManager    配置管理
    │     └── EngineFactory    引擎工厂
    └── ClasspathLoader        动态类加载

EngineFactory
    └── BaseEngine (模板方法)
          ├── WebPerformanceEngine
          ├── BackendPerformanceEngine
          ├── RestAPIEngine
          ├── DatabaseEngine
          ├── KnowledgeQAEngine
          ├── PenetrationEngine
          └── AuthBypassEngine

AdapterFactory
    └── BaseAdapter (适配器接口)
          ├── HttpAdapter
          ├── BrowserAdapter
          ├── DatabaseAdapter
          ├── MessagingAdapter
          └── LoadGeneratorAdapter
```

---

## 报告三层分离与跨引擎聚合

| 层 | 职责 | 产物 | 实现 |
|---|---|---|---|
| Layer 1 | 各引擎原生报告完整保留 | `artifacts/{engine}/{run_id}/`（junit.xml 等） | 各引擎自身 |
| Layer 2 | 单引擎单次运行的统一结果契约 | 同目录 `summary.json`（schema 1.0：totals/failures/plan_name） | `JSONReporter.on_plan_completed` |
| Layer 3 | 跨引擎总览，回答"这一轮整体质量如何" | `artifacts/aggregate/{aggregate_id}/aggregate.json` + 控制台总览 | `reporters/aggregator/cross_engine.py` |

聚合器只读消费 Layer 2 契约，坏数据（损坏/schema 违规/主版本不兼容）
不静默——全部计入 `sources.warning_detail`；通过率按用例数加权合并，
不对各 run 百分比取平均。支持 `engines`/`since` 过滤限定聚合窗口。
外部推送（IM/邮件/看板）规划同样收敛到 Layer 3，尚未实现。

---

## IoC 容器

IoC 容器是框架的核心基础设施，管理所有服务的生命周期：

```python
from test_framework.core.container import Container
from test_framework.core.models.enums import Lifecycle

container = Container()

# 注册 — 接口绑定实现类
container.register(IEventBus, EventBus, Lifecycle.SINGLETON)
container.register(IReporter, HtmlReporter, Lifecycle.TRANSIENT)

# 解析 — 按接口获取实例
bus = container.resolve(IEventBus)      # 单例，返回缓存实例
reporter = container.resolve(IReporter) # 瞬态，每次创建新实例
```

**生命周期**：
- `SINGLETON` — 全局唯一，首次 resolve 时创建并缓存
- `TRANSIENT` — 每次 resolve 创建新实例

---

## 事件系统

基于发布/订阅模式的事件总线，实现模块间松耦合通信：

```python
from test_framework.core.events import EventBus

bus = EventBus()

# 订阅
bus.subscribe("test.started", lambda data: print(f"开始: {data}"))
bus.subscribe("test.completed", lambda data: print(f"完成: {data}"))

# 发布
bus.publish("test.started", {"test_id": "TC-001"})
bus.publish("test.completed", {"test_id": "TC-001", "status": "passed"})
```

**内置事件类型**：
- `test.started` / `test.completed` / `test.failed`
- `engine.initialized` / `engine.shutdown`
- `config.loaded` / `config.reloaded`
- `plugin.activated` / `plugin.deactivated`

---

## 管道引擎

责任链模式，将测试执行拆分为多个阶段（Stage）：

```
Filter → Stage A → Stage B → Stage C → Hook
         (准备)    (执行)    (清理)
```

每个 Stage 实现 `execute(context)` 方法，PipelineContext 在阶段间传递数据。

---

## 异常体系

```
FrameworkException (基类)
├── ConfigException       配置异常
├── ExecutionException    执行异常
├── AdapterException      适配器异常
└── PluginException       插件异常
```

所有框架异常继承自 `FrameworkException`，便于统一捕获和处理。

---

## 多语言协同

```
Python 核心框架 ──(子进程/IPC)──→ Node.js 高性能引擎
       │                                │
       ├──(subprocess)──→ Shell 运维     ├── HTTP 压测
       │                  脚本          ├── WebSocket 测试
       │                                └── gRPC 测试
       │
       └── 统一通过 JSON 协议通信
```

- **Python ↔ Node.js**：通过 stdin/stdout JSON 协议或子进程调用
- **Python ↔ Shell**：通过 subprocess 执行 Shell 脚本
- 所有外部依赖使用延迟导入 + `ImportError` 优雅降级
