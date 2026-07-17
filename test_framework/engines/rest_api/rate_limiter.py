"""
限流器 — 令牌桶算法。

职责：控制 HTTP 请求发送速率，防止对目标系统造成过载压力。
算法：令牌桶（Token Bucket）— 以固定速率生成令牌，
      每次请求消耗一个令牌，桶满时令牌丢弃。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    请求限流器（令牌桶算法）。

    以配置的速率（requests per second）生成令牌，
    每次请求需获取一个令牌方可执行。当令牌耗尽时，
    请求将被阻塞直到新的令牌生成。

    Attributes:
        _rps: 每秒请求数（令牌生成速率）。
        _max_tokens: 令牌桶容量上限。
        _tokens: 当前可用令牌数。
        _last_refill: 上次补充令牌的时间戳。
        _lock: 异步锁，保证并发安全。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化限流器。

        配置格式::

            {
                "rps": 100,           # 每秒请求数
                "max_tokens": 200,    # 令牌桶容量（默认 = rps * 2）
                "enabled": true       # 是否启用限流
            }

        Args:
            config: 限流配置字典。
        """
        self._enabled: bool = config.get("enabled", True)
        self._rps: int = config.get("rps", 100)
        self._max_tokens: int = config.get("max_tokens", self._rps * 2)
        self._tokens: float = float(self._max_tokens)
        self._last_refill: float = time.monotonic()
        self._lock: asyncio.Lock = asyncio.Lock()

        logger.debug(
            f"限流器已初始化: rps={self._rps}, "
            f"max_tokens={self._max_tokens}, enabled={self._enabled}"
        )

    async def acquire(self) -> None:
        """
        获取一个请求令牌。

        如果限流未启用则直接返回。否则补充令牌后尝试获取，
        若令牌不足则等待直到有新令牌生成。

        Raises:
            asyncio.CancelledError: 等待期间被取消。
        """
        if not self._enabled:
            return

        async with self._lock:
            # 补充令牌
            self._refill()

            # 如果令牌不足，计算等待时间
            while self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self._rps
                # 释放锁后再等待，避免死锁
                self._lock.release()
                try:
                    await asyncio.sleep(wait_time)
                finally:
                    await self._lock.acquire()
                self._refill()

            # 消耗一个令牌
            self._tokens -= 1.0

    def set_rate(self, rps: int) -> None:
        """
        动态调整请求速率。

        Args:
            rps: 新的每秒请求数。
        """
        self._rps = max(1, rps)
        self._max_tokens = self._rps * 2
        logger.info(f"限流速率已调整为 {self._rps} rps")

    @property
    def available_tokens(self) -> float:
        """当前可用令牌数（只读属性）。"""
        self._refill()
        return self._tokens

    @property
    def is_enabled(self) -> bool:
        """限流器是否启用（只读属性）。"""
        return self._enabled

    def enable(self) -> None:
        """启用限流。"""
        self._enabled = True

    def disable(self) -> None:
        """禁用限流。"""
        self._enabled = False

    # ===== 私有方法 =====

    def _refill(self) -> None:
        """
        补充令牌。

        根据自上次补充以来经过的时间，按 rps 速率计算
        应补充的令牌数量，但不超过桶容量上限。
        """
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self._rps
        self._tokens = min(self._max_tokens, self._tokens + new_tokens)
        self._last_refill = now
