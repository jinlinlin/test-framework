"""
逐步上升负载策略 — 并发数线性增长。

场景：容量规划测试，找到系统性能拐点。
曲线：/ 斜线上升
"""
from __future__ import annotations

from typing import Any, Dict

from ..base import BaseStrategy
from .constant import LoadProfile, LoadProfilePoint


class RampUpLoadStrategy(BaseStrategy):
    """
    逐步上升负载策略。

    并发数从 start 线性增长到 end，用于找到系统性能拐点。

    负载曲线::

        end ─────────── /
          │            /
        start         /
          │          /
        0 └───────────────────────────────
          0     ramp_duration    total_duration
    """

    def __init__(
        self,
        start: int = 1,
        end: int = 100,
        ramp_duration: float = 30.0,
        hold_duration: float = 30.0,
    ) -> None:
        """
        Args:
            start: 起始并发数。
            end: 目标并发数。
            ramp_duration: 爬升时间（秒）。
            hold_duration: 达到目标后保持时间（秒）。
        """
        self._start = start
        self._end = end
        self._ramp_duration = ramp_duration
        self._hold_duration = hold_duration

    @property
    def strategy_type(self) -> str:
        return "load"

    @property
    def name(self) -> str:
        return "ramp_up"

    def get_config(self) -> Dict[str, Any]:
        return {
            "start": self._start,
            "end": self._end,
            "ramp_duration": self._ramp_duration,
            "hold_duration": self._hold_duration,
        }

    def get_load_profile(self) -> LoadProfile:
        """生成线性上升负载曲线。"""
        total = self._ramp_duration + self._hold_duration
        points = [
            LoadProfilePoint(timestamp=0, concurrency=self._start),
            LoadProfilePoint(timestamp=self._ramp_duration, concurrency=self._end),
            LoadProfilePoint(timestamp=total, concurrency=self._end),
        ]
        return LoadProfile(
            points=points,
            total_duration=total,
            max_concurrency=self._end,
            description=f"爬升负载: {self._start}→{self._end}, 爬升{self._ramp_duration}s, 保持{self._hold_duration}s",
        )

    def get_concurrency_at(self, timestamp: float) -> int:
        """获取指定时间点的并发数。"""
        if timestamp < 0:
            return 0
        if timestamp <= self._ramp_duration:
            # 线性插值
            ratio = timestamp / self._ramp_duration if self._ramp_duration > 0 else 1
            return int(self._start + (self._end - self._start) * ratio)
        if timestamp <= self._ramp_duration + self._hold_duration:
            return self._end
        return 0
