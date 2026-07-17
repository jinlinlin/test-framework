"""
分布式追踪 — OpenTelemetry 集成。

职责：提供 Span 创建、上下文注入/提取、追踪导出等接口。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DistributedTracing:
    """
    分布式追踪集成（OpenTelemetry）。

    使用示例::

        tracing = DistributedTracing(service_name="test-framework")
        span = tracing.start_span("http_request")
        headers = tracing.inject_context({})
        # ... 发起请求 ...
        tracing.end_span(span)
    """

    def __init__(
        self,
        service_name: str = "test-framework",
        exporter_endpoint: Optional[str] = None,
    ) -> None:
        """
        初始化分布式追踪。

        Args:
            service_name: 服务名称。
            exporter_endpoint: OTLP 导出器端点（如 http://localhost:4317）。
        """
        self._service_name = service_name
        self._exporter_endpoint = exporter_endpoint
        self._tracer = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """确保 OpenTelemetry SDK 已初始化。"""
        if self._initialized:
            return

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.resources import Resource

            resource = Resource.create({"service.name": self._service_name})
            provider = TracerProvider(resource=resource)

            # 如果指定了导出端点，配置 OTLP 导出器
            if self._exporter_endpoint:
                try:
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                    from opentelemetry.sdk.trace.export import BatchSpanProcessor
                    exporter = OTLPSpanExporter(endpoint=self._exporter_endpoint)
                    provider.add_span_processor(BatchSpanProcessor(exporter))
                except ImportError:
                    logger.debug("OTLP 导出器未安装，使用控制台导出")

            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(self._service_name)
            self._initialized = True
            logger.debug(f"OpenTelemetry 已初始化: {self._service_name}")

        except ImportError:
            logger.debug("OpenTelemetry SDK 未安装，追踪功能降级")
            self._initialized = True  # 标记为已初始化（降级模式）

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Any:
        """
        开始一个新的 Span。

        Args:
            name: Span 名称。
            attributes: Span 属性字典。

        Returns:
            Span 对象，或 None（降级模式）。
        """
        self._ensure_initialized()
        if self._tracer:
            span = self._tracer.start_span(name)
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
            return span
        return None

    def end_span(self, span: Any) -> None:
        """
        结束 Span。

        Args:
            span: start_span 返回的 Span 对象。
        """
        if span and hasattr(span, "end"):
            span.end()

    def inject_context(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        将追踪上下文注入到 HTTP 请求头。

        Args:
            headers: 原始请求头字典。

        Returns:
            注入追踪信息后的请求头。
        """
        self._ensure_initialized()
        try:
            from opentelemetry.context import get_current
            from opentelemetry.trace.propagation import get_current_span
            from opentelemetry.propagate import inject

            inject(headers)
        except (ImportError, Exception) as e:
            logger.debug(f"注入追踪上下文失败: {e}")

        return headers

    def extract_context(self, headers: Dict[str, str]) -> Any:
        """
        从 HTTP 请求头提取追踪上下文。

        Args:
            headers: 请求头字典。

        Returns:
            追踪上下文对象。
        """
        self._ensure_initialized()
        try:
            from opentelemetry.propagate import extract
            return extract(headers)
        except (ImportError, Exception) as e:
            logger.debug(f"提取追踪上下文失败: {e}")
        return None
