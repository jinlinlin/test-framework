"""
测试引擎基类 — 所有测试引擎的统一执行骨架（模板模式）。

设计模式：模板模式（Template Method）
职责：定义所有测试引擎的固定执行流程，
      子类仅需实现差异化的步骤（setup / execute_case / collect_metrics / teardown）。

执行生命周期：
    validate_config → setup → [execute_case × N] → collect_metrics → generate_report → teardown
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.events import EventBus, Event, EventTypes
from ..core.models import (
    TestCase,
    TestMetrics,
    TestPlan,
    TestReport,
    TestResult,
    TestSuite,
    TargetSystem,
)
from ..core.models.enums import TestStatus, TestType

logger = logging.getLogger(__name__)


class BaseEngine(ABC):
    """
    测试引擎抽象基类（模板模式）。

    提供统一的 run() 模板方法，按固定流程调用各步骤，
    子类只需实现 setup / execute_case / collect_metrics / teardown。

    Attributes:
        _config: 引擎配置字典。
        _container: IoC 容器引用。
        _event_bus: 事件总线。
        _results: 测试过程中收集的结果列表。
    """

    def __init__(self, config: Dict[str, Any], container: Any) -> None:
        """
        初始化引擎。

        Args:
            config: 引擎配置字典（来自 ConfigManager）。
            container: IoC 容器实例。
        """
        self._config = config
        self._container = container
        self._results: List[TestResult] = []

        # 从容器解析事件总线（如果可用）
        try:
            self._event_bus: Optional[EventBus] = container.resolve(EventBus)
        except Exception:
            self._event_bus = None

    @property
    @abstractmethod
    def engine_type(self) -> TestType:
        """
        返回引擎对应的测试类型枚举。

        Returns:
            TestType 枚举值。
        """
        ...

    async def run(self, plan: TestPlan, target: TargetSystem) -> TestReport:
        """
        模板方法 — 固定执行流程，子类实现各步骤。

        执行顺序：
        1. validate_config() — 验证配置
        2. setup(target) — 初始化引擎资源
        3. 遍历 TestPlan 中的所有用例，逐个执行 execute_case()
        4. collect_metrics() — 采集性能指标
        5. generate_report() — 生成报告
        6. teardown() — 清理资源（始终执行）

        Args:
            plan: 测试计划。
            target: 被测目标系统。

        Returns:
            测试报告。
        """
        logger.info(f"引擎 {self.engine_type.value} 开始执行，计划: {plan.name}")

        # 步骤 1：验证配置
        self.validate_config()

        # 步骤 2：初始化
        await self.setup(target)

        try:
            # 步骤 3：遍历执行所有测试用例
            for suite in plan.suites:
                for case in suite.get_all_cases():
                    logger.info(f"执行用例: {case.name} (ID: {case.id})")

                    # 发布用例开始事件
                    await self._publish_event(
                        EventTypes.TEST_CASE_STARTED,
                        {"case_id": case.id, "case_name": case.name},
                    )

                    # 执行用例
                    result = await self.execute_case(case, target)
                    self._results.append(result)

                    # 发布用例完成事件
                    await self._publish_event(
                        EventTypes.TEST_CASE_COMPLETED,
                        {"case_id": case.id, "status": result.status.value},
                    )

                    logger.info(f"用例完成: {case.name} → {result.status.value}")

            # 步骤 4：采集指标
            metrics = await self.collect_metrics()

            # 步骤 5：生成报告
            report = await self.generate_report(plan, metrics)

            logger.info(f"引擎 {self.engine_type.value} 执行完成，报告裁定: {report.verdict}")
            return report

        finally:
            # 步骤 6：清理资源（始终执行）
            await self.teardown()
            logger.info(f"引擎 {self.engine_type.value} 资源已清理")

    def validate_config(self) -> None:
        """
        验证引擎配置（可选覆盖）。

        默认不做验证，子类可覆盖此方法添加配置校验逻辑。

        Raises:
            ConfigException: 配置不合法时抛出。
        """
        logger.debug(f"引擎 {self.engine_type.value} 配置验证通过（默认）")

    @abstractmethod
    async def setup(self, target: TargetSystem) -> None:
        """
        初始化引擎资源。

        Args:
            target: 被测目标系统。
        """
        ...

    @abstractmethod
    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        """
        执行单个测试用例。

        Args:
            case: 测试用例。
            target: 被测目标系统。

        Returns:
            测试结果。
        """
        ...

    @abstractmethod
    async def collect_metrics(self) -> TestMetrics:
        """
        采集测试指标。

        Returns:
            测试指标数据。
        """
        ...

    @abstractmethod
    async def teardown(self) -> None:
        """清理引擎资源。"""
        ...

    async def generate_report(
        self, plan: TestPlan, metrics: TestMetrics
    ) -> TestReport:
        """
        生成测试报告。

        Args:
            plan: 测试计划。
            metrics: 测试指标。

        Returns:
            测试报告。
        """
        return TestReport.from_results(
            plan_name=plan.name,
            results=self._results,
            metrics=metrics,
        )

    async def _publish_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        发布事件（如果事件总线可用）。

        Args:
            event_type: 事件类型。
            data: 事件数据。
        """
        if self._event_bus:
            try:
                await self._event_bus.publish(Event(
                    type=event_type,
                    source=self,
                    data=data,
                ))
            except Exception as e:
                logger.warning(f"事件发布失败: {e}")
