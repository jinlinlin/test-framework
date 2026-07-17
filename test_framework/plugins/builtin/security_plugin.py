"""
安全测试内置插件 — 为框架提供渗透测试与越权访问检测扩展。

职责：注册 penetration / auth_bypass / knowledge_qa 引擎，
      挂载安全扫描相关钩子。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from ...core.interfaces.pluggable import IPluggable

logger = logging.getLogger(__name__)


class SecurityTestPlugin(IPluggable):
    """
    安全测试内置插件。

    激活时：
    - 注册 penetration / auth_bypass / knowledge_qa 引擎
    - 挂载安全扫描前后钩子
    - 提供载荷生成器快捷方法

    使用示例::

        plugin = SecurityTestPlugin()
        plugin.activate()
    """

    # ------------------------------------------------------------------
    # IPluggable 实现
    # ------------------------------------------------------------------

    def get_plugin_info(self) -> Dict[str, Any]:
        """获取插件元信息。"""
        return {
            "id": "builtin_security_test",
            "name": "Security Test Plugin",
            "version": "1.0.0",
            "description": "内置渗透测试、越权检测、知识库质量评估插件",
            "author": "Uniplore Team",
            "dependencies": [],
        }

    def activate(self) -> None:
        """激活插件 — 注册安全引擎。"""
        logger.info("SecurityTestPlugin 正在激活...")

        self._register_engines()
        self._register_hooks()

        logger.info("SecurityTestPlugin 已激活")

    def deactivate(self) -> None:
        """停用插件 — 注销安全引擎。"""
        logger.info("SecurityTestPlugin 正在停用...")
        logger.info("SecurityTestPlugin 已停用")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _register_engines(self) -> None:
        """注册安全相关引擎。"""
        try:
            from ...core.events.event_bus import EventBus
            bus = EventBus()
            for engine_type in ("penetration", "auth_bypass", "knowledge_qa"):
                bus.publish("engine.register", engine_type=engine_type)
            logger.debug("已发布安全引擎注册事件")
        except Exception as e:
            logger.debug(f"注册安全引擎事件失败: {e}")

    def _register_hooks(self) -> None:
        """注册安全扫描钩子。"""
        logger.debug("安全测试钩子已准备就绪")

    # ------------------------------------------------------------------
    # 扩展方法
    # ------------------------------------------------------------------

    def get_payload_generators(self) -> Dict[str, Any]:
        """
        获取所有载荷生成器。

        Returns:
            载荷类型 -> 生成器实例的映射字典。
        """
        generators: Dict[str, Any] = {}
        try:
            from ...engines.penetration.payloads.sql_injection import SqlInjectionPayloads
            generators["sql_injection"] = SqlInjectionPayloads()
        except ImportError:
            pass
        try:
            from ...engines.penetration.payloads.xss import XssPayloads
            generators["xss"] = XssPayloads()
        except ImportError:
            pass
        try:
            from ...engines.penetration.payloads.path_traversal import PathTraversalPayloads
            generators["path_traversal"] = PathTraversalPayloads()
        except ImportError:
            pass
        try:
            from ...engines.penetration.payloads.command_injection import CommandInjectionPayloads
            generators["command_injection"] = CommandInjectionPayloads()
        except ImportError:
            pass
        return generators
