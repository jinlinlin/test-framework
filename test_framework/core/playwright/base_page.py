"""
页面基类 - 模板模式

所有Page Object继承此类，提供页面导航、元素定位、交互、断言等通用能力。

设计模式：模板模式（Template Method）
"""
from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any, List, Optional, Union

from playwright.async_api import Locator, Page, expect

from ...core.interfaces import IAssertable, IElementLocatable, IUIInteractable

logger = logging.getLogger(__name__)


class BasePage(IUIInteractable, IElementLocatable, IAssertable):
    """
    Page Object基类

    提供所有页面共用的方法和属性，支持链式调用。
    """

    URL_PATH: str = ""
    LOAD_INDICATOR: Optional[str] = None

    def __init__(self, page: Page, base_url: Optional[str] = None, timeout: int = 30000) -> None:
        self._page = page
        self._base_url = base_url or ""
        self._timeout = timeout
        self._retry_count = 3
        self._screenshot_on_failure = True
        self._init_page()

    def _init_page(self) -> None:
        """子类可重写的初始化方法"""
        pass

    @property
    def page(self) -> Page:
        return self._page

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def timeout(self) -> int:
        return self._timeout

    async def navigate(self, path: str = "", **kwargs: Any) -> "BasePage":
        """导航到指定路径"""
        url = f"{self._base_url}{path or self.URL_PATH}"
        await self._page.goto(url, wait_until="networkidle", **kwargs)
        await self.wait_for_load()
        return self

    async def goto(self, url: str, **kwargs: Any) -> "BasePage":
        """直接跳转到URL"""
        await self._page.goto(url, wait_until="networkidle", **kwargs)
        await self.wait_for_load()
        return self

    async def refresh(self) -> "BasePage":
        """刷新页面"""
        await self._page.reload(wait_until="networkidle")
        await self.wait_for_load()
        return self

    async def go_back(self) -> "BasePage":
        """后退"""
        await self._page.go_back(wait_until="networkidle")
        await self.wait_for_load()
        return self

    async def go_forward(self) -> "BasePage":
        """前进"""
        await self._page.go_forward(wait_until="networkidle")
        await self.wait_for_load()
        return self

    def locate(self, selector: str, **kwargs: Any) -> Locator:
        """定位元素"""
        return self._page.locator(selector, **kwargs)

    def locate_by_test_id(self, test_id: str) -> Locator:
        """通过data-testid定位"""
        return self._page.locator(f'[data-testid="{test_id}"]')

    def locate_by_role(self, role: str, name: Optional[str] = None) -> Locator:
        """通过ARIA role定位"""
        return self._page.get_by_role(role, name=name)

    def locate_by_text(self, text: str, exact: bool = False) -> Locator:
        """通过文本定位"""
        return self._page.get_by_text(text, exact=exact)

    def locate_by_placeholder(self, placeholder: str) -> Locator:
        """通过placeholder定位"""
        return self._page.get_by_placeholder(placeholder)

    def locate_by_label(self, label: str) -> Locator:
        """通过label定位"""
        return self._page.get_by_label(label)

    def locate_by_alt(self, alt: str) -> Locator:
        """通过alt文本定位"""
        return self._page.get_by_alt_text(alt)

    def locate_by_title(self, title: str) -> Locator:
        """通过title属性定位"""
        return self._page.get_by_title(title)

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

    async def wait_for_load(self, timeout: Optional[int] = None) -> "BasePage":
        """等待页面加载完成"""
        await self._page.wait_for_load_state("networkidle", timeout=timeout or self._timeout)

        if self.LOAD_INDICATOR:
            try:
                await self._page.locator(self.LOAD_INDICATOR).wait_for(state="hidden", timeout=5000)
            except Exception:
                pass

        return self

    async def wait_for_navigation(self, timeout: Optional[int] = None) -> "BasePage":
        """等待导航完成"""
        async with self._page.expect_navigation(timeout=timeout or self._timeout):
            pass
        return self

    async def wait_for_url(self, url_pattern: str, timeout: Optional[int] = None) -> "BasePage":
        """等待URL匹配"""
        await self._page.wait_for_url(url_pattern, timeout=timeout or self._timeout)
        return self

    async def wait_for_timeout(self, milliseconds: int) -> "BasePage":
        """等待指定毫秒"""
        await self._page.wait_for_timeout(milliseconds)
        return self

    async def click(self, selector: str, **kwargs: Any) -> "BasePage":
        """点击元素"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.click(**kwargs)
        return self

    async def dblclick(self, selector: str, **kwargs: Any) -> "BasePage":
        """双击元素"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.dblclick(**kwargs)
        return self

    async def rightclick(self, selector: str, **kwargs: Any) -> "BasePage":
        """右键点击"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.click(button="right", **kwargs)
        return self

    async def fill(self, selector: str, text: str, clear_first: bool = True, **kwargs: Any) -> "BasePage":
        """填充文本"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        if clear_first:
            await locator.clear()
        await locator.fill(text)
        return self

    async def type_text(self, selector: str, text: str, delay: int = 50, **kwargs: Any) -> "BasePage":
        """逐字输入"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.type(text, delay=delay)
        return self

    async def clear(self, selector: str, **kwargs: Any) -> "BasePage":
        """清空输入框"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.clear()
        return self

    async def hover(self, selector: str, **kwargs: Any) -> "BasePage":
        """悬停"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.hover()
        return self

    async def drag_to(self, source_selector: str, target_selector: str, **kwargs: Any) -> "BasePage":
        """拖拽"""
        source = await self.find_element(source_selector, kwargs.get("timeout"))
        target = await self.find_element(target_selector, kwargs.get("timeout"))
        await source.drag_to(target)
        return self

    async def select_option(self, selector: str, value: Union[str, List[str]], **kwargs: Any) -> "BasePage":
        """选择下拉选项"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.select_option(value)
        return self

    async def check(self, selector: str, **kwargs: Any) -> "BasePage":
        """勾选复选框"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.check()
        return self

    async def uncheck(self, selector: str, **kwargs: Any) -> "BasePage":
        """取消勾选"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.uncheck()
        return self

    async def upload_file(self, selector: str, file_path: Union[str, List[str]], **kwargs: Any) -> "BasePage":
        """上传文件"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.set_input_files(file_path)
        return self

    async def focus(self, selector: str, **kwargs: Any) -> "BasePage":
        """聚焦元素"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.focus()
        return self

    async def press(self, selector: str, key: str, **kwargs: Any) -> "BasePage":
        """按键"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.press(key)
        return self

    async def scroll_to(self, selector: str, **kwargs: Any) -> "BasePage":
        """滚动到元素"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        await locator.scroll_into_view_if_needed()
        return self

    async def scroll(self, x: int = 0, y: int = 0) -> "BasePage":
        """滚动页面"""
        await self._page.mouse.wheel(x, y)
        return self

    async def get_text(self, selector: str, **kwargs: Any) -> str:
        """获取文本"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        return await locator.text_content() or ""

    async def get_attribute(self, selector: str, attribute: str, **kwargs: Any) -> Optional[str]:
        """获取属性"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        return await locator.get_attribute(attribute)

    async def get_value(self, selector: str, **kwargs: Any) -> str:
        """获取输入框值"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        return await locator.input_value()

    async def get_url(self) -> str:
        """获取当前URL"""
        return self._page.url

    async def get_title(self) -> str:
        """获取页面标题"""
        return await self._page.title()

    async def get_inner_html(self, selector: str, **kwargs: Any) -> str:
        """获取内部HTML"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        return await locator.inner_html()

    async def get_outer_html(self, selector: str, **kwargs: Any) -> str:
        """获取外部HTML"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        return await locator.inner_html()

    async def screenshot(self, path: Optional[str] = None, full_page: bool = True, **kwargs: Any) -> bytes:
        """截图"""
        return await self._page.screenshot(path=path, full_page=full_page, **kwargs)

    async def element_screenshot(self, selector: str, path: Optional[str] = None, **kwargs: Any) -> bytes:
        """元素截图"""
        locator = await self.find_element(selector, kwargs.get("timeout"))
        return await locator.screenshot(path=path)

    async def assert_visible(self, selector: str, timeout: Optional[int] = None) -> "BasePage":
        """断言元素可见"""
        locator = self.locate(selector)
        await expect(locator).to_be_visible(timeout=timeout or self._timeout)
        return self

    async def assert_hidden(self, selector: str, timeout: Optional[int] = None) -> "BasePage":
        """断言元素隐藏"""
        locator = self.locate(selector)
        await expect(locator).to_be_hidden(timeout=timeout or self._timeout)
        return self

    async def assert_text(self, selector: str, expected_text: str, timeout: Optional[int] = None) -> "BasePage":
        """断言元素文本"""
        locator = self.locate(selector)
        await expect(locator).to_have_text(expected_text, timeout=timeout or self._timeout)
        return self

    async def assert_attribute(
        self, selector: str, attribute: str, expected_value: str, timeout: Optional[int] = None
    ) -> "BasePage":
        """断言元素属性"""
        locator = self.locate(selector)
        await expect(locator).to_have_attribute(attribute, expected_value, timeout=timeout or self._timeout)
        return self

    async def assert_css_property(
        self, selector: str, property_name: str, expected_value: str, timeout: Optional[int] = None
    ) -> "BasePage":
        """断言CSS属性"""
        locator = self.locate(selector)
        computed_style = await locator.evaluate(
            f'(el) => window.getComputedStyle(el).getPropertyValue("{property_name}")'
        )
        assert computed_style == expected_value, f"Expected CSS {property_name} to be {expected_value}, got {computed_style}"
        return self

    async def assert_count(self, selector: str, expected_count: int, timeout: Optional[int] = None) -> "BasePage":
        """断言元素数量"""
        locator = self.locate(selector)
        await expect(locator).to_have_count(expected_count, timeout=timeout or self._timeout)
        return self

    async def assert_url(self, url_pattern: str, timeout: Optional[int] = None) -> "BasePage":
        """断言URL"""
        await expect(self._page).to_have_url(url_pattern, timeout=timeout or self._timeout)
        return self

    async def assert_title(self, expected_title: str, timeout: Optional[int] = None) -> "BasePage":
        """断言页面标题"""
        await expect(self._page).to_have_title(expected_title, timeout=timeout or self._timeout)
        return self

    async def assert_enabled(self, selector: str, timeout: Optional[int] = None) -> "BasePage":
        """断言元素启用状态"""
        locator = self.locate(selector)
        await expect(locator).to_be_enabled(timeout=timeout or self._timeout)
        return self

    async def assert_checked(self, selector: str, timeout: Optional[int] = None) -> "BasePage":
        """断言元素勾选状态"""
        locator = self.locate(selector)
        await expect(locator).to_be_checked(timeout=timeout or self._timeout)
        return self

    async def assert_focused(self, selector: str, timeout: Optional[int] = None) -> "BasePage":
        """断言元素聚焦状态"""
        locator = self.locate(selector)
        await expect(locator).to_be_focused(timeout=timeout or self._timeout)
        return self