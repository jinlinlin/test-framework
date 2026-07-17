"""
操作链 - 建造者模式

提供链式操作能力，支持组合多个操作步骤。

设计模式：建造者模式（Builder）
"""
from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional, Union

from playwright.async_api import Locator, Page

logger = logging.getLogger(__name__)


class ActionStep:
    """操作步骤"""

    def __init__(self, action: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self._action = action
        self._args = args
        self._kwargs = kwargs

    async def execute(self, page: Page) -> None:
        """执行操作步骤"""
        await self._action(page, *self._args, **self._kwargs)


class ActionChains:
    """
    操作链

    支持链式调用，组合多个操作步骤一次性执行。
    """

    def __init__(self, page: Page) -> None:
        self._page = page
        self._steps: List[ActionStep] = []

    def click(self, selector: str, **kwargs: Any) -> "ActionChains":
        """添加点击操作"""
        async def _click(page: Page) -> None:
            await page.click(selector, **kwargs)
        self._steps.append(ActionStep(_click))
        return self

    def dblclick(self, selector: str, **kwargs: Any) -> "ActionChains":
        """添加双击操作"""
        async def _dblclick(page: Page) -> None:
            await page.dblclick(selector, **kwargs)
        self._steps.append(ActionStep(_dblclick))
        return self

    def rightclick(self, selector: str, **kwargs: Any) -> "ActionChains":
        """添加右键点击操作"""
        async def _rightclick(page: Page) -> None:
            await page.click(selector, button="right", **kwargs)
        self._steps.append(ActionStep(_rightclick))
        return self

    def fill(self, selector: str, text: str, clear_first: bool = True) -> "ActionChains":
        """添加填充文本操作"""
        async def _fill(page: Page) -> None:
            if clear_first:
                await page.fill(selector, "")
            await page.fill(selector, text)
        self._steps.append(ActionStep(_fill))
        return self

    def type_text(self, selector: str, text: str, delay: int = 50) -> "ActionChains":
        """添加逐字输入操作"""
        async def _type_text(page: Page) -> None:
            await page.type(selector, text, delay=delay)
        self._steps.append(ActionStep(_type_text))
        return self

    def clear(self, selector: str) -> "ActionChains":
        """添加清空操作"""
        async def _clear(page: Page) -> None:
            await page.fill(selector, "")
        self._steps.append(ActionStep(_clear))
        return self

    def hover(self, selector: str) -> "ActionChains":
        """添加悬停操作"""
        async def _hover(page: Page) -> None:
            await page.hover(selector)
        self._steps.append(ActionStep(_hover))
        return self

    def drag_to(self, source_selector: str, target_selector: str) -> "ActionChains":
        """添加拖拽操作"""
        async def _drag_to(page: Page) -> None:
            await page.drag_and_drop(source_selector, target_selector)
        self._steps.append(ActionStep(_drag_to))
        return self

    def select_option(self, selector: str, value: Union[str, List[str]]) -> "ActionChains":
        """添加选择下拉选项操作"""
        async def _select_option(page: Page) -> None:
            await page.select_option(selector, value)
        self._steps.append(ActionStep(_select_option))
        return self

    def check(self, selector: str) -> "ActionChains":
        """添加勾选操作"""
        async def _check(page: Page) -> None:
            await page.check(selector)
        self._steps.append(ActionStep(_check))
        return self

    def uncheck(self, selector: str) -> "ActionChains":
        """添加取消勾选操作"""
        async def _uncheck(page: Page) -> None:
            await page.uncheck(selector)
        self._steps.append(ActionStep(_uncheck))
        return self

    def upload_file(self, selector: str, file_path: Union[str, List[str]]) -> "ActionChains":
        """添加文件上传操作"""
        async def _upload_file(page: Page) -> None:
            await page.set_input_files(selector, file_path)
        self._steps.append(ActionStep(_upload_file))
        return self

    def focus(self, selector: str) -> "ActionChains":
        """添加聚焦操作"""
        async def _focus(page: Page) -> None:
            await page.focus(selector)
        self._steps.append(ActionStep(_focus))
        return self

    def press(self, key: str) -> "ActionChains":
        """添加按键操作"""
        async def _press(page: Page) -> None:
            await page.keyboard.press(key)
        self._steps.append(ActionStep(_press))
        return self

    def scroll_to(self, selector: str) -> "ActionChains":
        """添加滚动到元素操作"""
        async def _scroll_to(page: Page) -> None:
            await page.locator(selector).scroll_into_view_if_needed()
        self._steps.append(ActionStep(_scroll_to))
        return self

    def wait_for(self, selector: str, state: str = "visible", timeout: int = 30000) -> "ActionChains":
        """添加等待操作"""
        async def _wait_for(page: Page) -> None:
            await page.locator(selector).wait_for(state=state, timeout=timeout)
        self._steps.append(ActionStep(_wait_for))
        return self

    def wait_for_timeout(self, milliseconds: int) -> "ActionChains":
        """添加等待指定时间操作"""
        async def _wait_for_timeout(page: Page) -> None:
            await page.wait_for_timeout(milliseconds)
        self._steps.append(ActionStep(_wait_for_timeout))
        return self

    async def perform(self) -> None:
        """执行所有操作步骤"""
        logger.debug(f"Performing {len(self._steps)} action steps")
        for i, step in enumerate(self._steps):
            try:
                await step.execute(self._page)
                logger.debug(f"Step {i + 1} completed")
            except Exception as e:
                logger.error(f"Step {i + 1} failed: {e}")
                raise

        self._steps.clear()