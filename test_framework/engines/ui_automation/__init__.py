"""
UI自动化测试引擎模块。

设计模式：
- 策略模式（定位策略、等待策略）
- 命令模式（UI操作）
- 模板模式（引擎基类）
"""
from .engine import UIAutomationEngine
from .test_runner import TestRunner

__all__ = [
    "UIAutomationEngine",
    "TestRunner",
]