"""
百分位验证策略 — 验证 P50/P90/P95/P99 是否达标。

场景：关注长尾延迟，确保大部分用户体验良好。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..base import BaseStrategy
from .threshold import ValidationResult, ValidationViolation


class PercentileValidationStrategy(BaseStrategy):
    """
    百分位验证策略。

    验证响应时间的各百分位指标是否在可接受范围内。

    配置示例::

        percentiles = {
            "p50": {"max": 200},     # 50% 请求 < 200ms
            "p90": {"max": 500},     # 90% 请求 < 500ms
            "p95": {"max": 1000},    # 95% 请求 < 1000ms
            "p99": {"max": 3000},    # 99% 请求 < 3000ms
        }
    """

    def __init__(
        self,
        percentiles: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> None:
        """
        Args:
            percentiles: 百分位阈值配置。
                键为百分位名称（p50/p90/p95/p99），值为阈值字典。
        """
        self._percentiles = percentiles or {
            "p50": {"max": 200},
            "p90": {"max": 500},
            "p95": {"max": 1000},
            "p99": {"max": 3000},
        }

    @property
    def strategy_type(self) -> str:
        return "validation"

    @property
    def name(self) -> str:
        return "percentile"

    def get_config(self) -> Dict[str, Any]:
        return {"percentiles": self._percentiles}

    def validate(self, response_times: List[float]) -> ValidationResult:
        """
        验证响应时间的百分位分布。

        Args:
            response_times: 响应时间列表（毫秒）。

        Returns:
            验证结果。
        """
        if not response_times:
            return ValidationResult(
                passed=False,
                summary="无响应时间数据",
            )

        sorted_times = sorted(response_times)
        n = len(sorted_times)
        violations: List[ValidationViolation] = []

        for percentile_name, limits in self._percentiles.items():
            # 解析百分位数值
            p_value = self._parse_percentile(percentile_name)
            if p_value is None:
                continue

            # 计算百分位值
            idx = int(p_value / 100.0 * (n - 1))
            actual = sorted_times[min(idx, n - 1)]

            # 检查最大值
            if "max" in limits and actual > limits["max"]:
                violations.append(ValidationViolation(
                    metric_name=percentile_name,
                    threshold=limits["max"],
                    actual_value=actual,
                    operator="<=",
                    message=f"{percentile_name} = {actual:.2f}ms 超过最大值 {limits['max']}ms",
                ))

        passed = len(violations) == 0
        summary = (
            f"百分位验证通过: {len(self._percentiles)} 项指标全部达标"
            if passed
            else f"百分位验证失败: {len(violations)}/{len(self._percentiles)} 项不达标"
        )

        return ValidationResult(
            passed=passed,
            violations=violations,
            summary=summary,
            metrics_checked=len(self._percentiles),
        )

    @staticmethod
    def _parse_percentile(name: str) -> Optional[float]:
        """解析百分位名称（p50 → 50, p95 → 95）。"""
        name = name.lower().strip()
        if name.startswith("p"):
            try:
                return float(name[1:])
            except ValueError:
                return None
        return None
