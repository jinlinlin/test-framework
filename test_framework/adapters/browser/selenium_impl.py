"""
基于 Selenium 的浏览器适配器。

特点：
- 支持 Chrome / Firefox / Edge 等多种浏览器
- 通过 asyncio 将同步 API 包装为异步
- 兼容已有的 Selenium WebDriver 生态
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .adapter import BrowserAdapter, NetworkEntry, PageElement, PageScreenshot

logger = logging.getLogger(__name__)


class SeleniumAdapter(BrowserAdapter):
    """
    Selenium WebDriver 浏览器适配器。

    将 Selenium 同步 API 包装为异步接口，
    在线程池中执行以避免阻塞事件循环。

    配置项::

        {
            "browser_type": "chrome",    # chrome / firefox / edge
            "headless": True,
            "implicit_wait": 10,         # 隐式等待（秒）
            "page_load_timeout": 30,     # 页面加载超时（秒）
            "window_size": "1280x720",
            "options": [],               # 额外 ChromeOptions 参数列表
        }
    """

    @property
    def implementation_name(self) -> str:
        return "selenium"

    def __init__(self) -> None:
        """初始化 Selenium 适配器。"""
        self._driver: Optional[Any] = None  # WebDriver 实例
        self._network_entries: List[NetworkEntry] = []  # 网络记录（通过 performance log）

    async def connect(self, config: Dict[str, Any]) -> None:
        """
        创建 WebDriver 实例。

        Args:
            config: 配置字典。
        """
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.firefox.options import Options as FirefoxOptions

        browser_type = config.get("browser_type", "chrome")
        headless = config.get("headless", True)
        implicit_wait = config.get("implicit_wait", 10)
        page_load_timeout = config.get("page_load_timeout", 30)
        window_size = config.get("window_size", "1280,720")
        extra_options = config.get("options", [])

        def _create_driver() -> Any:
            if browser_type == "chrome":
                options = ChromeOptions()
                if headless:
                    options.add_argument("--headless=new")
                options.add_argument(f"--window-size={window_size}")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                # 启用性能日志（记录网络请求）
                options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
                for opt in extra_options:
                    options.add_argument(opt)
                driver = webdriver.Chrome(options=options)
            elif browser_type == "firefox":
                options = FirefoxOptions()
                if headless:
                    options.add_argument("--headless")
                options.add_argument(f"--width={window_size.split(',')[0]}")
                options.add_argument(f"--height={window_size.split(',')[1]}")
                driver = webdriver.Firefox(options=options)
            else:
                # Edge 等使用类似 Chrome 的方式
                from selenium.webdriver.edge.options import Options as EdgeOptions
                options = EdgeOptions()
                if headless:
                    options.add_argument("--headless=new")
                driver = webdriver.Edge(options=options)

            driver.implicitly_wait(implicit_wait)
            driver.set_page_load_timeout(page_load_timeout)
            return driver

        self._driver = await asyncio.get_event_loop().run_in_executor(
            None, _create_driver
        )
        logger.debug(f"SeleniumAdapter 已连接: browser={browser_type}")

    async def disconnect(self) -> None:
        """关闭浏览器并释放资源。"""
        if self._driver:
            await asyncio.get_event_loop().run_in_executor(
                None, self._driver.quit
            )
            self._driver = None
        self._network_entries.clear()
        logger.debug("SeleniumAdapter 已断开")

    async def is_connected(self) -> bool:
        if not self._driver:
            return False
        try:
            # 尝试获取标题来判断连接
            _ = self._driver.title
            return True
        except Exception:
            return False

    # ===== 内部辅助 =====

    def _ensure_driver(self) -> Any:
        """确保 WebDriver 可用。"""
        if not self._driver:
            raise RuntimeError("SeleniumAdapter 未连接")
        return self._driver

    async def _run_in_executor(self, func: Any, *args: Any) -> Any:
        """在线程池中执行同步函数。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args)

    def _element_to_page_element(self, elem: Any) -> PageElement:
        """将 Selenium WebElement 转换为 PageElement。"""
        tag_name = elem.tag_name
        text = elem.text
        inner_html = elem.get_attribute("innerHTML") or ""
        is_visible = elem.is_displayed()
        rect = elem.rect
        bounding_box = {
            "x": rect.get("x", 0),
            "y": rect.get("y", 0),
            "width": rect.get("width", 0),
            "height": rect.get("height", 0),
        }
        # 获取常用属性
        attributes: Dict[str, str] = {}
        for attr_name in ["id", "class", "name", "type", "value", "href", "src"]:
            val = elem.get_attribute(attr_name)
            if val:
                attributes[attr_name] = val
        return PageElement(
            tag_name=tag_name,
            text=text,
            attributes=attributes,
            inner_html=inner_html,
            is_visible=is_visible,
            bounding_box=bounding_box,
        )

    # ===== 页面导航 =====

    async def goto(self, url: str, wait_until: str = "load") -> None:
        driver = self._ensure_driver()
        await self._run_in_executor(driver.get, url)

    async def get_url(self) -> str:
        driver = self._ensure_driver()
        return driver.current_url

    async def get_title(self) -> str:
        driver = self._ensure_driver()
        return driver.title

    # ===== 元素交互 =====

    async def click(self, selector: str, **kwargs: Any) -> None:
        driver = self._ensure_driver()
        elem = driver.find_element("css selector", selector)
        await self._run_in_executor(elem.click)

    async def fill(self, selector: str, value: str) -> None:
        driver = self._ensure_driver()
        elem = driver.find_element("css selector", selector)
        await self._run_in_executor(elem.clear)
        await self._run_in_executor(elem.send_keys, value)

    async def select_option(self, selector: str, value: str) -> None:
        from selenium.webdriver.support.select import Select
        driver = self._ensure_driver()
        elem = driver.find_element("css selector", selector)
        select = Select(elem)
        await self._run_in_executor(select.select_by_value, value)

    async def hover(self, selector: str) -> None:
        from selenium.webdriver.common.action_chains import ActionChains
        driver = self._ensure_driver()
        elem = driver.find_element("css selector", selector)

        def _hover() -> None:
            ActionChains(driver).move_to_element(elem).perform()

        await self._run_in_executor(_hover)

    # ===== 元素查询 =====

    async def query_selector(self, selector: str) -> Optional[PageElement]:
        from selenium.common.exceptions import NoSuchElementException
        driver = self._ensure_driver()
        try:
            elem = driver.find_element("css selector", selector)
            return self._element_to_page_element(elem)
        except NoSuchElementException:
            return None

    async def query_selector_all(self, selector: str) -> List[PageElement]:
        driver = self._ensure_driver()
        elements = driver.find_elements("css selector", selector)
        return [self._element_to_page_element(e) for e in elements]

    async def wait_for_selector(self, selector: str, timeout: float = 30.0) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        driver = self._ensure_driver()

        def _wait() -> None:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )

        await self._run_in_executor(_wait)

    # ===== 截图与脚本 =====

    async def screenshot(self, path: str = "", full_page: bool = False) -> PageScreenshot:
        driver = self._ensure_driver()
        if path:
            await self._run_in_executor(driver.save_screenshot, path)
        data = await self._run_in_executor(driver.get_screenshot_as_png)
        size = driver.get_window_size()
        return PageScreenshot(
            data=data,
            path=path,
            width=size.get("width", 0),
            height=size.get("height", 0),
        )

    async def evaluate(self, script: str) -> Any:
        driver = self._ensure_driver()
        return await self._run_in_executor(driver.execute_script, script)

    # ===== 网络拦截 =====

    async def get_network_entries(self) -> List[NetworkEntry]:
        """从性能日志中提取网络请求记录。"""
        driver = self._ensure_driver()
        try:
            logs = driver.get_log("performance")
            entries: List[NetworkEntry] = []
            for log_entry in logs:
                import json
                message = json.loads(log_entry["message"])
                method_name = message.get("message", {}).get("method", "")
                params = message.get("message", {}).get("params", {})

                if method_name == "Network.responseReceived":
                    resp = params.get("response", {})
                    entries.append(NetworkEntry(
                        url=resp.get("url", ""),
                        method=params.get("request", {}).get("method", ""),
                        status=resp.get("status", 0),
                        resource_type=params.get("type", ""),
                    ))
            self._network_entries.extend(entries)
        except Exception as e:
            logger.debug(f"获取 Selenium 性能日志失败: {e}")
        return list(self._network_entries)

    # ===== 页面管理 =====

    async def new_page(self) -> None:
        driver = self._ensure_driver()
        await self._run_in_executor(driver.execute_script, "window.open('about:blank', '_blank');")
        # 切换到新标签页
        handles = driver.window_handles
        await self._run_in_executor(driver.switch_to.window, handles[-1])

    async def close_page(self) -> None:
        driver = self._ensure_driver()
        await self._run_in_executor(driver.close)
        # 切换回前一个标签页
        handles = driver.window_handles
        if handles:
            await self._run_in_executor(driver.switch_to.window, handles[-1])

    async def get_cookies(self) -> List[Dict[str, Any]]:
        driver = self._ensure_driver()
        return driver.get_cookies()

    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        driver = self._ensure_driver()
        for cookie in cookies:
            driver.add_cookie(cookie)

    async def clear_cookies(self) -> None:
        driver = self._ensure_driver()
        driver.delete_all_cookies()
