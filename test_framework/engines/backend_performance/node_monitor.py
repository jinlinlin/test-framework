"""
Node.js 监控器 — 通过 metrics 端点采集 Node 运行时指标。

职责：采集事件循环延迟、堆内存使用、活跃句柄数等 Node.js 运行时指标。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class NodeMonitor:
    """
    Node.js 运行时监控器。

    通过 Node.js 暴露的 Prometheus metrics 端点或
    自定义 JSON 接口采集运行时指标。
    """

    async def collect(self, metrics_url: str) -> Dict[str, Any]:
        """
        采集 Node.js 运行时指标。

        Args:
            metrics_url: metrics HTTP 端点 URL。

        Returns:
            Node.js 运行时指标字典。
        """
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(metrics_url, timeout=10)
                data = response.json()

                return {
                    "event_loop_lag_ms": data.get("eventLoopLag", 0),
                    "heap_used_mb": data.get("heapUsed", 0) / (1024 * 1024),
                    "heap_total_mb": data.get("heapTotal", 0) / (1024 * 1024),
                    "rss_mb": data.get("rss", 0) / (1024 * 1024),
                    "active_handles": data.get("activeHandles", 0),
                    "active_requests": data.get("activeRequests", 0),
                    "uptime_seconds": data.get("uptime", 0),
                }
        except Exception as e:
            logger.warning(f"Node.js 指标采集失败: {e}")
            return {"error": str(e)}
