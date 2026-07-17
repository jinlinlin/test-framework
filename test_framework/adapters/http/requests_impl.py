"""基于 requests 的同步 HTTP 适配器（包装为异步）。"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from .adapter import HTTPAdapter, HTTPResponse

logger = logging.getLogger(__name__)


class RequestsAdapter(HTTPAdapter):
    """requests 同步 HTTP 适配器（在线程池中执行）。"""

    @property
    def implementation_name(self) -> str:
        return "requests"

    def __init__(self) -> None:
        self._session: Optional[Any] = None

    async def connect(self, config: Dict[str, Any]) -> None:
        import requests
        self._session = requests.Session()
        self._session.verify = config.get("verify_ssl", True)
        logger.debug("RequestsAdapter 已连接")

    async def disconnect(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    async def is_connected(self) -> bool:
        return self._session is not None

    async def request(self, method: str, url: str, **kwargs: Any) -> HTTPResponse:
        if not self._session:
            raise RuntimeError("RequestsAdapter 未连接")

        def _sync_request() -> HTTPResponse:
            start = time.monotonic()
            resp = self._session.request(method, url, **kwargs)
            elapsed = time.monotonic() - start
            return HTTPResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp.text,
                elapsed=elapsed,
                url=resp.url,
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_request)
