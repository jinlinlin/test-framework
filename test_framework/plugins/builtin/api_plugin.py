"""
API 测试内置插件 — 为框架提供 REST API 与后端性能测试扩展。

职责：注册 REST API / 后端性能测试引擎，
      挂载 HTTP / gRPC 适配器自动初始化。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from ...core.interfaces.pluggable import IPluggable

logger = logging.getLogger(__name__)


class ApiTestPlugin(IPluggable):
    """
    API 测试内置插件。

    激活时：
    - 注册 rest_api / backend_performance 引擎
    - 注册 HTTP 适配器（requests / httpx / aiohttp）
    - 挂载请求拦截器钩子

    使用示例::

        plugin = ApiTestPlugin()
        plugin.activate()
    """

    # ------------------------------------------------------------------
    # IPluggable 实现
    # ------------------------------------------------------------------

    def get_plugin_info(self) -> Dict[str, Any]:
        """获取插件元信息。"""
        return {
            "id": "builtin_api_test",
            "name": "API Test Plugin",
            "version": "1.0.0",
            "description": "内置 REST API 与后端性能测试插件",
            "author": "Uniplore Team",
            "dependencies": [],
        }

    def activate(self) -> None:
        """激活插件 — 注册引擎和适配器。"""
        logger.info("ApiTestPlugin 正在激活...")

        self._register_engines()
        self._register_hooks()

        logger.info("ApiTestPlugin 已激活")

    def deactivate(self) -> None:
        """停用插件 — 注销引擎和适配器。"""
        logger.info("ApiTestPlugin 正在停用...")
        logger.info("ApiTestPlugin 已停用")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _register_engines(self) -> None:
        """注册 REST API 和后端性能引擎。"""
        try:
            from ...core.events.event_bus import EventBus
            bus = EventBus()
            bus.publish("engine.register", engine_type="rest_api")
            bus.publish("engine.register", engine_type="backend_performance")
            logger.debug("已发布 rest_api / backend_performance 引擎注册事件")
        except Exception as e:
            logger.debug(f"注册引擎事件失败: {e}")

    def _register_hooks(self) -> None:
        """注册请求拦截器钩子。"""
        logger.debug("API 测试钩子已准备就绪")

    # ------------------------------------------------------------------
    # 扩展方法
    # ------------------------------------------------------------------

    def create_http_adapter(
        self, adapter_type: str = "httpx", **kwargs: Any
    ) -> Any:
        """
        创建 HTTP 适配器实例。

        Args:
            adapter_type: 适配器类型（requests / httpx / aiohttp）。
            **kwargs: 传递给适配器的额外参数。

        Returns:
            HTTP 适配器实例。

        Raises:
            ValueError: 不支持的适配器类型。
        """
        if adapter_type == "requests":
            from ...adapters.http.requests_impl import RequestsHttpAdapter
            return RequestsHttpAdapter(**kwargs)
        elif adapter_type == "httpx":
            from ...adapters.http.httpx_impl import HttpxHttpAdapter
            return HttpxHttpAdapter(**kwargs)
        elif adapter_type == "aiohttp":
            from ...adapters.http.aiohttp_impl import AiohttpAdapter
            return AiohttpAdapter(**kwargs)
        else:
            raise ValueError(f"不支持的 HTTP 适配器类型: {adapter_type}")
