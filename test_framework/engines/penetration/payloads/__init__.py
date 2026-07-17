"""engines.penetration.payloads 包 — 攻击载荷库（策略模式）。"""
from .base import Payload
from .sql_injection import SQLInjectionPayload
from .xss import XSSPayload
from .path_traversal import PathTraversalPayload
from .command_injection import CommandInjectionPayload
from .ssrf import SSRFPayload
from .xxe import XXEPayload

__all__ = [
    "Payload",
    "SQLInjectionPayload",
    "XSSPayload",
    "PathTraversalPayload",
    "CommandInjectionPayload",
    "SSRFPayload",
    "XXEPayload",
]
