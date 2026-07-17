"""
并行调度器 — 并发执行多个测试计划。

职责：使用 asyncio.gather 并行运行多个 SchedulePlan，
      支持最大并发数限制。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .base import BaseScheduler, SchedulePlan, ScheduleResult, ScheduleStatus

logger = logging.getLogger(__name__)


class ParallelScheduler(BaseScheduler):
    """
    并行调度器。

    使用 asyncio.gather 并发执行多个测试计划，
    通过 max_concurrency 控制最大并发数量。

    使用示例::

        scheduler = ParallelScheduler(max_concurrency=5)
        results = await scheduler.submit_batch([plan1, plan2, plan3])
    """

    def __init__(
        self,
        max_concurrency: int = 10,
        executor: Optional[Callable[..., Coroutine]] = None,
    ) -> None:
        """
        初始化并行调度器。

        Args:
            max_concurrency: 最大并发数。
            executor: 异步执行回调函数。
        """
        super().__init__()
        self._max_concurrency = max_concurrency
        self._executor = executor or self._default_executor
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def submit_batch(self, plans: List[SchedulePlan]) -> List[ScheduleResult]:
        """
        批量并行提交多个计划。

        Args:
            plans: 调度计划列表。

        Returns:
            所有执行结果列表。
        """
        logger.info(f"批量并行提交 {len(plans)} 个计划 (max_concurrency={self._max_concurrency})")

        tasks = []
        for plan in plans:
            self._plans[plan.id] = plan
            tasks.append(self._execute_with_semaphore(plan))

        results = await asyncio.gather(*tasks, return_exceptions=False)

        # 记录结果
        for plan, result in zip(plans, results):
            if plan.id not in self._results:
                self._results[plan.id] = []
            self._results[plan.id].append(result)

        return list(results)

    async def _execute_with_semaphore(self, plan: SchedulePlan) -> ScheduleResult:
        """通过信号量控制并发数执行计划。"""
        async with self._semaphore:
            return await self._execute_plan(plan)

    async def _execute_plan(self, plan: SchedulePlan) -> ScheduleResult:
        """
        并行执行单个计划。

        Args:
            plan: 调度计划。

        Returns:
            执行结果。
        """
        result = ScheduleResult(plan_id=plan.id, status=ScheduleStatus.RUNNING)
        result.started_at = datetime.now()

        try:
            exec_result = await asyncio.wait_for(
                self._executor(plan.test_plan_id, plan.metadata),
                timeout=plan.timeout,
            )
            result.status = ScheduleStatus.COMPLETED
            result.metrics = exec_result if isinstance(exec_result, dict) else {}
            logger.info(f"并行计划完成: {plan.name}")
        except asyncio.TimeoutError:
            result.status = ScheduleStatus.FAILED
            result.error = f"执行超时 ({plan.timeout}s)"
            logger.error(f"并行计划超时: {plan.name}")
        except Exception as e:
            result.status = ScheduleStatus.FAILED
            result.error = str(e)
            logger.error(f"并行计划失败: {plan.name} — {e}")
        finally:
            result.finished_at = datetime.now()

        return result

    async def submit(self, plan: SchedulePlan) -> ScheduleResult:
        """提交单个计划（立即执行，不等待批次）。"""
        self._plans[plan.id] = plan
        result = await self._execute_with_semaphore(plan)

        if plan.id not in self._results:
            self._results[plan.id] = []
        self._results[plan.id].append(result)

        return result

    def set_max_concurrency(self, value: int) -> None:
        """动态调整最大并发数。"""
        self._max_concurrency = value
        self._semaphore = asyncio.Semaphore(value)
        logger.info(f"最大并发数已调整为: {value}")

    @staticmethod
    async def _default_executor(test_plan_id: str, metadata: dict) -> dict:
        """默认模拟执行器。"""
        logger.debug(f"模拟并行执行测试计划: {test_plan_id}")
        await asyncio.sleep(0.05)
        return {"test_plan_id": test_plan_id, "status": "simulated"}
