"""OAuth 攻击策略 — redirect_uri 篡改、state 参数缺失、scope 提升。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import AuthBypassFinding, AuthBypassStrategy

logger = logging.getLogger(__name__)


class OAuthAttackStrategy(AuthBypassStrategy):
    """OAuth 攻击越权检测：redirect_uri 篡改、state 缺失、scope 提升。"""

    @property
    def name(self) -> str:
        return "oauth_attack"

    @property
    def severity(self) -> str:
        return "high"

    async def execute(self, target: Any, context: Dict[str, Any]) -> List[AuthBypassFinding]:
        """
        OAuth 攻击检测：
        1. redirect_uri 篡改（指向攻击者控制的域名）
        2. state 参数缺失检测
        3. scope 权限提升
        """
        findings: List[AuthBypassFinding] = []
        oauth_endpoint = context.get("oauth_endpoint", "/oauth/authorize")
        client_id = context.get("client_id", "test_client")
        redirect_uri = context.get("redirect_uri", "http://localhost/callback")
        base_url = getattr(target, "base_url", "")

        try:
            import httpx
            async with httpx.AsyncClient(base_url=base_url, verify=False, follow_redirects=False) as client:
                # 测试 1: redirect_uri 篡改
                evil_redirect = "http://evil.com/callback"
                response = await client.get(oauth_endpoint, params={
                    "client_id": client_id,
                    "redirect_uri": evil_redirect,
                    "response_type": "code",
                    "scope": "read",
                })
                if response.status_code in (200, 302):
                    location = response.headers.get("location", "")
                    if "evil.com" in location or response.status_code == 200:
                        findings.append(AuthBypassFinding(
                            strategy=self.name,
                            severity="critical",
                            endpoint=oauth_endpoint,
                            description="redirect_uri 可被篡改，可能导致授权码泄露",
                            evidence=f"使用恶意 redirect_uri 后状态码: {response.status_code}",
                        ))

                # 测试 2: state 参数缺失
                response = await client.get(oauth_endpoint, params={
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "scope": "read",
                    # 故意不传 state
                })
                if response.status_code in (200, 302):
                    findings.append(AuthBypassFinding(
                        strategy=self.name,
                        severity="medium",
                        endpoint=oauth_endpoint,
                        description="OAuth 授权流程未强制要求 state 参数（CSRF 风险）",
                        evidence="缺少 state 参数仍成功发起授权",
                    ))

                # 测试 3: scope 提升
                response = await client.get(oauth_endpoint, params={
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "scope": "read write admin",  # 请求额外权限
                })
                if response.status_code in (200, 302):
                    findings.append(AuthBypassFinding(
                        strategy=self.name,
                        severity="high",
                        endpoint=oauth_endpoint,
                        description="OAuth scope 可能被提升，请求额外权限未被拒绝",
                        evidence="请求 scope=read write admin 未被拒绝",
                    ))
        except ImportError:
            logger.error("httpx 未安装")
        except Exception as e:
            logger.error(f"OAuth 攻击测试异常: {e}")

        return findings
