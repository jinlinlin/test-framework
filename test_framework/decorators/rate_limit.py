"""
限流装饰器 — 控制函数调用频率，防止过载。

职责：基于令牌桶算法限制函数在时间窗口内的调用次数。
"""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def rate_limit(
    func: Optional[Callable] = None,
    *,
    max_calls: int = 10,
    period: float = 1.0,
    raise_on_limit: bool = False,
) -> Callable:
    """
    限流装饰器 — 令牌桶算法。

    Args:
        func: 被装饰的函数。
        max_calls: 时间窗口内最大调用次数。
        period: 时间窗口大小（秒）。
        raise_on_limit: 达到限制时是否抛出异常（False 则阻塞等待）。

    Returns:
        装饰后的函数。

    Raises:
        RuntimeError: 当 raise_on_limit=True 且达到限流时。

    使用示例::

        @rate_limit(max_calls=100, period=60)
        async def call_api():
            pass
    """

    def decorator(fn: Callable) -> Callable:
        # 令牌桶状态
        _tokens: list = []  # 存储调用时间戳

        def _cleanup(now: float) -> None:
            """清理过期令牌。"""
            cutoff = now - period
            while _tokens and _tokens[0] < cutoff:
                _tokens.pop(0)

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                now = time.monotonic()
                _cleanup(now)

                if len(_tokens) >= max_calls:
                    if raise_on_limit:
                        raise RuntimeError(
                            f"[{fn.__name__}] 达到限流: {max_calls}/{period}s"
                        )
                    # 阻塞等待直到有可用令牌
                    wait_time = _tokens[0] + period - now
                    if wait_time > 0:
                        logger.debug(f"[{fn.__name__}] 限流等待 {wait_time:.2f}s")
                        await asyncio.sleep(wait_time)
                        _cleanup(time.monotonic())

                _tokens.append(time.monotonic())
                return await fn(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                now = time.monotonic()
                _cleanup(now)

                if len(_tokens) >= max_calls:
                    if raise_on_limit:
                        raise RuntimeError(
                            f"[{fn.__name__}] 达到限流: {max_calls}/{period}s"
                        )
                    wait_time = _tokens[0] + period - now
                    if wait_time > 0:
                        logger.debug(f"[{fn.__name__}] 限流等待 {wait_time:.2f}s")
                        time.sleep(wait_time)
                        _cleanup(time.monotonic())

                _tokens.append(time.monotonic())
                return fn(*args, **kwargs)

            return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator
