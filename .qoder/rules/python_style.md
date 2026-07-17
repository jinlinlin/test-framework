# Python 编码规范

## 命名规范
- 模块/文件名：全小写 + 下划线（snake_case），如 `engine_factory.py`
- 类名：大驼峰（PascalCase），如 `WebPerformanceEngine`
- 函数/方法：下划线命名（snake_case），如 `execute_case`
- 常量：全大写 + 下划线，如 `MAX_RETRIES`
- 私有成员：单下划线前缀，如 `_internal_state`
- 受保护成员：双下划线前缀（名称改写），仅在需要时使用

## 类型注解
- 所有函数参数和返回值必须添加类型注解
- 使用 `from __future__ import annotations` 支持延迟求值
- 复杂类型使用 `typing` 模块：`Optional`, `Union`, `Dict`, `List`, `Tuple`, `Callable`, `Any`
- 使用 `TypeVar` 和 `Generic` 实现泛型

## Docstring 格式
- 使用 Google 风格 docstring
- 模块级 docstring：描述模块职责、主要类/函数
- 类级 docstring：描述类职责、设计模式、依赖关系
- 方法级 docstring：描述功能、参数、返回值、异常

```python
def example_method(self, name: str, timeout: float = 30.0) -> Dict[str, Any]:
    """执行指定操作并返回结果。

    详细描述该方法的业务逻辑和执行流程。

    Args:
        name: 操作名称，必须是已注册的有效操作。
        timeout: 超时时间（秒），默认 30 秒。

    Returns:
        包含操作结果的字典，格式为 {"status": "ok", "data": ...}。

    Raises:
        TimeoutException: 当操作在指定时间内未完成时抛出。
        ConfigException: 当配置无效时抛出。
    """
```

## Import 顺序
1. 标准库（`import os`, `from typing import ...`）
2. 第三方库（`import httpx`, `from pydantic import ...`）
3. 框架内部模块（`from core.models import ...`）
4. 相对导入（`from .base import ...`）

每组之间空一行。

## 异常处理
- 禁止裸 `except:`，必须指定具体异常类型
- 优先使用框架自定义异常（`core/exceptions/`）
- 异常消息必须包含上下文信息

## 异步编程
- 优先使用 `async/await` 异步模式
- I/O 密集型操作必须使用异步
- 使用 `asyncio.gather` 实现并发
- 使用 `async with` 管理异步资源

## 数据类
- 数据传输对象（DTO）使用 `@dataclass`
- 需要验证的配置数据使用 `pydantic.BaseModel`
- 枚举使用 `enum.Enum`

## 代码长度
- 单个函数不超过 80 行
- 单个类不超过 300 行
- 行宽不超过 120 字符
