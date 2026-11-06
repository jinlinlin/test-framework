# -*- coding: utf-8 -*-
"""数据库引擎单元测试。

测试 DatabaseEngine 和连接池、查询执行器。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestDatabaseEngine:
    """测试数据库测试引擎。"""

    def test_engine_creation(self, minimal_config, mock_container):
        """测试引擎实例化。"""
        from test_framework.engines.database.engine import DatabaseEngine

        # 引擎构造契约为 (config, container)，依赖注入不可无参
        engine = DatabaseEngine(config=minimal_config, container=mock_container)
        assert engine is not None
        assert engine.engine_type == "database"

    def test_connection_pool_init(self):
        """测试连接池初始化。"""
        from test_framework.engines.database.connection_pool import ConnectionPool

        pool = ConnectionPool(max_size=10)
        assert pool.max_size == 10

    def test_query_executor_init(self):
        """测试查询执行器初始化。"""
        from test_framework.engines.database.query_executor import QueryExecutor

        executor = QueryExecutor()
        assert executor is not None

    def test_explain_analyzer_init(self):
        """测试 EXPLAIN 分析器初始化。"""
        from test_framework.engines.database.explain_analyzer import ExplainAnalyzer

        analyzer = ExplainAnalyzer()
        assert analyzer is not None

    def test_index_advisor_init(self):
        """测试索引建议器初始化。"""
        from test_framework.engines.database.index_advisor import IndexAdvisor

        advisor = IndexAdvisor()
        assert advisor is not None
