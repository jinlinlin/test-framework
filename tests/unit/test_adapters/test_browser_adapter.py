# -*- coding: utf-8 -*-
"""浏览器适配器单元测试。

测试 BrowserAdapter 和各浏览器实现。
"""
import pytest
from unittest.mock import MagicMock


class TestBrowserAdapter:
    """测试浏览器适配器。"""

    def test_adapter_creation(self):
        """测试适配器实例化。"""
        from test_framework.adapters.browser.adapter import BrowserAdapter

        adapter = BrowserAdapter()
        assert adapter is not None
        assert adapter.adapter_type == "browser"

    def test_adapter_factory(self):
        """测试适配器工厂创建浏览器适配器。"""
        from test_framework.adapters.adapter_factory import AdapterFactory

        factory = AdapterFactory()
        adapter = factory.create("browser")
        assert adapter is not None

    def test_playwright_impl_init(self):
        """测试 Playwright 实现初始化。"""
        from test_framework.adapters.browser.playwright_impl import PlaywrightImpl

        impl = PlaywrightImpl()
        assert impl is not None
