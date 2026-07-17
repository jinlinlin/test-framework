"""
config 包 — 配置管理层。

提供配置管理器（单例）、多格式加载器、Schema 验证器。
"""
from .loader import (
    ConfigLoader,
    ConfigLoaderFactory,
    YamlLoader,
    JsonLoader,
    TomlLoader,
    EnvLoader,
    deep_merge,
)
from .manager import ConfigManager
from .validator import ConfigValidator, ValidationResult

__all__ = [
    "ConfigLoader",
    "ConfigLoaderFactory",
    "YamlLoader",
    "JsonLoader",
    "TomlLoader",
    "EnvLoader",
    "deep_merge",
    "ConfigManager",
    "ConfigValidator",
    "ValidationResult",
]
