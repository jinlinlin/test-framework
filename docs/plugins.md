# 插件开发

## 插件系统概述

插件系统支持动态发现、加载和管理插件，实现框架能力的灵活扩展：

```
发现(discover) → 加载(load) → 注册(register) → 激活(activate) → ... → 停用(deactivate)
```

---

## 内置插件

| 插件 | 文件 | 功能 |
|------|------|------|
| WebTestPlugin | `plugins/builtin/web_plugin.py` | 网页性能测试能力注册 |
| ApiTestPlugin | `plugins/builtin/api_plugin.py` | API 测试能力注册 |
| SecurityTestPlugin | `plugins/builtin/security_plugin.py` | 安全测试能力注册 |

---

## 插件接口

所有插件实现 `IPluggable` 接口：

```python
from abc import ABC, abstractmethod

class IPluggable(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    async def activate(self, context: dict) -> None: ...

    @abstractmethod
    async def deactivate(self) -> None: ...

    @abstractmethod
    def get_info(self) -> dict: ...
```

---

## 开发自定义插件

### 1. 创建插件类

```python
from test_framework.plugins.base import IPluggable

class MyCustomPlugin(IPluggable):
    """自定义插件示例 — 添加自定义报告格式。"""

    @property
    def name(self) -> str:
        return "custom_report_plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def activate(self, context: dict) -> None:
        """激活插件 — 注册自定义报告器。"""
        from test_framework.core.events import EventBus

        bus = context.get("event_bus")
        if bus:
            bus.subscribe("test.completed", self._on_test_completed)

    async def deactivate(self) -> None:
        """停用插件 — 清理资源。"""
        pass

    def get_info(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": "自定义报告格式插件",
        }

    async def _on_test_completed(self, event_data: dict):
        """处理测试完成事件，生成自定义报告。"""
        # 自定义报告生成逻辑
        pass
```

### 2. 放置到插件目录

将插件文件放入以下任一目录：

- `test_framework/plugins/builtin/` — 内置插件（框架自带）
- `test_framework/plugins/custom/` — 自定义插件

### 3. 使用插件管理器

```python
from test_framework.plugins.manager import PluginManager

manager = PluginManager()

# 发现插件（扫描插件目录）
manager.discover("./test_framework/plugins")

# 列出可用插件
plugins = manager.list_plugins()
print(plugins)  # ["web_test_plugin", "api_test_plugin", "custom_report_plugin"]

# 激活插件
await manager.activate("custom_report_plugin", context={"event_bus": bus})

# 停用插件
await manager.deactivate("custom_report_plugin")
```

---

## 插件管理器 API

```python
class PluginManager:
    def discover(self, path: str) -> List[str]
        """扫描目录，发现可用插件。"""

    def load(self, plugin_name: str) -> IPluggable
        """加载指定插件。"""

    def register(self, plugin: IPluggable) -> None
        """注册插件到管理器。"""

    async def activate(self, name: str, context: dict = None) -> None
        """激活插件。"""

    async def deactivate(self, name: str) -> None
        """停用插件。"""

    def list_plugins(self) -> List[str]
        """列出所有已注册插件名。"""

    def get_plugin(self, name: str) -> Optional[IPluggable]
        """获取插件实例。"""
```

---

## 插件开发最佳实践

1. **命名规范**：插件名使用小写 + 下划线，如 `my_feature_plugin`
2. **版本管理**：遵循语义化版本（SemVer）
3. **资源清理**：在 `deactivate()` 中确保释放所有资源
4. **错误处理**：`activate()` 中的异常不应影响其他插件
5. **依赖声明**：在 `get_info()` 中声明依赖的其他插件
6. **事件驱动**：优先使用 EventBus 而非直接调用其他模块
