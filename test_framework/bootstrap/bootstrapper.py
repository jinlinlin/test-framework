"""
启动器模块 — 框架总启动器（单例模式）。

设计模式：单例模式
职责：按顺序初始化框架所有子系统：
    环境检测 → 依赖检查 → IoC 容器初始化 → 配置加载 → 事件总线注册 → 就绪
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..core.container import Container
from ..core.events import EventBus, Event, EventTypes

from .classpath_loader import ClasspathLoader
from .dependency_checker import DependencyChecker
from .environment import EnvironmentDetector

logger = logging.getLogger(__name__)


@dataclass
class BootstrapStage:
    """
    启动阶段定义。

    Attributes:
        name: 阶段名称。
        action: 阶段执行的异步函数。
        cleanup: 阶段清理函数（shutdown 时逆序调用）。
    """

    name: str
    action: Callable
    cleanup: Optional[Callable] = None


class Bootstrapper:
    """
    框架总启动器（单例模式）。

    管理框架的完整启动和关闭流程，
    按注册顺序执行启动阶段，逆序执行清理。

    Attributes:
        _instance: 单例实例引用。
        _stages: 启动阶段列表。
        _container: IoC 容器。
        _event_bus: 事件总线。
    """

    _instance: Optional[Bootstrapper] = None

    def __new__(cls) -> Bootstrapper:
        """确保全局只有一个 Bootstrapper 实例。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """初始化启动器（仅首次生效）。"""
        if self._initialized:
            return
        self._initialized = True
        self._stages: List[BootstrapStage] = []
        self._container: Optional[Container] = None
        self._event_bus: Optional[EventBus] = None
        self._env_info = None

    def register_stage(self, stage: BootstrapStage) -> None:
        """
        注册自定义启动阶段。

        Args:
            stage: 启动阶段实例。
        """
        self._stages.append(stage)
        logger.debug(f"注册启动阶段: {stage.name}")

    async def boot(self) -> None:
        """
        执行框架启动流程。

        按顺序执行：
        1. 环境检测
        2. 依赖检查
        3. IoC 容器初始化
        4. 事件总线注册
        5. 自定义阶段
        """
        logger.info("框架启动中...")

        # 阶段 1：环境检测
        detector = EnvironmentDetector()
        self._env_info = detector.detect()
        warnings = detector.validate(self._env_info)
        for w in warnings:
            logger.warning(f"环境警告: {w}")
        logger.info(f"环境检测完成: OS={self._env_info.os}, Python={self._env_info.python_version}")

        # 阶段 2：依赖检查
        checker = DependencyChecker()
        checker.ensure_or_raise()
        logger.info("依赖检查通过")

        # 阶段 3：初始化 IoC 容器
        self._container = Container()
        logger.info("IoC 容器已初始化")

        # 阶段 4：注册事件总线
        self._event_bus = EventBus()
        self._container.register_instance(EventBus, self._event_bus)
        self._container.register_instance(Container, self._container)
        logger.info("事件总线已注册到容器")

        # 阶段 5：执行自定义阶段
        for stage in self._stages:
            try:
                logger.info(f"执行启动阶段: {stage.name}")
                await stage.action()
            except Exception as e:
                logger.error(f"启动阶段 {stage.name!r} 失败: {e}")
                raise

        # 发布框架启动完成事件
        await self._event_bus.publish(Event(
            type=EventTypes.FRAMEWORK_STARTED,
            source=self,
            data={"env": self._env_info.os, "python": self._env_info.python_version}
        ))
        logger.info("框架启动完成")

    async def shutdown(self) -> None:
        """
        优雅关闭框架 — 逆序执行各阶段的 cleanup。
        """
        logger.info("框架关闭中...")

        # 逆序执行清理
        for stage in reversed(self._stages):
            if stage.cleanup:
                try:
                    await stage.cleanup()
                    logger.debug(f"清理阶段完成: {stage.name}")
                except Exception as e:
                    logger.error(f"清理阶段 {stage.name!r} 失败: {e}")

        # 发布关闭事件
        if self._event_bus:
            await self._event_bus.publish(Event(
                type=EventTypes.FRAMEWORK_SHUTDOWN,
                source=self,
            ))

        logger.info("框架已关闭")

    @property
    def container(self) -> Optional[Container]:
        """获取 IoC 容器实例。"""
        return self._container

    @property
    def event_bus(self) -> Optional[EventBus]:
        """获取事件总线实例。"""
        return self._event_bus

    @property
    def environment_info(self):
        """获取环境信息。"""
        return self._env_info

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（仅测试用）。"""
        cls._instance = None
