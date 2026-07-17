"""
可测试接口 — 定义所有可执行测试对象的统一契约（模板模式）。

设计模式：模板模式（Template Method Pattern）
所有测试引擎必须实现此接口，遵循 setup → execute → teardown 生命周期。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class ITestable(ABC):
    """
    可测试接口 — 定义测试执行的标准生命周期。

    所有测试引擎和测试执行器必须实现此接口，
    确保框架可以统一调度不同类型的测试。
    """

    @abstractmethod
    async def setup(self) -> None:
        """
        测试前置准备。

        在执行测试前调用，用于初始化资源、建立连接、加载数据等。
        """

    @abstractmethod
    async def execute(self) -> Dict[str, Any]:
        """
        执行测试主体逻辑。

        Returns:
            测试执行的原始结果字典。
        """

    @abstractmethod
    async def teardown(self) -> None:
        """
        测试后置清理。

        无论测试是否成功都会调用，用于释放资源、关闭连接等。
        """

    @abstractmethod
    def get_result(self) -> Any:
        """
        获取格式化的测试结果。

        Returns:
            格式化的测试结果对象（通常为 TestResult）。
        """
