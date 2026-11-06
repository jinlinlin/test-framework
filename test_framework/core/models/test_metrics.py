"""
测试指标模型 — 定义一次测试运行的量化指标。

覆盖两类指标：
    - 性能指标（throughput/latency_*/error_rate/cpu_usage/memory_usage），
      主要用于网页性能、后端性能、数据库性能等性能类引擎。
    - 用例统计指标（total_cases/passed_cases/failed_cases/skipped_cases/
      errored_cases/duration），所有引擎通用，含 Agent、REST API、UI 自动化等。

保留原有性能字段，新增的用例统计字段均带默认值，向后兼容。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TestMetrics:
    """
    测试指标数据模型。

    标准化存储各类型性能测试的量化结果，
    支持自定义扩展指标（custom 字段）。

    Attributes:
        throughput: 吞吐量（请求/秒 或 查询/秒）。
        latency_avg: 平均延迟（毫秒）。
        latency_p50: P50 延迟（中位数，毫秒）。
        latency_p95: P95 延迟（毫秒）。
        latency_p99: P99 延迟（毫秒）。
        error_rate: 错误率（0.0 ~ 1.0）。
        cpu_usage: CPU 使用率百分比（可选）。
        memory_usage: 内存使用率百分比（可选）。
        custom: 自定义指标字典（如 Web Vitals、JVM 堆内存等）。
        total_cases: 本次运行的用例总数（所有引擎通用）。
        passed_cases: 通过的用例数（TestStatus.PASS）。
        failed_cases: 失败的用例数（TestStatus.FAIL）。
        skipped_cases: 跳过的用例数（TestStatus.SKIP）。
        errored_cases: 错误的用例数（TestStatus.ERROR，非断言失败）。
        duration: 本次运行总耗时（秒）。
    """

    throughput: float = 0.0
    latency_avg: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    error_rate: float = 0.0
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    # ── 用例统计字段（所有引擎通用，包括 Agent 行为测试）──
    # 均带默认值，旧的纯性能构造（如 TestMetrics(throughput=100)）仍可运行。
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    skipped_cases: int = 0
    errored_cases: int = 0
    duration: float = 0.0

    def set_custom_metric(self, name: str, value: float) -> None:
        """
        设置自定义指标。

        Args:
            name: 指标名称（如 'LCP', 'jvm_heap_used_mb'）。
            value: 指标数值。
        """
        self.custom[name] = value

    def get_custom_metric(self, name: str, default: float = 0.0) -> float:
        """
        获取自定义指标值。

        Args:
            name: 指标名称。
            default: 不存在时的默认值。

        Returns:
            指标数值。
        """
        return self.custom.get(name, default)

    def to_dict(self) -> Dict[str, Any]:
        """将指标序列化为字典。

        旧行为保留：性能字段始终写入；cpu/memory/custom 非空才写。
        用例统计字段仅在任一非零时写入，避免污染纯性能场景的输出。
        """
        result = {
            "throughput": self.throughput,
            "latency_avg": self.latency_avg,
            "latency_p50": self.latency_p50,
            "latency_p95": self.latency_p95,
            "latency_p99": self.latency_p99,
            "error_rate": self.error_rate,
        }
        if self.cpu_usage is not None:
            result["cpu_usage"] = self.cpu_usage
        if self.memory_usage is not None:
            result["memory_usage"] = self.memory_usage
        if self.custom:
            result["custom"] = self.custom
        # 用例统计字段按需写入：任一计数或 duration 非零即写入全组。
        if (self.total_cases or self.passed_cases or self.failed_cases
                or self.skipped_cases or self.errored_cases or self.duration):
            result["total_cases"] = self.total_cases
            result["passed_cases"] = self.passed_cases
            result["failed_cases"] = self.failed_cases
            result["skipped_cases"] = self.skipped_cases
            result["errored_cases"] = self.errored_cases
            result["duration"] = self.duration
        return result
