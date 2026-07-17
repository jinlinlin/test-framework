"""
追踪查看器。

封装Playwright追踪的启动、停止和查看功能。
"""
from __future__ import annotations

import logging
from typing import Optional

from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)


class TraceViewer:
    """
    追踪查看器

    封装Playwright追踪的启动、停止和查看功能。
    """

    def __init__(self, context: BrowserContext) -> None:
        self._context = context
        self._enabled = False

    async def start(self, name: str = "trace", screenshots: bool = True, snapshots: bool = True, sources: bool = True) -> None:
        """
        开始追踪

        Args:
            name: 追踪名称
            screenshots: 是否包含截图
            snapshots: 是否包含快照
            sources: 是否包含源码
        """
        await self._context.tracing.start(
            name=name,
            screenshots=screenshots,
            snapshots=snapshots,
            sources=sources
        )
        self._enabled = True
        logger.info(f"Trace started: {name}")

    async def stop(self, path: str) -> None:
        """
        停止追踪并保存

        Args:
            path: 保存路径
        """
        if self._enabled:
            await self._context.tracing.stop(path=path)
            self._enabled = False
            logger.info(f"Trace saved to: {path}")