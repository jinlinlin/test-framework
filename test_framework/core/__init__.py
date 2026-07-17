"""
core 包 — 框架核心抽象层。

包含 IoC 容器、接口契约、领域模型、事件系统、管道引擎和异常体系。
所有上层模块均依赖 core 包提供的抽象。
"""
from .container import Container, DependencyResolver, ServiceRegistry
from .events import Event, EventBus, EventTypes, ListenerRegistry
from .models import (
    EnvironmentInfo,
    ExecutionContext,
    Lifecycle,
    Priority,
    TargetSystem,
    TestCase,
    TestMetrics,
    TestPlan,
    TestReport,
    TestResult,
    TestStatus,
    TestSuite,
    TestType,
    Verdict,
)
from .pipeline import Filter, HookManager, Pipeline, PipelineContext, Stage

__all__ = [
    # 容器
    "Container",
    "ServiceRegistry",
    "DependencyResolver",
    # 事件
    "Event",
    "EventBus",
    "EventTypes",
    "ListenerRegistry",
    # 模型
    "TestCase",
    "TestSuite",
    "TestPlan",
    "TestResult",
    "TestMetrics",
    "TestReport",
    "TargetSystem",
    "ExecutionContext",
    "EnvironmentInfo",
    "TestType",
    "TestStatus",
    "Priority",
    "Lifecycle",
    "Verdict",
    # 管道
    "Pipeline",
    "Stage",
    "PipelineContext",
    "Filter",
    "HookManager",
]
