"""
自定义重试策略 — 用户自定义重试逻辑。

场景：需要复杂重试逻辑（如基于错误码、响应内容判断是否重试）的场景。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, Optional

from ..base import BaseStrategy

logger = logging.getLogger(__name__)


class CustomRetryStrategy(BaseStrategy):
    """
    自定义重试策略。

    允许用户自定义：
    - 是否应该重试的判断函数（should_retry_fn）
    - 等待时间计算函数（wait_fn）

    配置::

        def should_retry(exception, attempt):
            # 仅在特定错误码时重试
            return hasattr(exception, 'status_code') and exception.status_code in (429, 503)

        def wait_time(attempt):
            return min(2 ** attempt, 30)  # 指数退避但上限 30s

        strategy = CustomRetryStrategy(
            max_retries=3,
            should_retry_fn=should_retry,
            wait_fn=wait_time,
        )
    """

    def __init__(
        self,
        max_retries: int = 3,
        should_retry_fn: Optional[Callable[[Exception, int], bool]] = None,
        wait_fn: Optional[Callable[[int], float]] = None,
    ) -> None:
        """
        Args:
            max_retries: 最大重试次数。
            should_retry_fn: 判断是否重试的函数。
                签名: (exception, attempt) -> bool
            wait_fn: 计算等待时间的函数。
                签名: (attempt) -> float_seconds
        """
        self._max_retries = max_retries
        self._should_retry_fn = should_retry_fn
        self._wait_fn = wait_fn or (lambda attempt: 1.0 * (2 ** attempt))

    @property
    def strategy_type(self) -> str:
        return "retry"

    @property
    def name(self) -> str:
        return "custom"

    def get_config(self) -> Dict[str, Any]:
        return {
            "max_retries": self._max_retries,
            "should_retry_fn": self._should_retry_fn.__name__ if self._should_retry_fn else None,
            "wait_fn": self._wait_fn.__name__ if self._wait_fn else None,
        }

    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """判断是否应该重试。"""
        if self._should_retry_fn:
            return self._should_retry_fn(exception, attempt)
        # 默认：所有异常都重试
        return True

    async def execute_with_retry(
        self,
        fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        带自定义重试逻辑的异步函数执行。

        Args:
            fn: 要执行的异步函数。
            *args: 函数位置参数。
            **kwargs: 函数关键字参数。

        Returns:
            函数返回值。

        Raises:
            Exception: 超过最大重试次数后的最后一次异常。
        """
        last_exception: Exception = RuntimeError("未执行")

        for attempt in range(self._max_retries + 1):
            try:
                result = await fn(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"第 {attempt} 次重试成功")
                return result
            except Exception as e:
                last_exception = e
                if attempt < self._max_retries and self._should_retry(e, attempt):
                    wait_time = self._wait_fn(attempt)
                    logger.warning(
                        f"执行失败 (尝试 {attempt + 1}/{self._max_retries + 1}): {e}, "
                        f"{wait_time:.2f}s 后重试"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    if not self._should_retry(e, attempt):
                        logger.warning(f"执行失败且不满足重试条件: {e}")
                    else:
                        logger.error(f"执行失败，已达最大重试次数: {e}")
                    break

        raise last_exception
