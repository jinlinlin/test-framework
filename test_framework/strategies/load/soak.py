"""
浸泡负载策略 — 中等负载持续长时间，检测内存泄漏。

场景：稳定性测试（endurance test），通常运行数小时甚至数天。
曲线：[====] 长时间水平直线
"""
from __future__ import annotations

from typing import Any, Dict

from ..base import BaseStrategy
from .constant import LoadProfile, LoadProfilePoint


class SoakLoadStrategy(BaseStrategy):
    """
    浸泡负载策略（稳定性测试）。

    以中等负载持续运行较长时间（如 4-8 小时），
    用于检测内存泄漏、资源耗尽等问题。

    负载曲线::

        concurrency ────────────────────────────
          │
        0 └──────────────────────────────────────
          0                                    duration (hours)
    """

    def __init__(
        self,
        concurrency: int = 50,
        duration: float = 14400.0,  # 默认 4 小时
    ) -> None:
        """
        Args:
            concurrency: 中等并发数（通常为最大容量的 50%-80%）。
            duration: 持续时间（秒），默认 4 小时。
        """
        self._concurrency = concurrency
        self._duration = duration

    @property
    def strategy_type(self) -> str:
        return "load"

    @property
    def name(self) -> str:
        return "soak"

    def get_config(self) -> Dict[str, Any]:
        return {"concurrency": self._concurrency, "duration": self._duration}

    def get_load_profile(self) -> LoadProfile:
        """生成浸泡负载曲线。"""
        hours = self._duration / 3600
        points = [
            LoadProfilePoint(timestamp=0, concurrency=self._concurrency),
            LoadProfilePoint(timestamp=self._duration, concurrency=self._concurrency),
        ]
        return LoadProfile(
            points=points,
            total_duration=self._duration,
            max_concurrency=self._concurrency,
            description=f"浸泡负载: {self._concurrency} 并发, 持续 {hours:.1f} 小时",
        )

    def get_concurrency_at(self, timestamp: float) -> int:
        """获取指定时间点的并发数。"""
        if 0 <= timestamp <= self._duration:
            return self._concurrency
        return 0
