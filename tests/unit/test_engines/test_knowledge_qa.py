# -*- coding: utf-8 -*-
"""知识库 QA 引擎单元测试。

测试 KnowledgeQAEngine 和 QA 客户端、质量评估器。
"""
import pytest
from unittest.mock import MagicMock


class TestKnowledgeQAEngine:
    """测试知识库问答引擎。"""

    def test_engine_creation(self):
        """测试引擎实例化。"""
        from test_framework.engines.knowledge_qa.engine import KnowledgeQAEngine

        engine = KnowledgeQAEngine()
        assert engine is not None
        assert engine.engine_type == "knowledge_qa"

    def test_config_schema(self):
        """测试配置 Schema。"""
        from test_framework.engines.knowledge_qa.config_schema import KnowledgeQAConfig

        config = KnowledgeQAConfig()
        assert config is not None

    def test_quality_evaluator_init(self):
        """测试质量评估器初始化。"""
        from test_framework.engines.knowledge_qa.quality_evaluator import (
            QualityEvaluator,
        )

        evaluator = QualityEvaluator()
        assert evaluator is not None

    def test_retrieval_tester_init(self):
        """测试检索测试器初始化。"""
        from test_framework.engines.knowledge_qa.retrieval_tester import (
            RetrievalTester,
        )

        tester = RetrievalTester()
        assert tester is not None
