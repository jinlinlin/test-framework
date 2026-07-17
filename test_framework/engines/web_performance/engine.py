"""
网页性能测试引擎 — 引擎主类（模板模式）。

职责：基于 Playwright 实现网页自动化渲染、资源加载监控、
      Web Vitals 采集，集成 Lighthouse 完成综合性能评分。

执行流程：启动浏览器 → 访问页面 → 采集 Web Vitals → 运行 Lighthouse → 生成报告
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...core.models import TestCase, TestMetrics, TestPlan, TestReport, TestResult, TargetSystem
from ...core.models.enums import TestStatus, TestType
from ..base import BaseEngine
from .lighthouse_integration import LighthouseIntegration
from .page_analyzer import PageAnalyzer
from .playwright_client import PlaywrightClient
from .resource_monitor import ResourceMonitor
from .web_vitals import WebVitalsCollector

logger = logging.getLogger(__name__)


class WebPerformanceEngine(BaseEngine):
    """
    网页性能测试引擎（模板模式）。

    继承 BaseEngine，实现网页性能测试的完整流程：
    1. 启动 Playwright 浏览器
    2. 导航到目标 URL
    3. 采集 Web Vitals 指标
    4. 分析页面 DOM 和资源加载
    5. 可选运行 Lighthouse 审计
    6. 生成性能测试报告

    Attributes:
        _playwright: Playwright 客户端。
        _vitals_collector: Web Vitals 采集器。
        _lighthouse: Lighthouse 集成。
        _resource_monitor: 资源监控器。
    """

    def __init__(self, config: Dict[str, Any], container: Any) -> None:
        """
        初始化网页性能引擎。

        Args:
            config: 引擎配置（来自 web.yaml）。
            container: IoC 容器。
        """
        super().__init__(config, container)
        self._playwright: Optional[PlaywrightClient] = None
        self._vitals_collector = WebVitalsCollector(config.get("web_vitals", {}))
        self._lighthouse = LighthouseIntegration(config.get("lighthouse", {}))
        self._resource_monitor = ResourceMonitor(config.get("resource_monitor", {}))

    @property
    def engine_type(self) -> TestType:
        """测试类型。"""
        return TestType.WEB_PERFORMANCE

    async def setup(self, target: TargetSystem) -> None:
        """
        启动浏览器。

        Args:
            target: 被测目标系统。
        """
        browser_type = self._config.get("browser", "chromium")
        headless = self._config.get("headless", True)

        self._playwright = PlaywrightClient(self._config)
        await self._playwright.launch(browser_type=browser_type, headless=headless)
        logger.info(f"浏览器已启动: {browser_type}, headless={headless}")

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        """
        执行单个网页性能测试用例。

        Args:
            case: 测试用例。
            target: 被测目标系统。

        Returns:
            测试结果。
        """
        url = f"{target.base_url}{case.config.get('path', '/')}"
        page = await self._playwright.new_page(
            viewport=self._config.get("viewport")
        )

        try:
            # 1. 开始资源监控
            await self._resource_monitor.start(page)

            # 2. 导航到目标页面
            response = await self._playwright.goto(page, url)

            # 3. 采集 Web Vitals
            vitals = await self._vitals_collector.collect(page)

            # 4. 页面分析
            analyzer = PageAnalyzer(page)
            analysis = await analyzer.analyze()

            # 5. 停止资源监控
            resources = await self._resource_monitor.stop()

            # 6. 可选 Lighthouse 审计
            lighthouse_score = None
            if self._config.get("lighthouse", {}).get("enabled", False):
                lighthouse_score = await self._lighthouse.audit(url)

            # 7. 评估指标是否达标
            threshold_results = self._vitals_collector.evaluate_thresholds(vitals)

            # 8. 判定测试结果
            has_failure = any(v == "FAIL" for v in threshold_results.values())
            status = TestStatus.FAIL if has_failure else TestStatus.PASS

            return TestResult(
                case_id=case.id,
                status=status,
                duration=analysis.get("load_time", 0),
                details={
                    "vitals": vitals,
                    "analysis": analysis,
                    "resources": resources,
                    "lighthouse": lighthouse_score,
                    "threshold_results": threshold_results,
                },
                metrics=TestMetrics(
                    latency_avg=vitals.get("LCP", 0),
                    custom=vitals,
                ),
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"网页性能测试异常: {url} — {e}")
            return TestResult(
                case_id=case.id,
                status=TestStatus.ERROR,
                duration=0,
                details={"error": str(e)},
                metrics=TestMetrics(),
                timestamp=datetime.now(),
            )
        finally:
            await self._playwright.close_page(page)

    async def collect_metrics(self) -> TestMetrics:
        """
        汇总所有用例的性能指标。

        Returns:
            聚合后的测试指标。
        """
        if not self._results:
            return TestMetrics()

        # 计算平均 LCP
        lcp_values = [
            r.metrics.latency_avg for r in self._results
            if r.metrics and r.metrics.latency_avg > 0
        ]
        avg_lcp = sum(lcp_values) / len(lcp_values) if lcp_values else 0

        return TestMetrics(
            total_cases=len(self._results),
            passed=sum(1 for r in self._results if r.status == TestStatus.PASS),
            failed=sum(1 for r in self._results if r.status == TestStatus.FAIL),
            latency_avg=avg_lcp,
        )

    async def teardown(self) -> None:
        """关闭浏览器。"""
        if self._playwright:
            await self._playwright.close()
            logger.info("浏览器已关闭")
