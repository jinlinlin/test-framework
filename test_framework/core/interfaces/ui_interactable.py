"""
UI交互接口 — 定义UI元素交互能力契约。

设计模式：接口隔离原则（ISP）
职责：定义页面元素的交互操作标准接口，
      包括点击、输入、选择等常见UI操作。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Union


class IUIInteractable(ABC):
    """
    UI交互接口。

    定义页面元素的交互操作能力，所有可交互的页面对象必须实现此接口。
    """

    @abstractmethod
    async def click(self, selector: str, **kwargs: Any) -> "IUIInteractable":
        """点击元素。"""
        ...

    @abstractmethod
    async def dblclick(self, selector: str, **kwargs: Any) -> "IUIInteractable":
        """双击元素。"""
        ...

    @abstractmethod
    async def rightclick(self, selector: str, **kwargs: Any) -> "IUIInteractable":
        """右键点击元素。"""
        ...

    @abstractmethod
    async def fill(self, selector: str, text: str, clear_first: bool = True) -> "IUIInteractable":
        """填充文本到输入框。"""
        ...

    @abstractmethod
    async def type_text(self, selector: str, text: str, delay: int = 50) -> "IUIInteractable":
        """逐字输入文本。"""
        ...

    @abstractmethod
    async def clear(self, selector: str) -> "IUIInteractable":
        """清空输入框。"""
        ...

    @abstractmethod
    async def hover(self, selector: str) -> "IUIInteractable":
        """悬停在元素上。"""
        ...

    @abstractmethod
    async def drag_to(self, source_selector: str, target_selector: str) -> "IUIInteractable":
        """拖拽元素到目标位置。"""
        ...

    @abstractmethod
    async def select_option(self, selector: str, value: Union[str, List[str]]) -> "IUIInteractable":
        """选择下拉选项。"""
        ...

    @abstractmethod
    async def check(self, selector: str) -> "IUIInteractable":
        """勾选复选框。"""
        ...

    @abstractmethod
    async def uncheck(self, selector: str) -> "IUIInteractable":
        """取消勾选复选框。"""
        ...

    @abstractmethod
    async def upload_file(self, selector: str, file_path: Union[str, List[str]]) -> "IUIInteractable":
        """上传文件。"""
        ...

    @abstractmethod
    async def focus(self, selector: str) -> "IUIInteractable":
        """聚焦元素。"""
        ...

    @abstractmethod
    async def press(self, selector: str, key: str) -> "IUIInteractable":
        """按键操作。"""
        ...

    @abstractmethod
    async def scroll_to(self, selector: str) -> "IUIInteractable":
        """滚动到元素位置。"""
        ...