"""
安全测试报告器 — 生成安全测试专项报告。

职责：汇总漏洞发现，按严重等级分类，
      生成包含漏洞分级和修复建议的结构化报告。
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from .detector import Vulnerability

logger = logging.getLogger(__name__)


class SecurityReporter:
    """
    安全测试报告器。

    将漏洞发现汇总为结构化报告，包含：
    - 漏洞统计摘要
    - 漏洞分级列表
    - 修复建议
    - 风险评级
    """

    # 严重等级排序
    SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def generate(self, findings: List[Vulnerability]) -> Dict[str, Any]:
        """
        生成安全测试报告。

        Args:
            findings: 漏洞列表。

        Returns:
            结构化报告字典。
        """
        if not findings:
            return {
                "summary": {
                    "total_vulnerabilities": 0,
                    "risk_level": "low",
                    "scan_time": datetime.now().isoformat(),
                },
                "vulnerabilities": [],
                "recommendations": [],
            }

        # 统计各等级数量
        severity_counts = Counter(f.severity for f in findings)
        type_counts = Counter(f.vuln_type for f in findings)

        # 风险评级
        risk_level = self._evaluate_risk(severity_counts)

        # 按严重程度排序
        sorted_findings = sorted(
            findings,
            key=lambda f: self.SEVERITY_ORDER.get(f.severity, 99),
        )

        # 去重修复建议
        unique_recommendations = {}
        for f in findings:
            key = f.vuln_type
            if key not in unique_recommendations:
                unique_recommendations[key] = {
                    "vulnerability_type": f.vuln_type,
                    "severity": f.severity,
                    "count": 0,
                    "recommendation": f.recommendation,
                }
            unique_recommendations[key]["count"] += 1

        return {
            "summary": {
                "total_vulnerabilities": len(findings),
                "risk_level": risk_level,
                "severity_distribution": dict(severity_counts),
                "type_distribution": dict(type_counts),
                "scan_time": datetime.now().isoformat(),
            },
            "vulnerabilities": [f.to_dict() for f in sorted_findings],
            "recommendations": list(unique_recommendations.values()),
        }

    def _evaluate_risk(self, severity_counts: Dict[str, int]) -> str:
        """
        根据漏洞分布评估整体风险等级。

        Args:
            severity_counts: 各严重等级的漏洞数量。

        Returns:
            风险等级字符串（critical / high / medium / low）。
        """
        if severity_counts.get("critical", 0) > 0:
            return "critical"
        if severity_counts.get("high", 0) > 0:
            return "high"
        if severity_counts.get("medium", 0) > 2:
            return "high"
        if severity_counts.get("medium", 0) > 0:
            return "medium"
        return "low"
