"""越权访问测试引擎配置 Schema。"""
from __future__ import annotations

import copy
from typing import Any, Dict


AUTH_BYPASS_DEFAULTS: Dict[str, Any] = {
    "engine_type": "auth_bypass",
    "timeout": 30,
    "strategies": [
        "role_escalation", "session_fixation", "token_replay",
        "jwt_attack", "oauth_attack", "idor",
    ],
}


AUTH_BYPASS_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "越权访问测试引擎配置",
    "type": "object",
    "properties": {
        "engine_type": {"type": "string", "const": "auth_bypass"},
        "timeout": {"type": "integer", "minimum": 5, "default": 30},
        "strategies": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "role_escalation", "session_fixation", "token_replay",
                    "jwt_attack", "oauth_attack", "idor",
                ],
            },
        },
    },
    "additionalProperties": True,
}


def get_defaults() -> Dict[str, Any]:
    """获取越权访问引擎默认配置。"""
    return copy.deepcopy(AUTH_BYPASS_DEFAULTS)


def get_schema() -> Dict[str, Any]:
    """获取配置 JSON Schema。"""
    return AUTH_BYPASS_SCHEMA
