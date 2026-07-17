"""
指标存储 — 集中管理测试指标的收集、查询、导出。

职责：线程安全的指标存储，支持时间序列、聚合查询。
"""
from __future__ import annotations

import logging
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """
    单个指标数据点。

    Attributes:
        name: 指标名称。
        value: 指标值。
        timestamp: 时间戳（秒）。
        tags: 标签字典。
    """

    name: str = ""
    value: float = 0.0
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsStore:
    """
    指标存储 — 线程安全的集中式指标管理。

    使用示例::

        store = MetricsStore()
        store.record("response_time", 0.235, tags={"endpoint": "/api/users"})
        avg = store.get_average("response_time")
    """

    def __init__(self) -> None:
        """初始化指标存储。"""
        self._lock = threading.Lock()
        self._data: Dict[str, List[MetricPoint]] = defaultdict(list)

    def record(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        记录一个指标数据点。

        Args:
            name: 指标名称。
            value: 指标值。
            tags: 标签字典。
            timestamp: 时间戳（默认当前时间）。
        """
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=timestamp or time.time(),
            tags=tags or {},
        )
        with self._lock:
            self._data[name].append(point)

    def get_values(self, name: str) -> List[float]:
        """获取指标的所有值。"""
        with self._lock:
            return [p.value for p in self._data.get(name, [])]

    def get_average(self, name: str) -> float:
        """获取指标的平均值。"""
        values = self.get_values(name)
        return statistics.mean(values) if values else 0.0

    def get_percentile(self, name: str, p: int) -> float:
        """获取指标的百分位值。"""
        values = sorted(self.get_values(name))
        if not values:
            return 0.0
        idx = min(int(len(values) * p / 100), len(values) - 1)
        return values[idx]

    def get_min(self, name: str) -> float:
        """获取最小值。"""
        values = self.get_values(name)
        return min(values) if values else 0.0

    def get_max(self, name: str) -> float:
        """获取最大值。"""
        values = self.get_values(name)
        return max(values) if values else 0.0

    def get_count(self, name: str) -> int:
        """获取数据点数量。"""
        with self._lock:
            return len(self._data.get(name, []))

    def get_summary(self, name: str) -> Dict[str, Any]:
        """
        获取指标摘要统计。

        Returns:
            包含 count / avg / min / max / p50 / p95 / p99 的字典。
        """
        return {
            "name": name,
            "count": self.get_count(name),
            "avg": round(self.get_average(name), 4),
            "min": round(self.get_min(name), 4),
            "max": round(self.get_max(name), 4),
            "p50": round(self.get_percentile(name, 50), 4),
            "p95": round(self.get_percentile(name, 95), 4),
            "p99": round(self.get_percentile(name, 99), 4),
        }

    def list_metrics(self) -> List[str]:
        """列出所有指标名称。"""
        with self._lock:
            return list(self._data.keys())

    def export_all(self) -> Dict[str, Dict[str, Any]]:
        """导出所有指标的摘要。"""
        return {name: self.get_summary(name) for name in self.list_metrics()}

    def clear(self, name: Optional[str] = None) -> None:
        """清除指定指标或全部数据。"""
        with self._lock:
            if name:
                self._data.pop(name, None)
            else:
                self._data.clear()
