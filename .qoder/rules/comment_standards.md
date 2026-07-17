# 注释标准

## 总则
- 所有代码必须包含详细注释，确保其他开发者无需阅读 spec 即可理解代码意图
- 注释使用中文，技术术语保留英文原文（如 IoC、Singleton、Playwright）
- 注释应解释"为什么"而非"是什么"，代码本身应清晰表达"做什么"

## 模块级注释（文件头部）

每个 Python 文件必须以模块 docstring 开头：

```python
"""
配置管理器模块 — 实现框架全局配置的统一管理。

设计模式：单例模式
职责：
    - 加载多格式配置文件（YAML/JSON/TOML/.env）
    - 按优先级合并配置（环境变量 > 命令行 > 环境配置 > 默认配置）
    - 支持点号路径访问和热重载
    - 基于 JSON Schema 进行配置验证

依赖：
    - core.exceptions.config.ConfigException
    - config.loader.ConfigLoaderFactory
    - config.validator.ConfigValidator

作者：framework-team
版本：1.0.0
"""
```

## 类级注释

```python
class ConfigManager:
    """
    全局配置管理器（单例模式）。

    管理框架全量配置的加载、合并、访问和验证。
    保证全局配置一致性，支持运行时热重载。

    Attributes:
        _instance: 单例实例引用
        _config: 当前生效配置字典
        _env: 当前环境名称

    Example:
        >>> manager = ConfigManager()
        >>> manager.load(env="dev")
        >>> timeout = manager.get("engines.rest_api.timeout")
    """
```

## 方法级注释

```python
def load(self, env: str = "dev", config_dir: Optional[str] = None) -> None:
    """
    加载并合并所有层级的配置文件。

    加载流程（后加载的覆盖先加载的）：
        1. 加载 schema/global.json 定义的基础约束
        2. 加载 defaults/ 目录下所有测试类型的默认配置
        3. 加载 environments/base.yaml 基础环境配置
        4. 加载 environments/{env}.yaml 环境特有配置（深度合并）
        5. 加载 TF_ 前缀的环境变量覆盖

    Args:
        env: 环境名称，可选值 dev/test/staging/production，默认 dev。
        config_dir: 配置文件根目录路径，为 None 时使用框架默认路径。

    Raises:
        ConfigException: 当配置文件不存在或格式错误时抛出。
    """
```

## 行内注释

- 复杂逻辑前必须添加注释说明意图
- 注释写在代码上方，不要写在行尾（除非极短说明）

```python
# 深度合并环境配置，确保嵌套字典不会被整体覆盖
merged = deep_merge(base_config, env_config)

# 遍历所有引擎类型，逐一注册到引擎工厂
for engine_type, engine_cls in ENGINE_MAP.items():
    EngineFactory.register(engine_type, engine_cls)
```

## TODO/FIXME/HACK 标记

```python
# TODO: 后续版本支持分布式配置中心（Consul/Nacos）
# FIXME: Windows 下路径分隔符兼容问题待修复
# HACK: 临时绕过 Playwright 1.40 的超时 Bug，升级后移除
```

## 注释语言对照表

| 场景 | 语言 |
|---|---|
| docstring 描述 | 中文 |
| 技术术语（Singleton/IoC/gRPC） | 英文原文 |
| 参数说明 | 中文 |
| 异常说明 | 中文 |
| 行内注释 | 中文 |
| TODO/FIXME 说明 | 中文 |
| 代码中的变量名/函数名 | 英文 |

## Node.js 注释

使用 JSDoc 格式，内容使用中文：

```javascript
/**
 * Node.js 桥接脚本 — 接收 Python 传入的参数并执行指定模块。
 *
 * 通过 stdin/命令行参数接收 JSON 格式的任务描述，
 * 执行完成后将结果以 JSON 格式输出到 stdout。
 *
 * @module bridge
 */
```

## Shell 注释

```bash
#!/usr/bin/env bash
#
# 框架主入口脚本
# 职责：解析命令行参数，调用 Python 主框架执行测试任务
# 依赖：python3, bash 4.0+
#
```
