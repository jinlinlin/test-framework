"""
趋势验证策略 — 对比历史数据，检测性能退化。

场景：CI/CD 流水线中，对比当前结果与基准线（baseline），
      检测性能退化（regression）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..base import BaseStrategy
from .threshold import ValidationResult, ValidationViolation


class TrendValidationStrategy(BaseStrategy):
    """
    趋势验证策略。

    将当前测试指标与历史基准线（baseline）对比，
    检测性能退化（regression）。

    配置示例::

        TrendValidationStrategy(
            baseline={"avg_response_time_ms": 200, "error_rate": 0.005},
            regression_threshold=0.1,  # 允许 10% 的退化
        )
    """

    def __init__(
        self,
        baseline: Optional[Dict[str, float]] = None,
        regression_threshold: float = 0.1,
    ) -> None:
        """
        Args:
            baseline: 基准指标值（从历史运行中获取）。
            regression_threshold: 允许的退化比例（0.1 = 10%）。
        """
        self._baseline = baseline or {}
        self._regression_threshold = regression_threshold

    @property
    def strategy_type(self) -> str:
        return "validation"

    @property
    def name(self) -> str:
        return "trend"

    def get_config(self) -> Dict[str, Any]:
        return {
            "baseline": self._baseline,
            "regression_threshold": self._regression_threshold,
        }

    def validate(self, current_metrics: Dict[str, float]) -> ValidationResult:
        """
        对比当前指标与基准线。

        对于响应时间类指标（越低越好），退化意味着值增大。
        对于吞吐量类指标（越高越好），退化意味着值减小。

        Args:
            current_metrics: 当前测试指标。

        Returns:
            验证结果。
        """
        if not self._baseline:
            return ValidationResult(
                passed=True,
                summary="无基准线数据，跳过趋势验证",
            )

        violations: List[ValidationViolation] = []

        # 越低越好的指标（响应时间、错误率等）
        lower_is_better = {
            "avg_response_time_ms", "p50_response_time_ms", "p90_response_time_ms",
            "p95_response_time_ms", "p99_response_time_ms", "error_rate",
            "max_response_time_ms", "min_response_time_ms",
        }

        for metric_name, baseline_value in self._baseline.items():
            current_value = current_metrics.get(metric_name)
            if current_value is None or baseline_value == 0:
                continue

            change_ratio = (current_value - baseline_value) / abs(baseline_value)
            is_lower_better = metric_name in lower_is_better

            # 判断是否退化
            regressed = False
            if is_lower_better and change_ratio > self._regression_threshold:
                regressed = True
            elif not is_lower_better and change_ratio < -self._regression_threshold:
                regressed = True

            if regressed:
                direction = "上升" if change_ratio > 0 else "下降"
                violations.append(ValidationViolation(
                    metric_name=metric_name,
                    threshold=baseline_value,
                    actual_value=current_value,
                    operator="trend",
                    message=(
                        f"{metric_name}: 基准={baseline_value:.2f}, "
                        f"当前={current_value:.2f}, "
                        f"{direction} {abs(change_ratio)*100:.1f}% "
                        f"(允许退化 {self._regression_threshold*100:.0f}%)"
                    ),
                ))

        passed = len(violations) == 0
        summary = (
            f"趋势验证通过: 与基准线对比无显著退化"
            if passed
            else f"趋势验证失败: {len(violations)} 项指标出现退化"
        )

        return ValidationResult(
            passed=passed,
            violations=violations,
            summary=summary,
            metrics_checked=len(self._baseline),
        )

    def update_baseline(self, metrics: Dict[str, float]) -> None:
        """
        更新基准线（通常在测试通过后调用）。

        Args:
            metrics: 新的基准指标值。
        """
        self._baseline = dict(metrics)
