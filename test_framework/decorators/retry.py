"""
重试装饰器 — 在函数失败时按策略自动重试。

职责：支持固定间隔 / 指数退避 / 自定义重试策略，
      可配置最大重试次数和异常过滤。
"""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


def retry(
    func: Optional[Callable] = None,
    *,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
) -> Callable:
    """
    重试装饰器 — 支持指数退避的自动重试。

    Args:
        func: 被装饰的函数。
        max_retries: 最大重试次数。
        delay: 初始延迟时间（秒）。
        backoff: 退避系数（每次重试延迟乘以此值）。
        exceptions: 触发重试的异常类型元组。
        on_retry: 重试回调 ``on_retry(exception, attempt_number)``。

    Returns:
        装饰后的函数。

    使用示例::

        @retry(max_retries=5, delay=0.5)
        async def fetch_data():
            pass
    """

    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                current_delay = delay
                last_exception: Optional[Exception] = None

                for attempt in range(max_retries + 1):
                    try:
                        return await fn(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            logger.warning(
                                f"[{fn.__name__}] 第 {attempt + 1} 次失败，"
                                f"{current_delay:.1f}s 后重试: {e}"
                            )
                            if on_retry:
                                on_retry(e, attempt + 1)
                            await asyncio.sleep(current_delay)
                            current_delay *= backoff

                raise last_exception  # type: ignore[misc]

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                current_delay = delay
                last_exception: Optional[Exception] = None

                for attempt in range(max_retries + 1):
                    try:
                        return fn(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            logger.warning(
                                f"[{fn.__name__}] 第 {attempt + 1} 次失败，"
                                f"{current_delay:.1f}s 后重试: {e}"
                            )
                            if on_retry:
                                on_retry(e, attempt + 1)
                            time.sleep(current_delay)
                            current_delay *= backoff

                raise last_exception  # type: ignore[misc]

            return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator
