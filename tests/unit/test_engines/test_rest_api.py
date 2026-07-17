# -*- coding: utf-8 -*-
"""REST API 引擎单元测试。

测试 RestApiEngine 和请求构建器、响应验证器。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestRestApiEngine:
    """测试 REST API 测试引擎。"""

    def test_engine_creation(self):
        """测试引擎实例化。"""
        from test_framework.engines.rest_api.engine import RestApiEngine

        engine = RestApiEngine()
        assert engine is not None
        assert engine.engine_type == "rest_api"

    def test_request_builder_fluent(self):
        """测试 RequestBuilder 建造者模式链式调用。"""
        from test_framework.engines.rest_api.request_builder import RequestBuilder

        builder = RequestBuilder()
        req = (
            builder
            .set_method("POST")
            .set_url("http://localhost/api/users")
            .set_headers({"Content-Type": "application/json"})
            .set_body({"name": "test"})
            .build()
        )
        assert req.method == "POST"
        assert "localhost" in req.url

    def test_response_validator_strategy(self):
        """测试 ResponseValidator 策略模式。"""
        from test_framework.engines.rest_api.response_validator import ResponseValidator

        validator = ResponseValidator()
        assert validator is not None

    def test_schema_validator_init(self):
        """测试 SchemaValidator 初始化。"""
        from test_framework.engines.rest_api.schema_validator import SchemaValidator

        sv = SchemaValidator()
        assert sv is not None
