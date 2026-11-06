# -*- coding: utf-8 -*-
"""越权访问引擎单元测试。

测试 AuthBypassEngine 和越权策略。
"""
import pytest
from unittest.mock import MagicMock


class TestAuthBypassEngine:
    """测试越权访问测试引擎。"""

    def test_engine_creation(self, minimal_config, mock_container):
        """测试引擎实例化。"""
        from test_framework.engines.auth_bypass.engine import AuthBypassEngine

        # 引擎构造契约为 (config, container)，依赖注入不可无参
        engine = AuthBypassEngine(config=minimal_config, container=mock_container)
        assert engine is not None
        assert engine.engine_type == "auth_bypass"

    def test_config_schema(self):
        """测试配置 Schema。"""
        from test_framework.engines.auth_bypass.config_schema import AuthBypassConfig

        config = AuthBypassConfig()
        assert config is not None

    def test_role_escalation_strategy(self):
        """测试角色提权策略初始化。"""
        from test_framework.engines.auth_bypass.strategies.role_escalation import (
            RoleEscalationStrategy,
        )

        strategy = RoleEscalationStrategy()
        assert strategy is not None

    def test_token_replay_strategy(self):
        """测试 Token 重放策略初始化。"""
        from test_framework.engines.auth_bypass.strategies.token_replay import (
            TokenReplayStrategy,
        )

        strategy = TokenReplayStrategy()
        assert strategy is not None

    def test_auth_bypass_detector(self):
        """测试越权检测器初始化。"""
        from test_framework.engines.auth_bypass.auth_bypass_detector import (
            AuthBypassDetector,
        )

        detector = AuthBypassDetector()
        assert detector is not None
