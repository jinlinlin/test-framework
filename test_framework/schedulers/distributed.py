"""
分布式调度器 — 将测试计划分发到多个 Worker 节点执行。

职责：管理 Worker 注册、任务分发、结果收集，
      支持 Worker 健康检查与故障转移。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .base import BaseScheduler, SchedulePlan, ScheduleResult, ScheduleStatus

logger = logging.getLogger(__name__)


class WorkerStatus(str, Enum):
    """Worker 节点状态。"""

    IDLE = "idle"           # 空闲
    BUSY = "busy"           # 忙碌
    OFFLINE = "offline"     # 离线


@dataclass
class WorkerNode:
    """
    Worker 节点信息。

    Attributes:
        id: Worker 唯一 ID。
        address: Worker 地址（host:port）。
        status: 当前状态。
        capacity: 最大并发任务数。
        current_load: 当前负载数。
        metadata: 附加信息。
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    address: str = "localhost:8000"
    status: WorkerStatus = WorkerStatus.IDLE
    capacity: int = 5
    current_load: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class DistributedScheduler(BaseScheduler):
    """
    分布式调度器。

    将测试计划拆分为子任务，分发到注册的 Worker 节点执行，
    收集结果并聚合。

    使用示例::

        scheduler = DistributedScheduler()
        scheduler.register_worker(WorkerNode(address="192.168.1.10:8000"))
        result = await scheduler.submit(plan)
    """

    def __init__(
        self,
        executor: Optional[Callable[..., Coroutine]] = None,
    ) -> None:
        """
        初始化分布式调度器。

        Args:
            executor: 异步执行回调（模拟远程调用）。
        """
        super().__init__()
        self._workers: Dict[str, WorkerNode] = {}  # worker_id -> WorkerNode
        self._executor = executor or self._default_executor

    # ------------------------------------------------------------------
    # Worker 管理
    # ------------------------------------------------------------------

    def register_worker(self, worker: WorkerNode) -> None:
        """
        注册 Worker 节点。

        Args:
            worker: Worker 节点信息。
        """
        self._workers[worker.id] = worker
        logger.info(f"Worker 已注册: {worker.id} @ {worker.address}")

    def unregister_worker(self, worker_id: str) -> None:
        """注销 Worker 节点。"""
        self._workers.pop(worker_id, None)
        logger.info(f"Worker 已注销: {worker_id}")

    def list_workers(self) -> List[WorkerNode]:
        """列出所有 Worker。"""
        return list(self._workers.values())

    def _select_worker(self) -> Optional[WorkerNode]:
        """
        选择负载最低的可用 Worker。

        Returns:
            可用的 Worker 节点，没有可用节点时返回 None。
        """
        available = [
            w for w in self._workers.values()
            if w.status != WorkerStatus.OFFLINE and w.current_load < w.capacity
        ]
        if not available:
            return None
        # 选择负载最低的
        return min(available, key=lambda w: w.current_load)

    # ------------------------------------------------------------------
    # 调度执行
    # ------------------------------------------------------------------

    async def _execute_plan(self, plan: SchedulePlan) -> ScheduleResult:
        """
        将计划分发到 Worker 执行。

        Args:
            plan: 调度计划。

        Returns:
            执行结果。
        """
        result = ScheduleResult(plan_id=plan.id, status=ScheduleStatus.RUNNING)
        result.started_at = datetime.now()

        worker = self._select_worker()
        if not worker:
            result.status = ScheduleStatus.FAILED
            result.error = "没有可用的 Worker 节点"
            result.finished_at = datetime.now()
            logger.error(f"无可用 Worker，计划失败: {plan.name}")
            return result

        # 增加 Worker 负载
        worker.current_load += 1
        worker.status = WorkerStatus.BUSY if worker.current_load >= worker.capacity else worker.status

        try:
            exec_result = await asyncio.wait_for(
                self._executor(plan.test_plan_id, plan.metadata, worker.address),
                timeout=plan.timeout,
            )
            result.status = ScheduleStatus.COMPLETED
            result.metrics = exec_result if isinstance(exec_result, dict) else {}
            result.metrics["worker_id"] = worker.id
            result.metrics["worker_address"] = worker.address
            logger.info(f"分布式计划完成: {plan.name} on {worker.id}")
        except asyncio.TimeoutError:
            result.status = ScheduleStatus.FAILED
            result.error = f"Worker {worker.id} 执行超时 ({plan.timeout}s)"
            logger.error(f"分布式计划超时: {plan.name}")
        except Exception as e:
            result.status = ScheduleStatus.FAILED
            result.error = str(e)
            logger.error(f"分布式计划失败: {plan.name} — {e}")
        finally:
            # 恢复 Worker 负载
            worker.current_load = max(0, worker.current_load - 1)
            if worker.current_load == 0:
                worker.status = WorkerStatus.IDLE
            result.finished_at = datetime.now()

        return result

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, WorkerStatus]:
        """
        检查所有 Worker 的健康状态。

        Returns:
            Worker ID -> 状态的映射。
        """
        statuses: Dict[str, WorkerStatus] = {}
        for worker_id, worker in self._workers.items():
            try:
                # 模拟心跳检测
                await asyncio.sleep(0.01)
                statuses[worker_id] = worker.status
            except Exception:
                worker.status = WorkerStatus.OFFLINE
                statuses[worker_id] = WorkerStatus.OFFLINE
        return statuses

    @staticmethod
    async def _default_executor(
        test_plan_id: str, metadata: dict, worker_address: str
    ) -> dict:
        """默认模拟远程执行器。"""
        logger.debug(f"模拟在 {worker_address} 执行: {test_plan_id}")
        await asyncio.sleep(0.05)
        return {"test_plan_id": test_plan_id, "worker": worker_address, "status": "simulated"}
