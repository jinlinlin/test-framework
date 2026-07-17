# -*- coding: utf-8 -*-
"""IoC 容器单元测试。

测试 Container 的注册、解析、生命周期管理。
"""
import pytest
from unittest.mock import MagicMock


class TestContainer:
    """测试 IoC 容器核心功能。"""

    def test_register_and_resolve(self):
        """测试注册服务后能正确解析。"""
        from test_framework.core.container.container import Container

        # 重置单例
        container = Container()
        container._services.clear()
        container._instances.clear()

        # 注册一个简单服务
        mock_service = MagicMock()
        container.register("test_service", mock_service)

        # 解析并验证
        resolved = container.resolve("test_service")
        assert resolved is mock_service

    def test_resolve_nonexistent_raises(self):
        """测试解析不存在的服务时抛出异常。"""
        from test_framework.core.container.container import Container

        container = Container()
        container._services.clear()
        container._instances.clear()

        with pytest.raises(Exception):
            container.resolve("nonexistent_service")

    def test_has_service(self):
        """测试 has() 方法判断服务是否存在。"""
        from test_framework.core.container.container import Container

        container = Container()
        container._services.clear()
        container._instances.clear()

        assert container.has("some_service") is False

        container.register("some_service", MagicMock())
        assert container.has("some_service") is True

    def test_unregister_service(self):
        """测试注销已注册的服务。"""
        from test_framework.core.container.container import Container

        container = Container()
        container._services.clear()
        container._instances.clear()

        container.register("temp_service", MagicMock())
        assert container.has("temp_service") is True

        container.unregister("temp_service")
        assert container.has("temp_service") is False
