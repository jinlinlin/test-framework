"""
网络工具 — 提供 HTTP 请求、端口检测、DNS 解析等网络操作。

职责：封装常用网络操作，支持异步 HTTP 请求。
"""
from __future__ import annotations

import asyncio
import logging
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class NetworkUtils:
    """
    网络工具类。

    使用示例::

        net = NetworkUtils()
        is_up = await net.check_port("localhost", 8080)
        result = await net.http_get("https://api.example.com/health")
    """

    # ------------------------------------------------------------------
    # 端口检测
    # ------------------------------------------------------------------

    @staticmethod
    async def check_port(host: str, port: int, timeout: float = 3.0) -> bool:
        """
        检测端口是否可用。

        Args:
            host: 主机地址。
            port: 端口号。
            timeout: 超时时间（秒）。

        Returns:
            端口是否可用。
        """
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            return False

    @staticmethod
    async def wait_for_port(
        host: str, port: int, timeout: float = 30.0, interval: float = 1.0
    ) -> bool:
        """
        等待端口可用。

        Args:
            host: 主机地址。
            port: 端口号。
            timeout: 总超时时间（秒）。
            interval: 检查间隔（秒）。

        Returns:
            是否在超时前端口变为可用。
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if await NetworkUtils.check_port(host, port, timeout=2.0):
                return True
            await asyncio.sleep(interval)
        return False

    # ------------------------------------------------------------------
    # HTTP 请求（轻量级，不依赖外部库）
    # ------------------------------------------------------------------

    @staticmethod
    async def http_get(
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        发送 HTTP GET 请求。

        优先使用 httpx，降级使用 aiohttp，再降级使用 urllib。

        Args:
            url: 请求 URL。
            headers: 请求头。
            timeout: 超时时间（秒）。

        Returns:
            包含 status_code / headers / body 的字典。
        """
        # 尝试 httpx
        try:
            import httpx
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, headers=headers)
                return {
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                    "body": resp.text,
                }
        except ImportError:
            pass

        # 尝试 aiohttp
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    body = await resp.text()
                    return {
                        "status_code": resp.status,
                        "headers": dict(resp.headers),
                        "body": body,
                    }
        except ImportError:
            pass

        # 降级 urllib
        import urllib.request
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {
                "status_code": resp.status,
                "headers": dict(resp.headers),
                "body": resp.read().decode("utf-8"),
            }

    # ------------------------------------------------------------------
    # DNS 解析
    # ------------------------------------------------------------------

    @staticmethod
    def resolve(hostname: str) -> List[str]:
        """
        解析域名获取 IP 地址列表。

        Args:
            hostname: 域名。

        Returns:
            IP 地址列表。
        """
        try:
            results = socket.getaddrinfo(hostname, None)
            ips = list({addr[4][0] for addr in results})
            return ips
        except socket.gaierror as e:
            logger.error(f"DNS 解析失败: {hostname} — {e}")
            return []

    # ------------------------------------------------------------------
    # URL 工具
    # ------------------------------------------------------------------

    @staticmethod
    def parse_url(url: str) -> Dict[str, str]:
        """解析 URL 为各组成部分。"""
        parsed = urlparse(url)
        return {
            "scheme": parsed.scheme,
            "host": parsed.hostname or "",
            "port": str(parsed.port or ""),
            "path": parsed.path,
            "query": parsed.query,
            "fragment": parsed.fragment,
        }
