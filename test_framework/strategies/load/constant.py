"""
恒定负载策略 — 固定并发数持续运行。

场景：基准性能测试，模拟稳定流量。
曲线：[====] 水平直线
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..base import BaseStrategy


@dataclass
class LoadProfilePoint:
    """
    负载曲线上的一个点。

    Attributes:
        timestamp: 时间点（秒）。
        concurrency: 并发数。
    """

    timestamp: float = 0.0
    concurrency: int = 0


@dataclass
class LoadProfile:
    """
    负载曲线描述。

    Attributes:
        points: 负载曲线点列表。
        total_duration: 总持续时间（秒）。
        max_concurrency: 最大并发数。
        description: 曲线描述文本。
    """

    points: List[LoadProfilePoint] = field(default_factory=list)
    total_duration: float = 0.0
    max_concurrency: int = 0
    description: str = ""


class ConstantLoadStrategy(BaseStrategy):
    """
    恒定负载策略。

    从开始到结束，始终保持固定的并发用户数。

    配置::

        ConstantLoadStrategy(concurrency=100, duration=300)

    负载曲线::

        100 ──────────────────────────────
          │
        0 └────────────────────────────────
          0                              300s
    """

    def __init__(self, concurrency: int = 10, duration: float = 60.0) -> None:
        """
        Args:
            concurrency: 固定并发数。
            duration: 持续时间（秒）。
        """
        self._concurrency = concurrency
        self._duration = duration

    @property
    def strategy_type(self) -> str:
        return "load"

    @property
    def name(self) -> str:
        return "constant"

    def get_config(self) -> Dict[str, Any]:
        return {"concurrency": self._concurrency, "duration": self._duration}

    def get_load_profile(self) -> LoadProfile:
        """
        生成恒定负载曲线。

        Returns:
            水平直线的负载曲线。
        """
        points = [
            LoadProfilePoint(timestamp=0, concurrency=self._concurrency),
            LoadProfilePoint(timestamp=self._duration, concurrency=self._concurrency),
        ]
        return LoadProfile(
            points=points,
            total_duration=self._duration,
            max_concurrency=self._concurrency,
            description=f"恒定负载: {self._concurrency} 并发, 持续 {self._duration}s",
        )

    def get_concurrency_at(self, timestamp: float) -> int:
        """获取指定时间点的并发数。"""
        if 0 <= timestamp <= self._duration:
            return self._concurrency
        return 0
