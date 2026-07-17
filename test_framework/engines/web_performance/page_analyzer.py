"""
页面分析器 — 分析页面 DOM 结构、加载时间和关键渲染路径。

职责：在页面加载完成后，分析 DOM 节点数量、关键资源、
      加载瀑布图等页面质量指标。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PageAnalyzer:
    """
    页面分析器。

    通过分析页面 DOM 和性能时间线，
    提供页面质量评估数据。

    Attributes:
        _page: Playwright Page 对象。
    """

    def __init__(self, page: Any) -> None:
        """
        初始化页面分析器。

        Args:
            page: Playwright Page 对象。
        """
        self._page = page

    async def analyze(self) -> Dict[str, Any]:
        """
        执行页面分析。

        Returns:
            分析结果字典，包含 DOM 节点数、加载时间、关键指标等。
        """
        try:
            # DOM 分析
            dom_info = await self._analyze_dom()

            # 性能时间线分析
            timing_info = await self._analyze_timing()

            # 合并结果
            return {
                **dom_info,
                **timing_info,
            }
        except Exception as e:
            logger.warning(f"页面分析失败: {e}")
            return {"error": str(e)}

    async def _analyze_dom(self) -> Dict[str, Any]:
        """
        分析页面 DOM 结构。

        Returns:
            DOM 相关信息字典。
        """
        js_code = """
        () => {
            const allElements = document.querySelectorAll('*');
            const images = document.querySelectorAll('img');
            const scripts = document.querySelectorAll('script');
            const stylesheets = document.querySelectorAll('link[rel="stylesheet"]');
            const iframes = document.querySelectorAll('iframe');

            // 计算 DOM 深度
            let maxDepth = 0;
            function getDepth(el, depth) {
                if (depth > maxDepth) maxDepth = depth;
                Array.from(el.children).forEach(child => getDepth(child, depth + 1));
            }
            if (document.body) getDepth(document.body, 0);

            return {
                dom_nodes: allElements.length,
                dom_depth: maxDepth,
                images: images.length,
                scripts: scripts.length,
                stylesheets: stylesheets.length,
                iframes: iframes.length,
                lazy_images: document.querySelectorAll('img[loading="lazy"]').length,
            };
        }
        """
        return await self._page.evaluate(js_code)

    async def _analyze_timing(self) -> Dict[str, Any]:
        """
        分析页面性能时间线。

        Returns:
            性能时间线数据字典。
        """
        js_code = """
        () => {
            const nav = performance.getEntriesByType('navigation')[0];
            if (!nav) return {};

            return {
                load_time: nav.loadEventEnd - nav.startTime,
                dom_content_loaded: nav.domContentLoadedEventEnd - nav.startTime,
                dom_interactive: nav.domInteractive - nav.startTime,
                dns_lookup: nav.domainLookupEnd - nav.domainLookupStart,
                tcp_connect: nav.connectEnd - nav.connectStart,
                tls_handshake: nav.connectEnd - nav.secureConnectionStart,
                server_response: nav.responseStart - nav.requestStart,
                content_download: nav.responseEnd - nav.responseStart,
                transfer_size: nav.transferSize,
            };
        }
        """
        return await self._page.evaluate(js_code)
