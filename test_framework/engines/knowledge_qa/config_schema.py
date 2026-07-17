"""
知识库问答引擎配置 Schema。

职责：定义知识库问答测试引擎的配置结构和默认值。
"""
from __future__ import annotations

import copy
from typing import Any, Dict


KNOWLEDGE_QA_DEFAULTS: Dict[str, Any] = {
    "engine_type": "knowledge_qa",
    "timeout": 60,
    "thresholds": {
        "min_score": 0.7,
        "min_retrieval": 0.5,
        "min_quality": 0.6,
    },
    "quality": {
        "semantic_weight": 0.4,
        "keyword_weight": 0.3,
        "length_weight": 0.3,
        "min_answer_length": 10,
        "max_answer_length": 5000,
    },
    "retrieval": {
        "default_k": 5,
        "ground_truth": {},
    },
    "rag_evaluation": {
        "faithfulness_weight": 0.4,
        "answer_relevancy_weight": 0.3,
        "context_precision_weight": 0.3,
    },
    "context_validation": {
        "min_context_count": 1,
        "max_context_count": 10,
        "min_chunk_length": 20,
        "max_duplicate_ratio": 0.3,
    },
}


KNOWLEDGE_QA_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "知识库问答引擎配置",
    "type": "object",
    "properties": {
        "engine_type": {"type": "string", "const": "knowledge_qa"},
        "timeout": {"type": "integer", "minimum": 5, "default": 60},
        "thresholds": {
            "type": "object",
            "properties": {
                "min_score": {"type": "number", "minimum": 0, "maximum": 1},
                "min_retrieval": {"type": "number", "minimum": 0, "maximum": 1},
                "min_quality": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
    },
    "additionalProperties": True,
}


def get_defaults() -> Dict[str, Any]:
    """获取知识库问答引擎默认配置。"""
    return copy.deepcopy(KNOWLEDGE_QA_DEFAULTS)


def get_schema() -> Dict[str, Any]:
    """获取配置 JSON Schema。"""
    return KNOWLEDGE_QA_SCHEMA
