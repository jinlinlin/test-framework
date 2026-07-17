"""
校验工具 — 提供通用的数据校验方法。

职责：校验邮箱、URL、IP、端口、JSON Schema 等常见格式。
"""
from __future__ import annotations

import ipaddress
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class Validator:
    """
    校验工具类。

    使用示例::

        v = Validator()
        assert v.is_email("user@example.com")
        assert v.is_port(8080)
        errors = v.validate_dict(data, rules={"name": "required|string", "age": "required|int"})
    """

    # ------------------------------------------------------------------
    # 基础格式校验
    # ------------------------------------------------------------------

    @staticmethod
    def is_email(value: str) -> bool:
        """校验邮箱格式。"""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, value))

    @staticmethod
    def is_url(value: str) -> bool:
        """校验 URL 格式。"""
        try:
            result = urlparse(value)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def is_ipv4(value: str) -> bool:
        """校验 IPv4 地址。"""
        try:
            ipaddress.IPv4Address(value)
            return True
        except (ipaddress.AddressValueError, ValueError):
            return False

    @staticmethod
    def is_ipv6(value: str) -> bool:
        """校验 IPv6 地址。"""
        try:
            ipaddress.IPv6Address(value)
            return True
        except (ipaddress.AddressValueError, ValueError):
            return False

    @staticmethod
    def is_port(value: int) -> bool:
        """校验端口号（1-65535）。"""
        return isinstance(value, int) and 1 <= value <= 65535

    @staticmethod
    def is_uuid(value: str) -> bool:
        """校验 UUID 格式。"""
        pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        return bool(re.match(pattern, value, re.IGNORECASE))

    # ------------------------------------------------------------------
    # 数值范围校验
    # ------------------------------------------------------------------

    @staticmethod
    def in_range(value: Any, min_val: Any = None, max_val: Any = None) -> bool:
        """校验值是否在范围内。"""
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        return True

    @staticmethod
    def is_positive(value: Any) -> bool:
        """校验正数。"""
        return isinstance(value, (int, float)) and value > 0

    # ------------------------------------------------------------------
    # 字典校验
    # ------------------------------------------------------------------

    @staticmethod
    def validate_dict(
        data: Dict[str, Any],
        rules: Dict[str, str],
    ) -> List[str]:
        """
        按规则校验字典。

        支持的规则（用 | 分隔多个）：
        - ``required``: 字段必须存在且非空
        - ``string``: 必须是字符串
        - ``int``: 必须是整数
        - ``float``: 必须是浮点数
        - ``bool``: 必须是布尔值
        - ``email``: 邮箱格式
        - ``url``: URL 格式

        Args:
            data: 待校验的数据字典。
            rules: 字段名 -> 规则字符串的映射。

        Returns:
            错误信息列表（空列表表示全部通过）。

        使用示例::

            errors = Validator.validate_dict(
                {"name": "Alice", "age": 25},
                {"name": "required|string", "age": "required|int"}
            )
        """
        errors: List[str] = []

        for field, rule_str in rules.items():
            rule_list = [r.strip() for r in rule_str.split("|")]
            value = data.get(field)

            for rule in rule_list:
                if rule == "required":
                    if value is None or value == "":
                        errors.append(f"[{field}] 不能为空")
                        break
                elif rule == "string":
                    if value is not None and not isinstance(value, str):
                        errors.append(f"[{field}] 必须是字符串")
                elif rule == "int":
                    if value is not None and not isinstance(value, int):
                        errors.append(f"[{field}] 必须是整数")
                elif rule == "float":
                    if value is not None and not isinstance(value, (int, float)):
                        errors.append(f"[{field}] 必须是数字")
                elif rule == "bool":
                    if value is not None and not isinstance(value, bool):
                        errors.append(f"[{field}] 必须是布尔值")
                elif rule == "email":
                    if value and not Validator.is_email(str(value)):
                        errors.append(f"[{field}] 邮箱格式不正确")
                elif rule == "url":
                    if value and not Validator.is_url(str(value)):
                        errors.append(f"[{field}] URL 格式不正确")

        return errors
