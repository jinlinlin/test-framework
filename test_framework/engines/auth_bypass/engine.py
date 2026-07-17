"""
越权访问测试引擎 — 引擎主类。

职责：加载越权策略 → 依次执行各策略 → 汇总检测结果。
      覆盖角色提升/会话固定/Token重放/JWT攻击/OAuth攻击/IDOR。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from ...core.models import TestCase, TestMetrics, TestResult, TargetSystem
from ...core.models.enums import TestStatus, TestType
from ..base import BaseEngine
from .auth_bypass_detector import AuthBypassDetector
from .strategies import (
    AuthBypassStrategy,
    IDORStrategy,
    JWTAttackStrategy,
    OAuthAttackStrategy,
    RoleEscalationStrategy,
    SessionFixationStrategy,
    TokenReplayStrategy,
)
from .strategies.base import AuthBypassFinding

logger = logging.getLogger(__name__)

# 策略注册表
STRATEGY_REGISTRY: Dict[str, type] = {
    "role_escalation": RoleEscalationStrategy,
    "session_fixation": SessionFixationStrategy,
    "token_replay": TokenReplayStrategy,
    "jwt_attack": JWTAttackStrategy,
    "oauth_attack": OAuthAttackStrategy,
    "idor": IDORStrategy,
}


class AuthBypassEngine(BaseEngine):
    """
    越权访问测试引擎。

    执行流程：加载越权策略 → 依次执行各策略 → 汇总检测结果。

    Attributes:
        _detector: 越权检测器。
        _strategies: 已加载的策略实例字典。
    """

    @property
    def engine_type(self) -> TestType:
        """引擎类型。"""
        return TestType.AUTH_BYPASS

    async def setup(self, target: TargetSystem) -> None:
        """
        初始化越权访问引擎。

        Args:
            target: 目标系统对象。
        """
        self._detector = AuthBypassDetector(target, self._config)
        self._strategies = self._load_strategies()
        logger.info(f"越权访问引擎已初始化: {len(self._strategies)} 种策略")

    def _load_strategies(self) -> Dict[str, AuthBypassStrategy]:
        """
        加载所有已注册的越权策略。

        Returns:
            策略名称 → 策略实例的映射。
        """
        strategies: Dict[str, AuthBypassStrategy] = {}
        enabled = self._config.get(
            "strategies",
            list(STRATEGY_REGISTRY.keys()),
        )
        for name in enabled:
            cls = STRATEGY_REGISTRY.get(name)
            if cls:
                strategies[name] = cls()
            else:
                logger.warning(f"未知的越权策略: {name}")
        return strategies

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        """
        执行单个越权测试用例。

        用例配置格式::

            {
                "strategies": ["role_escalation", "token_replay", "idor"],
                "low_privilege_token": "xxx",
                "admin_endpoints": ["/admin"],
                "protected_endpoints": ["/api/user/profile"],
                "resource_endpoint": "/api/resources/{id}",
                "own_resource_ids": ["1"],
                "other_resource_ids": ["2", "3"]
            }

        Args:
            case: 测试用例。
            target: 目标系统。

        Returns:
            测试结果。
        """
        try:
            strategy_names = case.config.get(
                "strategies", list(self._strategies.keys())
            )

            all_findings: List[AuthBypassFinding] = []

            for name in strategy_names:
                strategy = self._strategies.get(name)
                if not strategy:
                    logger.warning(f"越权策略 '{name}' 未加载")
                    continue

                findings = await self._detector.run_strategy(strategy, case.config)
                all_findings.extend(findings)

            # 判断状态
            status = TestStatus.FAIL if all_findings else TestStatus.PASS

            return TestResult(
                case_id=case.id,
                status=status,
                duration=0,
                details={
                    "findings_count": len(all_findings),
                    "findings": [f.to_dict() for f in all_findings],
                    "strategies_tested": strategy_names,
                },
                metrics=TestMetrics(
                    custom={"bypass_issues_found": len(all_findings)},
                ),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"越权测试异常: {e}")
            return TestResult(
                case_id=case.id,
                status=TestStatus.ERROR,
                duration=0,
                details={"error": str(e)},
                metrics=TestMetrics(),
                timestamp=datetime.now(),
            )

    async def collect_metrics(self) -> TestMetrics:
        """汇总越权测试指标。"""
        if not self._results:
            return TestMetrics()
        total_issues = sum(
            r.details.get("findings_count", 0) for r in self._results
        )
        return TestMetrics(
            total_cases=len(self._results),
            passed=sum(1 for r in self._results if r.status == TestStatus.PASS),
            failed=sum(1 for r in self._results if r.status == TestStatus.FAIL),
            custom={"total_bypass_issues": total_issues},
        )

    async def teardown(self) -> None:
        """关闭引擎。"""
        logger.info("越权访问引擎已关闭")
