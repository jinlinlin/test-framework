# -*- coding: utf-8 -*-
"""核心数据模型单元测试。

测试 TestCase、TestSuite、TestResult 等数据模型的创建与序列化。
"""
import pytest
from datetime import datetime
from dataclasses import asdict


class TestModels:
    """测试核心数据模型。"""

    def test_test_case_creation(self):
        """测试 TestCase 基本创建。"""
        from test_framework.core.models.test_case import TestCase

        tc = TestCase(
            id="TC-001",
            name="示例测试用例",
            test_type="functional",
            priority=5,
        )
        assert tc.id == "TC-001"
        assert tc.name == "示例测试用例"
        assert tc.test_type == "functional"
        assert tc.priority == 5

    def test_test_result_creation(self):
        """测试 TestResult 基本创建。"""
        from test_framework.core.models.test_result import TestResult

        result = TestResult(
            test_case_id="TC-001",
            status="passed",
            duration_ms=150.5,
        )
        assert result.test_case_id == "TC-001"
        assert result.status == "passed"
        assert result.duration_ms == 150.5

    def test_test_suite_composite(self):
        """测试 TestSuite 组合模式 — 添加子用例。"""
        from test_framework.core.models.test_suite import TestSuite
        from test_framework.core.models.test_case import TestCase

        suite = TestSuite(id="TS-001", name="套件A")
        tc1 = TestCase(id="TC-001", name="用例1")
        tc2 = TestCase(id="TC-002", name="用例2")

        suite.add_case(tc1)
        suite.add_case(tc2)

        assert len(suite.cases) == 2
        assert suite.cases[0].id == "TC-001"

    def test_execution_context(self):
        """测试 ExecutionContext 创建。"""
        from test_framework.core.models.execution_context import ExecutionContext

        ctx = ExecutionContext(
            environment="test",
            tags=["smoke", "regression"],
        )
        assert ctx.environment == "test"
        assert "smoke" in ctx.tags

    def test_enums(self):
        """测试枚举值定义。"""
        from test_framework.core.models.enums import TestStatus, TestType

        assert TestStatus.PASSED.value == "passed"
        assert TestType.FUNCTIONAL.value == "functional"
