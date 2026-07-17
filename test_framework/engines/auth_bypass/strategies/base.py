"""
越权访问策略抽象基类 — 策略模式。

职责：定义越权访问检测策略的统一接口，
      所有具体策略（角色提升/会话固定/Token重放等）继承此类。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class AuthBypassFinding:
    """
    越权访问发现。

    Attributes:
        strategy: 使用的策略名称。
        severity: 严重等级。
        endpoint: 涉及的端点。
        description: 问题描述。
        evidence: 证据信息。
    """

    strategy: str = ""
    severity: str = "medium"
    endpoint: str = ""
    description: str = ""
    evidence: str = ""

    def to_dict(self) -> Dict[str, str]:
        """转为字典。"""
        return {
            "strategy": self.strategy,
            "severity": self.severity,
            "endpoint": self.endpoint,
            "description": self.description,
            "evidence": self.evidence,
        }


class AuthBypassStrategy(ABC):
    """
    越权访问策略抽象基类。

    每种越权检测方式实现一个具体策略类。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称。"""
        ...

    @property
    def severity(self) -> str:
        """默认严重等级。"""
        return "high"

    @abstractmethod
    async def execute(
        self,
        target: Any,
        context: Dict[str, Any],
    ) -> List[AuthBypassFinding]:
        """
        执行越权检测。

        Args:
            target: 目标系统对象。
            context: 测试上下文（含 token、端点、用户信息等）。

        Returns:
            越权发现列表。
        """
        ...
