"""
等待响应策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from typing import Optional

from .base import WaiterStrategy


class ResponseWaiter(WaiterStrategy):
    """等待响应策略"""

    def __init__(self, selector: str = "", url_pattern: str = "", status_code: Optional[int] = None, **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._url_pattern = url_pattern
        self._status_code = status_code

    async def wait(self, page) -> None:
        response = await page.wait_for_response(
            lambda r: self._url_pattern in r.url
            and (self._status_code is None or r.status == self._status_code),
            **self._kwargs
        )
        if self._status_code and response.status != self._status_code:
            raise RuntimeError(f"Expected status {self._status_code}, got {response.status}")

    @property
    def name(self) -> str:
        return "response"