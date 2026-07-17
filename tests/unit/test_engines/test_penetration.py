# -*- coding: utf-8 -*-
"""渗透测试引擎单元测试。

测试 PenetrationEngine、扫描器和 Payload 生成器。
"""
import pytest
from unittest.mock import MagicMock


class TestPenetrationEngine:
    """测试渗透测试引擎。"""

    def test_engine_creation(self):
        """测试引擎实例化。"""
        from test_framework.engines.penetration.engine import PenetrationEngine

        engine = PenetrationEngine()
        assert engine is not None
        assert engine.engine_type == "penetration"

    def test_config_schema(self):
        """测试配置 Schema。"""
        from test_framework.engines.penetration.config_schema import (
            PenetrationConfig,
        )

        config = PenetrationConfig()
        assert config is not None

    def test_scanner_init(self):
        """测试扫描器初始化。"""
        from test_framework.engines.penetration.scanner import Scanner

        scanner = Scanner()
        assert scanner is not None

    def test_sql_injection_payloads(self):
        """测试 SQL 注入 Payload 生成。"""
        from test_framework.engines.penetration.payloads.sql_injection import (
            SQLInjectionPayload,
        )

        payload_gen = SQLInjectionPayload()
        payloads = payload_gen.generate()
        assert isinstance(payloads, list)
        assert len(payloads) > 0

    def test_xss_payloads(self):
        """测试 XSS Payload 生成。"""
        from test_framework.engines.penetration.payloads.xss import XSSPayload

        payload_gen = XSSPayload()
        payloads = payload_gen.generate()
        assert isinstance(payloads, list)
        assert len(payloads) > 0

    def test_detector_init(self):
        """测试漏洞检测器初始化。"""
        from test_framework.engines.penetration.detector import Detector

        detector = Detector()
        assert detector is not None
