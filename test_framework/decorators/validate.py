"""
校验装饰器 — 对函数参数和返回值进行类型/值校验。

职责：在运行时验证参数类型、范围、必填性等，
      不符合预期时抛出 ValidationError。
"""
from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Dict, Optional, Type, get_type_hints

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """参数/返回值校验失败异常。"""

    def __init__(self, field: str, expected: str, actual: str) -> None:
        super().__init__(f"校验失败 [{field}]: 期望 {expected}，实际 {actual}")
        self.field = field
        self.expected = expected
        self.actual = actual


def validate_args(
    func: Optional[Callable] = None,
    *,
    strict: bool = False,
    checks: Optional[Dict[str, Callable[[Any], bool]]] = None,
) -> Callable:
    """
    参数校验装饰器。

    Args:
        func: 被装饰的函数。
        strict: 严格模式 — 自动校验类型注解匹配。
        checks: 自定义校验函数映射 ``{param_name: check_fn}``。

    Returns:
        装饰后的函数。

    Raises:
        ValidationError: 参数校验失败时。

    使用示例::

        @validate_args(strict=True, checks={"age": lambda x: x > 0})
        def create_user(name: str, age: int):
            pass
    """

    def decorator(fn: Callable) -> Callable:

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            sig = inspect.signature(fn)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # 严格类型校验
            if strict:
                hints = get_type_hints(fn)
                for param_name, value in bound.arguments.items():
                    if param_name in hints:
                        expected_type = hints[param_name]
                        if not isinstance(value, expected_type):
                            raise ValidationError(
                                param_name,
                                str(expected_type),
                                type(value).__name__,
                            )

            # 自定义校验
            if checks:
                for param_name, check_fn in checks.items():
                    if param_name in bound.arguments:
                        value = bound.arguments[param_name]
                        if not check_fn(value):
                            raise ValidationError(
                                param_name,
                                "通过自定义校验",
                                repr(value),
                            )

            return fn(*args, **kwargs)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def validate_return(
    func: Optional[Callable] = None,
    *,
    expected_type: Optional[Type] = None,
    check: Optional[Callable[[Any], bool]] = None,
) -> Callable:
    """
    返回值校验装饰器。

    Args:
        func: 被装饰的函数。
        expected_type: 期望的返回值类型。
        check: 自定义校验函数。

    Returns:
        装饰后的函数。

    Raises:
        ValidationError: 返回值校验失败时。

    使用示例::

        @validate_return(expected_type=list)
        def get_items() -> list:
            return [1, 2, 3]
    """

    def decorator(fn: Callable) -> Callable:

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = fn(*args, **kwargs)

            if expected_type and not isinstance(result, expected_type):
                raise ValidationError(
                    f"{fn.__name__} return",
                    expected_type.__name__,
                    type(result).__name__,
                )

            if check and not check(result):
                raise ValidationError(
                    f"{fn.__name__} return",
                    "通过自定义校验",
                    repr(result),
                )

            return result

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
