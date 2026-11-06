"""
Agent 行为测试引擎配置 Schema。

职责：定义薄壳引擎的配置结构与默认值，
      与 config/defaults/agent.yaml 保持同构（yaml 为部署侧来源，
      本模块为代码侧兜底，引擎构造时以二者合并结果运行）。
"""
from __future__ import annotations

import copy
from typing import Any, Dict


AGENT_BEHAVIOR_DEFAULTS: Dict[str, Any] = {
    "engine_type": "agent_behavior",
    "executor": "pytest",
    "cases_dir": "test-cases/agent",
    "data_dir": "test-data",
    "pytest": {
        "timeout": 1800,
        "markers": [],
        "extra_args": [],
        "use_xdist": False,
    },
    "scoring": {
        "default_threshold": 0.75,
        "use_deepeval": True,
        "dimensions": {
            "relevance": "deepeval",
            "faithfulness": "deepeval",
            "data_accuracy": "deepeval",
            "completeness": "deepeval",
            "depth": "judge",
            "key_concepts": "judge",
            "format": "judge",
            "instruction_follow": "judge",
        },
    },
    "artifacts": {
        "base_dir": "artifacts/agent_behavior",
        "summary": True,
    },
    "observability": {
        "langfuse_enabled": False,
    },
}


AGENT_BEHAVIOR_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Agent 行为测试引擎配置",
    "type": "object",
    "properties": {
        "engine_type": {"type": "string", "const": "agent_behavior"},
        "executor": {"type": "string", "enum": ["pytest"]},
        "cases_dir": {"type": "string"},
        "data_dir": {"type": "string"},
        "run_id": {"type": "string"},
        "target_url": {"type": "string"},
        "pytest": {
            "type": "object",
            "properties": {
                "timeout": {"type": "number", "minimum": 1},
                "markers": {"type": "array", "items": {"type": "string"}},
                "extra_args": {"type": "array", "items": {"type": "string"}},
                "use_xdist": {"type": "boolean"},
            },
        },
        "scoring": {
            "type": "object",
            "properties": {
                "default_threshold": {"type": "number", "minimum": 0, "maximum": 1},
                "use_deepeval": {"type": "boolean"},
                "dimensions": {"type": "object"},
            },
        },
    },
    "additionalProperties": True,
}


def get_defaults() -> Dict[str, Any]:
    """获取薄壳引擎默认配置（深拷贝，防止调用方污染模块级字典）。"""
    return copy.deepcopy(AGENT_BEHAVIOR_DEFAULTS)


def get_schema() -> Dict[str, Any]:
    """获取配置 JSON Schema。"""
    return AGENT_BEHAVIOR_SCHEMA
