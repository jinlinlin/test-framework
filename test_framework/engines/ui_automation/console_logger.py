"""
控制台日志器。

封装浏览器控制台日志的捕获和记录功能。
"""
from __future__ import annotations

import logging
from typing import Any, List

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class ConsoleLogger:
    """
    控制台日志器

    封装浏览器控制台日志的捕获和记录功能。
    """

    def __init__(self, page: Page) -> None:
        self._page = page
        self._enabled = False
        self._logs: List[dict] = []

    async def enable(self) -> None:
        """启用控制台日志捕获"""
        if self._enabled:
            return

        self._page.on("console", self._on_console)
        self._enabled = True
        logger.info("Console logging enabled")

    async def disable(self) -> None:
        """禁用控制台日志捕获"""
        if not self._enabled:
            return

        self._page.remove_listener("console", self._on_console)
        self._enabled = False
        logger.info("Console logging disabled")

    def get_logs(self) -> List[dict]:
        """获取所有日志"""
        return list(self._logs)

    def clear_logs(self) -> None:
        """清除所有日志"""
        self._logs.clear()

    def _on_console(self, msg) -> None:
        """控制台事件处理"""
        log_entry = {
            "type": msg.type,
            "text": msg.text,
            "args": [arg.json() if arg.json is not None else str(arg) for arg in msg.args],
        }
        self._logs.append(log_entry)
        logger.debug(f"Console [{msg.type}]: {msg.text}")