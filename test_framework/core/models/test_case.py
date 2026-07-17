"""
测试用例模型 — 定义单个测试用例的数据结构。

TestCase 是框架中最小的可执行单元，
包含用例标识、测试类型、目标配置、超时/重试策略等信息。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .enums import Priority, TestType


@dataclass
class TestCase:
    """
    测试用例数据模型。

    每个 TestCase 代表一个独立的测试步骤，由引擎按序执行。

    Attributes:
        id: 用例唯一标识符（如 'api_test_001'）。
        name: 用例可读名称。
        test_type: 所属测试类型，对应引擎类型。
        target: 被测目标系统标识符，关联 TargetSystem.id。
        config: 用例级私有配置，覆盖引擎默认配置。
            例如 REST API 用例：{"method": "GET", "path": "/api/users", "expected_status": 200}
        tags: 标签列表，用于筛选和分组（如 ['smoke', 'regression']）。
        priority: 用例优先级，影响调度排序。
        timeout: 单用例执行超时时间（秒）。
        retries: 失败后最大重试次数。
        metadata: 扩展元数据（如用例描述、关联需求 ID 等）。
    """

    id: str
    name: str
    test_type: TestType
    target: str
    config: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    timeout: float = 60.0
    retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_tag(self, tag: str) -> bool:
        """
        检查用例是否包含指定标签。

        Args:
            tag: 标签名称。

        Returns:
            包含返回 True，否则返回 False。
        """
        return tag in self.tags

    def merge_config(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        将基础配置与用例私有配置合并，用例配置优先。

        Args:
            base_config: 引擎/套件级基础配置。

        Returns:
            合并后的完整配置字典。
        """
        merged = {**base_config}
        merged.update(self.config)
        return merged

    def to_dict(self) -> Dict[str, Any]:
        """将用例序列化为字典，便于 JSON 输出和持久化。"""
        return {
            "id": self.id,
            "name": self.name,
            "test_type": self.test_type.value,
            "target": self.target,
            "config": self.config,
            "tags": self.tags,
            "priority": self.priority.value,
            "timeout": self.timeout,
            "retries": self.retries,
            "metadata": self.metadata,
        }
