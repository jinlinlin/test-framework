"""
资源监控器 — 监控页面加载过程中的网络请求和资源使用。

职责：拦截页面网络请求，统计资源类型、大小、请求数量，
      为性能分析提供网络维度的数据支撑。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """
    页面资源监控器。

    在页面加载过程中拦截网络请求，
    按资源类型（JS/CSS/图片/字体/API）分类统计。

    Attributes:
        _config: 资源监控配置。
        _requests: 收集的请求列表。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化资源监控器。

        Args:
            config: resource_monitor 配置区块。
        """
        self._config = config
        self._requests: List[Dict[str, Any]] = []
        self._tracking = False

    async def start(self, page: Any) -> None:
        """
        开始监控页面网络请求。

        通过 Playwright 的 route/response 事件拦截请求。

        Args:
            page: Playwright Page 对象。
        """
        self._requests = []
        self._tracking = True

        # 监听响应事件
        page.on("response", self._on_response)
        logger.debug("资源监控已启动")

    def _on_response(self, response: Any) -> None:
        """
        响应事件回调 — 记录每个请求的资源信息。

        Args:
            response: Playwright Response 对象。
        """
        if not self._tracking:
            return

        try:
            url = response.url
            status = response.status
            resource_type = response.request.resource_type
            headers = response.headers

            self._requests.append({
                "url": url,
                "status": status,
                "type": resource_type,
                "content_type": headers.get("content-type", ""),
                "size": int(headers.get("content-length", 0)),
            })
        except Exception:
            pass  # 忽略无法解析的响应

    async def stop(self) -> Dict[str, Any]:
        """
        停止监控并返回统计摘要。

        Returns:
            资源统计摘要字典。
        """
        self._tracking = False
        return self.get_summary()

    def get_summary(self) -> Dict[str, Any]:
        """
        获取资源统计摘要。

        Returns:
            包含总请求数、各类型资源统计的字典。
        """
        # 按类型分组统计
        type_stats: Dict[str, Dict[str, Any]] = {}
        total_size = 0

        for req in self._requests:
            rtype = req.get("type", "other")
            if rtype not in type_stats:
                type_stats[rtype] = {"count": 0, "size": 0}
            type_stats[rtype]["count"] += 1
            type_stats[rtype]["size"] += req.get("size", 0)
            total_size += req.get("size", 0)

        # 统计失败请求数
        failed = sum(1 for r in self._requests if r.get("status", 200) >= 400)

        return {
            "total_requests": len(self._requests),
            "total_size_bytes": total_size,
            "total_size_kb": round(total_size / 1024, 2),
            "failed_requests": failed,
            "by_type": type_stats,
        }
