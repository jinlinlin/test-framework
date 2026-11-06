# -*- coding: utf-8 -*-
"""引擎单元测试共享夹具。

引擎基类构造契约为 (config, container)（依赖注入模式），
所有引擎测试必须显式传入这两个参数：

- mock_container: MagicMock 模拟 IoC 容器，隔离真实容器的注册逻辑；
- minimal_config: 最小可用配置字典，仅含通用字段，
  各引擎专属字段可在测试内覆盖补充。

新增引擎测试直接复用这两个夹具，不要无参构造引擎实例。
"""
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_container():
    """模拟 IoC 容器（resolve 返回可用 mock，不抛异常）。"""
    container = MagicMock()
    container.resolve.return_value = MagicMock()
    return container


@pytest.fixture
def minimal_config():
    """最小可用配置。"""
    return {
        "target_url": "http://example.com",
        "timeout": 30,
    }
