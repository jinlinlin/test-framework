"""
报告器基类 — 观察者模式的事件驱动报告生成。

设计模式：观察者模式（Observer Pattern）
职责：报告器订阅事件总线事件，收集测试结果，
      在适当时机生成报告（实时输出 / 批量汇总）。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseReporter(ABC):
    """
    报告器抽象基类。

    所有报告器（HTML / JSON / Console / Allure）必须继承此类。

    生命周期::

        1. 报告器被注册到 ReporterRegistry
        2. 测试执行过程中，通过 on_test_completed 接收每个用例结果
        3. 测试计划完成后，通过 on_plan_completed 生成最终报告
        4. 引擎执行完成后，通过 on_engine_completed 输出引擎级 summary
           （供 Layer 3 聚合器收集，默认 no-op，仅聚合器需要覆盖）
        5. 报告器返回报告路径或推送至外部系统
    """

    @property
    @abstractmethod
    def reporter_type(self) -> str:
        """
        报告器类型。

        Returns:
            "html" / "json" / "console" / "allure" / "external"
        """
        ...

    @abstractmethod
    async def on_test_completed(self, result: Dict[str, Any]) -> None:
        """
        单个测试用例完成时的回调。

        Args:
            result: 测试结果字典，包含:
                - test_name: 测试名称
                - status: 状态 (passed/failed/error/skipped)
                - duration: 耗时（秒）
                - error_message: 错误信息（可选）
                - metrics: 指标数据（可选）
        """
        ...

    @abstractmethod
    async def on_plan_completed(
        self,
        plan_name: str,
        results: List[Dict[str, Any]],
        run_id: Optional[str] = None,
        engine: Optional[str] = None,
    ) -> str:
        """
        测试计划完成时生成最终报告。

        Args:
            plan_name: 测试计划名称。
            results: 所有测试结果列表。
            run_id: 运行 ID（跨引擎共享）；None 表示调用方未提供运行维度。
            engine: 引擎标识（如 "agent_behavior"）；None 表示未提供。

        Returns:
            报告文件路径（或空字符串表示无文件输出）。
        """
        ...

    async def on_engine_completed(
        self,
        engine: str,
        run_id: str,
        summary: Dict[str, Any],
    ) -> None:
        """
        引擎执行完成时的回调（可选覆盖）。

        默认实现：no-op。Layer 3 聚合器（如 DashboardReporter）覆盖此方法，
        用于收集各引擎的 summary 并生成跨引擎报告；仅由编排器调用。

        Args:
            engine: 引擎标识（如 "agent_behavior"）。
            run_id: 运行 ID。
            summary: 引擎级 summary（dict 形式）。
        """
        pass

    async def on_suite_started(self, suite_name: str) -> None:
        """测试套件开始时的回调（可选覆盖）。"""
        pass

    async def on_suite_completed(self, suite_name: str, results: List[Dict[str, Any]]) -> None:
        """测试套件完成时的回调（可选覆盖）。"""
        pass

    async def setup(self) -> None:
        """报告器初始化（可选覆盖）。"""
        pass

    async def teardown(self) -> None:
        """报告器清理（可选覆盖）。"""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(type={self.reporter_type})>"
