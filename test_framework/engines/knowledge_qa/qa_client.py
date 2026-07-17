"""
问答 API 客户端 — 封装知识库问答接口调用。

职责：向知识库问答服务发送问题，获取回答、来源文档、
      上下文及响应延迟。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class QAResponse:
    """
    问答接口响应数据。

    Attributes:
        answer: 回答文本。
        sources: 来源文档 ID / 路径列表。
        context: 上下文片段列表。
        latency: 响应延迟（秒）。
        raw_response: 原始响应体。
        metadata: 额外元数据。
    """

    answer: str = ""
    sources: List[str] = field(default_factory=list)
    context: List[str] = field(default_factory=list)
    latency: float = 0.0
    raw_response: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class QAClient:
    """
    问答 API 客户端。

    封装 HTTP 调用，向知识库问答服务发送问题并解析响应。
    支持 REST API 和 gRPC 两种协议。

    Attributes:
        _base_url: 问答服务基础 URL。
        _auth: 认证信息。
        _timeout: 请求超时（秒）。
        _client: httpx 异步客户端。
    """

    def __init__(
        self,
        base_url: str,
        auth: Optional[Dict[str, Any]] = None,
        timeout: int = 60,
    ) -> None:
        """
        初始化问答客户端。

        Args:
            base_url: 问答服务基础 URL。
            auth: 认证配置字典（token / api_key）。
            timeout: 请求超时秒数。
        """
        self._base_url = base_url.rstrip("/")
        self._auth = auth or {}
        self._timeout = timeout
        self._client: Optional[Any] = None
        self._headers: Dict[str, str] = {}

        # 构建认证头
        token = self._auth.get("token", "")
        api_key = self._auth.get("api_key", "")
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        if api_key:
            self._headers["X-API-Key"] = api_key

    async def initialize(self) -> None:
        """初始化 HTTP 客户端。"""
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._headers,
            )
            logger.info(f"QA 客户端已初始化: {self._base_url}")
        except ImportError:
            logger.error("httpx 未安装")
            raise

    async def ask(self, question: str, **kwargs: Any) -> QAResponse:
        """
        向问答服务发送问题。

        Args:
            question: 问题文本。
            **kwargs: 额外参数（如 top_k、temperature、filters）。

        Returns:
            问答响应数据。
        """
        if not self._client:
            await self.initialize()

        payload = {
            "question": question,
            "top_k": kwargs.get("top_k", 5),
            "temperature": kwargs.get("temperature", 0.7),
            "filters": kwargs.get("filters", {}),
        }

        # 支持自定义端点
        endpoint = kwargs.get("endpoint", "/api/qa/ask")

        start = time.monotonic()
        try:
            response = await self._client.post(endpoint, json=payload)
            latency = time.monotonic() - start

            data = response.json()

            return QAResponse(
                answer=data.get("answer", data.get("text", "")),
                sources=data.get("sources", data.get("references", [])),
                context=data.get("context", data.get("context_docs", [])),
                latency=latency,
                raw_response=data,
                metadata={
                    "status_code": response.status_code,
                    "model": data.get("model", ""),
                    "tokens_used": data.get("tokens_used", 0),
                },
            )
        except Exception as e:
            latency = time.monotonic() - start
            logger.error(f"问答接口调用失败: {e}")
            return QAResponse(
                answer="",
                latency=latency,
                metadata={"error": str(e)},
            )

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._client:
            await self._client.aclose()
            logger.info("QA 客户端已关闭")
