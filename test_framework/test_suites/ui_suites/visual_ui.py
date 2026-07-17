"""
UI视觉回归测试套件。

包含页面截图对比测试用例。
"""
from __future__ import annotations

import logging

from ...core.models import TestCase, TestSuite

logger = logging.getLogger(__name__)


class VisualUISuite(TestSuite):
    """
    UI视觉回归测试套件

    包含页面截图对比测试用例。
    """

    def __init__(self) -> None:
        super().__init__(name="UI视觉回归测试", description="页面截图对比测试")
        self._build_cases()

    def _build_cases(self) -> None:
        """构建测试用例"""
        self.add_case(TestCase(
            id="visual_ui_001",
            name="登录页面视觉",
            description="验证登录页面视觉效果",
            config={
                "steps": [
                    {"action": "navigate", "value": "/login"},
                    {"action": "screenshot", "value": "screenshots/login_page.png"},
                ]
            },
        ))

        self.add_case(TestCase(
            id="visual_ui_002",
            name="仪表板视觉",
            description="验证仪表板视觉效果",
            config={
                "steps": [
                    {"action": "navigate", "value": "/dashboard"},
                    {"action": "screenshot", "value": "screenshots/dashboard.png"},
                ]
            },
        ))