"""
引擎注册表 — 维护引擎的元数据信息。

职责：支持插件式注册/发现引擎，
      存储引擎的描述、版本、依赖等元数据。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..core.models.enums import TestType

logger = logging.getLogger(__name__)


class EngineRegistry:
    """
    引擎注册表。

    存储各引擎的元数据（名称、描述、版本、配置 Schema 路径等），
    供框架启动时展示可用引擎列表。

    Attributes:
        _metadata: 测试类型 → 元数据字典 的映射。
    """

    _metadata: Dict[TestType, Dict[str, Any]] = {}

    @classmethod
    def register(cls, engine_type: TestType, metadata: Dict[str, Any]) -> None:
        """
        注册引擎元数据。

        Args:
            engine_type: 测试类型。
            metadata: 元数据字典（包含 name, description, version 等）。
        """
        cls._metadata[engine_type] = metadata
        logger.debug(f"注册引擎元数据: {engine_type.value}")

    @classmethod
    def get_metadata(cls, engine_type: TestType) -> Dict[str, Any]:
        """
        获取引擎元数据。

        Args:
            engine_type: 测试类型。

        Returns:
            元数据字典，不存在时返回空字典。
        """
        return cls._metadata.get(engine_type, {})

    @classmethod
    def list_all(cls) -> Dict[TestType, Dict[str, Any]]:
        """
        列出所有已注册的引擎元数据。

        Returns:
            测试类型 → 元数据的字典。
        """
        return dict(cls._metadata)


# ===== 注册内置引擎元数据 =====
EngineRegistry.register(TestType.WEB_PERFORMANCE, {
    "name": "网页性能测试引擎",
    "description": "基于 Playwright 的网页性能测试，支持 Web Vitals 采集和 Lighthouse 审计",
    "version": "1.0.0",
    "config_schema": "config/defaults/web.yaml",
})

EngineRegistry.register(TestType.BACKEND_PERFORMANCE, {
    "name": "后端性能测试引擎",
    "description": "HTTP/gRPC 负载施压，支持多语言后端监控（JVM/Go/Node/Python/Container）",
    "version": "1.0.0",
    "config_schema": "config/defaults/backend.yaml",
})

EngineRegistry.register(TestType.UI_AUTOMATION, {
    "name": "UI自动化测试引擎",
    "description": "基于 Playwright 的UI自动化测试，支持多浏览器、网络拦截、截图、视频录制",
    "version": "1.0.0",
    "config_schema": "config/defaults/web.yaml",
})
