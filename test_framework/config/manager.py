"""
配置管理器模块 — 全局统一配置入口（单例模式）。

设计模式：单例模式
职责：全局统一的配置管理，支持层级合并、热重载、按路径访问。
配置优先级（从高到低）：
    环境变量（TF_ 前缀） > 命令行参数 > 环境配置 > 默认配置
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import yaml

from ..core.exceptions.config import ConfigException
from .loader import ConfigLoaderFactory, deep_merge
from .validator import ConfigValidator, ValidationResult

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    配置管理器（单例模式）— 全局统一配置入口。

    支持功能：
    - 多格式配置加载（YAML / JSON / TOML / .env）
    - 层级深度合并（defaults → base → env → 环境变量）
    - 点号路径访问（如 'engines.web_performance.timeout'）
    - 运行时动态设置（不影响文件）
    - 热重载（重新读取配置文件并合并）
    - 配置验证（基于 JSON Schema）
    - 配置导出（导出为 YAML 文件）

    Attributes:
        _instance: 单例实例引用。
        _config: 当前生效的配置字典。
        _env: 当前环境名称（dev/test/staging/production）。
        _config_dir: 配置文件根目录。
    """

    _instance: Optional["ConfigManager"] = None

    def __new__(cls) -> "ConfigManager":
        """确保全局只有一个 ConfigManager 实例。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = {}
            cls._instance._env = "dev"
            cls._instance._config_dir = ""
        return cls._instance

    def load(self, env: str = "dev", config_dir: Optional[str] = None) -> None:
        """
        加载配置，按优先级合并各层级。

        加载顺序（后者覆盖前者）：
        1. defaults/ 下所有 YAML 文件
        2. environments/base.yaml
        3. environments/{env}.yaml
        4. 环境变量覆盖（TF_ 前缀）

        Args:
            env: 环境名称（dev / test / staging / production）。
            config_dir: 配置根目录，默认使用框架内置 config/ 目录。
        """
        if config_dir is None:
            config_dir = os.path.dirname(os.path.abspath(__file__))
        self._config_dir = config_dir
        self._env = env

        logger.info(f"加载配置: env={env}, dir={config_dir}")

        # 1. 加载 defaults/ 目录下所有 YAML
        defaults_dir = os.path.join(config_dir, "defaults")
        if os.path.isdir(defaults_dir):
            for filename in sorted(os.listdir(defaults_dir)):
                if filename.endswith((".yaml", ".yml")):
                    file_path = os.path.join(defaults_dir, filename)
                    data = self._load_file(file_path)
                    self._config = deep_merge(self._config, data)
                    logger.debug(f"加载默认配置: {filename}")

        # 2. 加载 environments/base.yaml
        base_path = os.path.join(config_dir, "environments", "base.yaml")
        if os.path.exists(base_path):
            data = self._load_file(base_path)
            self._config = deep_merge(self._config, data)
            logger.debug("加载基础环境配置: base.yaml")

        # 3. 加载 environments/{env}.yaml
        env_path = os.path.join(config_dir, "environments", f"{env}.yaml")
        if os.path.exists(env_path):
            data = self._load_file(env_path)
            self._config = deep_merge(self._config, data)
            logger.debug(f"加载环境配置: {env}.yaml")

        # 4. 加载环境变量覆盖（TF_ 前缀）
        env_overrides = self._load_env_overrides()
        if env_overrides:
            self._config = deep_merge(self._config, env_overrides)
            logger.debug(f"应用环境变量覆盖: {len(env_overrides)} 项")

        logger.info(f"配置加载完成，顶层键: {list(self._config.keys())}")

    def get(self, path: str, default: Any = None) -> Any:
        """
        按点号路径获取配置值。

        Args:
            path: 点号分隔的配置路径（如 'engines.web_performance.timeout'）。
            default: 路径不存在时的默认值。

        Returns:
            配置值，或默认值。

        Example:
            >>> config.get('engines.web_performance.timeout')
            30000
        """
        keys = path.split(".")
        current = self._config

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def set(self, path: str, value: Any) -> None:
        """
        运行时动态设置配置值（不影响文件）。

        Args:
            path: 点号分隔的配置路径。
            value: 要设置的值。

        Example:
            >>> config.set('engines.web_performance.timeout', 60000)
        """
        keys = path.split(".")
        current = self._config

        # 逐层深入到倒数第二层
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]

        # 设置最后一层的值
        current[keys[-1]] = value
        logger.debug(f"动态设置配置: {path} = {value!r}")

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        获取整个配置区块。

        Args:
            section: 配置区块路径（如 'engines.rest_api'）。

        Returns:
            配置区块字典；路径不存在时返回空字典。
        """
        result = self.get(section, {})
        return result if isinstance(result, dict) else {}

    def reload(self) -> None:
        """
        热重载 — 重新读取配置文件并合并。

        使用上次 load() 时的 env 和 config_dir 参数。
        """
        logger.info("热重载配置...")
        # 保存当前环境参数，清空后重新加载
        env = self._env
        config_dir = self._config_dir
        self._config = {}
        self.load(env=env, config_dir=config_dir)
        logger.info("配置热重载完成")

    def validate(self) -> ValidationResult:
        """
        调用 ConfigValidator 验证当前配置。

        Returns:
            验证结果对象。
        """
        validator = ConfigValidator()
        result = validator.validate_all(self._config)
        if not result.is_valid:
            logger.warning(f"配置验证失败:\n{result}")
        else:
            logger.debug("配置验证通过")
        return result

    def export(self, path: str) -> None:
        """
        将当前生效的配置导出为 YAML 文件。

        Args:
            path: 导出文件路径。
        """
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                self._config,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        logger.info(f"配置已导出到: {path}")

    @property
    def environment(self) -> str:
        """当前环境名称。"""
        return self._env

    @property
    def config(self) -> Dict[str, Any]:
        """当前完整的配置字典（只读访问）。"""
        return self._config

    def _load_file(self, file_path: str) -> Dict[str, Any]:
        """
        使用工厂加载器读取配置文件。

        Args:
            file_path: 配置文件路径。

        Returns:
            解析后的配置字典。
        """
        try:
            loader = ConfigLoaderFactory.get_loader(file_path)
            return loader.load(file_path)
        except Exception as e:
            logger.error(f"加载配置文件失败 {file_path}: {e}")
            return {}

    def _load_env_overrides(self) -> Dict[str, Any]:
        """
        从环境变量加载覆盖配置。

        扫描 TF_ 前缀的环境变量，转换为嵌套字典。
        例如：TF_ENGINES__WEB_PERFORMANCE__TIMEOUT=60000
        转换为：{'engines': {'web_performance': {'timeout': '60000'}}}

        Returns:
            环境变量转换的配置字典。
        """
        prefix = "TF_"
        overrides: Dict[str, Any] = {}

        for key, value in os.environ.items():
            if key.startswith(prefix):
                # 去除前缀，双下划线分隔层级
                config_path = key[len(prefix):]
                parts = config_path.lower().split("__")

                # 构建嵌套字典
                current = overrides
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value

        return overrides

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（仅测试用）。"""
        cls._instance = None
