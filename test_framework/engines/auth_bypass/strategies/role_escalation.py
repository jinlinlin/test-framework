"""
角色提升策略 — 低权限用户尝试访问高权限接口。

职责：使用低权限 Token 访问管理员端点，
      检测是否存在权限校验缺失。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import AuthBypassFinding, AuthBypassStrategy

logger = logging.getLogger(__name__)


class RoleEscalationStrategy(AuthBypassStrategy):
    """角色提升越权检测策略。"""

    @property
    def name(self) -> str:
        return "role_escalation"

    @property
    def severity(self) -> str:
        return "critical"

    async def execute(self, target: Any, context: Dict[str, Any]) -> List[AuthBypassFinding]:
        """
        使用低权限 Token 访问管理员接口。

        上下文需包含::
            - low_privilege_token: 低权限用户 Token
            - admin_endpoints: 管理员端点列表
            - base_url: 基础 URL

        Args:
            target: 目标系统。
            context: 测试上下文。

        Returns:
            越权发现列表。
        """
        findings: List[AuthBypassFinding] = []
        token = context.get("low_privilege_token", "")
        admin_endpoints = context.get("admin_endpoints", ["/admin", "/api/admin/users"])
        base_url = getattr(target, "base_url", "")

        if not token:
            logger.warning("角色提升测试: 未提供低权限 Token")
            return findings

        try:
            import httpx
            async with httpx.AsyncClient(base_url=base_url, verify=False) as client:
                for endpoint in admin_endpoints:
                    response = await client.get(
                        endpoint,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    # 如果返回 200 说明低权限可以访问管理员接口
                    if response.status_code == 200:
                        findings.append(AuthBypassFinding(
                            strategy=self.name,
                            severity=self.severity,
                            endpoint=endpoint,
                            description="低权限用户可访问管理员接口",
                            evidence=f"状态码: {response.status_code}",
                        ))
                    logger.debug(
                        f"角色提升测试 {endpoint}: {response.status_code}"
                    )
        except ImportError:
            logger.error("httpx 未安装")
        except Exception as e:
            logger.error(f"角色提升测试异常: {e}")

        return findings
