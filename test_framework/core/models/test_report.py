"""
测试报告模型 — 定义一次完整测试运行的汇总报告。

TestReport 由引擎在测试计划执行完毕后生成，
包含汇总统计、全部结果列表、聚合指标和最终裁定。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from .enums import TestStatus, Verdict
from .test_metrics import TestMetrics
from .test_result import TestResult


@dataclass
class TestReport:
    """
    测试报告数据模型。

    Attributes:
        id: 报告唯一标识符。
        plan_id: 关联的测试计划 ID。
        generated_at: 报告生成时间。
        summary: 汇总统计字典（如 total, passed, failed, error, skip）。
        results: 所有测试结果列表。
        metrics: 聚合性能指标。
        verdict: 最终裁定（PASS/FAIL/WARN）。
    """

    id: str
    plan_id: str
    generated_at: datetime = field(default_factory=datetime.now)
    summary: Dict[str, Any] = field(default_factory=dict)
    results: List[TestResult] = field(default_factory=list)
    metrics: TestMetrics = field(default_factory=TestMetrics)
    verdict: Verdict = Verdict.PASS

    @classmethod
    def from_results(cls, report_id: str, plan_id: str, results: List[TestResult]) -> TestReport:
        """
        从测试结果列表自动构建报告。

        自动计算汇总统计和最终裁定。

        Args:
            report_id: 报告 ID。
            plan_id: 测试计划 ID。
            results: 所有测试结果列表。

        Returns:
            构建完成的 TestReport 实例。
        """
        # 统计各状态数量
        total = len(results)
        passed = sum(1 for r in results if r.status == TestStatus.PASS)
        failed = sum(1 for r in results if r.status == TestStatus.FAIL)
        errored = sum(1 for r in results if r.status == TestStatus.ERROR)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIP)

        # 计算总耗时
        total_duration = sum(r.duration for r in results)

        # 确定最终裁定
        if failed > 0 or errored > 0:
            verdict = Verdict.FAIL
        else:
            verdict = Verdict.PASS

        summary = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errored": errored,
            "skipped": skipped,
            "pass_rate": passed / total if total > 0 else 0.0,
            "total_duration": total_duration,
        }

        return cls(
            id=report_id,
            plan_id=plan_id,
            summary=summary,
            results=results,
            verdict=verdict,
        )

    def to_dict(self) -> Dict[str, Any]:
        """将报告序列化为字典。"""
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "generated_at": self.generated_at.isoformat(),
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results],
            "metrics": self.metrics.to_dict(),
            "verdict": self.verdict.value,
        }
