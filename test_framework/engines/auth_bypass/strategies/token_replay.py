"""Token 重放策略 — 过期/已注销 Token 是否仍可使用。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import AuthBypassFinding, AuthBypassStrategy

logger = logging.getLogger(__name__)


class TokenReplayStrategy(AuthBypassStrategy):
    """Token 重放越权检测：过期或已注销的 Token 是否仍可使用。"""

    @property
    def name(self) -> str:
        return "token_replay"

    @property
    def severity(self) -> str:
        return "high"

    async def execute(self, target: Any, context: Dict[str, Any]) -> List[AuthBypassFinding]:
        """
        检测已注销/过期 Token 是否仍可使用。

        上下文需包含::
            - expired_token: 已过期/注销的 Token
            - protected_endpoints: 受保护端点列表
        """
        findings: List[AuthBypassFinding] = []
        expired_token = context.get("expired_token", "")
        endpoints = context.get("protected_endpoints", ["/api/user/profile"])
        base_url = getattr(target, "base_url", "")

        if not expired_token:
            logger.warning("Token 重放测试: 未提供过期 Token")
            return findings

        try:
            import httpx
            async with httpx.AsyncClient(base_url=base_url, verify=False) as client:
                for endpoint in endpoints:
                    response = await client.get(
                        endpoint,
                        headers={"Authorization": f"Bearer {expired_token}"},
                    )
                    if response.status_code == 200:
                        findings.append(AuthBypassFinding(
                            strategy=self.name,
                            severity=self.severity,
                            endpoint=endpoint,
                            description="已过期/注销的 Token 仍可访问受保护资源",
                            evidence=f"使用过期 Token 访问 {endpoint}，返回 200",
                        ))
        except ImportError:
            logger.error("httpx 未安装")
        except Exception as e:
            logger.error(f"Token 重放测试异常: {e}")

        return findings
