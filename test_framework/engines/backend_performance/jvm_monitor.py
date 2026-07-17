"""
JVM 监控器 — 通过 JMX / Jolokia 采集 JVM 指标。

职责：采集堆内存使用、GC 次数和耗时、线程数等 JVM 运行时指标。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class JVMMonitor:
    """
    JVM 监控器。

    通过 Jolokia HTTP 接口或 JMX 连接采集 JVM 指标。

    Attributes:
        _jolokia_url: Jolokia HTTP 端点 URL。
    """

    def __init__(self) -> None:
        """初始化 JVM 监控器。"""
        self._jolokia_url: Optional[str] = None

    async def connect(self, host: str, port: int) -> None:
        """
        连接到 Jolokia 端点。

        Args:
            host: Jolokia 主机地址。
            port: Jolokia 端口。
        """
        self._jolokia_url = f"http://{host}:{port}/jolokia"
        logger.info(f"JVM 监控器已连接: {self._jolokia_url}")

    async def collect(self) -> Dict[str, Any]:
        """
        采集 JVM 指标。

        Returns:
            JVM 指标字典（heap_used, gc_count, thread_count 等）。
        """
        if not self._jolokia_url:
            return {"error": "JVM 监控器未连接"}

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                # 读取堆内存
                heap_resp = await client.get(
                    f"{self._jolokia_url}/read/java.lang:type=Memory/HeapMemoryUsage"
                )
                heap_data = heap_resp.json().get("value", {})

                # 读取 GC 信息
                gc_resp = await client.get(
                    f"{self._jolokia_url}/read/java.lang:type=GarbageCollector"
                )

                # 读取线程数
                thread_resp = await client.get(
                    f"{self._jolokia_url}/read/java.lang:type=Threading/ThreadCount"
                )

                return {
                    "heap_used": heap_data.get("used", 0),
                    "heap_max": heap_data.get("max", 0),
                    "thread_count": thread_resp.json().get("value", 0),
                }
        except Exception as e:
            logger.warning(f"JVM 指标采集失败: {e}")
            return {"error": str(e)}

    async def disconnect(self) -> None:
        """断开 Jolokia 连接。"""
        self._jolokia_url = None
        logger.debug("JVM 监控器已断开")
