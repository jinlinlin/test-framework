"""
缓存装饰器 — 基于 LRU 策略缓存函数返回值。

职责：减少重复计算，支持 TTL 过期、手动清除。
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Callable, Hashable, Optional

logger = logging.getLogger(__name__)


def cached(
    func: Optional[Callable] = None,
    *,
    max_size: int = 128,
    ttl: Optional[float] = None,
    key_func: Optional[Callable[..., Hashable]] = None,
) -> Callable:
    """
    缓存装饰器 — LRU + 可选 TTL。

    Args:
        func: 被装饰的函数。
        max_size: 最大缓存条目数。
        ttl: 缓存过期时间（秒），None 表示永不过期。
        key_func: 自定义缓存键生成函数。

    Returns:
        装饰后的函数。

    使用示例::

        @cached(max_size=256, ttl=300)
        def expensive_calculation(x, y):
            return x ** y
    """

    def decorator(fn: Callable) -> Callable:
        # 缓存存储：key -> (value, expire_time)
        _cache: OrderedDict[str, tuple] = OrderedDict()

        def _make_key(args: tuple, kwargs: dict) -> str:
            """生成缓存键。"""
            if key_func:
                return str(key_func(*args, **kwargs))
            # 默认使用参数的 JSON 序列化哈希
            try:
                raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
            except (TypeError, ValueError):
                raw = f"{args}:{kwargs}"
            return hashlib.md5(raw.encode()).hexdigest()

        def _get(key: str) -> Optional[Any]:
            """获取缓存值（检查 TTL）。"""
            if key not in _cache:
                return None
            value, expire_at = _cache[key]
            if ttl is not None and time.monotonic() > expire_at:
                del _cache[key]
                return None
            # 移到末尾（最近使用）
            _cache.move_to_end(key)
            return value

        def _set(key: str, value: Any) -> None:
            """设置缓存值。"""
            if len(_cache) >= max_size:
                _cache.popitem(last=False)  # 淘汰最旧条目
            expire_at = time.monotonic() + (ttl or float("inf"))
            _cache[key] = (value, expire_at)

        def clear_cache() -> None:
            """清除所有缓存。"""
            _cache.clear()
            logger.debug(f"[{fn.__name__}] 缓存已清除")

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = _make_key(args, kwargs)
                result = _get(key)
                if result is not None:
                    logger.debug(f"[{fn.__name__}] 缓存命中: {key}")
                    return result

                result = await fn(*args, **kwargs)
                _set(key, result)
                return result

            async_wrapper.clear_cache = clear_cache  # type: ignore[attr-defined]
            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = _make_key(args, kwargs)
                result = _get(key)
                if result is not None:
                    logger.debug(f"[{fn.__name__}] 缓存命中: {key}")
                    return result

                result = fn(*args, **kwargs)
                _set(key, result)
                return result

            sync_wrapper.clear_cache = clear_cache  # type: ignore[attr-defined]
            return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator
