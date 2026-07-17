"""
浏览器适配器统一接口。

职责：定义浏览器操作的统一抽象，
      包含页面导航、元素交互、截图、脚本执行等方法。
      所有浏览器实现（Playwright / Selenium）必须遵循此接口。
"""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..base import BaseAdapter


@dataclass
class PageElement:
    """
    页面元素数据对象。

    Attributes:
        tag_name: 标签名称（div / span / input 等）。
        text: 元素文本内容。
        attributes: 元素属性字典。
        inner_html: 元素内部 HTML。
        is_visible: 元素是否可见。
        bounding_box: 元素边界矩形 (x, y, width, height)。
    """

    tag_name: str = ""
    text: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)
    inner_html: str = ""
    is_visible: bool = True
    bounding_box: Optional[Dict[str, float]] = None


@dataclass
class PageScreenshot:
    """
    页面截图数据对象。

    Attributes:
        data: 截图二进制数据（PNG）。
        path: 截图保存路径（可选）。
        width: 截图宽度。
        height: 截图高度。
    """

    data: bytes = b""
    path: str = ""
    width: int = 0
    height: int = 0


@dataclass
class NetworkEntry:
    """
    网络请求记录。

    Attributes:
        url: 请求 URL。
        method: HTTP 方法。
        status: HTTP 状态码。
        resource_type: 资源类型（document / script / stylesheet / image 等）。
        duration: 请求耗时（秒）。
        size: 响应体大小（字节）。
    """

    url: str = ""
    method: str = ""
    status: int = 0
    resource_type: str = ""
    duration: float = 0.0
    size: int = 0


class BrowserAdapter(BaseAdapter):
    """
    浏览器适配器抽象基类。

    定义页面导航、元素交互、截图、脚本执行等统一方法。
    """

    @property
    def adapter_type(self) -> str:
        return "browser"

    # ===== 页面导航 =====

    @abstractmethod
    async def goto(self, url: str, wait_until: str = "load") -> None:
        """
        导航到指定 URL。

        Args:
            url: 目标 URL。
            wait_until: 等待条件（load / domcontentloaded / networkidle）。
        """
        ...

    @abstractmethod
    async def get_url(self) -> str:
        """获取当前页面 URL。"""
        ...

    @abstractmethod
    async def get_title(self) -> str:
        """获取当前页面标题。"""
        ...

    # ===== 元素交互 =====

    @abstractmethod
    async def click(self, selector: str, **kwargs: Any) -> None:
        """
        点击元素。

        Args:
            selector: CSS 选择器或 XPath。
            **kwargs: 额外选项（force / timeout 等）。
        """
        ...

    @abstractmethod
    async def fill(self, selector: str, value: str) -> None:
        """
        填充输入框。

        Args:
            selector: CSS 选择器。
            value: 输入值。
        """
        ...

    @abstractmethod
    async def select_option(self, selector: str, value: str) -> None:
        """
        选择下拉选项。

        Args:
            selector: CSS 选择器。
            value: 选项值。
        """
        ...

    @abstractmethod
    async def hover(self, selector: str) -> None:
        """
        悬停在元素上。

        Args:
            selector: CSS 选择器。
        """
        ...

    # ===== 元素查询 =====

    @abstractmethod
    async def query_selector(self, selector: str) -> Optional[PageElement]:
        """
        查询单个元素。

        Args:
            selector: CSS 选择器。

        Returns:
            页面元素，不存在时返回 None。
        """
        ...

    @abstractmethod
    async def query_selector_all(self, selector: str) -> List[PageElement]:
        """
        查询所有匹配元素。

        Args:
            selector: CSS 选择器。

        Returns:
            页面元素列表。
        """
        ...

    @abstractmethod
    async def wait_for_selector(self, selector: str, timeout: float = 30.0) -> None:
        """
        等待元素出现。

        Args:
            selector: CSS 选择器。
            timeout: 超时秒数。
        """
        ...

    # ===== 截图与脚本 =====

    @abstractmethod
    async def screenshot(self, path: str = "", full_page: bool = False) -> PageScreenshot:
        """
        页面截图。

        Args:
            path: 保存路径（为空时仅返回二进制数据）。
            full_page: 是否全页截图。

        Returns:
            截图数据对象。
        """
        ...

    @abstractmethod
    async def evaluate(self, script: str) -> Any:
        """
        执行 JavaScript 脚本。

        Args:
            script: JavaScript 代码字符串。

        Returns:
            脚本返回值。
        """
        ...

    # ===== 网络拦截 =====

    @abstractmethod
    async def get_network_entries(self) -> List[NetworkEntry]:
        """获取所有已记录的网络请求。"""
        ...

    # ===== 页面管理 =====

    @abstractmethod
    async def new_page(self) -> None:
        """打开新页面（标签页）。"""
        ...

    @abstractmethod
    async def close_page(self) -> None:
        """关闭当前页面。"""
        ...

    @abstractmethod
    async def get_cookies(self) -> List[Dict[str, Any]]:
        """获取所有 Cookie。"""
        ...

    @abstractmethod
    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        """设置 Cookie。"""
        ...

    @abstractmethod
    async def clear_cookies(self) -> None:
        """清除所有 Cookie。"""
        ...
