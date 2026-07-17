"""
API冒烟测试套件。

包含核心API的基础测试用例。
"""
from __future__ import annotations

import logging

from ...core.models import TestCase, TestSuite

logger = logging.getLogger(__name__)


class SmokeAPISuite(TestSuite):
    """
    API冒烟测试套件

    包含核心API的基础测试用例。
    """

    def __init__(self) -> None:
        super().__init__(name="API冒烟测试", description="核心API基础测试")
        self._build_cases()

    def _build_cases(self) -> None:
        """构建测试用例"""
        self.add_case(TestCase(
            id="smoke_api_001",
            name="健康检查",
            description="验证健康检查接口",
            config={
                "method": "GET",
                "path": "/api/health",
                "expected_status": 200,
            },
        ))