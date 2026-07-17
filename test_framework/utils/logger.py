"""
日志工具 — 统一日志配置与格式化。

职责：提供全局日志初始化、格式化、轮转文件处理器配置。
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

# 默认日志格式
_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 已创建的 logger 缓存
_loggers: dict = {}


def setup_logger(
    name: str = "test_framework",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    fmt: str = _DEFAULT_FORMAT,
    date_fmt: str = _DEFAULT_DATE_FORMAT,
    console: bool = True,
) -> logging.Logger:
    """
    配置并返回 logger 实例。

    Args:
        name: Logger 名称。
        level: 日志级别。
        log_file: 日志文件路径（None 则不输出到文件）。
        max_bytes: 单文件最大字节数（超出自动轮转）。
        backup_count: 保留的轮转文件数量。
        fmt: 日志格式字符串。
        date_fmt: 时间格式字符串。
        console: 是否同时输出到控制台。

    Returns:
        配置好的 Logger 实例。

    使用示例::

        logger = setup_logger("my_app", level=logging.DEBUG, log_file="app.log")
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(fmt, datefmt=date_fmt)

    # 控制台处理器
    if console and not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取已配置的 logger（若不存在则自动创建）。

    Args:
        name: Logger 名称。

    Returns:
        Logger 实例。
    """
    if name in _loggers:
        return _loggers[name]
    logger = logging.getLogger(name)
    _loggers[name] = logger
    return logger
