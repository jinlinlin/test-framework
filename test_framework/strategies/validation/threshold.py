"""
阈值验证策略 — 逐指标对比阈值，判断是否达标。

设计模式：策略模式
场景：定义性能阈值（如 avg_response < 500ms），自动判断测试通过/失败。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..base import BaseStrategy


@dataclass
class ValidationViolation:
    """
    验证违规记录。

    Attributes:
        metric_name: 指标名称。
        threshold: 设定的阈值。
        actual_value: 实际值。
        operator: 比较运算符（< / > / <= / >= / ==）。
        message: 违规描述。
    """

    metric_name: str = ""
    threshold: float = 0.0
    actual_value: float = 0.0
    operator: str = "<"
    message: str = ""


@dataclass
class ValidationResult:
    """
    验证结果。

    Attributes:
        passed: 是否通过验证。
        violations: 违规列表。
        summary: 验证摘要。
        metrics_checked: 检查的指标数量。
    """

    passed: bool = True
    violations: List[ValidationViolation] = field(default_factory=list)
    summary: str = ""
    metrics_checked: int = 0


class ThresholdValidationStrategy(BaseStrategy):
    """
    阈值验证策略。

    逐指标对比阈值，支持 < / > / <= / >= / == 五种运算符。

    配置示例::

        thresholds = {
            "avg_response_time_ms": {"max": 500},
            "error_rate": {"max": 0.01},
            "p99_response_time_ms": {"max": 2000},
            "requests_per_second": {"min": 100},
        }
    """

    def __init__(
        self,
        thresholds: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> None:
        """
        Args:
            thresholds: 阈值配置字典。
                每个指标可设置 max / min / exact 三种阈值。
        """
        self._thresholds = thresholds or {}

    @property
    def strategy_type(self) -> str:
        return "validation"

    @property
    def name(self) -> str:
        return "threshold"

    def get_config(self) -> Dict[str, Any]:
        return {"thresholds": self._thresholds}

    def validate(self, metrics: Dict[str, float]) -> ValidationResult:
        """
        验证指标是否满足阈值。

        Args:
            metrics: 指标名称→值的映射。

        Returns:
            验证结果，包含通过/失败状态和违规列表。
        """
        violations: List[ValidationViolation] = []

        for metric_name, limits in self._thresholds.items():
            actual = metrics.get(metric_name)
            if actual is None:
                continue  # 指标不存在则跳过

            # 检查最大值限制
            if "max" in limits and actual > limits["max"]:
                violations.append(ValidationViolation(
                    metric_name=metric_name,
                    threshold=limits["max"],
                    actual_value=actual,
                    operator="<=",
                    message=f"{metric_name} = {actual} 超过最大值 {limits['max']}",
                ))

            # 检查最小值限制
            if "min" in limits and actual < limits["min"]:
                violations.append(ValidationViolation(
                    metric_name=metric_name,
                    threshold=limits["min"],
                    actual_value=actual,
                    operator=">=",
                    message=f"{metric_name} = {actual} 低于最小值 {limits['min']}",
                ))

            # 检查精确值
            if "exact" in limits and actual != limits["exact"]:
                violations.append(ValidationViolation(
                    metric_name=metric_name,
                    threshold=limits["exact"],
                    actual_value=actual,
                    operator="==",
                    message=f"{metric_name} = {actual} 不等于 {limits['exact']}",
                ))

        passed = len(violations) == 0
        summary = (
            f"阈值验证通过: {len(self._thresholds)} 项指标全部达标"
            if passed
            else f"阈值验证失败: {len(violations)}/{len(self._thresholds)} 项指标不达标"
        )

        return ValidationResult(
            passed=passed,
            violations=violations,
            summary=summary,
            metrics_checked=len(self._thresholds),
        )
