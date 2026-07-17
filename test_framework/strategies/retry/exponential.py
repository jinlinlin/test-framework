"""
指数退避重试策略 — 重试间隔指数增长。

场景：API 限流（429）、服务降级等场景，避免雪崩效应。
等待时间：base * 2^attempt + jitter
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Callable, Coroutine, Dict, Tuple, Type

from ..base import BaseStrategy

logger = logging.getLogger(__name__)


class ExponentialRetryStrategy(BaseStrategy):
    """
    指数退避重试策略。

    每次重试等待时间指数增长，加入随机抖动（jitter）避免惊群效应。

    等待时间公式::

        wait = min(base_interval * 2^attempt + jitter, max_interval)

    配置::

        ExponentialRetryStrategy(
            max_retries=5,
            base_interval=1.0,
            max_interval=60.0,
            jitter=True,
        )
    """

    def __init__(
        self,
        max_retries: int = 5,
        base_interval: float = 1.0,
        max_interval: float = 60.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> None:
        """
        Args:
            max_retries: 最大重试次数。
            base_interval: 基础间隔时间（秒）。
            max_interval: 最大间隔时间（秒）。
            jitter: 是否添加随机抖动。
            retryable_exceptions: 可重试的异常类型。
        """
        self._max_retries = max_retries
        self._base_interval = base_interval
        self._max_interval = max_interval
        self._jitter = jitter
        self._retryable_exceptions = retryable_exceptions

    @property
    def strategy_type(self) -> str:
        return "retry"

    @property
    def name(self) -> str:
        return "exponential"

    def get_config(self) -> Dict[str, Any]:
        return {
            "max_retries": self._max_retries,
            "base_interval": self._base_interval,
            "max_interval": self._max_interval,
            "jitter": self._jitter,
        }

    def _calculate_wait(self, attempt: int) -> float:
        """
        计算等待时间。

        Args:
            attempt: 当前重试次数（从 0 开始）。

        Returns:
            等待时间（秒）。
        """
        wait = self._base_interval * (2 ** attempt)
        if self._jitter:
            wait += random.uniform(0, self._base_interval)
        return min(wait, self._max_interval)

    async def execute_with_retry(
        self,
        fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        带指数退避重试的异步函数执行。

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
                    wait_time = self._calculate_wait(attempt)
                    logger.warning(
                        f"执行失败 (尝试 {attempt + 1}/{self._max_retries + 1}): {e}, "
                        f"{wait_time:.2f}s 后重试"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"执行失败，已达最大重试次数 ({self._max_retries}): {e}"
                    )

        raise last_exception
