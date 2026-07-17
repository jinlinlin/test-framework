"""
网络拦截器

提供网络请求的拦截、修改和记录能力。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from playwright.async_api import Page, Request, Response, Route

logger = logging.getLogger(__name__)


@dataclass
class NetworkRequest:
    """网络请求记录"""
    method: str = ""
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    timestamp: float = 0.0


@dataclass
class NetworkResponse:
    """网络响应记录"""
    status: int = 0
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    duration: float = 0.0
    size: int = 0


@dataclass
class NetworkEntry:
    """完整的网络请求/响应记录"""
    request: NetworkRequest = field(default_factory=NetworkRequest)
    response: Optional[NetworkResponse] = None
    success: bool = False


class NetworkInterceptor:
    """
    网络拦截器

    提供网络请求的拦截、修改和记录能力。
    """

    def __init__(self, page: Page) -> None:
        self._page = page
        self._entries: List[NetworkEntry] = []
        self._request_handlers: List[Callable[[Request], None]] = []
        self._response_handlers: List[Callable[[Response], None]] = []
        self._route_handlers: Dict[str, Callable[[Route], None]] = {}
        self._enabled = False

    @property
    def enabled(self) -> bool:
        """是否启用"""
        return self._enabled

    @property
    def entries(self) -> List[NetworkEntry]:
        """获取所有网络记录"""
        return list(self._entries)

    async def enable(self) -> None:
        """启用网络拦截"""
        if self._enabled:
            return

        self._page.on("request", self._on_request)
        self._page.on("response", self._on_response)
        self._enabled = True
        logger.info("Network interceptor enabled")

    async def disable(self) -> None:
        """禁用网络拦截"""
        if not self._enabled:
            return

        self._page.remove_listener("request", self._on_request)
        self._page.remove_listener("response", self._on_response)
        for pattern in list(self._route_handlers.keys()):
            await self._page.unroute(pattern)
        self._enabled = False
        logger.info("Network interceptor disabled")

    def add_request_handler(self, handler: Callable[[Request], None]) -> None:
        """添加请求处理器"""
        self._request_handlers.append(handler)

    def add_response_handler(self, handler: Callable[[Response], None]) -> None:
        """添加响应处理器"""
        self._response_handlers.append(handler)

    async def intercept(
        self,
        url_pattern: str,
        handler: Callable[[Route], None]
    ) -> None:
        """
        拦截指定URL模式的请求

        Args:
            url_pattern: URL模式
            handler: 处理函数
        """
        await self._page.route(url_pattern, handler)
        self._route_handlers[url_pattern] = handler
        logger.debug(f"Added route interceptor for pattern: {url_pattern}")

    async def mock_response(
        self,
        url_pattern: str,
        status: int = 200,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        json_body: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        模拟响应

        Args:
            url_pattern: URL模式
            status: 状态码
            headers: 响应头
            body: 响应体
            json_body: JSON响应体
        """
        if json_body:
            body = json.dumps(json_body)
            headers = headers or {}
            headers.setdefault("Content-Type", "application/json")

        async def _handle_route(route: Route) -> None:
            await route.fulfill(
                status=status,
                headers=headers or {},
                body=body or ""
            )

        await self.intercept(url_pattern, _handle_route)
        logger.debug(f"Added mock response for pattern: {url_pattern}")

    async def abort_request(self, url_pattern: str, error_code: str = "failed") -> None:
        """
        中止指定URL模式的请求

        Args:
            url_pattern: URL模式
            error_code: 错误码
        """
        async def _abort_route(route: Route) -> None:
            await route.abort(error_code)

        await self.intercept(url_pattern, _abort_route)
        logger.debug(f"Added abort interceptor for pattern: {url_pattern}")

    async def clear_interceptors(self) -> None:
        """清除所有拦截器"""
        for pattern in list(self._route_handlers.keys()):
            await self._page.unroute(pattern)
            del self._route_handlers[pattern]
        logger.info("Cleared all route interceptors")

    def clear_entries(self) -> None:
        """清除所有网络记录"""
        self._entries.clear()

    def get_entries_by_url(self, url_pattern: str) -> List[NetworkEntry]:
        """根据URL模式过滤记录"""
        return [entry for entry in self._entries if url_pattern in entry.request.url]

    def get_entries_by_method(self, method: str) -> List[NetworkEntry]:
        """根据HTTP方法过滤记录"""
        return [entry for entry in self._entries if entry.request.method.upper() == method.upper()]

    async def save_har(self, path: str) -> None:
        """保存HAR文件"""
        har_data = {
            "log": {
                "version": "1.2",
                "creator": {"name": "Uniplore Test Framework", "version": "1.0"},
                "entries": [
                    {
                        "request": {
                            "method": entry.request.method,
                            "url": entry.request.url,
                            "headers": [
                                {"name": k, "value": v} for k, v in entry.request.headers.items()
                            ],
                            "bodySize": len(entry.request.body or ""),
                            "postData": {"text": entry.request.body or ""} if entry.request.body else {}
                        },
                        "response": {
                            "status": entry.response.status if entry.response else 0,
                            "headers": [
                                {"name": k, "value": v} for k, v in (entry.response.headers if entry.response else {}).items()
                            ],
                            "bodySize": entry.response.size if entry.response else 0,
                        },
                        "time": entry.response.duration * 1000 if entry.response else 0
                    }
                    for entry in self._entries
                ]
            }
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(har_data, f, indent=2, ensure_ascii=False)

        logger.info(f"HAR file saved to: {path}")

    def _on_request(self, request: Request) -> None:
        """请求事件处理"""
        entry = NetworkEntry(
            request=NetworkRequest(
                method=request.method,
                url=request.url,
                headers=dict(request.headers),
                body=request.post_data,
                timestamp=request.start_time
            )
        )
        self._entries.append(entry)

        for handler in self._request_handlers:
            try:
                handler(request)
            except Exception as e:
                logger.warning(f"Request handler failed: {e}")

        logger.debug(f"Request: {request.method} {request.url}")

    async def _on_response(self, response: Response) -> None:
        """响应事件处理"""
        request = response.request
        entry = None
        for e in reversed(self._entries):
            if e.request.url == request.url and e.response is None:
                entry = e
                break

        if entry:
            try:
                body = await response.text()
            except Exception:
                body = None

            entry.response = NetworkResponse(
                status=response.status,
                url=response.url,
                headers=dict(response.headers),
                body=body,
                duration=response.request.start_time - response.start_time if hasattr(response, 'start_time') else 0,
                size=len(body or "")
            )
            entry.success = 200 <= response.status < 300

        for handler in self._response_handlers:
            try:
                handler(response)
            except Exception as e:
                logger.warning(f"Response handler failed: {e}")

        logger.debug(f"Response: {response.status} {response.url}")