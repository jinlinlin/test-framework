"""
UI回归测试套件。

包含完整的回归测试用例。
"""
from __future__ import annotations

import logging

from ...core.models import TestCase, TestSuite

logger = logging.getLogger(__name__)


class RegressionUISuite(TestSuite):
    """
    UI回归测试套件

    包含完整的回归测试用例，用于验证系统变更后功能正常。
    """

    def __init__(self) -> None:
        super().__init__(name="UI回归测试", description="完整功能回归测试")
        self._build_cases()

    def _build_cases(self) -> None:
        """构建测试用例"""
        self.add_case(TestCase(
            id="reg_ui_001",
            name="用户管理页面",
            description="验证用户管理页面功能",
            config={
                "steps": [
                    {"action": "navigate", "value": "/users"},
                    {"action": "assert_visible", "selector": '[data-testid="user-list"]'},
                ]
            },
        ))

        self.add_case(TestCase(
            id="reg_ui_002",
            name="用户搜索",
            description="验证用户搜索功能",
            config={
                "steps": [
                    {"action": "navigate", "value": "/users"},
                    {"action": "fill", "selector": '[data-testid="user-search"]', "value": "test"},
                    {"action": "press", "selector": '[data-testid="user-search"]', "key": "Enter"},
                ]
            },
        ))