"""基于 httpx 的异步 HTTP 适配器（推荐默认）。"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from .adapter import HTTPAdapter, HTTPResponse

logger = logging.getLogger(__name__)


class HttpxAdapter(HTTPAdapter):
    """httpx 异步 HTTP 适配器。"""

    @property
    def implementation_name(self) -> str:
        return "httpx"

    def __init__(self) -> None:
        self._client: Optional[Any] = None

    async def connect(self, config: Dict[str, Any]) -> None:
        import httpx
        self._client = httpx.AsyncClient(
            timeout=config.get("timeout", 30),
            verify=config.get("verify_ssl", True),
            follow_redirects=config.get("follow_redirects", True),
            limits=httpx.Limits(max_connections=config.get("max_connections", 100)),
        )
        logger.debug("HttpxAdapter 已连接")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def is_connected(self) -> bool:
        return self._client is not None

    async def request(self, method: str, url: str, **kwargs: Any) -> HTTPResponse:
        if not self._client:
            raise RuntimeError("HttpxAdapter 未连接")
        start = time.monotonic()
        resp = await self._client.request(method, url, **kwargs)
        elapsed = time.monotonic() - start
        return HTTPResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            body=resp.text,
            elapsed=elapsed,
            url=str(resp.url),
        )
