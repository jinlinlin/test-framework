"""
渗透测试扫描器 — 对目标端点发送攻击载荷。

职责：向目标端点发送带有攻击载荷的请求，
      收集响应数据供漏洞检测器分析。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """
    扫描结果数据对象。

    Attributes:
        endpoint: 目标端点。
        payload: 使用的攻击载荷。
        status_code: HTTP 响应状态码。
        response_body: 响应体文本。
        response_headers: 响应头字典。
        elapsed: 响应耗时（秒）。
        error: 请求错误信息。
    """

    endpoint: str = ""
    payload: str = ""
    status_code: int = 0
    response_body: str = ""
    response_headers: Dict[str, str] = field(default_factory=dict)
    elapsed: float = 0.0
    error: str = ""


class Scanner:
    """
    渗透测试扫描器。

    使用 httpx 向目标端点发送攻击载荷请求，
    支持 GET / POST 两种注入方式。

    Attributes:
        _base_url: 目标系统基础 URL。
        _config: 扫描配置。
        _client: httpx 客户端。
    """

    def __init__(self, target: Any, config: Dict[str, Any]) -> None:
        """
        初始化扫描器。

        Args:
            target: 目标系统对象。
            config: 扫描配置。
        """
        self._base_url = getattr(target, "base_url", "")
        self._config = config
        self._timeout = config.get("timeout", 30)
        self._client: Optional[Any] = None

    async def initialize(self) -> None:
        """初始化 HTTP 客户端。"""
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                verify=False,  # 渗透测试不验证 SSL
                follow_redirects=True,
            )
        except ImportError:
            raise ImportError("httpx 未安装")

    async def scan(self, endpoint: str, payload_obj: Any, method: str = "GET") -> List[ScanResult]:
        """
        对端点使用指定载荷类型进行扫描。

        生成载荷列表后逐个发送请求。

        Args:
            endpoint: 目标端点路径。
            payload_obj: Payload 实例。
            method: HTTP 方法。

        Returns:
            扫描结果列表。
        """
        if not self._client:
            await self.initialize()

        payloads = payload_obj.generate()
        results: List[ScanResult] = []

        for p in payloads:
            result = await self._send_payload(endpoint, p, method)
            results.append(result)

        return results

    async def scan_all_params(self, endpoint: str, payload_obj: Any) -> List[ScanResult]:
        """
        对端点的所有参数位置注入载荷（GET 参数 + POST Body + Header）。

        Args:
            endpoint: 目标端点。
            payload_obj: Payload 实例。

        Returns:
            所有参数位置的扫描结果。
        """
        results: List[ScanResult] = []

        # GET 参数注入
        get_results = await self.scan(endpoint, payload_obj, method="GET")
        results.extend(get_results)

        # POST Body 注入
        post_results = await self.scan(endpoint, payload_obj, method="POST")
        results.extend(post_results)

        return results

    async def _send_payload(self, endpoint: str, payload: str, method: str) -> ScanResult:
        """
        发送单个载荷请求。

        Args:
            endpoint: 端点路径。
            payload: 攻击载荷字符串。
            method: HTTP 方法。

        Returns:
            扫描结果。
        """
        start = time.monotonic()
        try:
            if method == "GET":
                # 载荷作为查询参数
                response = await self._client.get(endpoint, params={"input": payload})
            elif method == "POST":
                # 载荷作为 JSON Body
                response = await self._client.post(endpoint, json={"input": payload, "data": payload})
            else:
                response = await self._client.request(method, endpoint, params={"q": payload})

            elapsed = time.monotonic() - start

            return ScanResult(
                endpoint=endpoint,
                payload=payload,
                status_code=response.status_code,
                response_body=response.text[:5000],
                response_headers=dict(response.headers),
                elapsed=elapsed,
            )
        except Exception as e:
            elapsed = time.monotonic() - start
            return ScanResult(
                endpoint=endpoint,
                payload=payload,
                elapsed=elapsed,
                error=str(e),
            )

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._client:
            await self._client.aclose()
