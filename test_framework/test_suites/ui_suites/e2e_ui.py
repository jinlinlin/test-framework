"""
UI端到端测试套件。

包含完整的端到端业务流程测试。
"""
from __future__ import annotations

import logging

from ...core.models import TestCase, TestSuite

logger = logging.getLogger(__name__)


class E2EUISuite(TestSuite):
    """
    UI端到端测试套件

    包含完整的端到端业务流程测试。
    """

    def __init__(self) -> None:
        super().__init__(name="UI端到端测试", description="完整业务流程测试")
        self._build_cases()

    def _build_cases(self) -> None:
        """构建测试用例"""
        self.add_case(TestCase(
            id="e2e_ui_001",
            name="完整登录流程",
            description="验证完整的用户登录流程",
            config={
                "steps": [
                    {"action": "navigate", "value": "/login"},
                    {"action": "fill", "selector": '[name="username"]', "value": "testuser"},
                    {"action": "fill", "selector": '[name="password"]', "value": "password123"},
                    {"action": "click", "selector": 'button[type="submit"]'},
                    {"action": "wait_for_url", "value": "/dashboard"},
                    {"action": "assert_visible", "selector": '[data-testid="welcome-message"]'},
                ]
            },
        ))