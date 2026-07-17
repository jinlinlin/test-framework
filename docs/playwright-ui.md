# Playwright UI 自动化测试

## 概述

本框架基于 [Playwright](https://playwright.dev/python/) 构建了完整的 UI 自动化测试能力，采用**分层架构 + 多种设计模式**，覆盖浏览器管理、Page Object 模型、组件复用、操作链、断言链、网络拦截、等待策略等核心场景。

整体架构分为四层：

```
┌─────────────────────────────────────────────────────────────┐
│  UI 自动化引擎 (engines/ui_automation/)                      │
│    UIAutomationEngine · TestRunner · 页面对象 · 组件库        │
├─────────────────────────────────────────────────────────────┤
│  Playwright 核心封装 (core/playwright/)                       │
│    PlaywrightManager · BasePage · BaseComponent              │
│    ActionChains · AssertionChain · NetworkInterceptor         │
│    ElementLocator · WaitConditions · FixtureManager           │
├─────────────────────────────────────────────────────────────┤
│  浏览器适配器层 (adapters/browser/)                            │
│    BrowserAdapter(ABC) · PlaywrightAdapter · SeleniumAdapter  │
├─────────────────────────────────────────────────────────────┤
│  Web 性能引擎 (engines/web_performance/)                      │
│    WebPerformanceEngine · WebVitals · Lighthouse · Resource   │
└─────────────────────────────────────────────────────────────┘
```

---

## 模块清单

### core/playwright/ — Playwright 核心封装

| 文件 | 说明 | 设计模式 |
|------|------|---------|
| `playwright_manager.py` | 浏览器/上下文/页面生命周期管理 | 单例模式 |
| `base_page.py` | Page Object 基类，提供导航/定位/交互/断言 | 模板模式 |
| `base_component.py` | 可复用 UI 组件基类，支持嵌套 | 组合模式 |
| `base_test.py` | 测试基类，统一 fixture 管理 | 模板模式 |
| `page_factory.py` | 页面对象工厂 | 工厂模式 |
| `element_locator.py` | 多策略元素定位 | 策略模式 |
| `wait_conditions.py` | 等待条件集合（可见/隐藏/文本/URL/网络等） | 策略模式 |
| `action_chains.py` | 操作链，组合多步骤一次性执行 | 建造者模式 |
| `assertion_chain.py` | 断言链，链式组合多个断言 | 建造者模式 |
| `network_interceptor.py` | 网络请求拦截、修改、Mock、记录 | 观察者模式 |
| `fixture_manager.py` | 测试数据与 Fixture 管理 | 单例模式 |

### engines/ui_automation/ — UI 自动化引擎

| 文件 | 说明 |
|------|------|
| `engine.py` | UIAutomationEngine，基于配置驱动执行测试用例 |
| `test_runner.py` | TestRunner 命令模式运行器，支持命令序列执行与取消 |
| `browser_manager.py` | 浏览器创建与关闭封装 |
| `context_manager.py` | 上下文创建/页面管理 |
| `config_schema.py` | pydantic 配置 Schema（BrowserConfig/TraceConfig/VideoConfig 等） |
| `console_logger.py` | 浏览器控制台日志采集 |
| `network_capture.py` | 网络请求捕获与过滤 |
| `accessibility_checker.py` | 无障碍访问检查 |
| `coverage_collector.py` | 前端代码覆盖率采集 |
| `trace_viewer.py` | Trace 查看器封装 |
| `video_recorder.py` | 视频录制封装 |
| `actions/` | 22 个操作类（click/fill/type/select/hover/drag/scroll 等） |
| `assertions/` | 15 个断言类（visible/text/attribute/url/title/count/network 等） |
| `locators/` | 11 个定位策略（css/xpath/test_id/role/text/placeholder/label 等） |
| `waiters/` | 18 个等待条件（visibility/hidden/url_change/network_idle/response 等） |
| `page_objects/` | Page Object 示例（LoginPage/DashboardPage 等） |
| `page_objects/components/` | 可复用组件（Modal/Form/Table/Tabs/Header/Sidebar 等 12 个） |
| `page_objects/modules/` | 业务模块页面（用户管理/订单管理/报表查看等） |

### adapters/browser/ — 浏览器适配器

| 文件 | 说明 |
|------|------|
| `adapter.py` | BrowserAdapter 抽象基类，定义统一接口 |
| `playwright_impl.py` | PlaywrightAdapter，支持 Chromium/Firefox/WebKit |
| `selenium_impl.py` | SeleniumAdapter，支持 Chrome/Firefox/Edge |

### engines/web_performance/ — Web 性能引擎

| 文件 | 说明 |
|------|------|
| `engine.py` | WebPerformanceEngine，模板模式执行性能采集 |
| `playwright_client.py` | PlaywrightClient，封装 Playwright API |
| `web_vitals.py` | WebVitalsCollector，注入 JS 采集 LCP/FCP/CLS/FID/INP/TTFB |
| `page_analyzer.py` | PageAnalyzer，DOM 分析 + 性能时间线分析 |
| `resource_monitor.py` | ResourceMonitor，按类型统计网络资源（count/size） |
| `lighthouse_integration.py` | LighthouseIntegration，调用 CLI 并解析 JSON 报告 |
| `config_schema.py` | pydantic 配置 Schema |

---

## 核心类详解

### PlaywrightManager — 单例管理器

管理 Playwright 实例、浏览器、上下文和页面的完整生命周期。

```python
from test_framework.core.playwright import PlaywrightManager, BrowserConfig

# 获取单例
manager = await PlaywrightManager.get_instance()

# 自定义配置
config = BrowserConfig(
    headless=True,
    viewport={"width": 1920, "height": 1080},
    locale="zh-CN",
    timezone_id="Asia/Shanghai",
    ignore_https_errors=True,
    slow_mo=100,
    record_video_dir="artifacts/videos",
    trace_dir="artifacts/traces",
)
await manager.initialize(config)

# 页面操作
page = manager.current_page
await page.goto("https://example.com")

# 多页面支持
page2 = await manager.new_page()
await manager.switch_to_page(1)

# Trace 追踪
await manager.start_trace("my-trace")
# ... 执行操作 ...
await manager.stop_trace("artifacts/trace.zip")

# 设备模拟
await manager.emulate_device("iPhone 13")
await manager.set_geolocation(39.9042, 116.4074)

# 关闭所有资源
await manager.close()
```

**BrowserConfig 完整参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `headless` | bool | True | 无头模式 |
| `viewport` | Dict | 1920×1080 | 视口大小 |
| `device_scale_factor` | float | 1.0 | 设备像素比 |
| `locale` | str | "zh-CN" | 语言 |
| `timezone_id` | str | "Asia/Shanghai" | 时区 |
| `permissions` | List | [] | 权限列表 |
| `user_agent` | str | None | UA |
| `ignore_https_errors` | bool | False | 忽略 HTTPS 错误 |
| `slow_mo` | int | 0 | 操作减速（ms） |
| `record_video_dir` | str | None | 视频录制目录 |
| `record_har_path` | str | None | HAR 录制路径 |
| `trace_dir` | str | None | Trace 目录 |
| `screenshot_on_failure` | bool | True | 失败时截图 |
| `video_on_failure` | bool | True | 失败时录视频 |

---

### BasePage — Page Object 基类

所有页面继承此类，提供导航、定位、交互、断言全套能力，**所有方法支持链式调用**。

```python
from test_framework.core.playwright import BasePage

class UserListPage(BasePage):
    URL_PATH = "/users"
    LOAD_INDICATOR = ".loading-spinner"

    def _init_page(self) -> None:
        self.search_input = self.locate_by_placeholder("搜索用户")
        self.add_button = self.locate_by_test_id("add-user-btn")
        self.user_rows = self.locate("tr.user-row")

    async def search(self, keyword: str) -> "UserListPage":
        await self.fill('input[placeholder="搜索用户"]', keyword)
        await self.press('input[placeholder="搜索用户"]', "Enter")
        await self.wait_for_load()
        return self

    async def click_add(self) -> "UserListPage":
        await self.click('button[data-testid="add-user-btn"]')
        return self

# 使用
page = UserListPage(driver_page, base_url="https://app.example.com")
await page.navigate()
await page.search("张三")
await page.assert_visible("tr.user-row")
```

**核心方法**：

- **导航**：`navigate()` / `goto()` / `refresh()` / `go_back()` / `go_forward()`
- **定位**：`locate()` / `locate_by_test_id()` / `locate_by_role()` / `locate_by_text()` / `locate_by_placeholder()` / `locate_by_label()` / `locate_by_alt()` / `locate_by_title()`
- **交互**：`click()` / `dblclick()` / `rightclick()` / `fill()` / `type_text()` / `clear()` / `hover()` / `drag_to()` / `select_option()` / `check()` / `uncheck()` / `upload_file()` / `focus()` / `press()` / `scroll_to()` / `scroll()`
- **查询**：`find_element()` / `find_elements()` / `wait_for_element()` / `get_text()` / `get_attribute()` / `get_value()` / `get_url()` / `get_title()`
- **断言**：`assert_visible()` / `assert_hidden()` / `assert_text()` / `assert_attribute()` / `assert_css_property()` / `assert_count()` / `assert_url()` / `assert_title()` / `assert_enabled()` / `assert_checked()` / `assert_focused()`
- **截图**：`screenshot()` / `element_screenshot()`

---

### BaseComponent — 可复用组件基类

将通用 UI 组件（Modal、Form、Table 等）抽象为可嵌套组合的组件类。

```python
from test_framework.core.playwright import BaseComponent

class SearchForm(BaseComponent):
    ROOT_SELECTOR = ".search-form"

    async def search(self, keyword: str) -> "SearchForm":
        await self.fill('input[type="text"]', keyword)
        await self.click('button[type="submit"]')
        return self

class UserListPage(BasePage):
    URL_PATH = "/users"

    def _init_page(self) -> None:
        self.search_form = SearchForm(self._page)
        # 注册为子组件，支持嵌套
        self.register_component("search", self.search_form)

# 使用
page = UserListPage(driver_page, base_url="https://app.example.com")
await page.navigate()
await page.search_form.search("张三")
```

**内置组件库**（`page_objects/components/`）：

| 组件 | 说明 |
|------|------|
| `ModalComponent` | 弹窗（确认/取消/关闭） |
| `FormComponent` | 表单（提交/重置/字段操作） |
| `TableComponent` | 数据表格 |
| `TabsComponent` | 选项卡 |
| `DropdownComponent` | 下拉菜单 |
| `MenuComponent` | 菜单导航 |
| `HeaderComponent` | 顶部导航栏 |
| `SidebarComponent` | 侧边栏 |
| `FooterComponent` | 底部栏 |
| `PaginationComponent` | 分页器 |
| `LoadingComponent` | 加载指示器 |
| `ToastComponent` | 消息提示 |

---

### ActionChains — 操作链

将多个操作步骤组合为链式调用，一次性执行：

```python
from test_framework.core.playwright.action_chains import ActionChains

chain = ActionChains(page)
await (chain
    .click("#login-btn")
    .fill("#username", "admin")
    .fill("#password", "secret")
    .click("#submit")
    .wait_for_url("**/dashboard")
    .execute()
)
```

### AssertionChain — 断言链

将多个断言组合为链式调用：

```python
from test_framework.core.playwright.assertion_chain import AssertionChain

chain = AssertionChain(page)
result = await (chain
    .visible("#header")
    .text("#title", "Welcome")
    .url("**/dashboard")
    .execute()
)
assert result.all_passed
```

### NetworkInterceptor — 网络拦截器

拦截、修改、Mock 和记录网络请求：

```python
from test_framework.core.playwright.network_interceptor import NetworkInterceptor

interceptor = NetworkInterceptor(page)

# 拦截并修改请求
await interceptor.intercept_request("**/api/users", method="GET",
    modify_headers={"Authorization": "Bearer mock-token"})

# Mock 响应
await interceptor.mock_response("**/api/config", 
    status=200, body={"feature_flag": True})

# 记录所有请求
entries = interceptor.get_entries()
for entry in entries:
    print(f"{entry.request.method} {entry.request.url} -> {entry.response.status}")

# 等待特定请求完成
entry = await interceptor.wait_for_request("**/api/submit", timeout=10000)
```

---

## UIAutomationEngine — 配置驱动引擎

通过 YAML 配置定义完整测试流程，无需编写代码：

```yaml
test:
  name: "登录功能测试"
  type: ui_automation
  target:
    base_url: "https://app.example.com"
  browser:
    headless: true
    viewport_width: 1920
    viewport_height: 1080
    locale: zh-CN
  trace:
    enabled: true
    dir: artifacts/traces
  screenshot:
    on_failure: true
    dir: artifacts/screenshots
  video:
    enabled: false
  steps:
    - action: navigate
      url: "/login"
    - action: fill
      selector: 'input[name="username"]'
      value: "admin"
    - action: fill
      selector: 'input[name="password"]'
      value: "password123"
    - action: click
      selector: 'button[type="submit"]'
    - action: wait
      selector: ".dashboard"
      timeout: 10000
    - action: assert
      assert: url
      expected: "**/dashboard"
    - action: assert
      assert: visible
      selector: ".welcome-message"
    - action: assert
      assert: text
      selector: ".welcome-message"
      expected: "欢迎回来"
```

**支持的步骤类型**：

| action | 说明 | 参数 |
|--------|------|------|
| `click` | 点击元素 | selector |
| `fill` | 填充输入框 | selector, value |
| `type` | 逐字输入 | selector, value, delay |
| `select` | 下拉选择 | selector, value |
| `hover` | 悬停 | selector |
| `wait` | 等待元素 | selector, timeout |
| `assert` | 断言 | assert 类型（visible/hidden/text/attribute/count/url/title） |

---

## TestRunner — 命令模式运行器

封装测试任务为命令序列，支持执行、取消、截图：

```python
from test_framework.engines.ui_automation import TestRunner
from test_framework.engines.ui_automation.test_runner import TestCommand

runner = TestRunner(config)
await runner.initialize()

commands = [
    TestCommand(name="打开登录页", action="navigate", value="https://app.example.com/login"),
    TestCommand(name="输入用户名", action="fill", selector="#username", value="admin"),
    TestCommand(name="输入密码", action="fill", selector="#password", value="secret"),
    TestCommand(name="点击登录", action="click", selector="#login-btn"),
    TestCommand(name="验证跳转", action="wait_for_url", value="**/dashboard"),
    TestCommand(name="截图", action="screenshot", value="artifacts/login_success.png"),
]

results = await runner.execute(commands)
for r in results:
    print(f"{r.status.value}: {r.message} ({r.duration:.2f}s)")

# 取消执行
runner.cancel()
```

---

## 浏览器适配器

通过 `BrowserAdapter` 抽象基类，统一 Playwright 和 Selenium 的接口：

```python
# Playwright 实现
from test_framework.adapters.browser.playwright_impl import PlaywrightAdapter
adapter = PlaywrightAdapter({"browser": "chromium", "headless": True})
await adapter.connect()
await adapter.goto("https://example.com")
title = await adapter.get_title()
await adapter.screenshot("screenshot.png")
await adapter.disconnect()

# Selenium 实现
from test_framework.adapters.browser.selenium_impl import SeleniumAdapter
adapter = SeleniumAdapter({"browser": "chrome", "headless": True})
await adapter.connect()
await adapter.goto("https://example.com")
title = await adapter.get_title()
await adapter.disconnect()
```

**统一接口**：`goto` / `get_url` / `get_title` / `click` / `fill` / `select_option` / `hover` / `query_selector` / `wait_for_selector` / `screenshot` / `evaluate` / `get_network_entries` / `new_page` / `close_page` / `get_cookies` / `set_cookies` / `clear_cookies`

---

## Web 性能引擎

采集页面性能指标、DOM 复杂度、资源负载等数据：

```yaml
test:
  name: "首页性能测试"
  type: web_performance
  target:
    base_url: "https://app.example.com"
  thresholds:
    lcp: 2500
    fid: 100
    cls: 0.1
    ttfb: 800
  lighthouse:
    enabled: true
    categories:
      - performance
      - accessibility
```

**采集指标**：

| 指标 | 说明 | 阈值建议 |
|------|------|---------|
| LCP | Largest Contentful Paint | ≤ 2500ms |
| FCP | First Contentful Paint | ≤ 1800ms |
| CLS | Cumulative Layout Shift | ≤ 0.1 |
| FID | First Input Delay | ≤ 100ms |
| INP | Interaction to Next Paint | ≤ 200ms |
| TTFB | Time to First Byte | ≤ 800ms |

**PageAnalyzer DOM 分析**：DOM 节点数 / 最大嵌套深度 / 图片数 / 脚本数 / 样式表数 / iframe 数

**ResourceMonitor**：按类型（document/xhr/fetch/script/stylesheet/image/font/media/other）统计请求数量和大小

---

## 等待策略

`wait_conditions.py` 和 `waiters/` 提供丰富的等待条件：

| 等待条件 | 说明 |
|---------|------|
| `VisibilityWaiter` | 等待元素可见 |
| `HiddenWaiter` | 等待元素隐藏 |
| `PresenceWaiter` | 等待元素存在（DOM 中） |
| `ClickableWaiter` | 等待元素可点击 |
| `EnabledWaiter` | 等待元素启用 |
| `NavigationWaiter` | 等待导航完成 |
| `URLChangeWaiter` | 等待 URL 变化 |
| `NetworkIdleWaiter` | 等待网络空闲 |
| `LoadStateWaiter` | 等待加载状态 |
| `ResponseWaiter` | 等待网络响应 |
| `RequestWaiter` | 等待网络请求 |
| `ConsoleLogWaiter` | 等待控制台日志 |
| `TextChangeWaiter` | 等待文本变化 |
| `CustomWaiter` | 自定义等待条件 |

---

## 完整使用示例

```python
import asyncio
from test_framework.core.playwright import (
    PlaywrightManager, BrowserConfig, BasePage, BaseComponent, PageFactory
)
from test_framework.core.playwright.action_chains import ActionChains
from test_framework.core.playwright.network_interceptor import NetworkInterceptor


# 定义页面对象
class LoginPage(BasePage):
    URL_PATH = "/login"

    def _init_page(self):
        self.username = self.locate_by_test_id("username")
        self.password = self.locate_by_test_id("password")
        self.submit_btn = self.locate("button[type='submit']")

    async def login(self, user: str, pwd: str) -> "LoginPage":
        await self.fill('input[name="username"]', user)
        await self.fill('input[name="password"]', pwd)
        await self.click("button[type='submit']")
        return self


class DashboardPage(BasePage):
    URL_PATH = "/dashboard"
    LOAD_INDICATOR = ".loading"

    async def get_welcome_text(self) -> str:
        return await self.get_text(".welcome-message")


# 定义可复用组件
class SearchBar(BaseComponent):
    ROOT_SELECTOR = ".search-bar"

    async def search(self, keyword: str) -> "SearchBar":
        await self.fill('input[type="text"]', keyword)
        await self.press('input[type="text"]', "Enter")
        return self


# 执行测试
async def main():
    manager = await PlaywrightManager.get_instance()
    config = BrowserConfig(
        headless=True,
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN",
    )
    await manager.initialize(config)

    try:
        page = manager.current_page

        # 使用 Page Object
        login_page = LoginPage(page, base_url="https://app.example.com")
        await login_page.navigate()
        await login_page.login("admin", "password123")

        # 等待跳转
        await page.wait_for_url("**/dashboard")

        # 使用 Dashboard 页面
        dashboard = DashboardPage(page, base_url="https://app.example.com")
        text = await dashboard.get_welcome_text()
        assert "欢迎" in text

        # 使用 ActionChains
        chain = ActionChains(page)
        await (chain
            .click("#menu-users")
            .wait_for_timeout(500)
            .click("#add-user-btn")
            .execute())

    finally:
        await manager.close()


asyncio.run(main())
```

---

## 配置参考

完整的 UI 自动化测试配置 Schema：

```yaml
# UI 自动化配置
ui_automation:
  browser:
    headless: true
    viewport_width: 1920
    viewport_height: 1080
    device_scale_factor: 1.0
    locale: zh-CN
    timezone_id: Asia/Shanghai
    user_agent: null
    slow_mo: 0
    ignore_https_errors: false

  trace:
    enabled: false
    dir: artifacts/traces
    screenshots: true
    snapshots: true

  video:
    enabled: false
    dir: artifacts/videos

  screenshot:
    on_failure: true
    dir: artifacts/screenshots

  network:
    har_path: null
    capture: false
    filter: null

# Web 性能配置
web_performance:
  thresholds:
    lcp: 2500
    fid: 100
    cls: 0.1
    ttfb: 800
    fcp: 1800
    inp: 200
  lighthouse:
    enabled: false
    categories: [performance, accessibility, best-practices, seo]
    output_path: artifacts/lighthouse
  resource_monitor:
    enabled: true
    types: [document, xhr, fetch, script, stylesheet, image, font, media]
```
