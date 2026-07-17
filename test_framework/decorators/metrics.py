"""
指标收集装饰器 — 自动收集函数执行的关键性能指标。

职责：收集调用次数、成功率、平均耗时、P95/P99 延迟等，
      支持导出为字典或上报到监控系统。
"""
from __future__ import annotations

import asyncio
import functools
import logging
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricsCollector:
    """
    指标收集器 — 记录单个函数的执行指标。

    Attributes:
        name: 函数名称。
        call_count: 总调用次数。
        success_count: 成功次数。
        failure_count: 失败次数。
        durations: 每次调用的耗时列表（秒）。
    """

    name: str = ""
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    durations: List[float] = field(default_factory=list)

    @property
    def avg_duration(self) -> float:
        """平均耗时（秒）。"""
        return statistics.mean(self.durations) if self.durations else 0.0

    @property
    def p95_duration(self) -> float:
        """P95 延迟（秒）。"""
        return self._percentile(95)

    @property
    def p99_duration(self) -> float:
        """P99 延迟（秒）。"""
        return self._percentile(99)

    @property
    def success_rate(self) -> float:
        """成功率（0.0 ~ 1.0）。"""
        if self.call_count == 0:
            return 0.0
        return self.success_count / self.call_count

    def _percentile(self, p: int) -> float:
        """计算百分位延迟。"""
        if not self.durations:
            return 0.0
        sorted_d = sorted(self.durations)
        idx = int(len(sorted_d) * p / 100)
        idx = min(idx, len(sorted_d) - 1)
        return sorted_d[idx]

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典。"""
        return {
            "name": self.name,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_duration": round(self.avg_duration, 4),
            "p95_duration": round(self.p95_duration, 4),
            "p99_duration": round(self.p99_duration, 4),
            "success_rate": round(self.success_rate, 4),
        }

    def reset(self) -> None:
        """重置所有指标。"""
        self.call_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.durations.clear()


# 全局指标注册表
_metrics_registry: Dict[str, MetricsCollector] = {}


def get_metrics(name: str) -> Optional[MetricsCollector]:
    """获取指定函数的指标收集器。"""
    return _metrics_registry.get(name)


def get_all_metrics() -> Dict[str, MetricsCollector]:
    """获取所有指标收集器。"""
    return dict(_metrics_registry)


def collect_metrics(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    callback: Optional[Callable[[MetricsCollector], None]] = None,
) -> Callable:
    """
    指标收集装饰器。

    Args:
        func: 被装饰的函数。
        name: 自定义指标名称（默认使用函数全名）。
        callback: 每次调用后的回调 ``callback(collector)``。

    Returns:
        装饰后的函数。

    使用示例::

        @collect_metrics(name="api_call")
        async def call_api():
            pass

        metrics = get_metrics("api_call")
        print(metrics.to_dict())
    """

    def decorator(fn: Callable) -> Callable:
        metric_name = name or f"{fn.__module__}.{fn.__qualname__}"
        collector = MetricsCollector(name=metric_name)
        _metrics_registry[metric_name] = collector

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                collector.call_count += 1
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    collector.success_count += 1
                    return result
                except Exception:
                    collector.failure_count += 1
                    raise
                finally:
                    elapsed = time.perf_counter() - start
                    collector.durations.append(elapsed)
                    if callback:
                        callback(collector)

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                collector.call_count += 1
                start = time.perf_counter()
                try:
                    result = fn(*args, **kwargs)
                    collector.success_count += 1
                    return result
                except Exception:
                    collector.failure_count += 1
                    raise
                finally:
                    elapsed = time.perf_counter() - start
                    collector.durations.append(elapsed)
                    if callback:
                        callback(collector)

            return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator
