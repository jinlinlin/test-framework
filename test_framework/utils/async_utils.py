"""
异步工具 — 提供 asyncio 常用辅助函数。

职责：简化异步编程模式，提供 run_async / gather_with_limit /
      retry_async / timeout_guard 等实用函数。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def run_async(coro: Coroutine, *, loop: Optional[asyncio.AbstractEventLoop] = None) -> Any:
    """
    在同步代码中运行异步协程。

    自动检测是否已有事件循环在运行，
    如果有则创建新线程运行，否则直接 asyncio.run。

    Args:
        coro: 要执行的协程。
        loop: 可选的事件循环。

    Returns:
        协程的返回值。

    使用示例::

        result = run_async(my_async_function())
    """
    try:
        # 尝试获取当前运行中的事件循环
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop and running_loop.is_running():
        # 已有循环在运行，创建新线程
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


async def gather_with_limit(
    coros: List[Coroutine],
    limit: int = 10,
    return_exceptions: bool = False,
) -> List[Any]:
    """
    带并发限制的 asyncio.gather。

    Args:
        coros: 协程列表。
        limit: 最大并发数。
        return_exceptions: 是否返回异常而不抛出。

    Returns:
        所有协程的结果列表。

    使用示例::

        results = await gather_with_limit([fetch(i) for i in range(100)], limit=5)
    """
    semaphore = asyncio.Semaphore(limit)

    async def _limited(coro: Coroutine) -> Any:
        async with semaphore:
            return await coro

    tasks = [_limited(c) for c in coros]
    return await asyncio.gather(*tasks, return_exceptions=return_exceptions)


async def retry_async(
    coro_factory: Callable[[], Coroutine],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Any:
    """
    异步重试。

    Args:
        coro_factory: 返回新协程的工厂函数（每次重试需创建新协程）。
        max_retries: 最大重试次数。
        delay: 初始延迟。
        backoff: 退避系数。
        exceptions: 触发重试的异常类型。

    Returns:
        协程的返回值。

    Raises:
        最后一次重试的异常。
    """
    current_delay = delay
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"异步重试 {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(current_delay)
                current_delay *= backoff

    raise last_exception  # type: ignore[misc]


async def timeout_guard(
    coro: Coroutine,
    timeout: float,
    default: Any = None,
    error_message: str = "操作超时",
) -> Any:
    """
    带超时保护的协程执行。

    Args:
        coro: 要执行的协程。
        timeout: 超时时间（秒）。
        default: 超时后的默认返回值。
        error_message: 超时日志消息。

    Returns:
        协程结果或默认值。
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"{error_message} ({timeout}s)")
        return default


async def periodic_task(
    func: Callable[[], Coroutine],
    interval: float,
    max_runs: int = 0,
) -> None:
    """
    周期性执行异步任务。

    Args:
        func: 异步函数（无参数）。
        interval: 执行间隔（秒）。
        max_runs: 最大执行次数（0 表示无限）。
    """
    run_count = 0
    while True:
        try:
            await func()
            run_count += 1
            if max_runs > 0 and run_count >= max_runs:
                break
        except Exception as e:
            logger.error(f"周期任务异常: {e}")

        await asyncio.sleep(interval)
