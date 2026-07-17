"""
等待控制台日志策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from .base import WaiterStrategy


class ConsoleLogWaiter(WaiterStrategy):
    """等待控制台日志策略"""

    def __init__(self, selector: str = "", message_pattern: str = "", log_type: str = "log", **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._message_pattern = message_pattern
        self._log_type = log_type

    async def wait(self, page) -> None:
        async with page.expect_console_message(
            lambda msg: msg.type == self._log_type and self._message_pattern in msg.text,
            **self._kwargs
        ):
            pass

    @property
    def name(self) -> str:
        return "console_log"