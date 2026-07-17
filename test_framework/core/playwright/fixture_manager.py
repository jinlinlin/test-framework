"""
夹具管理器

管理测试夹具，包括测试数据、测试用户、测试凭证等。
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class TestUser:
    """测试用户"""
    username: str = ""
    password: str = ""
    email: str = ""
    role: str = "user"


@dataclass
class TestCredentials:
    """测试凭证"""
    api_key: Optional[str] = None
    token: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class TestProduct:
    """测试产品数据"""
    id: str = ""
    name: str = ""
    price: float = 0.0
    category: str = ""


@dataclass
class TestData:
    """测试数据集合"""
    users: Dict[str, TestUser] = field(default_factory=dict)
    credentials: Dict[str, TestCredentials] = field(default_factory=dict)
    products: Dict[str, TestProduct] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)


class FixtureManager:
    """
    夹具管理器

    管理测试夹具，支持从文件加载和动态生成测试数据。
    """

    _instance: Optional["FixtureManager"] = None

    def __new__(cls) -> "FixtureManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self._test_data = TestData()
        self._fixture_dir = os.path.join("test_framework", "engines", "ui_automation", "fixtures")

    def load_fixtures(self, fixture_dir: Optional[str] = None) -> None:
        """
        加载夹具数据

        Args:
            fixture_dir: 夹具目录
        """
        directory = fixture_dir or self._fixture_dir
        if not os.path.exists(directory):
            logger.warning(f"Fixture directory not found: {directory}")
            return

        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if not os.path.isfile(filepath):
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                name, _ = os.path.splitext(filename)
                if name == "test_users":
                    self._load_users(data)
                elif name == "test_credentials":
                    self._load_credentials(data)
                elif name == "test_products":
                    self._load_products(data)
                elif name == "test_data":
                    self._load_custom_data(data)

                logger.debug(f"Loaded fixture: {filename}")
            except Exception as e:
                logger.warning(f"Failed to load fixture {filename}: {e}")

    def _load_users(self, data: Dict[str, Any]) -> None:
        """加载测试用户"""
        for key, user_data in data.items():
            self._test_data.users[key] = TestUser(**user_data)

    def _load_credentials(self, data: Dict[str, Any]) -> None:
        """加载测试凭证"""
        for key, cred_data in data.items():
            self._test_data.credentials[key] = TestCredentials(**cred_data)

    def _load_products(self, data: Dict[str, Any]) -> None:
        """加载测试产品"""
        for key, product_data in data.items():
            self._test_data.products[key] = TestProduct(**product_data)

    def _load_custom_data(self, data: Dict[str, Any]) -> None:
        """加载自定义数据"""
        self._test_data.custom_data.update(data)

    def get_user(self, user_key: str) -> TestUser:
        """
        获取测试用户

        Args:
            user_key: 用户标识

        Returns:
            测试用户

        Raises:
            KeyError: 用户不存在时抛出
        """
        if user_key not in self._test_data.users:
            raise KeyError(f"User '{user_key}' not found in fixtures")
        return self._test_data.users[user_key]

    def get_credentials(self, cred_key: str) -> TestCredentials:
        """
        获取测试凭证

        Args:
            cred_key: 凭证标识

        Returns:
            测试凭证

        Raises:
            KeyError: 凭证不存在时抛出
        """
        if cred_key not in self._test_data.credentials:
            raise KeyError(f"Credentials '{cred_key}' not found in fixtures")
        return self._test_data.credentials[cred_key]

    def get_product(self, product_key: str) -> TestProduct:
        """
        获取测试产品

        Args:
            product_key: 产品标识

        Returns:
            测试产品

        Raises:
            KeyError: 产品不存在时抛出
        """
        if product_key not in self._test_data.products:
            raise KeyError(f"Product '{product_key}' not found in fixtures")
        return self._test_data.products[product_key]

    def get_custom_data(self, data_key: str) -> Any:
        """
        获取自定义数据

        Args:
            data_key: 数据标识

        Returns:
            数据值

        Raises:
            KeyError: 数据不存在时抛出
        """
        if data_key not in self._test_data.custom_data:
            raise KeyError(f"Custom data '{data_key}' not found in fixtures")
        return self._test_data.custom_data[data_key]

    def add_user(self, user_key: str, user: TestUser) -> None:
        """添加测试用户"""
        self._test_data.users[user_key] = user

    def add_credentials(self, cred_key: str, credentials: TestCredentials) -> None:
        """添加测试凭证"""
        self._test_data.credentials[cred_key] = credentials

    def add_product(self, product_key: str, product: TestProduct) -> None:
        """添加测试产品"""
        self._test_data.products[product_key] = product

    def add_custom_data(self, data_key: str, value: Any) -> None:
        """添加自定义数据"""
        self._test_data.custom_data[data_key] = value

    def generate_random_user(self, prefix: str = "test") -> TestUser:
        """生成随机测试用户"""
        import uuid
        user_id = str(uuid.uuid4())[:8]
        return TestUser(
            username=f"{prefix}_{user_id}",
            password=f"password_{user_id}",
            email=f"{prefix}_{user_id}@example.com",
            role="user"
        )

    def reset(self) -> None:
        """重置夹具数据"""
        self._test_data = TestData()
        logger.info("Fixture manager reset")