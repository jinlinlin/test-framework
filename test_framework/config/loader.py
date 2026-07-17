"""
配置加载器模块 — 多格式配置文件的加载与解析（工厂模式）。

设计模式：工厂模式
职责：根据文件扩展名自动选择对应的解析器，
      支持 YAML / JSON / TOML / .env 四种配置格式。
"""
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Type

logger = logging.getLogger(__name__)


class ConfigLoader(ABC):
    """
    配置加载器抽象基类。

    所有具体加载器（YAML / JSON / TOML / .env）必须继承此类，
    并实现 load() 和 dump() 方法。
    """

    @abstractmethod
    def load(self, file_path: str) -> Dict[str, Any]:
        """
        从文件加载配置。

        Args:
            file_path: 配置文件的绝对或相对路径。

        Returns:
            解析后的配置字典。
        """
        ...

    @abstractmethod
    def dump(self, data: Dict[str, Any], file_path: str) -> None:
        """
        将配置字典写入文件。

        Args:
            data: 要写入的配置字典。
            file_path: 输出文件路径。
        """
        ...


class YamlLoader(ConfigLoader):
    """
    YAML 配置加载器。

    支持 .yaml 和 .yml 文件格式，
    使用 PyYAML 库进行解析和序列化。
    """

    def load(self, file_path: str) -> Dict[str, Any]:
        """
        加载 YAML 配置文件。

        Args:
            file_path: YAML 文件路径。

        Returns:
            解析后的配置字典；文件为空时返回空字典。
        """
        import yaml  # 延迟导入，避免未安装时报错

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        logger.debug(f"已加载 YAML 配置: {file_path}")
        return data if isinstance(data, dict) else {}

    def dump(self, data: Dict[str, Any], file_path: str) -> None:
        """
        将配置字典写入 YAML 文件。

        Args:
            data: 配置字典。
            file_path: 输出文件路径。
        """
        import yaml

        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.debug(f"已写入 YAML 配置: {file_path}")


class JsonLoader(ConfigLoader):
    """
    JSON 配置加载器。

    支持 .json 文件格式，
    使用标准库 json 进行解析和序列化。
    """

    def load(self, file_path: str) -> Dict[str, Any]:
        """
        加载 JSON 配置文件。

        Args:
            file_path: JSON 文件路径。

        Returns:
            解析后的配置字典。
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"已加载 JSON 配置: {file_path}")
        return data if isinstance(data, dict) else {}

    def dump(self, data: Dict[str, Any], file_path: str) -> None:
        """
        将配置字典写入 JSON 文件。

        Args:
            data: 配置字典。
            file_path: 输出文件路径。
        """
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"已写入 JSON 配置: {file_path}")


class TomlLoader(ConfigLoader):
    """
    TOML 配置加载器。

    支持 .toml 文件格式，
    Python 3.11+ 使用标准库 tomllib，低版本使用 tomli。
    """

    def load(self, file_path: str) -> Dict[str, Any]:
        """
        加载 TOML 配置文件。

        Args:
            file_path: TOML 文件路径。

        Returns:
            解析后的配置字典。
        """
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            import tomli as tomllib  # 低版本回退

        with open(file_path, "rb") as f:
            data = tomllib.load(f)
        logger.debug(f"已加载 TOML 配置: {file_path}")
        return data

    def dump(self, data: Dict[str, Any], file_path: str) -> None:
        """
        将配置字典写入 TOML 文件。

        Args:
            data: 配置字典。
            file_path: 输出文件路径。

        Note:
            需要安装 tomli-w 库才能写入 TOML。
        """
        try:
            import tomli_w
        except ImportError:
            raise ImportError("写入 TOML 需要安装 tomli-w: pip install tomli-w")

        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "wb") as f:
            tomli_w.dump(data, f)
        logger.debug(f"已写入 TOML 配置: {file_path}")


class EnvLoader(ConfigLoader):
    """
    .env 环境变量文件加载器。

    解析 KEY=VALUE 格式的环境变量文件，
    支持注释行（# 开头）和空行。
    """

    def load(self, file_path: str) -> Dict[str, Any]:
        """
        加载 .env 文件并解析为字典。

        Args:
            file_path: .env 文件路径。

        Returns:
            键值对字典（所有值均为字符串）。
        """
        data: Dict[str, str] = {}
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释行
                if not line or line.startswith("#"):
                    continue
                # 解析 KEY=VALUE
                if "=" in line:
                    key, _, value = line.partition("=")
                    # 去除首尾引号
                    data[key.strip()] = value.strip().strip("'\"")
        logger.debug(f"已加载 .env 配置: {file_path}，共 {len(data)} 项")
        return data

    def dump(self, data: Dict[str, Any], file_path: str) -> None:
        """
        将字典写入 .env 文件。

        Args:
            data: 键值对字典。
            file_path: 输出文件路径。
        """
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            for key, value in data.items():
                f.write(f"{key}={value}\n")
        logger.debug(f"已写入 .env 配置: {file_path}")


class ConfigLoaderFactory:
    """
    配置加载器工厂（工厂模式）。

    根据文件扩展名自动选择对应的加载器实例。
    支持注册自定义加载器以扩展格式支持。

    Attributes:
        _loaders: 扩展名 → 加载器类的映射表。
    """

    _loaders: Dict[str, Type[ConfigLoader]] = {
        ".yaml": YamlLoader,
        ".yml": YamlLoader,
        ".json": JsonLoader,
        ".toml": TomlLoader,
        ".env": EnvLoader,
    }

    @classmethod
    def get_loader(cls, file_path: str) -> ConfigLoader:
        """
        根据文件路径获取对应的加载器实例。

        Args:
            file_path: 配置文件路径。

        Returns:
            匹配的配置加载器实例。

        Raises:
            ValueError: 不支持的文件格式。
        """
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        loader_cls = cls._loaders.get(ext)
        if loader_cls is None:
            raise ValueError(f"不支持的配置格式: {ext!r}，支持: {list(cls._loaders.keys())}")

        return loader_cls()

    @classmethod
    def register_loader(cls, ext: str, loader_cls: Type[ConfigLoader]) -> None:
        """
        注册自定义配置加载器。

        Args:
            ext: 文件扩展名（如 '.xml'）。
            loader_cls: 加载器类（必须继承 ConfigLoader）。
        """
        if not ext.startswith("."):
            ext = f".{ext}"
        cls._loaders[ext] = loader_cls
        logger.debug(f"注册自定义加载器: {ext!r} → {loader_cls.__name__}")

    @classmethod
    def supported_extensions(cls) -> list:
        """返回当前支持的所有文件扩展名列表。"""
        return list(cls._loaders.keys())


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    深度合并两个字典，override 中的值优先。

    对于嵌套字典进行递归合并，非字典值直接覆盖。

    Args:
        base: 基础配置字典。
        override: 覆盖配置字典（优先级更高）。

    Returns:
        合并后的新字典（不修改原始输入）。

    Example:
        >>> deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"c": 3, "d": 4}})
        {'a': {'b': 1, 'c': 3, 'd': 4}}
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # 两个值都是字典，递归合并
            result[key] = deep_merge(result[key], value)
        else:
            # 直接覆盖
            result[key] = value

    return result
