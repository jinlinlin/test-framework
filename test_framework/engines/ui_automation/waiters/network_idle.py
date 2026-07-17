"""
等待网络空闲策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from .base import WaiterStrategy


class NetworkIdleWaiter(WaiterStrategy):
    """等待网络空闲策略"""

    async def wait(self, page) -> None:
        await page.wait_for_load_state("networkidle", **self._kwargs)

    @property
    def name(self) -> str:
        return "network_idle"