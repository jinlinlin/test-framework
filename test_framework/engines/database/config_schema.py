"""
数据库引擎配置 Schema。

职责：定义数据库性能测试引擎的配置结构、默认值、
      验证规则，支持 PostgreSQL / MySQL / MongoDB / Redis。
"""
from __future__ import annotations

import copy
from typing import Any, Dict


# ===== 数据库引擎默认配置 =====
DATABASE_DEFAULTS: Dict[str, Any] = {
    # 引擎类型标识
    "engine_type": "database",

    # 连接池配置
    "pool": {
        "min_size": 5,              # 最小连接数
        "max_size": 20,             # 最大连接数
        "idle_timeout": 300,        # 空闲超时（秒）
        "health_check": 60,         # 健康检查间隔（秒）
    },

    # 查询配置
    "query": {
        "explain": True,            # 启用执行计划分析
        "index_advice": True,       # 启用索引建议
        "default_iterations": 100,  # 默认迭代次数
        "default_concurrency": 1,   # 默认并发数
        "timeout": 30,              # 单次查询超时（秒）
    },

    # 索引建议器配置
    "index_advisor": {
        "enabled": True,
        "min_improvement_threshold": 10,  # 最低改善百分比阈值
        "max_suggestions": 10,            # 最大建议数
    },

    # 数据库连接默认值
    "connection": {
        "db_type": "postgresql",    # 数据库类型
        "host": "localhost",
        "port": 5432,
        "database": "test",
        "user": "postgres",
        "password": "",
    },
}


# ===== 数据库引擎配置 JSON Schema =====
DATABASE_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "数据库引擎配置",
    "description": "数据库性能测试引擎的完整配置 Schema",
    "type": "object",
    "properties": {
        "engine_type": {
            "type": "string",
            "const": "database",
        },
        "pool": {
            "type": "object",
            "properties": {
                "min_size": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 5,
                },
                "max_size": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 20,
                },
                "idle_timeout": {
                    "type": "integer",
                    "minimum": 60,
                    "default": 300,
                },
                "health_check": {
                    "type": "integer",
                    "minimum": 10,
                    "default": 60,
                },
            },
            "description": "连接池配置",
        },
        "query": {
            "type": "object",
            "properties": {
                "explain": {
                    "type": "boolean",
                    "default": True,
                    "description": "启用执行计划分析",
                },
                "index_advice": {
                    "type": "boolean",
                    "default": True,
                    "description": "启用索引建议",
                },
                "default_iterations": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 100,
                },
                "default_concurrency": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1,
                },
                "timeout": {
                    "type": "number",
                    "minimum": 1,
                    "default": 30,
                },
            },
            "description": "查询配置",
        },
        "index_advisor": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "default": True,
                },
                "min_improvement_threshold": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 10,
                },
                "max_suggestions": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 10,
                },
            },
            "description": "索引建议器配置",
        },
        "connection": {
            "type": "object",
            "properties": {
                "db_type": {
                    "type": "string",
                    "enum": ["postgresql", "mysql", "mongodb", "redis"],
                    "default": "postgresql",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "database": {"type": "string"},
                "user": {"type": "string"},
                "password": {"type": "string"},
            },
            "required": ["db_type"],
            "description": "数据库连接配置",
        },
    },
    "additionalProperties": True,
}


# ===== 各数据库类型默认端口 =====
DB_TYPE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "postgresql": {"port": 5432, "user": "postgres", "database": "postgres"},
    "mysql": {"port": 3306, "user": "root", "database": "test"},
    "mongodb": {"port": 27017, "user": "", "database": "test"},
    "redis": {"port": 6379, "user": "", "database": "", "db": 0},
}


# ===== 测试用例配置 Schema =====
DB_TEST_CASE_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "数据库测试用例配置",
    "type": "object",
    "required": ["query"],
    "properties": {
        "query": {
            "type": "string",
            "description": "SQL 查询语句或 JSON 查询配置",
        },
        "iterations": {
            "type": "integer",
            "minimum": 1,
            "default": 100,
            "description": "基准测试迭代次数",
        },
        "concurrency": {
            "type": "integer",
            "minimum": 1,
            "default": 1,
            "description": "并发执行数",
        },
        "explain": {
            "type": "boolean",
            "description": "是否执行 EXPLAIN 分析",
        },
        "index_advice": {
            "type": "boolean",
            "description": "是否生成索引建议",
        },
        "params": {
            "description": "查询参数",
        },
    },
}


def get_defaults() -> Dict[str, Any]:
    """获取数据库引擎默认配置。"""
    return copy.deepcopy(DATABASE_DEFAULTS)


def get_schema() -> Dict[str, Any]:
    """获取数据库引擎配置 JSON Schema。"""
    return DATABASE_SCHEMA


def get_db_type_defaults(db_type: str) -> Dict[str, Any]:
    """获取指定数据库类型的默认连接参数。"""
    return DB_TYPE_DEFAULTS.get(db_type, {})


def get_test_case_schema() -> Dict[str, Any]:
    """获取测试用例配置 JSON Schema。"""
    return DB_TEST_CASE_SCHEMA
