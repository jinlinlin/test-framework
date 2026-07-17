"""
波浪负载策略 — 周期性波动，模拟真实流量。

场景：模拟日常业务流量波动（如白天高、晚上低）。
曲线：~∿~∿~  正弦波
"""
from __future__ import annotations

import math
from typing import Any, Dict

from ..base import BaseStrategy
from .constant import LoadProfile, LoadProfilePoint


class WaveLoadStrategy(BaseStrategy):
    """
    波浪负载策略。

    并发数在 min 和 max 之间周期性波动（正弦波），
    模拟真实业务流量的波峰波谷。

    负载曲线::

        max ──── ∿∿∿∿
          │    /    \\    /
        avg ──/──────\\──/──
          │  /        \\/
        min ─────────────────
          │
        0 └─────────────────────
          0                    duration
    """

    def __init__(
        self,
        min_concurrency: int = 10,
        max_concurrency: int = 100,
        period: float = 60.0,
        duration: float = 300.0,
        sample_interval: float = 5.0,
    ) -> None:
        """
        Args:
            min_concurrency: 最小并发数（波谷）。
            max_concurrency: 最大并发数（波峰）。
            period: 一个周期的时间（秒）。
            duration: 总持续时间（秒）。
            sample_interval: 采样间隔（秒），用于生成离散曲线点。
        """
        self._min = min_concurrency
        self._max = max_concurrency
        self._period = period
        self._duration = duration
        self._sample_interval = sample_interval

    @property
    def strategy_type(self) -> str:
        return "load"

    @property
    def name(self) -> str:
        return "wave"

    def get_config(self) -> Dict[str, Any]:
        return {
            "min_concurrency": self._min,
            "max_concurrency": self._max,
            "period": self._period,
            "duration": self._duration,
        }

    def _compute_concurrency(self, timestamp: float) -> int:
        """根据正弦波计算指定时间点的并发数。"""
        amplitude = (self._max - self._min) / 2.0
        center = (self._max + self._min) / 2.0
        # 正弦波: center + amplitude * sin(2π * t / period)
        value = center + amplitude * math.sin(2 * math.pi * timestamp / self._period)
        return max(self._min, min(self._max, int(round(value))))

    def get_load_profile(self) -> LoadProfile:
        """生成波浪负载曲线。"""
        points = []
        t = 0.0
        while t <= self._duration:
            conc = self._compute_concurrency(t)
            points.append(LoadProfilePoint(timestamp=t, concurrency=conc))
            t += self._sample_interval

        return LoadProfile(
            points=points,
            total_duration=self._duration,
            max_concurrency=self._max,
            description=(
                f"波浪负载: {self._min}↔{self._max}, "
                f"周期 {self._period}s, 持续 {self._duration}s"
            ),
        )

    def get_concurrency_at(self, timestamp: float) -> int:
        """获取指定时间点的并发数。"""
        if 0 <= timestamp <= self._duration:
            return self._compute_concurrency(timestamp)
        return 0
