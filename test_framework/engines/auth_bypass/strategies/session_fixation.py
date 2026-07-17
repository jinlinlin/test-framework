"""会话固定策略 — 登录后 Session ID 是否变更。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import AuthBypassFinding, AuthBypassStrategy

logger = logging.getLogger(__name__)


class SessionFixationStrategy(AuthBypassStrategy):
    """会话固定越权检测：登录后 Session ID 是否变更。"""

    @property
    def name(self) -> str:
        return "session_fixation"

    @property
    def severity(self) -> str:
        return "high"

    async def execute(self, target: Any, context: Dict[str, Any]) -> List[AuthBypassFinding]:
        """
        检测登录后 Session ID 是否更新。

        流程：获取初始 Session → 执行登录 → 比较 Session 是否变更。
        """
        findings: List[AuthBypassFinding] = []
        login_endpoint = context.get("login_endpoint", "/api/login")
        credentials = context.get("credentials", {})
        base_url = getattr(target, "base_url", "")

        try:
            import httpx
            async with httpx.AsyncClient(base_url=base_url, verify=False) as client:
                # 获取初始 session
                await client.get("/")
                session_before = client.cookies.get("sessionid", client.cookies.get("JSESSIONID", ""))

                # 执行登录
                await client.post(login_endpoint, json=credentials)
                session_after = client.cookies.get("sessionid", client.cookies.get("JSESSIONID", ""))

                if session_before and session_after and session_before == session_after:
                    findings.append(AuthBypassFinding(
                        strategy=self.name,
                        severity=self.severity,
                        endpoint=login_endpoint,
                        description="登录后 Session ID 未变更（会话固定漏洞）",
                        evidence=f"Session before: {session_before[:8]}..., after: {session_after[:8]}...",
                    ))
        except ImportError:
            logger.error("httpx 未安装")
        except Exception as e:
            logger.error(f"会话固定测试异常: {e}")

        return findings
