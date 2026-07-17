"""
自定义验证策略 — 用户自定义验证函数。

场景：当内置验证策略无法满足需求时，允许用户传入自定义验证逻辑。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..base import BaseStrategy
from .threshold import ValidationResult


class CustomValidationStrategy(BaseStrategy):
    """
    自定义验证策略。

    用户传入自定义验证函数，函数签名::

        def my_validator(metrics: Dict[str, Any]) -> ValidationResult:
            ...

    配置示例::

        def check_error_budget(metrics):
            if metrics.get("error_count", 0) > 100:
                return ValidationResult(passed=False, summary="错误预算已耗尽")
            return ValidationResult(passed=True, summary="错误预算正常")

        strategy = CustomValidationStrategy(validate_fn=check_error_budget)
    """

    def __init__(
        self,
        validate_fn: Optional[Callable[..., ValidationResult]] = None,
    ) -> None:
        """
        Args:
            validate_fn: 自定义验证函数。
                接收指标字典，返回 ValidationResult。
        """
        self._validate_fn = validate_fn

    @property
    def strategy_type(self) -> str:
        return "validation"

    @property
    def name(self) -> str:
        return "custom"

    def get_config(self) -> Dict[str, Any]:
        return {
            "validate_fn": self._validate_fn.__name__ if self._validate_fn else None,
        }

    def validate(self, metrics: Dict[str, Any]) -> ValidationResult:
        """
        执行自定义验证函数。

        Args:
            metrics: 指标字典。

        Returns:
            验证结果。
        """
        if not self._validate_fn:
            return ValidationResult(
                passed=True,
                summary="未设置自定义验证函数，跳过验证",
            )

        try:
            result = self._validate_fn(metrics)
            if isinstance(result, ValidationResult):
                return result
            # 如果函数返回布尔值
            passed = bool(result)
            return ValidationResult(
                passed=passed,
                summary="自定义验证通过" if passed else "自定义验证失败",
            )
        except Exception as e:
            return ValidationResult(
                passed=False,
                summary=f"自定义验证函数执行异常: {e}",
            )
