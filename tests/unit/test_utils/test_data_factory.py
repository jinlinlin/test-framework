# -*- coding: utf-8 -*-
"""DataFactory 单元测试。

测试随机数据生成工具。
"""
import pytest
import re


class TestDataFactory:
    """测试数据工厂。"""

    def test_random_string(self):
        """测试随机字符串生成。"""
        from test_framework.utils.data_factory import DataFactory

        factory = DataFactory()
        s = factory.random_string(length=10)
        assert isinstance(s, str)
        assert len(s) == 10

    def test_random_int(self):
        """测试随机整数生成。"""
        from test_framework.utils.data_factory import DataFactory

        factory = DataFactory()
        n = factory.random_int(min_val=1, max_val=100)
        assert isinstance(n, int)
        assert 1 <= n <= 100

    def test_random_email(self):
        """测试随机邮箱生成。"""
        from test_framework.utils.data_factory import DataFactory

        factory = DataFactory()
        email = factory.random_email()
        assert isinstance(email, str)
        assert "@" in email
        assert "." in email

    def test_random_uuid(self):
        """测试 UUID 生成。"""
        from test_framework.utils.data_factory import DataFactory

        factory = DataFactory()
        uid = factory.random_uuid()
        assert isinstance(uid, str)
        # UUID 格式: 8-4-4-4-12
        assert len(uid.replace("-", "")) == 32
