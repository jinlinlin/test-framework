# 项目结构与文件命名规范

## 顶层目录结构

```
test_framework/          # 框架主包（Python 模块）
├── bootstrap/           # 启动引导层
├── core/                # 核心抽象层
├── languages/           # 多语言桥接层
├── engines/             # 测试引擎层
├── adapters/            # 适配器层
├── strategies/          # 策略层
├── reporters/           # 报告层
├── config/              # 配置管理层
├── plugins/             # 插件系统
├── schedulers/          # 调度层
├── decorators/          # 装饰器层
├── utils/               # 工具层
└── extensions/          # 扩展层

scripts/                 # 脚本层
├── shell/               # Shell 运维脚本
└── nodejs/              # Node.js 高性能脚本

tests/                   # 框架自测
├── unit/                # 单元测试
├── integration/         # 集成测试
└── fixtures/            # 测试数据

docs/                    # 文档
logs/                    # 日志输出
reports/                 # 报告输出
results/                 # 测试结果输出
artifacts/               # 测试产物

python_modules/          # Python 依赖管理
nodejs_modules/          # Node.js 依赖管理
docker/                  # Docker 支持
kubernetes/              # Kubernetes 支持
specs/                   # 需求规格文档
```

## 文件命名规范

### Python 文件
- 全小写 + 下划线：`engine_factory.py`, `connection_pool.py`
- 实现文件以 `_impl` 后缀：`httpx_impl.py`, `playwright_impl.py`
- 测试文件以 `test_` 前缀：`test_container.py`
- 配置 Schema 文件命名为 `config_schema.py`

### Node.js 文件
- 小写 + 下划线：`bridge.js`, `api_load_test.js`
- 包配置文件：`package.json`

### Shell 文件
- 小写 + 下划线 + `.sh` 后缀：`run.sh`, `health_check.sh`

### 配置文件
- YAML：小写命名，如 `base.yaml`, `dev.yaml`
- JSON：小写命名，如 `global.json`
- 环境变量：`.env.example`

## __init__.py 规范
- 每个 Python 包目录必须包含 `__init__.py`
- `__init__.py` 中导出包的主要公共类/函数
- 使用 `__all__` 显式声明导出列表

```python
"""
core.models 包 — 领域模型定义。

导出所有核心数据模型供其他模块使用。
"""
from .test_case import TestCase
from .test_suite import TestSuite
from .enums import TestType, TestStatus, Priority

__all__ = [
    "TestCase",
    "TestSuite",
    "TestType",
    "TestStatus",
    "Priority",
]
```

## 目录创建规范
- 输出目录（logs/reports/results/artifacts）使用 `.keep` 文件保持 Git 追踪
- 自定义插件放入 `plugins/custom/` 目录
- 临时文件放入系统临时目录，不入库

## 禁止事项
- 禁止在根目录创建临时文件
- 禁止将密钥/Token 写入代码或配置文件（使用环境变量）
- 禁止硬编码路径分隔符（使用 `os.path` 或 `pathlib`）
