"""
测试套件模型 — 支持嵌套组合的用例集合（组合模式）。

设计模式：组合模式（Composite Pattern）
TestSuite 可包含 TestCase 或其他 TestSuite，
形成树形结构，支持递归展平获取全部用例。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Union

from .test_case import TestCase


@dataclass
class TestSuite:
    """
    测试套件 — 测试用例的逻辑分组容器（组合模式）。

    支持嵌套：一个 TestSuite 可包含子 TestSuite 或 TestCase，
    通过 get_all_cases() 递归展平获取全部叶子用例。

    Attributes:
        id: 套件唯一标识符。
        name: 套件可读名称（如 '用户接口回归测试'）。
        children: 子节点列表，可以是嵌套的 TestSuite 或叶子 TestCase。
        metadata: 扩展元数据（如套件描述、负责人等）。
    """

    id: str
    name: str
    children: List[Union[TestSuite, TestCase]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add(self, child: Union[TestSuite, TestCase]) -> None:
        """
        添加子节点（用例或子套件）。

        Args:
            child: 要添加的 TestCase 或 TestSuite 实例。
        """
        self.children.append(child)

    def remove(self, child_id: str) -> bool:
        """
        根据 ID 移除直接子节点。

        Args:
            child_id: 要移除的子节点 ID。

        Returns:
            成功移除返回 True，未找到返回 False。
        """
        for i, child in enumerate(self.children):
            if child.id == child_id:
                self.children.pop(i)
                return True
        return False

    def get_all_cases(self) -> List[TestCase]:
        """
        递归展平获取套件下所有叶子测试用例。

        遍历所有子节点：
        - 如果是 TestCase，直接加入结果列表
        - 如果是 TestSuite，递归获取其子用例

        Returns:
            所有叶子 TestCase 的列表（按深度优先顺序）。
        """
        cases: List[TestCase] = []
        for child in self.children:
            if isinstance(child, TestCase):
                cases.append(child)
            elif isinstance(child, TestSuite):
                cases.extend(child.get_all_cases())
        return cases

    def count(self) -> int:
        """
        递归统计套件下所有叶子用例的总数。

        Returns:
            叶子 TestCase 的总数量。
        """
        return len(self.get_all_cases())

    def get_suite_tree(self, indent: int = 0) -> str:
        """
        生成套件树形结构的文本表示（调试用）。

        Args:
            indent: 当前缩进层级。

        Returns:
            树形结构的多行字符串。
        """
        prefix = "  " * indent
        lines = [f"{prefix}├── [{self.id}] {self.name} ({self.count()} cases)"]
        for child in self.children:
            if isinstance(child, TestSuite):
                lines.append(child.get_suite_tree(indent + 1))
            else:
                lines.append(f"{prefix}  ├── [{child.id}] {child.name}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """将套件序列化为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "children": [
                child.to_dict() for child in self.children
            ],
            "metadata": self.metadata,
            "total_cases": self.count(),
        }
