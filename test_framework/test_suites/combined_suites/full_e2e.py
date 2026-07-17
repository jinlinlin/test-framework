"""
完整端到端测试套件。

包含UI和API的组合测试用例。
"""
from __future__ import annotations

import logging

from ...core.models import TestCase, TestSuite
from ..ui_suites import SmokeUISuite
from ..api_suites import SmokeAPISuite

logger = logging.getLogger(__name__)


class FullE2ESuite(TestSuite):
    """
    完整端到端测试套件

    包含UI和API的组合测试用例。
    """

    def __init__(self) -> None:
        super().__init__(name="完整端到端测试", description="UI+API组合测试")
        self._build_cases()

    def _build_cases(self) -> None:
        """构建测试用例"""
        ui_suite = SmokeUISuite()
        api_suite = SmokeAPISuite()

        for case in ui_suite.get_all_cases():
            self.add_case(case)

        for case in api_suite.get_all_cases():
            self.add_case(case)