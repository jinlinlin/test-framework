"""
Schema 验证器 — 基于 JSON Schema 验证响应体结构。

职责：提供独立的 JSON Schema 验证能力，可单独使用，
      也可被 ResponseValidator 的 SchemaCheckStrategy 调用。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class SchemaValidationResult:
    """
    Schema 验证结果。

    Attributes:
        valid: 是否符合 Schema。
        errors: 错误信息列表。
        message: 验证结果消息。
    """

    valid: bool = True
    errors: List[str] = field(default_factory=list)
    message: str = "Schema 验证通过"


class SchemaValidator:
    """
    JSON Schema 验证器。

    基于 JSON Schema 规范验证数据结构，
    支持内联 Schema 和文件 Schema 两种模式。

    Attributes:
        _schema_cache: Schema 文件路径 → Schema 字典的缓存。
    """

    def __init__(self) -> None:
        """初始化 Schema 验证器，创建空缓存。"""
        self._schema_cache: Dict[str, Dict[str, Any]] = {}

    def validate(self, data: Any, schema: Dict[str, Any]) -> SchemaValidationResult:
        """
        使用 JSON Schema 验证数据。

        Args:
            data: 待验证的数据。
            schema: JSON Schema 定义字典。

        Returns:
            Schema 验证结果。
        """
        try:
            import jsonschema
            validator_cls = jsonschema.Draft7Validator
            validator = validator_cls(schema)
            errors = list(validator.iter_errors(data))

            if not errors:
                return SchemaValidationResult(
                    valid=True,
                    message="Schema 验证通过",
                )

            error_messages = []
            for err in errors:
                path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
                error_messages.append(f"[{path}] {err.message}")

            return SchemaValidationResult(
                valid=False,
                errors=error_messages,
                message=f"发现 {len(error_messages)} 个 Schema 违规",
            )

        except ImportError:
            # jsonschema 未安装时回退到基础类型检查
            logger.warning("jsonschema 未安装，回退到基础验证")
            return self._basic_validate(data, schema)

    def validate_from_file(self, data: Any, schema_path: str) -> SchemaValidationResult:
        """
        从文件加载 Schema 并验证数据。

        Schema 文件会被缓存，避免重复读取。

        Args:
            data: 待验证的数据。
            schema_path: JSON Schema 文件路径。

        Returns:
            Schema 验证结果。

        Raises:
            FileNotFoundError: Schema 文件不存在。
        """
        # 从缓存加载
        if schema_path in self._schema_cache:
            schema = self._schema_cache[schema_path]
        else:
            path = Path(schema_path)
            if not path.exists():
                raise FileNotFoundError(f"Schema 文件不存在: {schema_path}")
            with open(path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            self._schema_cache[schema_path] = schema

        return self.validate(data, schema)

    def clear_cache(self) -> None:
        """清除 Schema 文件缓存。"""
        self._schema_cache.clear()

    # ===== 私有方法：基础验证（无 jsonschema 库时回退） =====

    def _basic_validate(self, data: Any, schema: Dict[str, Any]) -> SchemaValidationResult:
        """
        基础 Schema 验证（不依赖 jsonschema 库）。

        仅检查类型和必需字段，作为 jsonschema 的降级方案。

        Args:
            data: 待验证的数据。
            schema: Schema 定义。

        Returns:
            基础验证结果。
        """
        errors: List[str] = []

        schema_type = schema.get("type", "")

        # 类型检查
        type_check = self._check_type(data, schema_type)
        if not type_check:
            errors.append(
                f"类型不匹配: 期望 {schema_type}，实际 {type(data).__name__}"
            )

        # 必需字段检查（仅 object 类型）
        if schema_type == "object" and isinstance(data, dict):
            required = schema.get("required", [])
            for req_field in required:
                if req_field not in data:
                    errors.append(f"缺少必需字段: '{req_field}'")

            # 递归检查 properties
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if prop_name in data:
                    sub_result = self._basic_validate(data[prop_name], prop_schema)
                    if not sub_result.valid:
                        for err in sub_result.errors:
                            errors.append(f"{prop_name}: {err}")

        # 数组元素检查
        if schema_type == "array" and isinstance(data, list):
            items_schema = schema.get("items", {})
            if items_schema:
                for i, item in enumerate(data):
                    sub_result = self._basic_validate(item, items_schema)
                    if not sub_result.valid:
                        for err in sub_result.errors:
                            errors.append(f"[{i}]: {err}")

        if errors:
            return SchemaValidationResult(
                valid=False,
                errors=errors,
                message=f"基础验证发现 {len(errors)} 个问题",
            )

        return SchemaValidationResult(valid=True, message="基础验证通过")

    @staticmethod
    def _check_type(value: Any, schema_type: str) -> bool:
        """
        检查值类型是否匹配 Schema 类型。

        Args:
            value: 待检查的值。
            schema_type: JSON Schema 类型字符串。

        Returns:
            类型是否匹配。
        """
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        expected = type_map.get(schema_type)
        if expected is None:
            return True
        return isinstance(value, expected)
