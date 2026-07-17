"""
生命周期接口 — 定义组件完整生命周期的统一契约。

引擎、适配器、插件等长生命周期组件实现此接口，
确保资源在 init → start → stop → destroy 各阶段正确管理。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ILifecycle(ABC):
    """生命周期接口 — 组件完整生命周期管理契约。"""

    @abstractmethod
    async def init(self) -> None:
        """
        初始化阶段 — 分配资源、加载配置。

        在组件创建后、使用前调用一次。
        """

    @abstractmethod
    async def start(self) -> None:
        """
        启动阶段 — 激活组件功能。

        初始化完成后调用，组件进入可用状态。
        """

    @abstractmethod
    async def stop(self) -> None:
        """
        停止阶段 — 暂停组件功能，保留资源。

        可在需要时通过 start() 重新启动。
        """

    @abstractmethod
    async def destroy(self) -> None:
        """
        销毁阶段 — 释放所有资源。

        组件生命周期结束，不可再使用。
        """
