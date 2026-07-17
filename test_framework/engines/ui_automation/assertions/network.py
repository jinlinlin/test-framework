"""
网络断言。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from typing import Optional

from .base import UIAssertion


class NetworkAssertion(UIAssertion):
    """网络断言"""

    def __init__(self, url_pattern: str, status_code: Optional[int] = None, method: Optional[str] = None, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._url_pattern = url_pattern
        self._status_code = status_code
        self._method = method
        self._responses = []

    async def execute(self, page) -> None:
        response = await page.wait_for_response(
            lambda r: self._url_pattern in r.url
            and (self._method is None or r.request.method == self._method)
            and (self._status_code is None or r.status == self._status_code),
            **self._kwargs
        )
        if self._status_code and response.status != self._status_code:
            raise AssertionError(
                f"Expected status {self._status_code} for {response.url}, got {response.status}"
            )

    @property
    def name(self) -> str:
        return "network"