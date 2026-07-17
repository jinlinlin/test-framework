"""
测试指标模型 — 定义性能测试中采集到的量化指标。

TestMetrics 主要用于性能类测试引擎（网页性能、后端性能、数据库性能），
包含延迟百分位、吞吐量、错误率、资源使用率等标准指标。
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
        """将指标序列化为字典。"""
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
        return result
