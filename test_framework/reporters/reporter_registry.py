"""
报告器注册表 — 管理所有活跃报告器，支持多报告器并行工作。

职责：维护报告器实例集合，提供注册/注销/通知/广播等操作。
      支持测试执行过程中动态添加或移除报告器。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BaseReporter

logger = logging.getLogger(__name__)


class ReporterRegistry:
    """
    报告器注册表。

    管理所有活跃的报告器实例，在事件发生时通知所有报告器。

    使用示例::

        registry = ReporterRegistry()
        registry.register(html_reporter)
        registry.register(json_reporter)
        registry.register(console_reporter)

        # 测试完成时通知所有报告器
        await registry.notify_test_completed(result)

        # 生成最终报告
        paths = await registry.generate_all_reports(plan_name, results)
    """

    def __init__(self) -> None:
        """初始化报告器注册表。"""
        self._reporters: Dict[str, BaseReporter] = {}

    def register(self, reporter: BaseReporter) -> None:
        """
        注册报告器。

        Args:
            reporter: 报告器实例。
        """
        self._reporters[reporter.reporter_type] = reporter
        logger.debug(f"注册报告器: {reporter.reporter_type}")

    def unregister(self, reporter_type: str) -> None:
        """
        注销报告器。

        Args:
            reporter_type: 报告器类型名。
        """
        removed = self._reporters.pop(reporter_type, None)
        if removed:
            logger.debug(f"注销报告器: {reporter_type}")

    def get(self, reporter_type: str) -> Optional[BaseReporter]:
        """获取指定类型的报告器。"""
        return self._reporters.get(reporter_type)

    def get_all(self) -> List[BaseReporter]:
        """获取所有已注册的报告器。"""
        return list(self._reporters.values())

    def has(self, reporter_type: str) -> bool:
        """检查是否已注册指定类型的报告器。"""
        return reporter_type in self._reporters

    async def setup_all(self) -> None:
        """初始化所有报告器。"""
        for reporter in self._reporters.values():
            try:
                await reporter.setup()
            except Exception as e:
                logger.error(f"报告器 {reporter.reporter_type} 初始化失败: {e}")

    async def teardown_all(self) -> None:
        """清理所有报告器。"""
        for reporter in self._reporters.values():
            try:
                await reporter.teardown()
            except Exception as e:
                logger.error(f"报告器 {reporter.reporter_type} 清理失败: {e}")

    async def notify_test_completed(self, result: Dict[str, Any]) -> None:
        """
        通知所有报告器：单个测试用例完成。

        Args:
            result: 测试结果字典。
        """
        for reporter in self._reporters.values():
            try:
                await reporter.on_test_completed(result)
            except Exception as e:
                logger.error(f"报告器 {reporter.reporter_type} 处理测试结果失败: {e}")

    async def notify_suite_started(self, suite_name: str) -> None:
        """通知所有报告器：测试套件开始。"""
        for reporter in self._reporters.values():
            try:
                await reporter.on_suite_started(suite_name)
            except Exception as e:
                logger.error(f"报告器 {reporter.reporter_type} 处理套件开始失败: {e}")

    async def notify_suite_completed(self, suite_name: str, results: List[Dict[str, Any]]) -> None:
        """通知所有报告器：测试套件完成。"""
        for reporter in self._reporters.values():
            try:
                await reporter.on_suite_completed(suite_name, results)
            except Exception as e:
                logger.error(f"报告器 {reporter.reporter_type} 处理套件完成失败: {e}")

    async def generate_all_reports(
        self,
        plan_name: str,
        results: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        生成所有报告器的最终报告。

        Args:
            plan_name: 测试计划名称。
            results: 所有测试结果。

        Returns:
            reporter_type → report_path 的映射。
        """
        paths: Dict[str, str] = {}
        for reporter in self._reporters.values():
            try:
                path = await reporter.on_plan_completed(plan_name, results)
                if path:
                    paths[reporter.reporter_type] = path
                    logger.info(f"报告已生成 [{reporter.reporter_type}]: {path}")
            except Exception as e:
                logger.error(f"报告器 {reporter.reporter_type} 生成报告失败: {e}")
        return paths
