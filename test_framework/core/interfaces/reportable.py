"""
可报告接口 — 定义可生成报告对象的统一契约。

所有引擎和报告器实现此接口，支持统一生成结构化报告数据。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class IReportable(ABC):
    """可报告接口 — 可生成报告数据的对象契约。"""

    @abstractmethod
    async def generate_report(self) -> Any:
        """
        生成完整报告对象。

        Returns:
            报告对象（通常为 TestReport 实例）。
        """

    @abstractmethod
    def get_report_data(self) -> Dict[str, Any]:
        """
        获取报告的原始数据字典。

        Returns:
            报告数据字典，可被报告器渲染。
        """
