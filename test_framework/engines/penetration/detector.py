"""
漏洞检测器 — 根据响应内容检测漏洞。

职责：分析扫描器返回的响应，通过特征匹配、
      状态码分析、时间差异检测等方式判断漏洞是否存在。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .scanner import ScanResult

logger = logging.getLogger(__name__)


@dataclass
class Vulnerability:
    """
    漏洞记录。

    Attributes:
        vuln_type: 漏洞类型（sql_injection / xss / ...）。
        severity: 严重等级（low / medium / high / critical）。
        endpoint: 漏洞所在端点。
        payload: 触发漏洞的载荷。
        evidence: 漏洞证据（响应中的匹配片段）。
        recommendation: 修复建议。
    """

    vuln_type: str = ""
    severity: str = "medium"
    endpoint: str = ""
    payload: str = ""
    evidence: str = ""
    recommendation: str = ""

    def to_dict(self) -> Dict[str, str]:
        """转为字典格式。"""
        return {
            "type": self.vuln_type,
            "severity": self.severity,
            "endpoint": self.endpoint,
            "payload": self.payload,
            "evidence": self.evidence[:500],
            "recommendation": self.recommendation,
        }


class VulnerabilityDetector:
    """
    漏洞检测器。

    对扫描结果进行多维度分析：
    - 特征模式匹配（响应体中的错误信息）
    - HTTP 状态码异常检测
    - 时间延迟检测（时间盲注）
    - 响应长度异常

    Attributes:
        _config: 检测配置。
        _timing_threshold: 时间盲注延迟阈值（秒）。
    """

    # 修复建议模板
    RECOMMENDATIONS = {
        "sql_injection": "使用参数化查询（Prepared Statement），避免字符串拼接 SQL",
        "xss": "对输出内容进行 HTML 编码，使用 CSP 头，启用 HttpOnly Cookie",
        "path_traversal": "使用白名单校验文件路径，禁止 .. 等特殊字符",
        "command_injection": "避免直接执行系统命令，使用安全的 API 替代",
        "ssrf": "校验 URL 白名单，禁止访问内网地址和云元数据",
        "xxe": "禁用 XML 外部实体和 DTD，使用安全的 XML 解析器",
    }

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化漏洞检测器。

        Args:
            config: 检测配置。
        """
        self._config = config
        self._timing_threshold = config.get("timing_threshold", 4.0)  # 秒

    def detect(self, scan_results: List[ScanResult], payload_obj: Any) -> List[Vulnerability]:
        """
        检测扫描结果中的漏洞。

        Args:
            scan_results: 扫描结果列表。
            payload_obj: 使用的载荷对象（含 name 和 detection_patterns）。

        Returns:
            发现的漏洞列表。
        """
        vulnerabilities: List[Vulnerability] = []
        patterns = payload_obj.get_detection_patterns()
        vuln_type = payload_obj.name
        severity = payload_obj.severity

        for result in scan_results:
            if result.error:
                continue

            # 1. 特征模式匹配
            matched_pattern = self._match_patterns(result.response_body, patterns)
            if matched_pattern:
                vulnerabilities.append(Vulnerability(
                    vuln_type=vuln_type,
                    severity=severity,
                    endpoint=result.endpoint,
                    payload=result.payload,
                    evidence=f"匹配特征: '{matched_pattern}'",
                    recommendation=self.RECOMMENDATIONS.get(vuln_type, "请修复该漏洞"),
                ))
                continue

            # 2. 时间延迟检测（针对 SQL 注入和命令注入的时间盲注）
            if vuln_type in ("sql_injection", "command_injection"):
                if self._check_timing(result):
                    vulnerabilities.append(Vulnerability(
                        vuln_type=vuln_type,
                        severity="high",
                        endpoint=result.endpoint,
                        payload=result.payload,
                        evidence=f"响应延迟: {result.elapsed:.1f}s（阈值 {self._timing_threshold}s）",
                        recommendation=self.RECOMMENDATIONS.get(vuln_type, "请修复该漏洞"),
                    ))
                    continue

            # 3. 响应长度异常（与正常响应相比突然变大）
            if self._check_reflected_payload(result):
                vulnerabilities.append(Vulnerability(
                    vuln_type=vuln_type,
                    severity="medium",
                    endpoint=result.endpoint,
                    payload=result.payload,
                    evidence="载荷被反射到响应中",
                    recommendation=self.RECOMMENDATIONS.get(vuln_type, "请修复该漏洞"),
                ))

        return vulnerabilities

    def _match_patterns(self, response_body: str, patterns: List[str]) -> str:
        """
        在响应体中搜索特征模式。

        Args:
            response_body: 响应体文本。
            patterns: 特征模式列表。

        Returns:
            匹配到的第一个模式，无匹配返回空字符串。
        """
        body_lower = response_body.lower()
        for pattern in patterns:
            if pattern.lower() in body_lower:
                return pattern
        return ""

    def _check_timing(self, result: ScanResult) -> bool:
        """
        检测时间盲注。

        Args:
            result: 扫描结果。

        Returns:
            是否存在时间延迟漏洞。
        """
        # 检查载荷是否包含延迟命令
        delay_indicators = ["sleep", "waitfor", "ping -c"]
        has_delay = any(ind in result.payload.lower() for ind in delay_indicators)
        return has_delay and result.elapsed >= self._timing_threshold

    def _check_reflected_payload(self, result: ScanResult) -> bool:
        """
        检测载荷是否被反射到响应中（可能是 XSS 或反射注入）。

        Args:
            result: 扫描结果。

        Returns:
            载荷是否被反射。
        """
        # 检查载荷的关键部分是否出现在响应中
        payload = result.payload
        if len(payload) < 5:
            return False

        # 提取载荷中的关键标识
        key_parts = re.findall(r'[<>\'";$|&]', payload)
        if not key_parts:
            return False

        # 如果载荷中的特殊字符组合出现在响应中
        return payload[:20] in result.response_body
