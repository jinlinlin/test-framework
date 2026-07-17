"""
渗透测试引擎 — 自动化漏洞扫描主引擎。

职责：加载攻击载荷 → 对目标端点逐一扫描 →
      检测漏洞 → 生成安全报告。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from ...core.models import TestCase, TestMetrics, TestResult, TargetSystem
from ...core.models.enums import TestStatus, TestType
from ..base import BaseEngine
from .detector import VulnerabilityDetector, Vulnerability
from .payloads import (
    CommandInjectionPayload,
    PathTraversalPayload,
    Payload,
    SQLInjectionPayload,
    SSRFPayload,
    XSSPayload,
    XXEPayload,
)
from .reporter import SecurityReporter
from .scanner import Scanner

logger = logging.getLogger(__name__)

# 载荷类型 → 载荷类的映射
PAYLOAD_REGISTRY: Dict[str, type] = {
    "sql_injection": SQLInjectionPayload,
    "xss": XSSPayload,
    "path_traversal": PathTraversalPayload,
    "command_injection": CommandInjectionPayload,
    "ssrf": SSRFPayload,
    "xxe": XXEPayload,
}


class PenetrationEngine(BaseEngine):
    """
    渗透测试引擎。

    执行流程：加载攻击载荷 → 对目标各端点逐一扫描 →
    检测漏洞 → 生成安全报告。

    Attributes:
        _scanner: 渗透扫描器。
        _detector: 漏洞检测器。
        _reporter: 安全报告器。
        _payloads: 已加载的载荷实例字典。
    """

    @property
    def engine_type(self) -> TestType:
        """引擎类型。"""
        return TestType.PENETRATION

    async def setup(self, target: TargetSystem) -> None:
        """
        初始化渗透测试引擎。

        Args:
            target: 目标系统对象。
        """
        self._scanner = Scanner(target, self._config)
        await self._scanner.initialize()
        self._detector = VulnerabilityDetector(self._config)
        self._reporter = SecurityReporter()
        self._payloads = self._load_payloads()
        logger.info(f"渗透测试引擎已初始化: {len(self._payloads)} 种载荷")

    def _load_payloads(self) -> Dict[str, Payload]:
        """
        加载所有已注册的攻击载荷。

        Returns:
            载荷名称 → 载荷实例的映射。
        """
        payloads: Dict[str, Payload] = {}
        enabled_types = self._config.get(
            "payload_types",
            list(PAYLOAD_REGISTRY.keys()),
        )
        for ptype in enabled_types:
            cls = PAYLOAD_REGISTRY.get(ptype)
            if cls:
                payloads[ptype] = cls()
            else:
                logger.warning(f"未知的载荷类型: {ptype}")
        return payloads

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        """
        执行单个渗透测试用例。

        用例配置格式::

            {
                "endpoint": "/api/login",
                "payload_types": ["sql_injection", "xss"],
                "method": "GET"
            }

        Args:
            case: 测试用例。
            target: 目标系统。

        Returns:
            测试结果。
        """
        try:
            endpoint = case.config.get("endpoint", "/")
            payload_types = case.config.get("payload_types", list(self._payloads.keys()))
            method = case.config.get("method", "GET")

            all_findings: List[Vulnerability] = []

            for ptype in payload_types:
                payload_obj = self._payloads.get(ptype)
                if not payload_obj:
                    logger.warning(f"载荷类型 '{ptype}' 未加载")
                    continue

                # 扫描
                scan_results = await self._scanner.scan(endpoint, payload_obj, method)

                # 检测
                vulns = self._detector.detect(scan_results, payload_obj)
                all_findings.extend(vulns)

            # 判断状态
            has_critical = any(
                f.severity in ("high", "critical") for f in all_findings
            )
            status = TestStatus.FAIL if has_critical else TestStatus.PASS

            # 生成报告
            report = self._reporter.generate(all_findings)

            return TestResult(
                case_id=case.id,
                status=status,
                duration=0,
                details={
                    "findings_count": len(all_findings),
                    "report": report,
                    "endpoint": endpoint,
                    "payload_types_tested": payload_types,
                },
                metrics=TestMetrics(
                    custom={"vulnerabilities_found": len(all_findings)},
                ),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"渗透测试异常: {e}")
            return TestResult(
                case_id=case.id,
                status=TestStatus.ERROR,
                duration=0,
                details={"error": str(e)},
                metrics=TestMetrics(),
                timestamp=datetime.now(),
            )

    async def collect_metrics(self) -> TestMetrics:
        """汇总渗透测试指标。"""
        if not self._results:
            return TestMetrics()
        total_vulns = sum(
            r.details.get("findings_count", 0) for r in self._results
        )
        return TestMetrics(
            total_cases=len(self._results),
            passed=sum(1 for r in self._results if r.status == TestStatus.PASS),
            failed=sum(1 for r in self._results if r.status == TestStatus.FAIL),
            custom={"total_vulnerabilities": total_vulns},
        )

    async def teardown(self) -> None:
        """关闭扫描器。"""
        if hasattr(self, "_scanner"):
            await self._scanner.close()
            logger.info("渗透测试引擎已关闭")
