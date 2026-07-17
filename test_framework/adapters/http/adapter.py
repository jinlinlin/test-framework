"""
HTTP 适配器统一接口。

职责：定义 HTTP 请求的统一抽象，所有 HTTP 实现
      （httpx / requests / aiohttp）必须遵循此接口。
"""
from __future__ import annotations

import json as json_lib
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..base import BaseAdapter


@dataclass
class HTTPResponse:
    """
    HTTP 响应数据对象。

    Attributes:
        status_code: HTTP 状态码。
        headers: 响应头字典。
        body: 响应体。
        elapsed: 耗时（秒）。
        url: 实际请求 URL。
    """

    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    elapsed: float = 0.0
    url: str = ""

    def json(self) -> Any:
        """解析响应体为 JSON。"""
        if isinstance(self.body, str):
            return json_lib.loads(self.body)
        return self.body

    def text(self) -> str:
        """获取响应体文本。"""
        if isinstance(self.body, bytes):
            return self.body.decode("utf-8", errors="replace")
        return str(self.body) if self.body is not None else ""

    def raise_for_status(self) -> None:
        """如果状态码 >= 400 则抛出异常。"""
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code} for {self.url}")


class HTTPAdapter(BaseAdapter):
    """
    HTTP 适配器抽象基类。

    定义 GET / POST / PUT / DELETE 等统一方法。
    """

    @property
    def adapter_type(self) -> str:
        return "http"

    @abstractmethod
    async def request(self, method: str, url: str, **kwargs: Any) -> HTTPResponse:
        """发送 HTTP 请求。"""
        ...

    async def get(self, url: str, **kwargs: Any) -> HTTPResponse:
        """GET 请求。"""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> HTTPResponse:
        """POST 请求。"""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> HTTPResponse:
        """PUT 请求。"""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> HTTPResponse:
        """DELETE 请求。"""
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> HTTPResponse:
        """PATCH 请求。"""
        return await self.request("PATCH", url, **kwargs)
