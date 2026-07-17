"""
阶梯负载策略 — 分阶段递增并发数。

场景：逐步增加负载，观察每个阶段的性能变化，找到系统瓶颈点。
曲线：_‾_‾_‾_  阶梯形
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..base import BaseStrategy
from .constant import LoadProfile, LoadProfilePoint


class StepLoadStrategy(BaseStrategy):
    """
    阶梯负载策略。

    将测试分为多个阶段，每个阶段并发数递增，
    用于逐步发现系统在不同负载级别下的表现。

    负载曲线::

        step3 ─────────────── ‾‾‾‾
        step2 ────────── ‾‾‾‾
        step1 ───── ‾‾‾‾
          │
        0 └─────────────────────────────
          0    t1    t2    t3    total
    """

    def __init__(
        self,
        steps: List[Dict[str, Any]] = None,
    ) -> None:
        """
        Args:
            steps: 阶梯配置列表，每项包含:
                - concurrency: 并发数
                - duration: 该阶段持续时间（秒）
                例如: [{"concurrency": 10, "duration": 30},
                       {"concurrency": 50, "duration": 30},
                       {"concurrency": 100, "duration": 30}]
                如果为 None，使用默认阶梯。
        """
        if steps is None:
            self._steps = [
                {"concurrency": 10, "duration": 30},
                {"concurrency": 50, "duration": 30},
                {"concurrency": 100, "duration": 30},
            ]
        else:
            self._steps = steps

    @property
    def strategy_type(self) -> str:
        return "load"

    @property
    def name(self) -> str:
        return "step"

    def get_config(self) -> Dict[str, Any]:
        return {"steps": self._steps}

    def get_load_profile(self) -> LoadProfile:
        """生成阶梯负载曲线。"""
        points: List[LoadProfilePoint] = []
        current_time = 0.0
        max_conc = 0

        for step in self._steps:
            conc = step.get("concurrency", 10)
            dur = step.get("duration", 30)
            max_conc = max(max_conc, conc)

            points.append(LoadProfilePoint(timestamp=current_time, concurrency=conc))
            current_time += dur
            points.append(LoadProfilePoint(timestamp=current_time, concurrency=conc))

        total = current_time
        return LoadProfile(
            points=points,
            total_duration=total,
            max_concurrency=max_conc,
            description=f"阶梯负载: {len(self._steps)} 个阶段, 最大并发 {max_conc}",
        )

    def get_concurrency_at(self, timestamp: float) -> int:
        """获取指定时间点的并发数。"""
        current_time = 0.0
        for step in self._steps:
            dur = step.get("duration", 30)
            conc = step.get("concurrency", 10)
            if timestamp < current_time + dur:
                return conc
            current_time += dur
        return 0
