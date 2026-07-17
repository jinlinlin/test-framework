# -*- coding: utf-8 -*-
"""异常体系单元测试。

测试 FrameworkException 层级结构和自定义异常。
"""
import pytest


class TestExceptions:
    """测试框架异常体系。"""

    def test_framework_exception_base(self):
        """测试 FrameworkException 基类。"""
        from test_framework.core.exceptions.framework_exception import FrameworkException

        exc = FrameworkException("基础框架异常")
        assert str(exc) == "基础框架异常"
        assert isinstance(exc, Exception)

    def test_config_exception(self):
        """测试 ConfigException 继承关系。"""
        from test_framework.core.exceptions.config_exception import ConfigException
        from test_framework.core.exceptions.framework_exception import FrameworkException

        exc = ConfigException("配置缺失: database.host")
        assert isinstance(exc, FrameworkException)
        assert "配置缺失" in str(exc)

    def test_execution_exception(self):
        """测试 ExecutionException。"""
        from test_framework.core.exceptions.execution_exception import ExecutionException
        from test_framework.core.exceptions.framework_exception import FrameworkException

        exc = ExecutionException("执行超时")
        assert isinstance(exc, FrameworkException)

    def test_adapter_exception(self):
        """测试 AdapterException。"""
        from test_framework.core.exceptions.adapter_exception import AdapterException
        from test_framework.core.exceptions.framework_exception import FrameworkException

        exc = AdapterException("适配器连接失败")
        assert isinstance(exc, FrameworkException)

    def test_plugin_exception(self):
        """测试 PluginException。"""
        from test_framework.core.exceptions.plugin_exception import PluginException
        from test_framework.core.exceptions.framework_exception import FrameworkException

        exc = PluginException("插件加载失败")
        assert isinstance(exc, FrameworkException)
