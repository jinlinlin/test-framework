"""IDOR 策略 — 不安全的直接对象引用，遍历资源 ID 检测越权访问。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import AuthBypassFinding, AuthBypassStrategy

logger = logging.getLogger(__name__)


class IDORStrategy(AuthBypassStrategy):
    """IDOR（不安全的直接对象引用）越权检测：遍历资源 ID 检测越权。"""

    @property
    def name(self) -> str:
        return "idor"

    @property
    def severity(self) -> str:
        return "high"

    async def execute(self, target: Any, context: Dict[str, Any]) -> List[AuthBypassFinding]:
        """
        IDOR 检测：使用用户 A 的 Token 访问用户 B 的资源。

        上下文需包含::
            - token: 当前用户 Token
            - resource_endpoint: 资源端点模板（如 /api/users/{id}）
            - own_resource_ids: 当前用户拥有的资源 ID
            - other_resource_ids: 其他用户的资源 ID
        """
        findings: List[AuthBypassFinding] = []
        token = context.get("token", "")
        resource_endpoint = context.get("resource_endpoint", "/api/resources/{id}")
        own_ids = context.get("own_resource_ids", ["1"])
        other_ids = context.get("other_resource_ids", ["2", "3", "100"])
        base_url = getattr(target, "base_url", "")

        if not token:
            logger.warning("IDOR 测试: 未提供 Token")
            return findings

        try:
            import httpx
            async with httpx.AsyncClient(base_url=base_url, verify=False) as client:
                # 先确认能访问自己的资源
                own_ok = False
                for rid in own_ids:
                    url = resource_endpoint.replace("{id}", str(rid))
                    resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
                    if resp.status_code == 200:
                        own_ok = True
                        break

                if not own_ok:
                    logger.debug("IDOR: 无法访问自己的资源，跳过测试")
                    return findings

                # 尝试访问其他用户的资源
                for rid in other_ids:
                    url = resource_endpoint.replace("{id}", str(rid))
                    resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
                    if resp.status_code == 200:
                        findings.append(AuthBypassFinding(
                            strategy=self.name,
                            severity=self.severity,
                            endpoint=url,
                            description=f"IDOR: 可访问其他用户资源 ID={rid}",
                            evidence=f"使用当前用户 Token 访问 {url}，返回 200",
                        ))
        except ImportError:
            logger.error("httpx 未安装")
        except Exception as e:
            logger.error(f"IDOR 测试异常: {e}")

        return findings
