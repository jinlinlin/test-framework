"""
API回归测试套件。

包含完整的API回归测试用例。
"""
from __future__ import annotations

import logging

from ...core.models import TestCase, TestSuite

logger = logging.getLogger(__name__)


class RegressionAPISuite(TestSuite):
    """
    API回归测试套件

    包含完整的API回归测试用例。
    """

    def __init__(self) -> None:
        super().__init__(name="API回归测试", description="完整API回归测试")
        self._build_cases()

    def _build_cases(self) -> None:
        """构建测试用例"""
        self.add_case(TestCase(
            id="reg_api_001",
            name="用户列表API",
            description="验证用户列表接口",
            config={
                "method": "GET",
                "path": "/api/users",
                "expected_status": 200,
            },
        ))