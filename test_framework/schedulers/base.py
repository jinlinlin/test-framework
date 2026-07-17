"""
调度器基类 — 定义所有调度器的统一抽象与共享数据模型。

职责：提供 SchedulePlan / ScheduleResult 数据类，
      定义 BaseScheduler ABC 的 schedule / execute / cancel 方法。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScheduleStatus(str, Enum):
    """调度状态枚举。"""

    PENDING = "pending"          # 等待调度
    RUNNING = "running"          # 正在执行
    COMPLETED = "completed"      # 执行完成
    FAILED = "failed"            # 执行失败
    CANCELLED = "cancelled"      # 已取消


@dataclass
class SchedulePlan:
    """
    调度计划 — 描述一个待执行的测试任务。

    Attributes:
        id: 计划唯一 ID（自动生成）。
        name: 计划名称。
        test_plan_id: 关联的 TestPlan ID。
        priority: 优先级（数字越小越优先）。
        scheduled_at: 计划执行时间（None 表示立即执行）。
        repeat_interval: 重复间隔（秒），0 表示不重复。
        max_repeats: 最大重复次数，0 表示无限。
        timeout: 超时时间（秒）。
        metadata: 附加元数据。
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    test_plan_id: str = ""
    priority: int = 10
    scheduled_at: Optional[datetime] = None
    repeat_interval: float = 0.0
    max_repeats: int = 0
    timeout: float = 3600.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleResult:
    """
    调度结果 — 记录单次调度的执行结果。

    Attributes:
        plan_id: 调度计划 ID。
        status: 执行状态。
        started_at: 开始时间。
        finished_at: 结束时间。
        error: 错误信息（仅在失败时有值）。
        metrics: 执行期间收集的指标。
    """

    plan_id: str = ""
    status: ScheduleStatus = ScheduleStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """计算执行时长（秒）。"""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0


class BaseScheduler(ABC):
    """
    调度器基类 — 所有调度策略的统一抽象。

    子类必须实现 _execute_plan 方法，
    基类提供通用的 提交 / 取消 / 查询 接口。

    使用示例::

        scheduler = SequentialScheduler()
        plan = SchedulePlan(name="冒烟测试", test_plan_id="tp-001")
        result = await scheduler.submit(plan)
    """

    def __init__(self) -> None:
        """初始化调度器。"""
        self._plans: Dict[str, SchedulePlan] = {}           # plan_id -> plan
        self._results: Dict[str, List[ScheduleResult]] = {}  # plan_id -> results
        self._running: bool = False

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    async def submit(self, plan: SchedulePlan) -> ScheduleResult:
        """
        提交调度计划。

        Args:
            plan: 调度计划。

        Returns:
            执行结果。
        """
        self._plans[plan.id] = plan
        logger.info(f"调度计划已提交: {plan.name} ({plan.id})")

        result = await self._execute_plan(plan)

        # 记录结果
        if plan.id not in self._results:
            self._results[plan.id] = []
        self._results[plan.id].append(result)

        return result

    async def cancel(self, plan_id: str) -> bool:
        """
        取消调度计划。

        Args:
            plan_id: 计划 ID。

        Returns:
            是否成功取消。
        """
        plan = self._plans.get(plan_id)
        if plan:
            logger.info(f"调度计划已取消: {plan_id}")
            return True
        return False

    def get_result(self, plan_id: str) -> Optional[List[ScheduleResult]]:
        """获取计划的所有执行结果。"""
        return self._results.get(plan_id)

    def get_plan(self, plan_id: str) -> Optional[SchedulePlan]:
        """获取调度计划。"""
        return self._plans.get(plan_id)

    def list_plans(self) -> List[SchedulePlan]:
        """列出所有调度计划。"""
        return list(self._plans.values())

    # ------------------------------------------------------------------
    # 子类必须实现
    # ------------------------------------------------------------------

    @abstractmethod
    async def _execute_plan(self, plan: SchedulePlan) -> ScheduleResult:
        """
        执行调度计划（由子类实现具体逻辑）。

        Args:
            plan: 调度计划。

        Returns:
            执行结果。
        """
