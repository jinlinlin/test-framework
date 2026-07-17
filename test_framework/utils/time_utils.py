"""
时间工具 — 提供计时器、时间格式化、时区转换等辅助函数。

职责：简化时间相关操作，支持上下文管理器计时。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class Timer:
    """
    计时器 — 支持上下文管理器和手动控制。

    使用示例::

        # 上下文管理器
        with Timer("数据库查询") as t:
            await db.execute(query)
        print(f"耗时: {t.elapsed:.3f}s")

        # 手动控制
        t = Timer()
        t.start()
        do_something()
        t.stop()
        print(t.elapsed)
    """

    def __init__(self, name: str = "") -> None:
        """
        初始化计时器。

        Args:
            name: 计时器名称（用于日志输出）。
        """
        self.name = name
        self._start: float = 0.0
        self._end: float = 0.0
        self._running: bool = False

    def start(self) -> "Timer":
        """开始计时。"""
        self._start = time.perf_counter()
        self._running = True
        return self

    def stop(self) -> float:
        """
        停止计时。

        Returns:
            耗时（秒）。
        """
        self._end = time.perf_counter()
        self._running = False
        elapsed = self._end - self._start
        if self.name:
            logger.debug(f"[{self.name}] 耗时: {elapsed:.4f}s")
        return elapsed

    @property
    def elapsed(self) -> float:
        """获取当前耗时（秒），支持运行中查询。"""
        if self._running:
            return time.perf_counter() - self._start
        return self._end - self._start

    def __enter__(self) -> "Timer":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


def format_duration(seconds: float) -> str:
    """
    格式化时间长度为人类可读字符串。

    Args:
        seconds: 时间长度（秒）。

    Returns:
        格式化字符串，如 "2h 15m 30s" 或 "123ms"。

    使用示例::

        >>> format_duration(3661.5)
        '1h 1m 1.50s'
        >>> format_duration(0.123)
        '123.00ms'
    """
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}µs"
    if seconds < 1.0:
        return f"{seconds * 1000:.2f}ms"

    parts = []
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs:.2f}s")

    return " ".join(parts)


def utc_now() -> datetime:
    """获取当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def to_timestamp(dt: datetime) -> float:
    """datetime 转 Unix 时间戳。"""
    return dt.timestamp()


def from_timestamp(ts: float) -> datetime:
    """Unix 时间戳转 datetime（UTC）。"""
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化日期时间为字符串。"""
    return dt.strftime(fmt)


def parse_datetime(s: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """解析字符串为 datetime。"""
    return datetime.strptime(s, fmt)


def time_ago(dt: datetime) -> str:
    """
    将时间转为"x 分钟前"的友好格式。

    Args:
        dt: 目标时间。

    Returns:
        友好时间描述字符串。
    """
    now = datetime.now()
    diff = now - dt

    if diff < timedelta(minutes=1):
        return "刚刚"
    elif diff < timedelta(hours=1):
        return f"{int(diff.total_seconds() / 60)} 分钟前"
    elif diff < timedelta(days=1):
        return f"{int(diff.total_seconds() / 3600)} 小时前"
    elif diff < timedelta(days=30):
        return f"{diff.days} 天前"
    else:
        return dt.strftime("%Y-%m-%d")
