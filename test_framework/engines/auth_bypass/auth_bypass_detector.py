"""
越权访问检测器 — 统一越权检测调度。

职责：接收越权策略实例，调度执行，汇总越权发现。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .strategies.base import AuthBypassFinding, AuthBypassStrategy

logger = logging.getLogger(__name__)


class AuthBypassDetector:
    """
    越权访问检测器。

    统一调度越权策略的执行，管理 HTTP 客户端生命周期，
    汇总各策略的越权发现。

    Attributes:
        _target: 目标系统对象。
        _config: 检测配置。
    """

    def __init__(self, target: Any, config: Dict[str, Any]) -> None:
        """
        初始化越权检测器。

        Args:
            target: 目标系统对象。
            config: 检测配置。
        """
        self._target = target
        self._config = config

    async def run_strategy(
        self,
        strategy: AuthBypassStrategy,
        context: Dict[str, Any],
    ) -> List[AuthBypassFinding]:
        """
        运行单个越权策略。

        Args:
            strategy: 越权策略实例。
            context: 测试上下文。

        Returns:
            越权发现列表。
        """
        try:
            findings = await strategy.execute(self._target, context)
            logger.info(
                f"策略 {strategy.name} 完成: 发现 {len(findings)} 个越权问题"
            )
            return findings
        except Exception as e:
            logger.error(f"策略 {strategy.name} 执行异常: {e}")
            return []

    async def run_all_strategies(
        self,
        strategies: List[AuthBypassStrategy],
        context: Dict[str, Any],
    ) -> List[AuthBypassFinding]:
        """
        运行所有越权策略。

        Args:
            strategies: 策略列表。
            context: 测试上下文。

        Returns:
            所有策略的越权发现汇总。
        """
        all_findings: List[AuthBypassFinding] = []
        for strategy in strategies:
            findings = await self.run_strategy(strategy, context)
            all_findings.extend(findings)

        logger.info(
            f"越权检测完成: {len(strategies)} 个策略，"
            f"共发现 {len(all_findings)} 个问题"
        )
        return all_findings
