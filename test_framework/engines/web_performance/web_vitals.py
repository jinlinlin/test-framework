"""
Web Vitals 采集器 — 采集 Core Web Vitals 指标。

职责：通过在页面注入 JavaScript 脚本，采集 LCP、FCP、CLS、FID、INP、TTFB 等指标，
      并与配置阈值对比评估性能达标情况。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class WebVitalsCollector:
    """
    Web Vitals 指标采集器。

    通过注入 web-vitals JS 库到页面中采集各项指标，
    支持与配置阈值对比生成 PASS/WARN/FAIL 评估。

    Attributes:
        _metrics: 要采集的指标列表。
        _thresholds: 各指标的阈值配置。
    """

    # 标准 Web Vitals 指标
    METRICS = ["LCP", "FCP", "CLS", "FID", "INP", "TTFB"]

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化 Web Vitals 采集器。

        Args:
            config: web_vitals 配置区块。
        """
        self._metrics: List[str] = config.get("metrics", self.METRICS)
        self._thresholds: Dict[str, float] = config.get("thresholds", {
            "LCP": 2500,   # Largest Contentful Paint (ms)
            "FCP": 1800,   # First Contentful Paint (ms)
            "CLS": 0.1,    # Cumulative Layout Shift
            "FID": 100,    # First Input Delay (ms)
            "INP": 200,    # Interaction to Next Paint (ms)
            "TTFB": 800,   # Time to First Byte (ms)
        })

    async def collect(self, page: Any) -> Dict[str, float]:
        """
        在页面中注入 JS 脚本采集 Web Vitals 指标。

        Args:
            page: Playwright Page 对象。

        Returns:
            指标名称 → 指标值 的字典。
        """
        # 注入采集脚本
        js_code = """
        () => {
            return new Promise((resolve) => {
                const vitals = {};

                // LCP - Largest Contentful Paint
                const lcpObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    vitals.LCP = entries[entries.length - 1].startTime;
                });
                lcpObserver.observe({type: 'largest-contentful-paint', buffered: true});

                // FCP - First Contentful Paint
                const paintObserver = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        if (entry.name === 'first-contentful-paint') {
                            vitals.FCP = entry.startTime;
                        }
                    }
                });
                paintObserver.observe({type: 'paint', buffered: true});

                // CLS - Cumulative Layout Shift
                let clsValue = 0;
                const clsObserver = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        if (!entry.hadRecentInput) {
                            clsValue += entry.value;
                        }
                    }
                    vitals.CLS = clsValue;
                });
                clsObserver.observe({type: 'layout-shift', buffered: true});

                // TTFB - Time to First Byte
                const navEntry = performance.getEntriesByType('navigation')[0];
                if (navEntry) {
                    vitals.TTFB = navEntry.responseStart;
                }

                // 延迟返回确保所有观察者采集完成
                setTimeout(() => resolve(vitals), 1000);
            });
        }
        """
        try:
            vitals = await page.evaluate(js_code)
            logger.debug(f"Web Vitals 采集完成: {vitals}")
            return vitals if isinstance(vitals, dict) else {}
        except Exception as e:
            logger.warning(f"Web Vitals 采集失败: {e}")
            return {}

    def evaluate_thresholds(self, vitals: Dict[str, float]) -> Dict[str, str]:
        """
        对比阈值评估各项指标。

        Args:
            vitals: 采集到的指标值。

        Returns:
            指标名称 → 评估结果（PASS / WARN / FAIL）的字典。
        """
        results: Dict[str, str] = {}

        for metric, value in vitals.items():
            threshold = self._thresholds.get(metric)
            if threshold is None:
                results[metric] = "PASS"
                continue

            if value <= threshold:
                results[metric] = "PASS"
            elif value <= threshold * 1.5:
                results[metric] = "WARN"
            else:
                results[metric] = "FAIL"

        return results
