"""
测试结果模型 — 定义单个测试用例执行完毕后的结果数据。

TestResult 由引擎在 execute_case() 中创建，
包含执行状态、耗时、消息、详情、指标等信息。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .enums import TestStatus
from .test_metrics import TestMetrics


@dataclass
class TestResult:
    """
    测试结果数据模型。

    Attributes:
        case_id: 关联的测试用例 ID。
        status: 执行状态（PASS/FAIL/ERROR/SKIP）。
        duration: 执行耗时（秒）。
        message: 结果摘要消息（如 '断言失败：期望 200 实际 404'）。
        details: 详细结果数据（如 HTTP 响应体、数据库查询计划等）。
        metrics: 性能指标数据（可选，性能测试引擎填充）。
        timestamp: 结果生成时间戳。
        attachments: 附件文件路径列表（如截图、日志文件）。
        score: 评分制总分（0.0~1.0），Agent/AI 类用例适用；
            为 None 表示非评分类用例，回退到 status 判定。
        dimensions: 分维度得分字典（如 relevance/faithfulness/depth）。
        threshold: 通过阈值；score >= threshold 视为通过。
    """

    case_id: str
    status: TestStatus
    duration: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    metrics: Optional[TestMetrics] = None
    timestamp: datetime = field(default_factory=datetime.now)
    attachments: List[str] = field(default_factory=list)

    # ── 评分制扩展（Agent/AI 类引擎适用，均 Optional 默认 None，向后兼容）──
    score: Optional[float] = None
    dimensions: Dict[str, float] = field(default_factory=dict)
    threshold: Optional[float] = None

    @property
    def passed(self) -> bool:
        """判断用例是否通过。"""
        return self.status == TestStatus.PASS

    @property
    def failed(self) -> bool:
        """判断用例是否失败。"""
        return self.status == TestStatus.FAIL

    @property
    def passed_by_score(self) -> bool:
        """
        基于评分制判定是否通过。

        判据优先级：
            1. 评分类用例（score 与 threshold 均非 None）：以 score >= threshold 为准。
            2. 非评分类用例（score 或 threshold 为 None）：回退到 status == PASS，
               保证二元判定旧用例行为不变。

        Returns:
            True 表示用例通过，False 表示未通过。
        """
        if self.score is None or self.threshold is None:
            return self.status == TestStatus.PASS
        return self.score >= self.threshold

    def add_attachment(self, path: str) -> None:
        """添加附件路径。"""
        self.attachments.append(path)

    def to_dict(self) -> Dict[str, Any]:
        """将结果序列化为字典。

        评分制字段仅在任一非默认时写入，避免污染二元判定旧用例的输出。
        """
        result = {
            "case_id": self.case_id,
            "status": self.status.value,
            "duration": self.duration,
            "message": self.message,
            "details": self.details,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "timestamp": self.timestamp.isoformat(),
            "attachments": self.attachments,
        }
        if self.score is not None or self.threshold is not None or self.dimensions:
            result["score"] = self.score
            result["threshold"] = self.threshold
            result["dimensions"] = self.dimensions
            result["passed_by_score"] = self.passed_by_score
        return result
