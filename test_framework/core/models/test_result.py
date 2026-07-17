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
    """

    case_id: str
    status: TestStatus
    duration: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    metrics: Optional[TestMetrics] = None
    timestamp: datetime = field(default_factory=datetime.now)
    attachments: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """判断用例是否通过。"""
        return self.status == TestStatus.PASS

    @property
    def failed(self) -> bool:
        """判断用例是否失败。"""
        return self.status == TestStatus.FAIL

    def add_attachment(self, path: str) -> None:
        """添加附件路径。"""
        self.attachments.append(path)

    def to_dict(self) -> Dict[str, Any]:
        """将结果序列化为字典。"""
        return {
            "case_id": self.case_id,
            "status": self.status.value,
            "duration": self.duration,
            "message": self.message,
            "details": self.details,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "timestamp": self.timestamp.isoformat(),
            "attachments": self.attachments,
        }
