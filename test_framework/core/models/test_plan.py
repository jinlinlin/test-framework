"""
测试计划模型 — 定义一次完整测试运行的顶层编排结构。

TestPlan 包含多个 TestSuite，是调度器的输入单元。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .test_case import TestCase
from .test_suite import TestSuite


@dataclass
class TestPlan:
    """
    测试计划 — 测试运行的顶层编排单元。

    一个 TestPlan 包含多个 TestSuite，由调度器按策略执行。
    支持全局配置、定时调度、并行执行等特性。

    Attributes:
        id: 计划唯一标识符。
        name: 计划可读名称（如 'v2.1 全量回归测试'）。
        suites: 测试套件列表，按执行顺序排列。
        global_config: 全局配置，覆盖各引擎默认配置。
        schedule: cron 表达式，用于定时调度（如 '0 2 * * *' 表示每天凌晨 2 点）。
        parallel: 是否并行执行多个套件。
        environment: 运行环境名称（dev/test/staging/production）。
        metadata: 扩展元数据。
    """

    id: str
    name: str
    suites: List[TestSuite] = field(default_factory=list)
    global_config: Dict[str, Any] = field(default_factory=dict)
    schedule: Optional[str] = None
    parallel: bool = False
    environment: str = "dev"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_suite(self, suite: TestSuite) -> None:
        """添加测试套件到计划。"""
        self.suites.append(suite)

    def get_all_cases(self) -> List[TestCase]:
        """递归展平获取计划下所有用例。"""
        cases: List[TestCase] = []
        for suite in self.suites:
            cases.extend(suite.get_all_cases())
        return cases

    def total_cases(self) -> int:
        """获取计划中所有用例的总数。"""
        return sum(suite.count() for suite in self.suites)

    def to_dict(self) -> Dict[str, Any]:
        """将计划序列化为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "suites": [s.to_dict() for s in self.suites],
            "global_config": self.global_config,
            "schedule": self.schedule,
            "parallel": self.parallel,
            "environment": self.environment,
            "metadata": self.metadata,
            "total_cases": self.total_cases(),
        }
