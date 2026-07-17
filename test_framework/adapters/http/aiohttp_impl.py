"""基于 aiohttp 的异步 HTTP 适配器。"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from .adapter import HTTPAdapter, HTTPResponse

logger = logging.getLogger(__name__)


class AiohttpAdapter(HTTPAdapter):
    """aiohttp 异步 HTTP 适配器。"""

    @property
    def implementation_name(self) -> str:
        return "aiohttp"

    def __init__(self) -> None:
        self._session: Optional[Any] = None

    async def connect(self, config: Dict[str, Any]) -> None:
        import aiohttp
        import ssl as ssl_module
        ssl_ctx = None if config.get("verify_ssl", True) else False
        timeout = aiohttp.ClientTimeout(total=config.get("timeout", 30))
        connector = aiohttp.TCPConnector(
            limit=config.get("max_connections", 100),
            ssl=ssl_ctx,
        )
        self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        logger.debug("AiohttpAdapter 已连接")

    async def disconnect(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def is_connected(self) -> bool:
        return self._session is not None and not self._session.closed

    async def request(self, method: str, url: str, **kwargs: Any) -> HTTPResponse:
        if not self._session or self._session.closed:
            raise RuntimeError("AiohttpAdapter 未连接")
        start = time.monotonic()
        async with self._session.request(method, url, **kwargs) as resp:
            body = await resp.text()
            elapsed = time.monotonic() - start
            return HTTPResponse(
                status_code=resp.status,
                headers=dict(resp.headers),
                body=body,
                elapsed=elapsed,
                url=str(resp.url),
            )
