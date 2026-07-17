"""
Go 监控器 — 通过 pprof HTTP 端点采集 Go 运行时指标。

职责：采集 goroutine 数量、堆内存使用、CPU profile 等 Go 运行时指标。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class GoMonitor:
    """
    Go 运行时监控器。

    通过 Go 标准库 net/http/pprof 暴露的 HTTP 端点采集指标。
    """

    async def collect(self, pprof_url: str) -> Dict[str, Any]:
        """
        采集 Go 运行时指标。

        Args:
            pprof_url: pprof HTTP 端点 URL（如 http://localhost:6060/debug/pprof）。

        Returns:
            Go 运行时指标字典。
        """
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                # 采集 goroutine 信息
                goroutine_resp = await client.get(
                    f"{pprof_url}/goroutine?debug=1", timeout=10
                )

                # 采集堆内存信息
                heap_resp = await client.get(
                    f"{pprof_url}/heap?debug=1", timeout=10
                )

                # 采集统计信息
                stats_resp = await client.get(
                    f"{pprof_url}/allocs?debug=1", timeout=10
                )

                return {
                    "goroutines": self._parse_goroutine_count(goroutine_resp.text),
                    "heap_alloc_bytes": self._parse_heap_value(heap_resp.text, "Alloc"),
                    "heap_sys_bytes": self._parse_heap_value(heap_resp.text, "Sys"),
                    "heap_objects": self._parse_heap_value(heap_resp.text, "HeapObjects"),
                }
        except Exception as e:
            logger.warning(f"Go 指标采集失败: {e}")
            return {"error": str(e)}

    @staticmethod
    def _parse_goroutine_count(text: str) -> int:
        """从 pprof 输出中解析 goroutine 数量。"""
        try:
            for line in text.split("\n"):
                if line.strip().startswith("goroutine profile: total"):
                    return int(line.split()[-1])
        except (ValueError, IndexError):
            pass
        return 0

    @staticmethod
    def _parse_heap_value(text: str, key: str) -> int:
        """从 pprof 堆信息中解析指定指标值。"""
        try:
            for line in text.split("\n"):
                if key in line and "=" in line:
                    parts = line.split("=")
                    return int(parts[-1].strip().split()[0])
        except (ValueError, IndexError):
            pass
        return 0
