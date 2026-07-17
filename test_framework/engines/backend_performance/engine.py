"""
后端性能测试引擎 — 引擎主类。

职责：支持 HTTP/gRPC 负载施压，采集 CPU/内存/JVM 等多维度运行指标。
可调度 Node.js 引擎实现高并发（通过 LanguageBridge）。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ...core.models import TestCase, TestMetrics, TestPlan, TestReport, TestResult, TargetSystem
from ...core.models.enums import TestStatus, TestType
from ..base import BaseEngine
from .http_loader import HTTPLoader
from .grpc_loader import GRPCLoader
from .resource_collector import ResourceCollector

logger = logging.getLogger(__name__)


class BackendPerformanceEngine(BaseEngine):
    """
    后端性能测试引擎。

    支持 HTTP 和 gRPC 两种协议的负载施压，
    集成多维度资源监控（JVM/Go/Node/Python/Container）。

    Attributes:
        _loader: 负载发生器（HTTP 或 gRPC）。
        _resource_collector: 资源采集器。
    """

    def __init__(self, config: Dict[str, Any], container: Any) -> None:
        """初始化后端性能引擎。"""
        super().__init__(config, container)
        self._loader: Optional[Any] = None
        self._resource_collector = ResourceCollector(
            config.get("resource_monitoring", {})
        )

    @property
    def engine_type(self) -> TestType:
        """测试类型。"""
        return TestType.BACKEND_PERFORMANCE

    async def setup(self, target: TargetSystem) -> None:
        """
        根据协议类型初始化负载发生器。

        Args:
            target: 被测目标系统。
        """
        protocol = getattr(target, "protocol", "http") or "http"

        if protocol in ("http", "https"):
            self._loader = HTTPLoader(self._config, target)
            logger.info(f"HTTP 负载发生器已初始化: {target.base_url}")
        elif protocol == "grpc":
            grpc_config = self._config.get("grpc", {})
            self._loader = GRPCLoader(grpc_config, target)
            logger.info(f"gRPC 负载发生器已初始化: {target.host}:{target.port}")
        else:
            logger.warning(f"不支持的协议: {protocol}，默认使用 HTTP")
            self._loader = HTTPLoader(self._config, target)

        # 启动资源监控
        await self._resource_collector.start()

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        """
        执行单个后端性能测试用例。

        Args:
            case: 测试用例。
            target: 被测目标系统。

        Returns:
            测试结果。
        """
        try:
            # 执行负载施压
            raw_results = await self._loader.apply_load(case.config)

            # 采集资源指标
            resources = await self._resource_collector.collect()

            # 构建测试结果
            return self._build_result(case, raw_results, resources)

        except Exception as e:
            logger.error(f"后端性能测试异常: {e}")
            return TestResult(
                case_id=case.id,
                status=TestStatus.ERROR,
                duration=0,
                details={"error": str(e)},
                metrics=TestMetrics(),
                timestamp=datetime.now(),
            )

    def _build_result(
        self,
        case: TestCase,
        raw_results: Dict[str, Any],
        resources: Dict[str, float],
    ) -> TestResult:
        """
        构建测试结果。

        Args:
            case: 测试用例。
            raw_results: 负载施压的原始结果。
            resources: 资源监控数据。

        Returns:
            标准化测试结果。
        """
        # 检查是否达到阈值
        thresholds = self._config.get("thresholds", {})
        error_rate = raw_results.get("error_rate", 0)
        p95 = raw_results.get("latency_p95", 0)

        status = TestStatus.PASS
        if error_rate > thresholds.get("error_rate", 0.01):
            status = TestStatus.FAIL
        if p95 > thresholds.get("response_time_p95", 500):
            status = TestStatus.FAIL

        return TestResult(
            case_id=case.id,
            status=status,
            duration=raw_results.get("duration", 0),
            details={
                "load_results": raw_results,
                "resources": resources,
            },
            metrics=TestMetrics(
                throughput=raw_results.get("throughput", 0),
                latency_avg=raw_results.get("latency_avg", 0),
                latency_p95=raw_results.get("latency_p95", 0),
                latency_p99=raw_results.get("latency_p99", 0),
                error_rate=error_rate,
                custom=resources,
            ),
            timestamp=datetime.now(),
        )

    async def collect_metrics(self) -> TestMetrics:
        """汇总所有用例的性能指标。"""
        if not self._results:
            return TestMetrics()

        avg_throughput = sum(r.metrics.throughput for r in self._results) / len(self._results)
        avg_latency = sum(r.metrics.latency_avg for r in self._results) / len(self._results)

        return TestMetrics(
            total_cases=len(self._results),
            passed=sum(1 for r in self._results if r.status == TestStatus.PASS),
            failed=sum(1 for r in self._results if r.status == TestStatus.FAIL),
            throughput=avg_throughput,
            latency_avg=avg_latency,
        )

    async def teardown(self) -> None:
        """清理资源。"""
        await self._resource_collector.stop()
        logger.info("后端性能引擎资源已清理")
