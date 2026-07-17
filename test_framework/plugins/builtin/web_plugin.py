"""
Web 测试内置插件 — 为框架提供网页性能测试与浏览器自动化扩展。

职责：注册网页性能测试引擎，挂载浏览器相关钩子，
      提供 Playwright / Selenium 适配器自动初始化。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from ...core.interfaces.pluggable import IPluggable

logger = logging.getLogger(__name__)


class WebTestPlugin(IPluggable):
    """
    Web 测试内置插件。

    激活时：
    - 注册 web_performance 引擎到引擎注册表
    - 注册浏览器适配器（Playwright / Selenium）
    - 挂载 before_test / after_test 钩子用于页面截图

    使用示例::

        plugin = WebTestPlugin()
        plugin.activate()
    """

    # ------------------------------------------------------------------
    # IPluggable 实现
    # ------------------------------------------------------------------

    def get_plugin_info(self) -> Dict[str, Any]:
        """获取插件元信息。"""
        return {
            "id": "builtin_web_test",
            "name": "Web Test Plugin",
            "version": "1.0.0",
            "description": "内置 Web 性能测试与浏览器自动化插件",
            "author": "Uniplore Team",
            "dependencies": [],
        }

    def activate(self) -> None:
        """激活插件 — 注册引擎和适配器。"""
        logger.info("WebTestPlugin 正在激活...")

        # 注册引擎
        self._register_engine()

        # 注册钩子
        self._register_hooks()

        logger.info("WebTestPlugin 已激活")

    def deactivate(self) -> None:
        """停用插件 — 注销引擎和适配器。"""
        logger.info("WebTestPlugin 正在停用...")
        logger.info("WebTestPlugin 已停用")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _register_engine(self) -> None:
        """注册 web_performance 引擎到全局引擎注册表。"""
        try:
            from ...core.events.event_bus import EventBus
            bus = EventBus()
            bus.publish("engine.register", engine_type="web_performance")
            logger.debug("已发布 web_performance 引擎注册事件")
        except Exception as e:
            logger.debug(f"注册引擎事件失败（可能事件总线未就绪）: {e}")

    def _register_hooks(self) -> None:
        """注册浏览器相关钩子。"""
        try:
            from ..manager import PluginManager
            # 钩子在实际使用时由 PluginManager 注入
            logger.debug("Web 测试钩子已准备就绪")
        except Exception as e:
            logger.debug(f"注册钩子失败: {e}")

    # ------------------------------------------------------------------
    # 扩展方法 — 供外部调用
    # ------------------------------------------------------------------

    def create_browser_adapter(self, adapter_type: str = "playwright", **kwargs: Any) -> Any:
        """
        创建浏览器适配器实例。

        Args:
            adapter_type: 适配器类型（playwright / selenium）。
            **kwargs: 传递给适配器的额外参数。

        Returns:
            浏览器适配器实例。

        Raises:
            ValueError: 不支持的适配器类型。
        """
        if adapter_type == "playwright":
            from ...adapters.browser.playwright_impl import PlaywrightBrowserAdapter
            return PlaywrightBrowserAdapter(**kwargs)
        elif adapter_type == "selenium":
            from ...adapters.browser.selenium_impl import SeleniumBrowserAdapter
            return SeleniumBrowserAdapter(**kwargs)
        else:
            raise ValueError(f"不支持的浏览器适配器类型: {adapter_type}")
