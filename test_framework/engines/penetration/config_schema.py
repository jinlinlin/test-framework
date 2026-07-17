"""渗透测试引擎配置 Schema。"""
from __future__ import annotations

import copy
from typing import Any, Dict


PENETRATION_DEFAULTS: Dict[str, Any] = {
    "engine_type": "penetration",
    "timeout": 30,
    "payload_types": [
        "sql_injection", "xss", "path_traversal",
        "command_injection", "ssrf", "xxe",
    ],
    "timing_threshold": 4.0,
    "max_retries": 1,
    "delay_between_requests": 0.1,
}


PENETRATION_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "渗透测试引擎配置",
    "type": "object",
    "properties": {
        "engine_type": {"type": "string", "const": "penetration"},
        "timeout": {"type": "integer", "minimum": 5, "default": 30},
        "payload_types": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "sql_injection", "xss", "path_traversal",
                    "command_injection", "ssrf", "xxe",
                ],
            },
        },
        "timing_threshold": {"type": "number", "minimum": 1, "default": 4.0},
    },
    "additionalProperties": True,
}


def get_defaults() -> Dict[str, Any]:
    """获取渗透测试引擎默认配置。"""
    return copy.deepcopy(PENETRATION_DEFAULTS)


def get_schema() -> Dict[str, Any]:
    """获取配置 JSON Schema。"""
    return PENETRATION_SCHEMA
