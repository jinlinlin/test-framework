"""
顺序调度器 — 按优先级顺序逐个执行测试计划。

职责：将多个 SchedulePlan 按优先级排序后串行执行，
      确保前一个完成后才启动下一个。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine, List, Optional

from .base import BaseScheduler, SchedulePlan, ScheduleResult, ScheduleStatus

logger = logging.getLogger(__name__)


class SequentialScheduler(BaseScheduler):
    """
    顺序调度器。

    按优先级（priority 升序）排列后依次执行，
    每个计划完成后才执行下一个。

    使用示例::

        scheduler = SequentialScheduler()
        plan = SchedulePlan(name="单元测试", test_plan_id="tp-001")
        result = await scheduler.submit(plan)
    """

    def __init__(self, executor: Optional[Callable[..., Coroutine]] = None) -> None:
        """
        初始化顺序调度器。

        Args:
            executor: 异步执行回调函数，签名为
                      ``async def executor(test_plan_id: str) -> dict``。
                      若为 None 则使用默认的模拟执行器。
        """
        super().__init__()
        self._executor = executor or self._default_executor
        self._queue: List[SchedulePlan] = []  # 待执行队列

    async def submit(self, plan: SchedulePlan) -> ScheduleResult:
        """提交并按优先级插入队列。"""
        self._plans[plan.id] = plan
        self._queue.append(plan)
        # 按优先级排序
        self._queue.sort(key=lambda p: p.priority)
        logger.info(f"计划已入队: {plan.name} (priority={plan.priority})")

        result = await self._execute_plan(plan)

        if plan.id not in self._results:
            self._results[plan.id] = []
        self._results[plan.id].append(result)

        # 从队列移除
        self._queue = [p for p in self._queue if p.id != plan.id]
        return result

    async def _execute_plan(self, plan: SchedulePlan) -> ScheduleResult:
        """
        顺序执行单个计划。

        Args:
            plan: 调度计划。

        Returns:
            执行结果。
        """
        result = ScheduleResult(plan_id=plan.id, status=ScheduleStatus.RUNNING)
        result.started_at = datetime.now()

        # 如果计划有延迟调度时间，先等待
        if plan.scheduled_at and plan.scheduled_at > datetime.now():
            delay = (plan.scheduled_at - datetime.now()).total_seconds()
            logger.debug(f"等待 {delay:.1f}s 后执行计划 {plan.name}")
            await asyncio.sleep(delay)

        try:
            # 带超时控制执行
            exec_result = await asyncio.wait_for(
                self._executor(plan.test_plan_id, plan.metadata),
                timeout=plan.timeout,
            )
            result.status = ScheduleStatus.COMPLETED
            result.metrics = exec_result if isinstance(exec_result, dict) else {}
            logger.info(f"计划执行完成: {plan.name}")
        except asyncio.TimeoutError:
            result.status = ScheduleStatus.FAILED
            result.error = f"执行超时 ({plan.timeout}s)"
            logger.error(f"计划执行超时: {plan.name}")
        except Exception as e:
            result.status = ScheduleStatus.FAILED
            result.error = str(e)
            logger.error(f"计划执行失败: {plan.name} — {e}")
        finally:
            result.finished_at = datetime.now()

        return result

    async def execute_all(self) -> List[ScheduleResult]:
        """
        按顺序执行队列中所有计划。

        Returns:
            所有执行结果列表。
        """
        results: List[ScheduleResult] = []
        # 按优先级排序
        self._queue.sort(key=lambda p: p.priority)

        for plan in list(self._queue):
            result = await self.submit(plan)
            results.append(result)

        return results

    @staticmethod
    async def _default_executor(test_plan_id: str, metadata: dict) -> dict:
        """默认模拟执行器。"""
        logger.debug(f"模拟执行测试计划: {test_plan_id}")
        await asyncio.sleep(0.1)  # 模拟耗时
        return {"test_plan_id": test_plan_id, "status": "simulated"}
