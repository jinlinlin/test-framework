"""
报告器注册表 — 管理所有活跃报告器，支持多报告器并行工作。

职责：维护报告器实例集合，提供注册/注销/通知/广播等操作。
      支持测试执行过程中动态添加或移除报告器。
"""
from __future__ import annotations

import inspect
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

    # 类级缓存：Reporter 类型 → 其 on_plan_completed 是否接受 run_id/engine。
    # 用签名探测而非盲传新参数，保证用旧签名 override 的第三方 Reporter 不会
    # 收到 unexpected keyword TypeError；首次按类探测，之后 O(1) 命中。
    _SUPPORTS_NEW_PARAMS: Dict[type, bool] = {}

    @classmethod
    def _accepts_new_params(cls, reporter: BaseReporter) -> bool:
        """
        探测报告器的 on_plan_completed 是否声明了 run_id 参数或接受 **kwargs。

        Args:
            reporter: 报告器实例。

        Returns:
            True 表示可以安全透传 run_id/engine 新参数。
        """
        klass = type(reporter)
        cached = cls._SUPPORTS_NEW_PARAMS.get(klass)
        if cached is not None:
            return cached
        try:
            sig = inspect.signature(reporter.on_plan_completed)
        except (TypeError, ValueError):  # 不可 introspect 的实现按旧签名处理
            supports = False
        else:
            supports = (
                "run_id" in sig.parameters
                or any(
                    p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in sig.parameters.values()
                )
            )
        cls._SUPPORTS_NEW_PARAMS[klass] = supports
        return supports

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
        run_id: Optional[str] = None,
        engine: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        生成所有报告器的最终报告。

        对新报告器（override 中声明了 run_id/engine 或 **kwargs）透传新参数；
        对旧签名报告器只传旧参数，保证零破坏。

        Args:
            plan_name: 测试计划名称。
            results: 所有测试结果。
            run_id: 运行 ID（跨引擎共享），可选。
            engine: 引擎标识，可选。

        Returns:
            reporter_type → report_path 的映射。
        """
        paths: Dict[str, str] = {}
        for reporter in self._reporters.values():
            try:
                if self._accepts_new_params(reporter):
                    path = await reporter.on_plan_completed(
                        plan_name, results, run_id=run_id, engine=engine,
                    )
                else:
                    path = await reporter.on_plan_completed(plan_name, results)
                if path:
                    paths[reporter.reporter_type] = path
                    logger.info(f"报告已生成 [{reporter.reporter_type}]: {path}")
            except Exception as e:
                logger.error(f"报告器 {reporter.reporter_type} 生成报告失败: {e}")
        return paths

    async def notify_engine_completed(
        self,
        engine: str,
        run_id: str,
        summary: Dict[str, Any],
    ) -> None:
        """
        通知所有报告器：单个引擎执行完成（供编排器/Layer 3 聚合链路调用）。

        Args:
            engine: 引擎标识（如 "agent_behavior"）。
            run_id: 运行 ID。
            summary: 引擎级 summary（dict 形式）。
        """
        for reporter in self._reporters.values():
            try:
                await reporter.on_engine_completed(engine, run_id, summary)
            except Exception as e:
                logger.error(f"报告器 {reporter.reporter_type} 处理引擎完成失败: {e}")
