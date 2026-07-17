"""
计时装饰器 — 测量函数/协程的执行耗时。

职责：在函数执行前后记录时间，输出到日志或通过回调上报。
"""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def timing(
    func: Optional[Callable] = None,
    *,
    log_level: int = logging.DEBUG,
    callback: Optional[Callable[[str, float], None]] = None,
) -> Callable:
    """
    计时装饰器 — 测量同步/异步函数的执行耗时。

    Args:
        func: 被装饰的函数（可直接使用 @timing 或 @timing(...)）。
        log_level: 日志级别。
        callback: 可选回调 ``callback(func_name, elapsed_seconds)``。

    Returns:
        装饰后的函数。

    使用示例::

        @timing
        def my_func():
            pass

        @timing(log_level=logging.INFO, callback=my_cb)
        async def my_async_func():
            pass
    """

    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    return result
                finally:
                    elapsed = time.perf_counter() - start
                    logger.log(log_level, f"[{fn.__name__}] 耗时: {elapsed:.4f}s")
                    if callback:
                        callback(fn.__name__, elapsed)

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    result = fn(*args, **kwargs)
                    return result
                finally:
                    elapsed = time.perf_counter() - start
                    logger.log(log_level, f"[{fn.__name__}] 耗时: {elapsed:.4f}s")
                    if callback:
                        callback(fn.__name__, elapsed)

            return sync_wrapper

    # 支持 @timing 和 @timing(...) 两种用法
    if func is not None:
        return decorator(func)
    return decorator
