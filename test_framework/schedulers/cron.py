"""
定时调度器 — 基于 cron 表达式或固定间隔周期性执行测试计划。

职责：解析 cron 表达式，在指定时间自动触发测试计划执行。
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .base import BaseScheduler, SchedulePlan, ScheduleResult, ScheduleStatus

logger = logging.getLogger(__name__)


class CronScheduler(BaseScheduler):
    """
    定时调度器。

    支持两种调度方式：
    1. 固定间隔（秒）：每隔 N 秒执行一次
    2. Cron 表达式：支持 ``分 时 日 月 周`` 五段式

    使用示例::

        scheduler = CronScheduler()
        scheduler.add_job(plan, cron="*/5 * * * *")  # 每 5 分钟
        await scheduler.start()
    """

    def __init__(
        self,
        executor: Optional[Callable[..., Coroutine]] = None,
    ) -> None:
        """
        初始化定时调度器。

        Args:
            executor: 异步执行回调函数。
        """
        super().__init__()
        self._executor = executor or self._default_executor
        self._jobs: Dict[str, _CronJob] = {}  # plan_id -> _CronJob
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # 作业管理
    # ------------------------------------------------------------------

    def add_job(
        self,
        plan: SchedulePlan,
        cron: Optional[str] = None,
        interval: Optional[float] = None,
    ) -> None:
        """
        添加定时作业。

        Args:
            plan: 调度计划。
            cron: Cron 表达式（五段式：分 时 日 月 周）。
            interval: 固定间隔（秒），与 cron 二选一。
        """
        self._plans[plan.id] = plan
        job = _CronJob(plan=plan, cron_expression=cron, interval=interval)
        self._jobs[plan.id] = job
        logger.info(f"定时作业已添加: {plan.name} (cron={cron}, interval={interval})")

    def remove_job(self, plan_id: str) -> None:
        """移除定时作业。"""
        self._jobs.pop(plan_id, None)
        self._plans.pop(plan_id, None)
        logger.info(f"定时作业已移除: {plan_id}")

    def list_jobs(self) -> List[SchedulePlan]:
        """列出所有定时作业的计划。"""
        return [job.plan for job in self._jobs.values()]

    # ------------------------------------------------------------------
    # 调度循环
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """启动定时调度循环。"""
        if self._running:
            logger.warning("调度器已在运行中")
            return

        self._running = True
        logger.info(f"定时调度器已启动，共 {len(self._jobs)} 个作业")

        while self._running:
            now = datetime.now()
            for job in list(self._jobs.values()):
                if job.should_run(now):
                    result = await self._execute_plan(job.plan)
                    job.last_run = now
                    job.run_count += 1

                    if job.plan.id not in self._results:
                        self._results[job.plan.id] = []
                    self._results[job.plan.id].append(result)

                    # 检查重复次数限制
                    if job.plan.max_repeats > 0 and job.run_count >= job.plan.max_repeats:
                        logger.info(f"作业达到最大重复次数，移除: {job.plan.name}")
                        self._jobs.pop(job.plan.id, None)

            # 每秒检查一次
            await asyncio.sleep(1.0)

    def stop(self) -> None:
        """停止调度循环。"""
        self._running = False
        logger.info("定时调度器已停止")

    # ------------------------------------------------------------------
    # 执行逻辑
    # ------------------------------------------------------------------

    async def _execute_plan(self, plan: SchedulePlan) -> ScheduleResult:
        """
        执行定时计划。

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
            logger.info(f"定时计划完成: {plan.name}")
        except asyncio.TimeoutError:
            result.status = ScheduleStatus.FAILED
            result.error = f"执行超时 ({plan.timeout}s)"
            logger.error(f"定时计划超时: {plan.name}")
        except Exception as e:
            result.status = ScheduleStatus.FAILED
            result.error = str(e)
            logger.error(f"定时计划失败: {plan.name} — {e}")
        finally:
            result.finished_at = datetime.now()

        return result

    @staticmethod
    async def _default_executor(test_plan_id: str, metadata: dict) -> dict:
        """默认模拟执行器。"""
        logger.debug(f"模拟定时执行: {test_plan_id}")
        await asyncio.sleep(0.05)
        return {"test_plan_id": test_plan_id, "status": "simulated"}


# ======================================================================
# 内部辅助类
# ======================================================================


class _CronJob:
    """内部定时作业描述。"""

    def __init__(
        self,
        plan: SchedulePlan,
        cron_expression: Optional[str] = None,
        interval: Optional[float] = None,
    ) -> None:
        self.plan = plan
        self.cron_expression = cron_expression
        self.interval = interval
        self.last_run: Optional[datetime] = None
        self.run_count: int = 0
        self._cron_parts = self._parse_cron(cron_expression) if cron_expression else None

    def should_run(self, now: datetime) -> bool:
        """判断当前时间是否应该执行。"""
        # 固定间隔模式
        if self.interval is not None:
            if self.last_run is None:
                return True
            elapsed = (now - self.last_run).total_seconds()
            return elapsed >= self.interval

        # Cron 表达式模式
        if self._cron_parts:
            return self._match_cron(now)

        return False

    def _parse_cron(self, expression: str) -> Optional[list]:
        """解析 cron 表达式为五段列表。"""
        parts = expression.strip().split()
        if len(parts) != 5:
            logger.error(f"无效的 cron 表达式: {expression}")
            return None
        return parts

    def _match_cron(self, now: datetime) -> bool:
        """检查当前时间是否匹配 cron 表达式。"""
        if not self._cron_parts:
            return False

        values = [now.minute, now.hour, now.day, now.month, now.weekday()]

        for i, (part, value) in enumerate(zip(self._cron_parts, values)):
            if part == "*":
                continue
            # 处理 */N 格式
            if part.startswith("*/"):
                try:
                    step = int(part[2:])
                    if value % step != 0:
                        return False
                except ValueError:
                    return False
                continue
            # 处理逗号分隔列表
            allowed = []
            for token in part.split(","):
                token = token.strip()
                if "-" in token:
                    start, end = token.split("-", 1)
                    allowed.extend(range(int(start), int(end) + 1))
                else:
                    allowed.append(int(token))
            if value not in allowed:
                return False

        return True
