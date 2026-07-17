"""
线程工具 — 提供线程池管理和同步原语封装。

职责：管理可复用的线程池，提供异步到同步的桥接方法。
"""
from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ThreadPoolManager:
    """
    线程池管理器 — 管理可复用的线程池。

    使用示例::

        manager = ThreadPoolManager(max_workers=8)
        result = await manager.run_in_thread(blocking_function, arg1, arg2)
        manager.shutdown()
    """

    def __init__(self, max_workers: int = 4, thread_name_prefix: str = "tf-worker") -> None:
        """
        初始化线程池。

        Args:
            max_workers: 最大工作线程数。
            thread_name_prefix: 线程名称前缀。
        """
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=thread_name_prefix
        )
        self._lock = threading.Lock()
        logger.debug(f"线程池已创建 (max_workers={max_workers})")

    async def run_in_thread(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        在线程池中执行阻塞函数（异步等待结果）。

        Args:
            func: 阻塞函数。
            *args: 位置参数。
            **kwargs: 关键字参数。

        Returns:
            函数返回值。
        """
        loop = asyncio.get_event_loop()
        if kwargs:
            # ThreadPoolExecutor 不直接支持 kwargs，用 lambda 包装
            wrapped = lambda: func(*args, **kwargs)
            return await loop.run_in_executor(self._executor, wrapped)
        return await loop.run_in_executor(self._executor, func, *args)

    def submit(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        同步提交任务到线程池。

        Returns:
            Future 对象。
        """
        if kwargs:
            wrapped = lambda: func(*args, **kwargs)
            return self._executor.submit(wrapped)
        return self._executor.submit(func, *args)

    def resize(self, max_workers: int) -> None:
        """调整线程池大小（会创建新的 executor）。"""
        with self._lock:
            self._executor.shutdown(wait=False)
            self._executor = ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix="tf-worker"
            )
            self._max_workers = max_workers
            logger.info(f"线程池已调整为 {max_workers} 个线程")

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池。"""
        self._executor.shutdown(wait=wait)
        logger.debug("线程池已关闭")

    @property
    def max_workers(self) -> int:
        """获取最大工作线程数。"""
        return self._max_workers


class AsyncLock:
    """
    异步安全锁 — 同时支持 async with 和 sync with。

    使用示例::

        lock = AsyncLock()
        async with lock:
            # 互斥操作
            pass
    """

    def __init__(self) -> None:
        self._async_lock: Optional[asyncio.Lock] = None
        self._sync_lock = threading.Lock()

    async def __aenter__(self) -> "AsyncLock":
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        await self._async_lock.acquire()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._async_lock:
            self._async_lock.release()

    def __enter__(self) -> "AsyncLock":
        self._sync_lock.acquire()
        return self

    def __exit__(self, *args: Any) -> None:
        self._sync_lock.release()
