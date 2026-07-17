"""
组件基类 - 组合模式

可复用UI组件的基类，支持嵌套组合。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from playwright.async_api import Locator, Page, expect

from ...core.interfaces import IAssertable, IElementLocatable, IUIInteractable

logger = logging.getLogger(__name__)


class BaseComponent(IUIInteractable, IElementLocatable, IAssertable):
    """
    UI组件基类

    提供可复用组件的通用能力，支持嵌套组合。
    """

    ROOT_SELECTOR: str = ""

    def __init__(self, page: Page, parent_locator: Optional[Locator] = None) -> None:
        self._page = page
        self._parent_locator = parent_locator
        self._timeout = 30000
        self._components: Dict[str, "BaseComponent"] = {}

    @property
    def page(self) -> Page:
        return self._page

    @property
    def timeout(self) -> int:
        return self._timeout

    @timeout.setter
    def timeout(self, value: int) -> None:
        self._timeout = value

    def root_locator(self) -> Locator:
        """获取组件根定位器"""
        if self._parent_locator:
            return self._parent_locator.locator(self.ROOT_SELECTOR)
        return self._page.locator(self.ROOT_SELECTOR)

    def register_component(self, name: str, component: "BaseComponent") -> None:
        """注册子组件"""
        self._components[name] = component

    def get_component(self, name: str) -> "BaseComponent":
        """获取子组件"""
        if name not in self._components:
            raise KeyError(f"Component '{name}' not registered")
        return self._components[name]

    def locate(self, selector: str, **kwargs: Any) -> Locator:
        """定位元素（相对于组件根）"""
        return self.root_locator().locator(selector, **kwargs)

    def locate_by_test_id(self, test_id: str) -> Locator:
        """通过data-testid定位"""
        return self.root_locator().locator(f'[data-testid="{test_id}"]')

    def locate_by_role(self, role: str, name: Optional[str] = None) -> Locator:
        """通过ARIA role定位"""
        return self.root_locator().get_by_role(role, name=name)

    def locate_by_text(self, text: str, exact: bool = False) -> Locator:
        """通过文本定位"""
        return self.root_locator().get_by_text(text, exact=exact)

    def locate_by_placeholder(self, placeholder: str) -> Locator:
        """通过placeholder定位"""
        return self.root_locator().get_by_placeholder(placeholder)

    def locate_by_label(self, label: str) -> Locator:
        """通过label定位"""
        return self.root_locator().get_by_label(label)

    def locate_by_alt(self, alt: str) -> Locator:
        """通过alt文本定位"""
        return self.root_locator().get_by_alt_text(alt)

    def locate_by_title(self, title: str) -> Locator:
        """通过title属性定位"""
        return self.root_locator().get_by_title(title)

    async def find_element(
        self, selector: str, timeout: Optional[int] = None, state: str = "visible"
    ) -> Locator:
        """查找单个元素"""
        locator = self.locate(selector)
        await locator.first.wait_for(state=state, timeout=timeout or self._timeout)
        return locator

    async def find_elements(self, selector: str) -> List[Locator]:
        """查找多个元素"""
        return await self.locate(selector).all()

    async def wait_for_element(
        self, selector: str, timeout: Optional[int] = None, state: str = "visible"
    ) -> Locator:
        """等待元素出现"""
        locator = self.locate(selector)
        await locator.first.wait_for(state=state, timeout=timeout or self._timeout)
        return locator

    async def wait_for_visible(self, timeout: Optional[int] = None) -> "BaseComponent":
        """等待组件可见"""
        await self.root_locator().wait_for(state="visible", timeout=timeout or self._timeout)
        return self

    async def wait_for_hidden(self, timeout: Optional[int] = None) -> "BaseComponent":
        """等待组件隐藏"""
        await self.root_locator().wait_for(state="hidden", timeout=timeout or self._timeout)
        return self

    async def click(self, selector: str = "", **kwargs: Any) -> "BaseComponent":
        """点击元素"""
        if selector:
            locator = await self.find_element(selector, kwargs.get("timeout"))
        else:
            locator = self.root_locator()
        await locator.click(**kwargs)
        return self

    async def dblclick(self, selector: str = "", **kwargs: Any) -> "BaseComponent":
        """双击元素"""
        if selector:
            locator = await self.find_element(selector, kwargs.get("timeout"))
        else:
            locator = self.root_locator()
        await locator.dblclick(**kwargs)
        return self

    async def rightclick(self, selector: str = "", **kwargs: Any) -> "BaseComponent":
        """右键点击"""
        if selector:
            locator = await self.find_element(selector, kwargs.get("timeout"))
        else:
            locator = self.root_locator()
        await locator.click(button="right", **kwargs)
        return self

    async def fill(self, selector: str, text: str, clear_first: bool = True, **kwargs: Any) -> "BaseComponent":
        """填充文本"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        if clear_first:
            await locator.clear()
        await locator.fill(text)
        return self

    async def type_text(self, selector: str, text: str, delay: int = 50, **kwargs: Any) -> "BaseComponent":
        """逐字输入"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.type(text, delay=delay)
        return self

    async def clear(self, selector: str, **kwargs: Any) -> "BaseComponent":
        """清空输入框"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.clear()
        return self

    async def hover(self, selector: str = "", **kwargs: Any) -> "BaseComponent":
        """悬停"""
        if selector:
            locator = await self.find_element(selector, kwargs.get("timeout"))
        else:
            locator = self.root_locator()
        await locator.hover()
        return self

    async def drag_to(self, source_selector: str, target_selector: str, **kwargs: Any) -> "BaseComponent":
        """拖拽"""
        source = await self.find_element(source_selector, kwargs.get("timeout"))
        target = await self.find_element(target_selector, kwargs.get("timeout"))
        await source.drag_to(target)
        return self

    async def select_option(self, selector: str, value: Union[str, List[str]], **kwargs: Any) -> "BaseComponent":
        """选择下拉选项"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.select_option(value)
        return self

    async def check(self, selector: str = "", **kwargs: Any) -> "BaseComponent":
        """勾选复选框"""
        if selector:
            locator = await self.find_element(selector, kwargs.get("timeout"))
        else:
            locator = self.root_locator()
        await locator.check()
        return self

    async def uncheck(self, selector: str = "", **kwargs: Any) -> "BaseComponent":
        """取消勾选"""
        if selector:
            locator = await self.find_element(selector, kwargs.get("timeout"))
        else:
            locator = self.root_locator()
        await locator.uncheck()
        return self

    async def upload_file(self, selector: str, file_path: Union[str, List[str]], **kwargs: Any) -> "BaseComponent":
        """上传文件"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.set_input_files(file_path)
        return self

    async def focus(self, selector: str = "", **kwargs: Any) -> "BaseComponent":
        """聚焦元素"""
        if selector:
            locator = await self.find_element(selector, kwargs.get("timeout"))
        else:
            locator = self.root_locator()
        await locator.focus()
        return self

    async def press(self, selector: str, key: str, **kwargs: Any) -> "BaseComponent":
        """按键"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.press(key)
        return self

    async def scroll_to(self, selector: str = "", **kwargs: Any) -> "BaseComponent":
        """滚动到元素"""
        if selector:
            locator = await self.find_element(selector, kwargs.get("timeout"))
        else:
            locator = self.root_locator()
        await locator.scroll_into_view_if_needed()
        return self

    async def get_text(self, selector: str = "", **kwargs: Any) -> str:
        """获取文本"""
        if selector:
            locator = await self.find_element(selector, kwargs.get("timeout"))
        else:
            locator = self.root_locator()
        return await locator.text_content() or ""

    async def get_attribute(self, selector: str = "", attribute: str = "", **kwargs: Any) -> Optional[str]:
        """获取属性"""
        if selector:
            locator = await self.find_element(selector, kwargs.get("timeout"))
        else:
            locator = self.root_locator()
        return await locator.get_attribute(attribute)

    async def get_value(self, selector: str, **kwargs: Any) -> str:
        """获取输入框值"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        return await locator.input_value()

    async def screenshot(self, path: Optional[str] = None, **kwargs: Any) -> bytes:
        """组件截图"""
        return await self.root_locator().screenshot(path=path, **kwargs)

    async def assert_visible(self, selector: str = "", timeout: Optional[int] = None) -> "BaseComponent":
        """断言元素可见"""
        if selector:
            locator = self.locate(selector)
        else:
            locator = self.root_locator()
        await expect(locator).to_be_visible(timeout=timeout or self._timeout)
        return self

    async def assert_hidden(self, selector: str = "", timeout: Optional[int] = None) -> "BaseComponent":
        """断言元素隐藏"""
        if selector:
            locator = self.locate(selector)
        else:
            locator = self.root_locator()
        await expect(locator).to_be_hidden(timeout=timeout or self._timeout)
        return self

    async def assert_text(self, selector: str = "", expected_text: str = "", timeout: Optional[int] = None) -> "BaseComponent":
        """断言元素文本"""
        if selector:
            locator = self.locate(selector)
        else:
            locator = self.root_locator()
        await expect(locator).to_have_text(expected_text, timeout=timeout or self._timeout)
        return self

    async def assert_attribute(
        self, selector: str = "", attribute: str = "", expected_value: str = "", timeout: Optional[int] = None
    ) -> "BaseComponent":
        """断言元素属性"""
        if selector:
            locator = self.locate(selector)
        else:
            locator = self.root_locator()
        await expect(locator).to_have_attribute(attribute, expected_value, timeout=timeout or self._timeout)
        return self

    async def assert_css_property(
        self, selector: str = "", property_name: str = "", expected_value: str = "", timeout: Optional[int] = None
    ) -> "BaseComponent":
        """断言CSS属性"""
        if selector:
            locator = self.locate(selector)
        else:
            locator = self.root_locator()
        computed_style = await locator.evaluate(
            f'(el) => window.getComputedStyle(el).getPropertyValue("{property_name}")'
        )
        assert computed_style == expected_value, f"Expected CSS {property_name} to be {expected_value}, got {computed_style}"
        return self

    async def assert_count(self, selector: str, expected_count: int, timeout: Optional[int] = None) -> "BaseComponent":
        """断言元素数量"""
        locator = self.locate(selector)
        await expect(locator).to_have_count(expected_count, timeout=timeout or self._timeout)
        return self

    async def assert_enabled(self, selector: str = "", timeout: Optional[int] = None) -> "BaseComponent":
        """断言元素启用状态"""
        if selector:
            locator = self.locate(selector)
        else:
            locator = self.root_locator()
        await expect(locator).to_be_enabled(timeout=timeout or self._timeout)
        return self

    async def assert_checked(self, selector: str = "", timeout: Optional[int] = None) -> "BaseComponent":
        """断言元素勾选状态"""
        if selector:
            locator = self.locate(selector)
        else:
            locator = self.root_locator()
        await expect(locator).to_be_checked(timeout=timeout or self._timeout)
        return self

    async def assert_focused(self, selector: str = "", timeout: Optional[int] = None) -> "BaseComponent":
        """断言元素聚焦状态"""
        if selector:
            locator = self.locate(selector)
        else:
            locator = self.root_locator()
        await expect(locator).to_be_focused(timeout=timeout or self._timeout)
        return self