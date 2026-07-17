"""
事件类型定义模块 — 框架标准事件类型的常量集合。

所有事件类型采用 '模块.动作' 的点号命名规范，
便于订阅者使用通配符匹配和日志分类。
"""
from __future__ import annotations


class EventTypes:
    """
    框架标准事件类型常量。

    事件类型采用 '主体.动作' 格式，例如：
    - 'test_plan.started'    表示测试计划开始执行
    - 'test_case.completed'  表示测试用例执行完成
    - 'engine.error'         表示引擎执行出错

    使用方式：
        event_bus.subscribe(EventTypes.TEST_CASE_COMPLETED, handler)
        event_bus.publish(Event(EventTypes.TEST_CASE_COMPLETED, ...))
    """

    # ---------- 测试计划事件 ----------
    TEST_PLAN_STARTED: str = "test_plan.started"
    TEST_PLAN_COMPLETED: str = "test_plan.completed"

    # ---------- 测试套件事件 ----------
    TEST_SUITE_STARTED: str = "test_suite.started"
    TEST_SUITE_COMPLETED: str = "test_suite.completed"

    # ---------- 测试用例事件 ----------
    TEST_CASE_STARTED: str = "test_case.started"
    TEST_CASE_COMPLETED: str = "test_case.completed"
    TEST_CASE_FAILED: str = "test_case.failed"
    TEST_CASE_SKIPPED: str = "test_case.skipped"

    # ---------- 引擎事件 ----------
    ENGINE_INITIALIZED: str = "engine.initialized"
    ENGINE_STARTED: str = "engine.started"
    ENGINE_COMPLETED: str = "engine.completed"
    ENGINE_ERROR: str = "engine.error"

    # ---------- 报告事件 ----------
    REPORT_GENERATED: str = "report.generated"
    REPORT_EXPORTED: str = "report.exported"

    # ---------- 插件事件 ----------
    PLUGIN_LOADED: str = "plugin.loaded"
    PLUGIN_ACTIVATED: str = "plugin.activated"
    PLUGIN_DEACTIVATED: str = "plugin.deactivated"

    # ---------- 系统事件 ----------
    FRAMEWORK_STARTED: str = "framework.started"
    FRAMEWORK_SHUTDOWN: str = "framework.shutdown"
