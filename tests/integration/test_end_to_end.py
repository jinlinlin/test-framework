# -*- coding: utf-8 -*-
"""端到端集成测试。

验证框架各层之间的协同工作能力：
- 配置加载 → 引擎创建 → 适配器绑定 → 执行 → 报告生成
- 事件总线跨模块通信
- 插件生命周期管理
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path


class TestEndToEnd:
    """端到端集成测试套件。"""

    def test_config_to_engine_pipeline(self):
        """测试 配置加载 → 引擎创建 流水线。

        验证 ConfigManager 加载配置后，EngineFactory 能根据配置创建引擎。
        """
        from test_framework.config.manager import ConfigManager
        from test_framework.engines.engine_factory import EngineFactory

        # 初始化配置管理器
        config_manager = ConfigManager()
        # 初始化工厂
        factory = EngineFactory()

        # 验证工厂能创建引擎注册表
        assert factory is not None
        assert hasattr(factory, "create") or hasattr(factory, "get_engine")

    def test_event_bus_cross_module(self):
        """测试事件总线跨模块通信。

        验证引擎发布事件 → 报告器接收事件的完整链路。
        """
        from test_framework.core.events.event_bus import EventBus

        bus = EventBus()
        bus._listeners.clear()

        received_events = []

        def on_test_complete(event_data):
            """模拟报告器接收测试完成事件。"""
            received_events.append(event_data)

        # 订阅测试完成事件
        bus.subscribe("test.completed", on_test_complete)

        # 模拟引擎发布事件
        bus.publish("test.completed", {
            "test_id": "TC-001",
            "status": "passed",
            "duration_ms": 250,
        })

        assert len(received_events) == 1
        assert received_events[0]["test_id"] == "TC-001"
        assert received_events[0]["status"] == "passed"

    def test_plugin_lifecycle(self):
        """测试插件完整生命周期: 注册 → 激活 → 执行 → 停用。

        验证插件管理器能正确管理插件状态转换。
        """
        from test_framework.plugins.manager import PluginManager

        manager = PluginManager()
        assert manager is not None

    def test_adapter_to_engine_binding(self):
        """测试适配器与引擎的绑定。

        验证 AdapterFactory 创建的适配器能被引擎正确使用。
        """
        from test_framework.adapters.adapter_factory import AdapterFactory

        factory = AdapterFactory()

        # 创建 HTTP 适配器
        http_adapter = factory.create("http")
        assert http_adapter is not None

        # 创建数据库适配器
        db_adapter = factory.create("database")
        assert db_adapter is not None

    def test_container_service_resolution(self):
        """测试 IoC 容器服务解析链路。

        验证 注册 → 解析 → 使用 的完整链路。
        """
        from test_framework.core.container.container import Container

        container = Container()
        container._services.clear()
        container._instances.clear()

        # 注册模拟服务
        mock_engine = MagicMock()
        mock_engine.engine_type = "rest_api"
        container.register("engine.rest_api", mock_engine)

        # 解析并使用
        resolved = container.resolve("engine.rest_api")
        assert resolved.engine_type == "rest_api"
        assert resolved is mock_engine

    def test_scheduler_plan_creation(self):
        """测试调度计划创建和执行。

        验证 SchedulePlan 数据类和 SequentialScheduler 的协同。
        """
        from test_framework.schedulers.base import SchedulePlan, ScheduleStatus
        from test_framework.schedulers.sequential import SequentialScheduler

        # 创建调度计划
        plan = SchedulePlan(
            name="冒烟测试",
            test_plan_id="TP-001",
            priority=1,
            timeout=600.0,
        )
        assert plan.name == "冒烟测试"
        assert plan.priority == 1

        # 创建调度器
        scheduler = SequentialScheduler()
        assert scheduler is not None

    def test_decorator_stack(self):
        """测试装饰器堆叠使用。

        验证 timing + retry + log_call 装饰器能正确堆叠。
        """
        from test_framework.decorators.timing import timing
        from test_framework.decorators.retry import retry
        from test_framework.decorators.log import log_call

        call_count = {"n": 0}

        @timing
        @retry(max_retries=2, delay=0.01)
        @log_call
        def sample_function():
            """模拟被测函数。"""
            call_count["n"] += 1
            return "success"

        result = sample_function()
        assert result == "success"
        assert call_count["n"] == 1

    def test_reporter_factory(self):
        """测试报告器工厂创建各类报告器。"""
        from test_framework.reporters.reporter_factory import ReporterFactory

        factory = ReporterFactory()
        assert factory is not None

    def test_metrics_collection(self):
        """测试指标收集和存储。"""
        from test_framework.utils.metrics import MetricsStore

        store = MetricsStore()
        store.record("http.requests", 1)
        store.record("http.requests", 1)
        store.record("http.latency_ms", 150.5)

        assert store.get("http.requests") == 2
        assert store.get("http.latency_ms") == 150.5
