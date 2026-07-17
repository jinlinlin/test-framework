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
        4. 报告器返回报告路径或推送至外部系统
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
    ) -> str:
        """
        测试计划完成时生成最终报告。

        Args:
            plan_name: 测试计划名称。
            results: 所有测试结果列表。

        Returns:
            报告文件路径（或空字符串表示无文件输出）。
        """
        ...

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
