"""
UI冒烟测试套件。

包含核心功能的基础测试用例。
"""
from __future__ import annotations

import logging

from ...core.models import TestCase, TestSuite

logger = logging.getLogger(__name__)


class SmokeUISuite(TestSuite):
    """
    UI冒烟测试套件

    包含核心功能的基础测试用例，用于快速验证系统基本功能。
    """

    def __init__(self) -> None:
        super().__init__(name="UI冒烟测试", description="核心功能基础测试")
        self._build_cases()

    def _build_cases(self) -> None:
        """构建测试用例"""
        self.add_case(TestCase(
            id="smoke_ui_001",
            name="登录页面访问",
            description="验证登录页面可正常访问",
            config={
                "steps": [
                    {"action": "navigate", "value": "/login"},
                    {"action": "assert_visible", "selector": '[data-testid="login-form"]'},
                ]
            },
        ))

        self.add_case(TestCase(
            id="smoke_ui_002",
            name="用户登录",
            description="验证用户可正常登录",
            config={
                "steps": [
                    {"action": "navigate", "value": "/login"},
                    {"action": "fill", "selector": '[name="username"]', "value": "testuser"},
                    {"action": "fill", "selector": '[name="password"]', "value": "password123"},
                    {"action": "click", "selector": 'button[type="submit"]'},
                    {"action": "assert_url", "value": "/dashboard"},
                ]
            },
        ))

        self.add_case(TestCase(
            id="smoke_ui_003",
            name="仪表板访问",
            description="验证仪表板可正常访问",
            config={
                "steps": [
                    {"action": "navigate", "value": "/dashboard"},
                    {"action": "assert_visible", "selector": '[data-testid="dashboard-container"]'},
                ]
            },
        ))