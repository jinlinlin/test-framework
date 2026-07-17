"""
API契约测试套件。

包含API契约测试用例。
"""
from __future__ import annotations

import logging

from ...core.models import TestCase, TestSuite

logger = logging.getLogger(__name__)


class ContractAPISuite(TestSuite):
    """
    API契约测试套件

    包含API契约测试用例。
    """

    def __init__(self) -> None:
        super().__init__(name="API契约测试", description="API契约验证测试")
        self._build_cases()

    def _build_cases(self) -> None:
        """构建测试用例"""
        self.add_case(TestCase(
            id="contract_api_001",
            name="用户API契约",
            description="验证用户API响应结构",
            config={
                "method": "GET",
                "path": "/api/users/1",
                "expected_status": 200,
                "validate_schema": True,
            },
        ))