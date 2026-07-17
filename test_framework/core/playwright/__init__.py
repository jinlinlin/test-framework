"""
Playwright核心封装模块。

设计模式：
- 单例模式（PlaywrightManager）
- 模板模式（BasePage）
- 组合模式（BaseComponent）
- 工厂模式（PageFactory）
- 策略模式（ElementLocator）
- 建造者模式（ActionChains, AssertionChain）
"""
from .base_component import BaseComponent
from .base_page import BasePage
from .base_test import BaseTest
from .element_locator import ElementLocator
from .fixture_manager import FixtureManager
from .page_factory import PageFactory
from .playwright_manager import BrowserConfig, PlaywrightManager
from .wait_conditions import WaitConditions

__all__ = [
    "PlaywrightManager",
    "BrowserConfig",
    "BasePage",
    "BaseComponent",
    "BaseTest",
    "PageFactory",
    "ElementLocator",
    "WaitConditions",
    "FixtureManager",
]