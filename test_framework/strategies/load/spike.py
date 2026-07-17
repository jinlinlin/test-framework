"""
尖峰负载策略 — 突然大量请求，测试系统恢复能力。

场景：模拟突发流量（如秒杀活动），验证系统在压力骤增/骤降时的表现。
曲线：_/‾\_  尖峰形状
"""
from __future__ import annotations

from typing import Any, Dict

from ..base import BaseStrategy
from .constant import LoadProfile, LoadProfilePoint


class SpikeLoadStrategy(BaseStrategy):
    """
    尖峰负载策略。

    先以正常负载运行，突然飙升到尖峰值，持续一段时间后再回到正常水平。

    负载曲线::

        spike  ────       ‾‾‾‾
          │      \\      /
        normal ────\\____/────────
          │
        0 └────────────────────────
          0    spike_start  spike_end  total
    """

    def __init__(
        self,
        normal: int = 10,
        spike: int = 200,
        warm_up_duration: float = 10.0,
        spike_duration: float = 30.0,
        cool_down_duration: float = 10.0,
    ) -> None:
        """
        Args:
            normal: 正常并发数。
            spike: 尖峰并发数。
            warm_up_duration: 预热时间（秒）。
            spike_duration: 尖峰持续时间（秒）。
            cool_down_duration: 冷却时间（秒）。
        """
        self._normal = normal
        self._spike = spike
        self._warm_up = warm_up_duration
        self._spike_duration = spike_duration
        self._cool_down = cool_down_duration

    @property
    def strategy_type(self) -> str:
        return "load"

    @property
    def name(self) -> str:
        return "spike"

    def get_config(self) -> Dict[str, Any]:
        return {
            "normal": self._normal,
            "spike": self._spike,
            "warm_up_duration": self._warm_up,
            "spike_duration": self._spike_duration,
            "cool_down_duration": self._cool_down,
        }

    def get_load_profile(self) -> LoadProfile:
        """生成尖峰负载曲线。"""
        t0 = 0.0
        t1 = self._warm_up  # 开始飙升
        t2 = t1 + self._spike_duration  # 结束飙升
        t3 = t2 + self._cool_down  # 冷却结束
        total = t3

        points = [
            LoadProfilePoint(timestamp=t0, concurrency=self._normal),
            LoadProfilePoint(timestamp=t1, concurrency=self._normal),
            LoadProfilePoint(timestamp=t1 + 1, concurrency=self._spike),  # 突然飙升
            LoadProfilePoint(timestamp=t2, concurrency=self._spike),
            LoadProfilePoint(timestamp=t2 + 1, concurrency=self._normal),  # 突然回落
            LoadProfilePoint(timestamp=t3, concurrency=self._normal),
        ]
        return LoadProfile(
            points=points,
            total_duration=total,
            max_concurrency=self._spike,
            description=f"尖峰负载: {self._normal}→{self._spike}→{self._normal}, 尖峰持续{self._spike_duration}s",
        )

    def get_concurrency_at(self, timestamp: float) -> int:
        """获取指定时间点的并发数。"""
        t1 = self._warm_up
        t2 = t1 + self._spike_duration
        t3 = t2 + self._cool_down

        if timestamp < 0 or timestamp > t3:
            return 0
        if timestamp < t1:
            return self._normal
        if timestamp < t2:
            return self._spike
        return self._normal
