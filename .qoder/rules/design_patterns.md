# 设计模式落地规范

## 总则
- 所有设计模式必须在类/模块的 docstring 中明确标注所用模式名称
- 模式实现必须遵循 SOLID 原则，避免过度设计
- 每个模式对应具体代码模块，禁止空壳模式

## 单例模式（Singleton）
**适用场景**：全局唯一实例，如 IoC 容器、事件总线、配置管理器

**实现方式**：
```python
class SingletonClass:
    """全局唯一实例，使用 __new__ + 标记位实现。"""
    _instance: Optional['SingletonClass'] = None

    def __new__(cls) -> 'SingletonClass':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        # 初始化逻辑
```

**约束**：
- 必须提供 `reset()` 方法用于测试重置
- 线程安全场景需加锁

## 工厂模式（Factory）
**适用场景**：对象创建逻辑封装，如引擎/适配器/策略/报告器的创建

**实现方式**：
```python
class XxxFactory:
    """统一创建接口，通过注册表管理实现类。"""
    _registry: Dict[str, Type[BaseXxx]] = {}

    @classmethod
    def register(cls, name: str, impl_cls: Type[BaseXxx]) -> None: ...

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseXxx: ...
```

**约束**：
- 注册表使用类变量
- 支持 `available()` 查询已注册实现
- 创建失败时抛出明确异常

## 策略模式（Strategy）
**适用场景**：可替换算法封装，如负载策略、验证策略、攻击载荷

**实现方式**：
- 定义抽象基类 `BaseStrategy(ABC)` + `@abstractmethod execute()`
- 每个具体策略继承基类并实现 `execute()`
- 策略工厂根据配置动态选择

## 适配器模式（Adapter）
**适用场景**：屏蔽第三方库/协议接口差异

**实现方式**：
- 定义统一抽象接口 `BaseAdapter(ABC)`
- 每个具体实现封装一个第三方库
- 支持 `async with` 上下文管理

## 模板模式（Template Method）
**适用场景**：固定执行骨架，子类实现差异步骤

**实现方式**：
```python
class BaseEngine(ABC):
    async def run(self, ...) -> TestReport:
        """模板方法：固定流程骨架"""
        self.validate_config()
        await self.setup(target)
        try:
            result = await self.execute_case(case, target)
        finally:
            await self.teardown()
        return result
```

**约束**：`run()` 方法禁止子类覆盖

## 观察者模式（Observer）
**适用场景**：事件驱动架构，如事件总线、报告器订阅

**实现方式**：
- `EventBus.subscribe(event_type, listener)` 注册监听
- `EventBus.publish(event)` 触发事件
- 支持优先级和异步监听器

## 责任链模式（Chain of Responsibility）
**适用场景**：管道执行引擎，阶段串联

**实现方式**：
- `Pipeline.add_stage(stage)` 添加阶段
- `Pipeline.execute(context)` 依次执行
- 支持 Filter 拦截和 Hook 注入

## 命令模式（Command）
**适用场景**：测试任务封装，调度器

**实现方式**：
- 每个调度命令封装为独立对象
- 支持 `execute()` / `cancel()` / `get_status()`

## 建造者模式（Builder）
**适用场景**：复杂对象分步构建，如 HTTP 请求构建

**实现方式**：
- 链式调用：`builder.method("POST").path("/api").header(...).build()`
- `build()` 返回不可变对象

## 组合模式（Composite）
**适用场景**：树形结构，如 TestSuite 嵌套

**实现方式**：
- `TestSuite.children` 支持嵌套 `TestSuite` 或 `TestCase`
- `get_all_cases()` 递归展平

## 对象池模式（Object Pool）
**适用场景**：连接复用，如数据库连接池

**实现方式**：
- `acquire()` 获取连接
- `release()` 归还连接
- 配置 `min_size` / `max_size` / `idle_timeout`

## 桥接模式（Bridge）
**适用场景**：多语言桥接层

**实现方式**：
- `LanguageBridge(ABC)` 定义抽象接口
- 每种语言一个具体实现
- 通过工厂创建
