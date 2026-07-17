"""
网络捕获器。

封装网络请求的捕获和分析功能。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class NetworkCapture:
    """
    网络捕获器

    封装网络请求的捕获和分析功能。
    """

    def __init__(self, page: Page) -> None:
        self._page = page
        self._enabled = False
        self._entries: List[Dict[str, Any]] = []

    async def enable(self) -> None:
        """启用网络捕获"""
        if self._enabled:
            return

        self._page.on("request", self._on_request)
        self._page.on("response", self._on_response)
        self._enabled = True
        logger.info("Network capture enabled")

    async def disable(self) -> None:
        """禁用网络捕获"""
        if not self._enabled:
            return

        self._page.remove_listener("request", self._on_request)
        self._page.remove_listener("response", self._on_response)
        self._enabled = False
        logger.info("Network capture disabled")

    def get_entries(self) -> List[Dict[str, Any]]:
        """获取所有网络记录"""
        return list(self._entries)

    def clear_entries(self) -> None:
        """清除所有记录"""
        self._entries.clear()

    def _on_request(self, request) -> None:
        """请求事件处理"""
        entry = {
            "method": request.method,
            "url": request.url,
            "headers": dict(request.headers),
            "body": request.post_data,
            "timestamp": request.start_time,
        }
        self._entries.append(entry)
        logger.debug(f"Request: {request.method} {request.url}")

    def _on_response(self, response) -> None:
        """响应事件处理"""
        logger.debug(f"Response: {response.status} {response.url}")