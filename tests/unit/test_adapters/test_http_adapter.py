# -*- coding: utf-8 -*-
"""HTTP 适配器单元测试。

测试 HttpAdapter 和各 HTTP 客户端实现。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestHttpAdapter:
    """测试 HTTP 适配器。"""

    def test_adapter_creation(self):
        """测试适配器实例化。"""
        from test_framework.adapters.http.adapter import HttpAdapter

        adapter = HttpAdapter()
        assert adapter is not None
        assert adapter.adapter_type == "http"

    def test_adapter_factory(self):
        """测试适配器工厂创建 HTTP 适配器。"""
        from test_framework.adapters.adapter_factory import AdapterFactory

        factory = AdapterFactory()
        adapter = factory.create("http")
        assert adapter is not None

    def test_adapter_base_interface(self):
        """测试适配器实现 IAdaptable 接口。"""
        from test_framework.adapters.http.adapter import HttpAdapter
        from test_framework.core.interfaces.adaptable import IAdaptable

        adapter = HttpAdapter()
        assert isinstance(adapter, IAdaptable)

    def test_requests_impl_init(self):
        """测试 Requests 实现初始化。"""
        from test_framework.adapters.http.requests_impl import RequestsImpl

        impl = RequestsImpl()
        assert impl is not None
