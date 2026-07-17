"""
languages 包 — 多语言桥接层。

提供 Python / Node.js / Shell 三种语言的统一执行接口，
支持桥接模式、工厂模式，可动态扩展新语言。
"""
from .bridge import ExecutionResult, LanguageBridge
from .bridge_factory import BridgeFactory

__all__ = [
    "ExecutionResult",
    "LanguageBridge",
    "BridgeFactory",
]
