"""
可执行接口 — 定义可执行命令的统一契约（命令模式）。

设计模式：命令模式（Command Pattern）
调度器和任务执行器使用此接口统一调度测试任务。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class IExecutable(ABC):
    """可执行接口 — 可被调度器执行的命令契约。"""

    @abstractmethod
    async def execute(self, context: Any) -> Dict[str, Any]:
        """
        执行命令。

        Args:
            context: 执行上下文（ExecutionContext 或 PipelineContext）。

        Returns:
            执行结果字典。
        """

    @abstractmethod
    async def cancel(self) -> None:
        """取消正在执行的命令。"""

    @abstractmethod
    def get_status(self) -> str:
        """
        获取命令当前状态。

        Returns:
            状态字符串：'pending' / 'running' / 'completed' / 'cancelled' / 'failed'。
        """
