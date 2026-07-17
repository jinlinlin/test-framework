"""
配置验证器模块 — 基于 JSON Schema 验证配置的完整性和类型正确性。

职责：加载 Schema 文件，对配置字典进行校验，
      输出结构化的验证结果（错误列表 + 警告列表）。
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """
    配置验证结果。

    Attributes:
        is_valid: 验证是否通过（无错误即为 True）。
        errors: 错误信息列表（阻塞性问题）。
        warnings: 警告信息列表（建议性问题）。
    """

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """
        合并两个验证结果。

        Args:
            other: 另一个验证结果。

        Returns:
            合并后的新 ValidationResult。
        """
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )

    def __str__(self) -> str:
        """可读的验证结果字符串。"""
        status = "通过" if self.is_valid else "失败"
        lines = [f"验证结果: {status}"]
        if self.errors:
            lines.append(f"  错误 ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"    - {e}")
        if self.warnings:
            lines.append(f"  警告 ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"    - {w}")
        return "\n".join(lines)


class ConfigValidator:
    """
    配置验证器 — 基于 JSON Schema 验证配置字典。

    支持全局 Schema（global.json）和各引擎类型的 Schema，
    提供 validate() 单 Schema 验证和 validate_all() 全量验证。

    Attributes:
        _schema_dir: Schema 文件所在目录。
        _schemas: 已加载的 Schema 缓存。
    """

    # 框架内置的 Schema 文件名列表
    SCHEMA_NAMES = ["global", "test_type", "adapter", "strategy"]

    def __init__(self, schema_dir: Optional[str] = None) -> None:
        """
        初始化配置验证器。

        Args:
            schema_dir: Schema 目录路径，默认使用框架内置的 config/schema/ 目录。
        """
        if schema_dir is None:
            # 默认指向本模块同级 schema/ 目录
            schema_dir = os.path.join(os.path.dirname(__file__), "schema")
        self._schema_dir = schema_dir
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def _load_schema(self, schema_name: str) -> Dict[str, Any]:
        """
        加载指定的 Schema 文件（带缓存）。

        Args:
            schema_name: Schema 名称（不含 .json 后缀）。

        Returns:
            Schema 字典。

        Raises:
            FileNotFoundError: Schema 文件不存在时抛出。
        """
        if schema_name in self._schemas:
            return self._schemas[schema_name]

        schema_path = os.path.join(self._schema_dir, f"{schema_name}.json")
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema 文件不存在: {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        self._schemas[schema_name] = schema
        logger.debug(f"已加载 Schema: {schema_name}")
        return schema

    def validate(self, config: Dict[str, Any], schema_name: str) -> ValidationResult:
        """
        使用指定 Schema 验证配置。

        Args:
            config: 待验证的配置字典。
            schema_name: Schema 名称（如 'global'、'test_type'）。

        Returns:
            验证结果。
        """
        try:
            schema = self._load_schema(schema_name)
        except FileNotFoundError as e:
            return ValidationResult(is_valid=False, errors=[str(e)])

        # 尝试使用 jsonschema 库进行验证
        try:
            import jsonschema
            validator = jsonschema.Draft7Validator(schema)
            errors = []
            for error in sorted(validator.iter_errors(config), key=lambda e: list(e.path)):
                path = ".".join(str(p) for p in error.path) or "(root)"
                errors.append(f"[{path}] {error.message}")

            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
            )
        except ImportError:
            # jsonschema 未安装，退化为基础类型检查
            logger.warning("jsonschema 库未安装，使用基础验证模式")
            return self._basic_validate(config, schema)

    def _basic_validate(self, config: Dict[str, Any], schema: Dict[str, Any]) -> ValidationResult:
        """
        基础验证模式（jsonschema 不可用时的退化方案）。

        仅检查 required 字段是否存在、类型是否匹配。

        Args:
            config: 配置字典。
            schema: Schema 字典。

        Returns:
            验证结果。
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 检查 required 字段
        required_fields = schema.get("required", [])
        for field_name in required_fields:
            if field_name not in config:
                errors.append(f"缺少必需字段: {field_name!r}")

        # 检查 properties 中定义的类型
        properties = schema.get("properties", {})
        for key, prop_schema in properties.items():
            if key in config:
                expected_type = prop_schema.get("type")
                if expected_type and not self._check_type(config[key], expected_type):
                    errors.append(
                        f"字段 {key!r} 类型错误: 期望 {expected_type}，"
                        f"实际 {type(config[key]).__name__}"
                    )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """
        检查值是否符合 JSON Schema 类型。

        Args:
            value: 待检查的值。
            expected_type: JSON Schema 类型名（string/integer/number/boolean/object/array）。

        Returns:
            类型是否匹配。
        """
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # 未知类型不做检查
        return isinstance(value, expected)

    def validate_all(self, config: Dict[str, Any]) -> ValidationResult:
        """
        依次验证所有内置 Schema（global / test_type / adapter / strategy）。

        Args:
            config: 完整的配置字典。

        Returns:
            合并后的验证结果。
        """
        combined = ValidationResult(is_valid=True)

        for schema_name in self.SCHEMA_NAMES:
            schema_path = os.path.join(self._schema_dir, f"{schema_name}.json")
            if not os.path.exists(schema_path):
                # Schema 文件不存在时跳过（不报错）
                logger.debug(f"跳过不存在的 Schema: {schema_name}")
                continue

            result = self.validate(config, schema_name)
            combined = combined.merge(result)

        return combined
