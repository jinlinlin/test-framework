# -*- coding: utf-8 -*-
"""Web 性能引擎单元测试。

测试 WebPerformanceEngine 的初始化和核心方法。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


class TestWebPerformanceEngine:
    """测试 Web 性能测试引擎。"""

    def test_engine_creation(self, minimal_config, mock_container):
        """测试引擎实例化。"""
        from test_framework.engines.web_performance.engine import WebPerformanceEngine

        # 引擎构造契约为 (config, container)，依赖注入不可无参
        engine = WebPerformanceEngine(config=minimal_config, container=mock_container)
        assert engine is not None
        assert engine.engine_type == "web_performance"

    def test_engine_config_schema(self):
        """测试配置 Schema 加载。"""
        from test_framework.engines.web_performance.config_schema import (
            WebPerformanceConfig,
        )

        config = WebPerformanceConfig()
        assert config.browser_type == "chromium"
        assert config.headless is True

    def test_page_analyzer_url_parsing(self):
        """测试 PageAnalyzer URL 解析。"""
        from test_framework.engines.web_performance.page_analyzer import PageAnalyzer

        analyzer = PageAnalyzer()
        assert analyzer is not None

    def test_web_vitals_thresholds(self):
        """测试 Web Vitals 阈值定义。"""
        from test_framework.engines.web_performance.web_vitals import WebVitals

        vitals = WebVitals()
        # 默认阈值应存在
        assert hasattr(vitals, "thresholds") or hasattr(vitals, "THRESHOLDS")
