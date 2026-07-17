"""
固定间隔重试策略 — 每次重试间隔固定时间。

场景：网络抖动、临时故障等瞬时错误的自动恢复。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, Type, Tuple

from ..base import BaseStrategy

logger = logging.getLogger(__name__)


class FixedRetryStrategy(BaseStrategy):
    """
    固定间隔重试策略。

    每次重试等待相同的时间间隔，超过最大重试次数后抛出异常。

    配置::

        FixedRetryStrategy(
            max_retries=3,
            interval=2.0,
            retryable_exceptions=(ConnectionError, TimeoutError),
        )
    """

    def __init__(
        self,
        max_retries: int = 3,
        interval: float = 1.0,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> None:
        """
        Args:
            max_retries: 最大重试次数。
            interval: 重试间隔（秒）。
            retryable_exceptions: 可重试的异常类型元组。
        """
        self._max_retries = max_retries
        self._interval = interval
        self._retryable_exceptions = retryable_exceptions

    @property
    def strategy_type(self) -> str:
        return "retry"

    @property
    def name(self) -> str:
        return "fixed"

    def get_config(self) -> Dict[str, Any]:
        return {
            "max_retries": self._max_retries,
            "interval": self._interval,
            "retryable_exceptions": [e.__name__ for e in self._retryable_exceptions],
        }

    async def execute_with_retry(
        self,
        fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        带固定间隔重试的异步函数执行。

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
            except self._retryable_exceptions as e:
                last_exception = e
                if attempt < self._max_retries:
                    logger.warning(
                        f"执行失败 (尝试 {attempt + 1}/{self._max_retries + 1}): {e}, "
                        f"{self._interval}s 后重试"
                    )
                    await asyncio.sleep(self._interval)
                else:
                    logger.error(
                        f"执行失败，已达最大重试次数 ({self._max_retries}): {e}"
                    )

        raise last_exception
