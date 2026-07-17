"""
core.models 包 — 框架领域模型定义。

导出所有核心数据模型和枚举类型，供其他模块使用。
"""
from .enums import (
    Lifecycle,
    LoadProfileType,
    Priority,
    Severity,
    TestStatus,
    TestType,
    Verdict,
)
from .execution_context import EnvironmentInfo, ExecutionContext
from .target_system import TargetSystem
from .test_case import TestCase
from .test_metrics import TestMetrics
from .test_plan import TestPlan
from .test_report import TestReport
from .test_result import TestResult
from .test_suite import TestSuite

__all__ = [
    # 枚举
    "TestType",
    "TestStatus",
    "Priority",
    "Lifecycle",
    "Verdict",
    "LoadProfileType",
    "Severity",
    # 数据模型
    "TestCase",
    "TestSuite",
    "TestPlan",
    "TestResult",
    "TestMetrics",
    "TestReport",
    "TargetSystem",
    "ExecutionContext",
    "EnvironmentInfo",
]
