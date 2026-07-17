"""
core.container 包 — IoC 容器（依赖注入）。

提供全局 IoC 容器、服务注册表和依赖解析器。
"""
from .container import Container
from .dependency_resolver import DependencyResolver
from .service_registry import ServiceRegistry

__all__ = [
    "Container",
    "ServiceRegistry",
    "DependencyResolver",
]
