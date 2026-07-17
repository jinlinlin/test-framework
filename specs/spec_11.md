# 基于PlayWright的UI自动化测试

## 补充：UI自动化测试（基于Playwright）

在原目录基础上，补充UI自动化测试的完整设计：

---

### 一、新增/调整的目录结构

```
test_framework/
│
├── core/
│   ├── playwright/                                      # 🆕 Playwright核心封装
│   │   ├── __init__.py
│   │   ├── base_page.py                                # 页面基类（模板模式）
│   │   ├── base_component.py                           # 组件基类（组合模式）
│   │   ├── base_test.py                                # 测试基类
│   │   ├── playwright_manager.py                       # Playwright管理器（单例模式）
│   │   ├── page_factory.py                             # 页面工厂（工厂模式）
│   │   ├── element_locator.py                          # 元素定位器（策略模式）
│   │   ├── wait_conditions.py                          # 等待条件
│   │   ├── action_chains.py                            # 操作链（建造者模式）
│   │   ├── assertion_chain.py                          # 断言链（建造者模式）
│   │   ├── network_interceptor.py                      # 网络拦截器
│   │   └── fixture_manager.py                          # 夹具管理
│   │
│   └── interfaces/
│       ├── ui_interactable.py                          # 🆕 UI交互接口
│       ├── element_locatable.py                        # 🆕 元素定位接口
│       └── assertable.py                               # 🆕 断言接口
│
├── engines/
│   ├── ui_automation/                                   # 🆕 UI自动化测试
│   │   ├── __init__.py
│   │   ├── engine.py                                   # UI自动化引擎
│   │   ├── test_runner.py                              # 测试运行器（命令模式）
│   │   │
│   │   ├── locators/                                   # 定位策略（策略模式）
│   │   │   ├── __init__.py
│   │   │   ├── base.py                                 # 定位器基类
│   │   │   ├── css.py                                  # CSS选择器
│   │   │   ├── xpath.py                                # XPath
│   │   │   ├── test_id.py                              # data-testid
│   │   │   ├── text.py                                 # 文本
│   │   │   ├── role.py                                 # ARIA role
│   │   │   ├── placeholder.py                          # placeholder
│   │   │   ├── label.py                                # label
│   │   │   ├── alt.py                                  # alt text
│   │   │   ├── title.py                                # title属性
│   │   │   └── composite.py                            # 复合定位器
│   │   │
│   │   ├── actions/                                    # UI操作（命令模式）
│   │   │   ├── __init__.py
│   │   │   ├── base.py                                 # 操作基类
│   │   │   ├── click.py                                # 点击
│   │   │   ├── dblclick.py                             # 双击
│   │   │   ├── rightclick.py                           # 右键
│   │   │   ├── fill.py                                 # 填充
│   │   │   ├── type.py                                 # 逐字输入
│   │   │   ├── clear.py                                # 清空
│   │   │   ├── hover.py                                # 悬停
│   │   │   ├── drag.py                                 # 拖拽
│   │   │   ├── scroll.py                               # 滚动
│   │   │   ├── select.py                               # 下拉选择
│   │   │   ├── check.py                                # 勾选
│   │   │   ├── uncheck.py                              # 取消勾选
│   │   │   ├── upload.py                               # 文件上传
│   │   │   ├── focus.py                                # 聚焦
│   │   │   ├── blur.py                                 # 失焦
│   │   │   ├── press.py                                # 按键
│   │   │   ├── screenshot.py                           # 截图
│   │   │   ├── wait.py                                 # 等待
│   │   │   └── composite.py                            # 复合操作
│   │   │
│   │   ├── assertions/                                 # UI断言
│   │   │   ├── __init__.py
│   │   │   ├── base.py                                 # 断言基类
│   │   │   ├── visibility.py                           # 可见性
│   │   │   ├── text.py                                 # 文本
│   │   │   ├── attribute.py                            # 属性
│   │   │   ├── css_property.py                         # CSS属性
│   │   │   ├── count.py                                # 元素数量
│   │   │   ├── url.py                                  # URL
│   │   │   ├── title.py                                # 标题
│   │   │   ├── enabled.py                              # 启用状态
│   │   │   ├── checked.py                              # 勾选状态
│   │   │   ├── focused.py                              # 聚焦状态
│   │   │   ├── screenshot_compare.py                   # 截图对比
│   │   │   ├── network.py                              # 网络断言
│   │   │   ├── console.py                              # 控制台断言
│   │   │   └── composite.py                            # 复合断言
│   │   │
│   │   ├── waiters/                                    # 等待策略（策略模式）
│   │   │   ├── __init__.py
│   │   │   ├── base.py                                 # 等待器基类
│   │   │   ├── visibility.py                           # 等待可见
│   │   │   ├── presence.py                             # 等待存在
│   │   │   ├── hidden.py                               # 等待隐藏
│   │   │   ├── clickable.py                            # 等待可点击
│   │   │   ├── enabled.py                              # 等待启用
│   │   │   ├── text_change.py                          # 等待文本变化
│   │   │   ├── network_idle.py                         # 等待网络空闲
│   │   │   ├── load_state.py                           # 等待加载状态
│   │   │   ├── url_change.py                           # 等待URL变化
│   │   │   ├── navigation.py                           # 等待导航
│   │   │   ├── response.py                             # 等待响应
│   │   │   ├── request.py                              # 等待请求
│   │   │   ├── console_log.py                          # 等待控制台日志
│   │   │   ├── custom.py                               # 自定义等待
│   │   │   └── composite.py                            # 复合等待
│   │   │
│   │   ├── page_objects/                               # Page Object
│   │   │   ├── __init__.py
│   │   │   ├── login_page.py                           # 登录页面
│   │   │   ├── dashboard_page.py                       # 仪表板
│   │   │   ├── components/                             # 可复用组件
│   │   │   │   ├── __init__.py
│   │   │   │   ├── header.py
│   │   │   │   ├── sidebar.py
│   │   │   │   ├── footer.py
│   │   │   │   ├── modal.py
│   │   │   │   ├── table.py
│   │   │   │   ├── form.py
│   │   │   │   ├── dropdown.py
│   │   │   │   ├── tabs.py
│   │   │   │   ├── pagination.py
│   │   │   │   ├── toast.py
│   │   │   │   ├── loading.py
│   │   │   │   └── menu.py
│   │   │   └── modules/                                 # 按功能模块
│   │   │       ├── __init__.py
│   │   │       ├── user_management/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── user_list_page.py
│   │   │       │   ├── user_create_page.py
│   │   │       │   └── user_edit_page.py
│   │   │       ├── order_management/
│   │   │       │   ├── __init__.py
│   │   │       │   └── order_list_page.py
│   │   │       └── reporting/
│   │   │           ├── __init__.py
│   │   │           └── report_viewer.py
│   │   │
│   │   ├── fixtures/                                    # 测试夹具
│   │   │   ├── __init__.py
│   │   │   ├── test_data.py                             # 测试数据
│   │   │   ├── test_users.py                            # 测试用户
│   │   │   ├── test_credentials.py                      # 测试凭证
│   │   │   └── test_products.py                         # 测试产品数据
│   │   │
│   │   ├── browser_manager.py                           # 浏览器管理器
│   │   ├── context_manager.py                           # 上下文管理器
│   │   ├── trace_viewer.py                              # 追踪查看器
│   │   ├── video_recorder.py                            # 视频录制
│   │   ├── network_capture.py                           # 网络捕获
│   │   ├── console_logger.py                            # 控制台日志
│   │   ├── coverage_collector.py                        # 代码覆盖率
│   │   ├── accessibility_checker.py                     # 可访问性检查
│   │   └── config_schema.py
│   │
│   ├── web_performance/                                  # 网页性能测试
│   │   ├── __init__.py
│   │   ├── engine.py                                    # 性能测试引擎
│   │   ├── web_vitals.py                                # Web Vitals采集
│   │   ├── lighthouse_integration.py                    # Lighthouse集成
│   │   ├── resource_monitor.py                          # 资源监控
│   │   └── config_schema.py
│   │
│   ├── rest_api/                                        # REST API测试
│   │   ├── __init__.py
│   │   ├── engine.py                                    # Python引擎
│   │   ├── engine.js                                    # Node.js引擎
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── client.py                                # API客户端
│   │   │   ├── request.py                               # 请求构建器
│   │   │   ├── response.py                              # 响应处理
│   │   │   └── session.py                               # 会话管理
│   │   ├── validators/                                  # 验证器
│   │   │   ├── __init__.py
│   │   │   ├── schema.py                                # Schema验证
│   │   │   ├── json_path.py                             # JSON Path
│   │   │   └── composite.py                             # 复合验证
│   │   └── config_schema.py
│   │
│   └── ... (其他引擎)
│
├── test_suites/                                         # 🆕 测试套件
│   ├── __init__.py
│   ├── ui_suites/
│   │   ├── __init__.py
│   │   ├── smoke_ui.py                                  # UI冒烟测试
│   │   ├── regression_ui.py                             # UI回归测试
│   │   ├── e2e_ui.py                                    # UI端到端测试
│   │   └── visual_ui.py                                 # 视觉回归测试
│   ├── api_suites/
│   │   ├── __init__.py
│   │   ├── smoke_api.py
│   │   ├── regression_api.py
│   │   └── contract_api.py
│   └── combined_suites/                                  # 组合测试
│       ├── __init__.py
│       └── full_e2e.py                                  # 完整端到端
│
├── config/
│   ├── playwright/                                      # 🆕 Playwright配置
│   │   ├── __init__.py
│   │   ├── base.json
│   │   ├── chromium.json
│   │   ├── firefox.json
│   │   └── webkit.json
│   └── ...
│
└── ... (其余目录保持不变)
```

---

### 二、Playwright核心代码实现

#### 1. Playwright管理器 (core/playwright/playwright_manager.py)

```python
"""
Playwright管理器 - 单例模式
管理浏览器实例、上下文、页面
"""

import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from playwright.async_api import (
    Playwright, Browser, BrowserContext, Page, 
    BrowserType, Request, Response, Route
)
import logging

logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """浏览器配置"""
    headless: bool = True
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    device_scale_factor: float = 1.0
    locale: str = "zh-CN"
    timezone_id: str = "Asia/Shanghai"
    permissions: List[str] = field(default_factory=list)
    downloads_path: Optional[str] = None
    user_agent: Optional[str] = None
    ignore_https_errors: bool = False
    slow_mo: int = 0
    record_video_dir: Optional[str] = None
    record_har_path: Optional[str] = None
    trace_dir: Optional[str] = None
    screenshot_on_failure: bool = True
    video_on_failure: bool = True


class PlaywrightManager:
    """
    Playwright管理器 - 单例模式
    管理浏览器生命周期
    """
    
    _instance: Optional["PlaywrightManager"] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._current_page: Optional[Page] = None
        self._config = BrowserConfig()
        self._contexts: List[BrowserContext] = []
        self._pages: List[Page] = []
        
    @classmethod
    async def get_instance(cls) -> "PlaywrightManager":
        """获取单例实例"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    async def initialize(self, config: Optional[BrowserConfig] = None) -> None:
        """初始化Playwright"""
        if config:
            self._config = config
            
        self._playwright = await self._launch_playwright()
        self._browser = await self._launch_browser()
        self._context = await self._create_context()
        self._current_page = await self._create_page()
        
        logger.info("Playwright initialized successfully")
    
    async def _launch_playwright(self) -> Playwright:
        """启动Playwright"""
        from playwright.async_api import async_playwright
        playwright = await async_playwright().start()
        return playwright
    
    async def _launch_browser(self) -> Browser:
        """启动浏览器"""
        browser = await self._playwright.chromium.launch(
            headless=self._config.headless,
            slow_mo=self._config.slow_mo,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
            ]
        )
        return browser
    
    async def _create_context(self) -> BrowserContext:
        """创建浏览器上下文"""
        context = await self._browser.new_context(
            viewport=self._config.viewport,
            device_scale_factor=self._config.device_scale_factor,
            locale=self._config.locale,
            timezone_id=self._config.timezone_id,
            permissions=self._config.permissions,
            downloads_path=self._config.downloads_path,
            user_agent=self._config.user_agent,
            ignore_https_errors=self._config.ignore_https_errors,
            record_video_dir=self._config.record_video_dir,
            record_har_path=self._config.record_har_path,
        )
        self._contexts.append(context)
        return context
    
    async def _create_page(self) -> Page:
        """创建页面"""
        page = await self._context.new_page()
        self._pages.append(page)
        
        # 设置默认超时
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(30000)
        
        # 注册事件监听
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("console", self._on_console)
        page.on("dialog", self._on_dialog)
        page.on("pageerror", self._on_page_error)
        
        return page
    
    async def close(self) -> None:
        """关闭所有资源"""
        # 关闭页面
        for page in self._pages:
            try:
                await page.close()
            except Exception as e:
                logger.warning(f"Error closing page: {e}")
        
        # 关闭上下文
        for context in self._contexts:
            try:
                if self._config.trace_dir:
                    await context.close()
                else:
                    await context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")
        
        # 关闭浏览器
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
        
        # 停止Playwright
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
        
        logger.info("Playwright closed successfully")
    
    # ========== 页面管理 ==========
    
    async def new_page(self) -> Page:
        """创建新页面"""
        page = await self._context.new_page()
        self._pages.append(page)
        return page
    
    async def switch_to_page(self, index: int) -> Page:
        """切换到指定页面"""
        if 0 <= index < len(self._pages):
            self._current_page = self._pages[index]
            return self._current_page
        raise IndexError(f"Page index {index} out of range")
    
    @property
    def current_page(self) -> Page:
        """获取当前页面"""
        if not self._current_page:
            raise RuntimeError("No current page available")
        return self._current_page
    
    # ========== 上下文管理 ==========
    
    async def new_context(self, **kwargs) -> BrowserContext:
        """创建新上下文"""
        context = await self._browser.new_context(**kwargs)
        self._contexts.append(context)
        return context
    
    async def switch_context(self, context: BrowserContext) -> None:
        """切换上下文"""
        self._context = context
        self._current_page = context.pages[0] if context.pages else await context.new_page()
    
    # ========== 事件监听 ==========
    
    def _on_request(self, request: Request) -> None:
        """请求事件"""
        logger.debug(f"Request: {request.method} {request.url}")
    
    def _on_response(self, response: Response) -> None:
        """响应事件"""
        logger.debug(f"Response: {response.status} {response.url}")
    
    def _on_console(self, msg) -> None:
        """控制台事件"""
        logger.debug(f"Console: {msg.type} - {msg.text}")
    
    def _on_dialog(self, dialog) -> None:
        """对话框事件"""
        logger.warning(f"Dialog: {dialog.type} - {dialog.message}")
        # 默认接受对话框
        dialog.accept()
    
    def _on_page_error(self, error) -> None:
        """页面错误事件"""
        logger.error(f"Page error: {error}")
    
    # ========== 追踪和录制 ==========
    
    async def start_trace(self, name: str = "trace") -> None:
        """开始追踪"""
        if self._context:
            await self._context.tracing.start(
                name=name,
                screenshots=True,
                snapshots=True,
                sources=True
            )
    
    async def stop_trace(self, path: str) -> None:
        """停止追踪"""
        if self._context:
            await self._context.tracing.stop(path=path)
    
    async def start_har(self, path: str) -> None:
        """开始录制HAR"""
        if self._context:
            await self._context.route_from_har(path)
    
    # ========== 截图 ==========
    
    async def screenshot(self, path: str, full_page: bool = True) -> bytes:
        """截图"""
        return await self.current_page.screenshot(path=path, full_page=full_page)
    
    # ========== 设备模拟 ==========
    
    async def emulate_device(self, device_name: str) -> None:
        """模拟设备"""
        from playwright.async_api import devices
        device = devices.get(device_name)
        if device:
            await self._context.set_viewport_size(device["viewport"])
            await self._context.add_init_script(
                f'Object.defineProperty(navigator, "userAgent", {{ value: "{device["user_agent"]}" }});'
            )
    
    # ========== 地理位置 ==========
    
    async def set_geolocation(self, latitude: float, longitude: float) -> None:
        """设置地理位置"""
        await self._context.set_geolocation({"latitude": latitude, "longitude": longitude})
        await self._context.grant_permissions(["geolocation"])
```

#### 2. 页面基类 (core/playwright/base_page.py)

```python
"""
页面基类 - 模板模式
所有Page Object继承此类
"""

from typing import Optional, Union, List, TypeVar, Generic, Any
from playwright.async_api import Page, Locator, ElementHandle, expect
import asyncio
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

T = TypeVar('T', bound='BasePage')


class BasePage(ABC):
    """
    Page Object基类
    提供所有页面共用的方法和属性
    """
    
    # 页面URL路径 - 子类必须重写
    URL_PATH: str = ""
    
    # 页面加载完成时的标识元素
    LOAD_INDICATOR: Optional[str] = None
    
    def __init__(
        self, 
        page: Page, 
        base_url: Optional[str] = None,
        timeout: int = 30000
    ):
        self._page = page
        self._base_url = base_url or ""
        self._timeout = timeout
        self._retry_count = 3
        self._screenshot_on_failure = True
        
        # 子类可重写此方法进行额外初始化
        self._init_page()
    
    def _init_page(self) -> None:
        """子类可重写的初始化方法"""
        pass
    
    # ========== 属性 ==========
    
    @property
    def page(self) -> Page:
        """获取Playwright Page对象"""
        return self._page
    
    @property
    def base_url(self) -> str:
        return self._base_url
    
    @property
    def timeout(self) -> int:
        return self._timeout
    
    # ========== 导航方法 ==========
    
    def navigate(self, path: str = "", **kwargs) -> T:
        """
        导航到指定路径
        返回self支持链式调用
        """
        url = f"{self._base_url}{path or self.URL_PATH}"
        
        async def _navigate():
            await self._page.goto(url, wait_until="networkidle", **kwargs)
            await self.wait_for_load()
            return self
        
        return _navigate()
    
    async def goto(self, url: str, **kwargs) -> T:
        """直接跳转到URL"""
        await self._page.goto(url, wait_until="networkidle", **kwargs)
        await self.wait_for_load()
        return self
    
    async def refresh(self) -> T:
        """刷新页面"""
        await self._page.reload(wait_until="networkidle")
        await self.wait_for_load()
        return self
    
    async def go_back(self) -> T:
        """后退"""
        await self._page.go_back(wait_until="networkidle")
        await self.wait_for_load()
        return self
    
    async def go_forward(self) -> T:
        """前进"""
        await self._page.go_forward(wait_until="networkidle")
        await self.wait_for_load()
        return self
    
    # ========== 元素定位方法 ==========
    
    def locate(self, selector: str, **kwargs) -> Locator:
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
        self, 
        selector: str, 
        timeout: Optional[int] = None,
        state: str = "visible"
    ) -> Locator:
        """查找单个元素"""
        locator = self.locate(selector)
        await locator.first.wait_for(state=state, timeout=timeout or self._timeout)
        return locator
    
    async def find_elements(self, selector: str) -> List[Locator]:
        """查找多个元素"""
        return await self.locate(selector).all()
    
    async def wait_for_element(
        self, 
        selector: str, 
        timeout: Optional[int] = None,
        state: str = "visible"
    ) -> Locator:
        """等待元素出现"""
        locator = self.locate(selector)
        await locator.first.wait_for(state=state, timeout=timeout or self._timeout)
        return locator
    
    # ========== 页面等待方法 ==========
    
    async def wait_for_load(self, timeout: Optional[int] = None) -> T:
        """等待页面加载完成"""
        await self._page.wait_for_load_state(
            "networkidle", 
            timeout=timeout or self._timeout
        )
        
        # 如果有加载指示器，等待其隐藏
        if self.LOAD_INDICATOR:
            try:
                await self._page.locator(self.LOAD_INDICATOR).wait_for(
                    state="hidden",
                    timeout=5000
                )
            except:
                pass
        
        return self
    
    async def wait_for_navigation(self, timeout: Optional[int] = None) -> T:
        """等待导航完成"""
        async with self._page.expect_navigation(
            timeout=timeout or self._timeout
        ):
            return self
    
    async def wait_for_url(self, url_pattern: str, timeout: Optional[int] = None) -> T:
        """等待URL匹配"""
        await self._page.wait_for_url(
            url_pattern,
            timeout=timeout or self._timeout
        )
        return self
    
    async def wait_for_timeout(self, milliseconds: int) -> T:
        """等待指定毫秒"""
        await self._page.wait_for_timeout(milliseconds)
        return self
    
    # ========== 交互方法 ==========
    
    async def click(
        self, 
        selector: str, 
        timeout: Optional[int] = None,
        **kwargs
    ) -> T:
        """点击元素"""
        locator = await self.find_element(selector, timeout)
        await locator.click(**kwargs)
        return self
    
    async def dblclick(
        self, 
        selector: str, 
        timeout: Optional[int] = None,
        **kwargs
    ) -> T:
        """双击元素"""
        locator = await self.find_element(selector, timeout)
        await locator.dblclick(**kwargs)
        return self
    
    async def rightclick(
        self, 
        selector: str, 
        timeout: Optional[int] = None,
        **kwargs
    ) -> T:
        """右键点击"""
        locator = await self.find_element(selector, timeout)
        await locator.click(button="right", **kwargs)
        return self
    
    async def fill(
        self, 
        selector: str, 
        text: str, 
        clear_first: bool = True,
        timeout: Optional[int] = None
    ) -> T:
        """填充文本"""
        locator = await self.find_element(selector, timeout)
        if clear_first:
            await locator.clear()
        await locator.fill(text)
        return self
    
    async def type_text(
        self, 
        selector: str, 
        text: str, 
        delay: int = 50,
        timeout: Optional[int] = None
    ) -> T:
        """逐字输入"""
        locator = await self.find_element(selector, timeout)
        await locator.type(text, delay=delay)
        return self
    
    async def clear(self, selector: str, timeout: Optional[int] = None) -> T:
        """清空输入框"""
        locator = await self.find_element(selector, timeout)
        await locator.clear()
        return self
    
    async def hover(self, selector: str, timeout: Optional[int] = None) -> T:
        """悬停"""
        locator = await self.find_element(selector, timeout)
        await locator.hover()
        return self
    
    async def drag_to(
        self, 
        source_selector: str, 
        target_selector: str,
        timeout: Optional[int] = None
    ) -> T:
        """拖拽"""
        source = await self.find_element(source_selector, timeout)
        target = await self.find_element(target_selector, timeout)
        await source.drag_to(target)
        return self
    
    async def select_option(
        self, 
        selector: str, 
        value: Union[str, List[str]],
        timeout: Optional[int] = None
    ) -> T:
        """选择下拉选项"""
        locator = await self.find_element(selector, timeout)
        await locator.select_option(value)
        return self
    
    async def check(self, selector: str, timeout: Optional[int] = None) -> T:
        """勾选复选框"""
        locator = await self.find_element(selector, timeout)
        await locator.check()
        return self
    
    async def uncheck(self, selector: str, timeout: Optional[int] = None) -> T:
        """取消勾选"""
        locator = await self.find_element(selector, timeout)
        await locator.uncheck()
        return self
    
    async def upload_file(
        self, 
        selector: str, 
        file_path: Union[str, List[str]],
        timeout: Optional[int] = None
    ) -> T:
        """上传文件"""
        locator = await self.find_element(selector, timeout)
        await locator.set_input_files(file_path)
        return self
    
    async def focus(self, selector: str, timeout: Optional[int] = None) -> T:
        """聚焦元素"""
        locator = await self.find_element(selector, timeout)
        await locator.focus()
        return self
    
    async def press(self, selector: str, key: str, timeout: Optional[int] = None) -> T:
        """按键"""
        locator = await self.find_element(selector, timeout)
        await locator.press(key)
        return self
    
    async def scroll_to(self, selector: str, timeout: Optional[int] = None) -> T:
        """滚动到元素"""
        locator = await self.find_element(selector, timeout)
        await locator.scroll_into_view_if_needed()
        return self
    
    async def scroll(self, x: int = 0, y: int = 0) -> T:
        """滚动页面"""
        await self._page.mouse.wheel(x, y)
        return self
    
    # ========== 获取信息方法 ==========
    
    async def get_text(self, selector: str, timeout: Optional[int] = None) -> str:
        """获取文本"""
        locator = await self.find_element(selector, timeout)
        return await locator.text_content() or ""
    
    async def get_attribute(
        self, 
        selector: str, 
        attribute: str,
        timeout: Optional[int] = None
    ) -> Optional[str]:
        """获取属性"""
        locator = await self.find_element(selector, timeout)
        return await locator.get_attribute(attribute)
    
    async def get_value(self, selector: str, timeout: Optional[int] = None) -> str:
        """获取输入框值"""
        locator = await self.find_element(selector, timeout)
        return await locator.input_value()
    
    async def get_url(self) -> str:
        """获取当前URL"""
        return self._page.url
    
    async def get_title(self) -> str:
        """获取页面标题"""
        return await self._page.title()
    
    async def get_inner_html(self, selector: str, timeout: Optional[int] = None) -> str:
        """获取内部HTML"""
        locator = await self.find_element(selector, timeout)
        return await locator.inner_html()
    
    async def get_outer_html(self, selector: str, timeout: Optional[int] = None) -> str:
        """获取外部HTML"""
        locator = await self.find_element(selector, timeout)
        return await locator.inner_html()
    
    # ========== 截图 ==========
    
    async def screenshot(
        self, 
        path: Optional[str] = None,
        full_page: bool = True,
        **kwargs
    ) -> bytes:
        """截图"""
        return await self._page.screenshot(
            path=path,
            full_page=full_page,
            **kwargs
        )
    
    async def element_screenshot(
        self, 
        selector: str, 
        path: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> bytes:
        """元素截图"""
        locator = await self.find_element(selector, timeout)
        return await locator.screenshot(path=path)
    
    # ========== 断言方法 (使用expect) ==========
    
    async def assert_visible(self, selector: str, timeout: Optional[int] = None) -> None:
        """断言元素可见"""
        locator = self.locate(selector)
        await expect(locator).to_be_visible(timeout=timeout or self._timeout)
    
    async def assert_hidden(self, selector: str, timeout: Optional[int] = None) -> None:
        """断言元素隐藏"""
        locator = self.locate(selector)
        await expect(locator).to_be_hidden(timeout=time