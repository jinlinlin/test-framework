"""
熔断器装饰器 — 当失败率超过阈值时自动熔断，保护下游服务。

职责：实现 Circuit Breaker 模式，三种状态：
      Closed（正常）→ Open（熔断）→ Half-Open（半开探测）。
"""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from enum import Enum
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """熔断器状态。"""

    CLOSED = "closed"          # 正常 — 请求正常通过
    OPEN = "open"              # 熔断 — 拒绝所有请求
    HALF_OPEN = "half_open"    # 半开 — 允许单个探测请求


class CircuitBreakerOpenError(Exception):
    """熔断器打开时抛出的异常。"""

    def __init__(self, name: str, reset_timeout: float) -> None:
        super().__init__(
            f"熔断器 [{name}] 已打开，需等待 {reset_timeout:.0f}s 后恢复"
        )
        self.name = name
        self.reset_timeout = reset_timeout


def circuit_breaker(
    func: Optional[Callable] = None,
    *,
    failure_threshold: int = 5,
    reset_timeout: float = 60.0,
    half_open_max_calls: int = 1,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_state_change: Optional[Callable[[str, CircuitState], None]] = None,
) -> Callable:
    """
    熔断器装饰器。

    Args:
        func: 被装饰的函数。
        failure_threshold: 连续失败次数阈值，达到后打开熔断器。
        reset_timeout: 熔断后恢复等待时间（秒）。
        half_open_max_calls: 半开状态允许的最大探测请求数。
        exceptions: 计入失败的异常类型。
        on_state_change: 状态变更回调 ``on_state_change(func_name, new_state)``。

    Returns:
        装饰后的函数。

    使用示例::

        @circuit_breaker(failure_threshold=3, reset_timeout=30)
        async def call_external_service():
            pass
    """

    def decorator(fn: Callable) -> Callable:
        # 熔断器状态
        state = {"status": CircuitState.CLOSED}
        failure_count = {"value": 0}
        last_failure_time = {"value": 0.0}
        half_open_calls = {"value": 0}

        def _change_state(new_state: CircuitState) -> None:
            """切换状态。"""
            old = state["status"]
            state["status"] = new_state
            if old != new_state:
                logger.info(f"[{fn.__name__}] 熔断器状态: {old.value} → {new_state.value}")
                if on_state_change:
                    on_state_change(fn.__name__, new_state)

        def _should_allow() -> bool:
            """判断是否允许请求通过。"""
            now = time.monotonic()

            if state["status"] == CircuitState.CLOSED:
                return True

            if state["status"] == CircuitState.OPEN:
                # 检查是否过了恢复期
                if now - last_failure_time["value"] >= reset_timeout:
                    _change_state(CircuitState.HALF_OPEN)
                    half_open_calls["value"] = 0
                    return True
                return False

            # HALF_OPEN
            if half_open_calls["value"] < half_open_max_calls:
                half_open_calls["value"] += 1
                return True
            return False

        def _record_success() -> None:
            """记录成功。"""
            if state["status"] == CircuitState.HALF_OPEN:
                _change_state(CircuitState.CLOSED)
            failure_count["value"] = 0

        def _record_failure() -> None:
            """记录失败。"""
            failure_count["value"] += 1
            last_failure_time["value"] = time.monotonic()

            if state["status"] == CircuitState.HALF_OPEN:
                _change_state(CircuitState.OPEN)
            elif failure_count["value"] >= failure_threshold:
                _change_state(CircuitState.OPEN)

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not _should_allow():
                    raise CircuitBreakerOpenError(fn.__name__, reset_timeout)

                try:
                    result = await fn(*args, **kwargs)
                    _record_success()
                    return result
                except exceptions:
                    _record_failure()
                    raise

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not _should_allow():
                    raise CircuitBreakerOpenError(fn.__name__, reset_timeout)

                try:
                    result = fn(*args, **kwargs)
                    _record_success()
                    return result
                except exceptions:
                    _record_failure()
                    raise

            return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator
