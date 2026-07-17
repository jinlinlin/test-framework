# -*- coding: utf-8 -*-
"""Validator 单元测试。

测试数据校验工具。
"""
import pytest


class TestValidator:
    """测试校验器工具类。"""

    def test_is_email_valid(self):
        """测试邮箱格式校验。"""
        from test_framework.utils.validation import Validator

        validator = Validator()
        assert validator.is_email("user@example.com") is True
        assert validator.is_email("invalid-email") is False
        assert validator.is_email("") is False

    def test_is_url_valid(self):
        """测试 URL 格式校验。"""
        from test_framework.utils.validation import Validator

        validator = Validator()
        assert validator.is_url("https://example.com") is True
        assert validator.is_url("http://localhost:8080/path") is True
        assert validator.is_url("not-a-url") is False

    def test_is_json_string(self):
        """测试 JSON 字符串校验。"""
        from test_framework.utils.validation import Validator

        validator = Validator()
        assert validator.is_json('{"key": "value"}') is True
        assert validator.is_json("[1, 2, 3]") is True
        assert validator.is_json("not json") is False

    def test_is_uuid(self):
        """测试 UUID 格式校验。"""
        from test_framework.utils.validation import Validator

        validator = Validator()
        assert validator.is_uuid("550e8400-e29b-41d4-a716-446655440000") is True
        assert validator.is_uuid("not-a-uuid") is False

    def test_is_port_valid(self):
        """测试端口号校验。"""
        from test_framework.utils.validation import Validator

        validator = Validator()
        assert validator.is_port(80) is True
        assert validator.is_port(8080) is True
        assert validator.is_port(0) is False
        assert validator.is_port(70000) is False
