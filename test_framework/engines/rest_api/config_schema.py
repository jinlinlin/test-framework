"""
REST API 引擎配置 Schema。

职责：定义 REST API 测试引擎的配置结构、默认值、
      验证规则，供 ConfigValidator 使用。
"""
from __future__ import annotations

from typing import Any, Dict


# ===== REST API 引擎默认配置 =====
REST_API_DEFAULTS: Dict[str, Any] = {
    # 引擎类型标识
    "engine_type": "rest_api",

    # HTTP 客户端配置
    "timeout": 30,                  # 请求超时（秒）
    "verify_ssl": True,             # 是否验证 SSL 证书
    "follow_redirects": True,       # 是否跟随重定向
    "max_redirects": 10,            # 最大重定向次数

    # 认证配置
    "auth": {
        "type": "",                 # basic / bearer / oauth2 / api_key
        "username": "",
        "password": "",
        "token": "",
        "client_id": "",
        "client_secret": "",
        "token_url": "",
        "scope": "",
        "key_name": "X-API-Key",
        "key_value": "",
        "location": "header",       # header 或 query
    },

    # 限流配置
    "rate_limit": {
        "enabled": True,
        "rps": 100,                 # 每秒请求数
        "max_tokens": 200,          # 令牌桶容量
    },

    # 验证策略配置
    "validation": {
        "schema_check": True,       # 启用 JSON Schema 验证
        "contract_check": False,    # 启用契约验证
        "response_time_check": False,  # 启用响应时间验证
    },

    # 契约测试配置
    "contract": {
        "contract_path": "",        # 契约文件路径
        "strict_mode": False,       # 严格模式：未定义的字段也报错
    },
}


# ===== REST API 引擎配置 JSON Schema =====
REST_API_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "REST API 引擎配置",
    "description": "REST API 测试引擎的完整配置 Schema",
    "type": "object",
    "properties": {
        "engine_type": {
            "type": "string",
            "const": "rest_api",
            "description": "引擎类型标识",
        },
        "timeout": {
            "type": "number",
            "minimum": 1,
            "maximum": 300,
            "default": 30,
            "description": "请求超时时间（秒）",
        },
        "verify_ssl": {
            "type": "boolean",
            "default": True,
            "description": "是否验证 SSL 证书",
        },
        "follow_redirects": {
            "type": "boolean",
            "default": True,
            "description": "是否跟随重定向",
        },
        "auth": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["", "basic", "bearer", "oauth2", "api_key"],
                    "description": "认证类型",
                },
                "username": {"type": "string"},
                "password": {"type": "string"},
                "token": {"type": "string"},
                "client_id": {"type": "string"},
                "client_secret": {"type": "string"},
                "token_url": {"type": "string", "format": "uri"},
                "scope": {"type": "string"},
                "key_name": {"type": "string"},
                "key_value": {"type": "string"},
                "location": {
                    "type": "string",
                    "enum": ["header", "query"],
                },
            },
            "description": "认证配置",
        },
        "rate_limit": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否启用限流",
                },
                "rps": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 100,
                    "description": "每秒请求数",
                },
                "max_tokens": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "令牌桶容量",
                },
            },
            "description": "限流配置",
        },
        "validation": {
            "type": "object",
            "properties": {
                "schema_check": {
                    "type": "boolean",
                    "default": True,
                    "description": "启用 JSON Schema 验证",
                },
                "contract_check": {
                    "type": "boolean",
                    "default": False,
                    "description": "启用契约验证",
                },
                "response_time_check": {
                    "type": "boolean",
                    "default": False,
                    "description": "启用响应时间验证",
                },
            },
            "description": "验证策略配置",
        },
    },
    "additionalProperties": True,
}


# ===== 测试用例配置 Schema =====
TEST_CASE_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "REST API 测试用例配置",
    "type": "object",
    "required": ["method", "path"],
    "properties": {
        "method": {
            "type": "string",
            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
            "description": "HTTP 方法",
        },
        "path": {
            "type": "string",
            "description": "请求路径",
        },
        "headers": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "请求头",
        },
        "params": {
            "type": "object",
            "description": "URL 查询参数",
        },
        "body": {
            "description": "请求体",
        },
        "body_type": {
            "type": "string",
            "enum": ["json", "form"],
            "default": "json",
            "description": "请求体类型",
        },
        "expected_status": {
            "oneOf": [
                {"type": "integer"},
                {"type": "array", "items": {"type": "integer"}},
            ],
            "default": 200,
            "description": "预期状态码（单个或列表）",
        },
        "response_schema": {
            "type": "object",
            "description": "JSON Schema 用于验证响应体",
        },
        "max_response_time": {
            "type": "number",
            "minimum": 0,
            "description": "最大响应时间（毫秒）",
        },
    },
}


def get_defaults() -> Dict[str, Any]:
    """
    获取 REST API 引擎默认配置。

    Returns:
        默认配置字典的深拷贝。
    """
    import copy
    return copy.deepcopy(REST_API_DEFAULTS)


def get_schema() -> Dict[str, Any]:
    """
    获取 REST API 引擎配置 JSON Schema。

    Returns:
        JSON Schema 字典。
    """
    return REST_API_SCHEMA


def get_test_case_schema() -> Dict[str, Any]:
    """
    获取测试用例配置 JSON Schema。

    Returns:
        测试用例 JSON Schema 字典。
    """
    return TEST_CASE_SCHEMA
