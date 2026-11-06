# -*- coding: utf-8 -*-
"""后端性能引擎单元测试。

测试 BackendPerformanceEngine 的初始化和资源监控。
"""
import pytest
from unittest.mock import MagicMock, patch


class TestBackendPerformanceEngine:
    """测试后端性能测试引擎。"""

    def test_engine_creation(self, minimal_config, mock_container):
        """测试引擎实例化。"""
        from test_framework.engines.backend_performance.engine import (
            BackendPerformanceEngine,
        )

        # 引擎构造契约为 (config, container)，依赖注入不可无参
        engine = BackendPerformanceEngine(config=minimal_config, container=mock_container)
        assert engine is not None
        assert engine.engine_type == "backend_performance"

    def test_config_schema(self):
        """测试后端性能配置 Schema。"""
        from test_framework.engines.backend_performance.config_schema import (
            BackendPerformanceConfig,
        )

        config = BackendPerformanceConfig()
        assert config.concurrent_users >= 1

    def test_resource_collector_init(self):
        """测试 ResourceCollector 初始化。"""
        from test_framework.engines.backend_performance.resource_collector import (
            ResourceCollector,
        )

        collector = ResourceCollector()
        assert collector is not None

    def test_container_monitor_init(self):
        """测试 ContainerMonitor 初始化。"""
        from test_framework.engines.backend_performance.container_monitor import (
            ContainerMonitor,
        )

        monitor = ContainerMonitor()
        assert monitor is not None
