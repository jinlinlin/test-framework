"""
等待请求策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from .base import WaiterStrategy


class RequestWaiter(WaiterStrategy):
    """等待请求策略"""

    def __init__(self, selector: str = "", url_pattern: str = "", **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._url_pattern = url_pattern

    async def wait(self, page) -> None:
        await page.wait_for_request(lambda r: self._url_pattern in r.url, **self._kwargs)

    @property
    def name(self) -> str:
        return "request"