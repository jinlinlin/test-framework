"""
日志装饰器 — 自动记录函数调用入参、出参、异常。

职责：在函数执行前后输出结构化日志，便于调试和审计。
"""
from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def log_call(
    func: Optional[Callable] = None,
    *,
    log_level: int = logging.INFO,
    log_args: bool = True,
    log_result: bool = True,
    log_exception: bool = True,
    logger_name: Optional[str] = None,
) -> Callable:
    """
    日志装饰器 — 自动记录函数调用。

    Args:
        func: 被装饰的函数。
        log_level: 日志级别。
        log_args: 是否记录入参。
        log_result: 是否记录返回值。
        log_exception: 是否记录异常。
        logger_name: 自定义 logger 名称（默认使用模块级 logger）。

    Returns:
        装饰后的函数。

    使用示例::

        @log_call(log_level=logging.DEBUG)
        def process_data(data: dict):
            pass
    """
    _logger = logging.getLogger(logger_name) if logger_name else logger

    def decorator(fn: Callable) -> Callable:
        fn_name = f"{fn.__module__}.{fn.__qualname__}"

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if log_args:
                    _logger.log(log_level, f"[调用] {fn_name} args={args} kwargs={kwargs}")
                else:
                    _logger.log(log_level, f"[调用] {fn_name}")

                try:
                    result = await fn(*args, **kwargs)
                    if log_result:
                        _logger.log(log_level, f"[返回] {fn_name} -> {result!r}")
                    return result
                except Exception as e:
                    if log_exception:
                        _logger.error(f"[异常] {fn_name}: {type(e).__name__}: {e}")
                    raise

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if log_args:
                    _logger.log(log_level, f"[调用] {fn_name} args={args} kwargs={kwargs}")
                else:
                    _logger.log(log_level, f"[调用] {fn_name}")

                try:
                    result = fn(*args, **kwargs)
                    if log_result:
                        _logger.log(log_level, f"[返回] {fn_name} -> {result!r}")
                    return result
                except Exception as e:
                    if log_exception:
                        _logger.error(f"[异常] {fn_name}: {type(e).__name__}: {e}")
                    raise

            return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator
