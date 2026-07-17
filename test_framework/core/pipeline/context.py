"""
管道上下文模块 — 管道执行期间各阶段共享的数据容器。

PipelineContext 在管道的各 Stage/Filter/Hook 之间传递，
承载执行上下文、阶段间数据和错误信息。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineContext:
    """
    管道上下文 — 管道执行期间的共享数据容器。

    各 Stage 通过 context.data 读写中间数据，
    通过 context.errors 记录执行错误。

    Attributes:
        data: 阶段间传递的共享数据字典。
        errors: 执行过程中收集的异常列表。
        current_stage: 当前正在执行的阶段名称。
        is_aborted: 是否中止管道执行。
        metadata: 附加元数据。
    """

    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[Exception] = field(default_factory=list)
    current_stage: str = ""
    is_aborted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        """设置数据项。"""
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取数据项。"""
        return self.data.get(key, default)

    def add_error(self, error: Exception) -> None:
        """添加执行错误。"""
        self.errors.append(error)

    def abort(self) -> None:
        """中止管道执行。"""
        self.is_aborted = True

    @property
    def has_errors(self) -> bool:
        """是否有执行错误。"""
        return len(self.errors) > 0
