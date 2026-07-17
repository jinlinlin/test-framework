# 开发者指南

## 开发环境搭建

```bash
# 克隆并进入项目
git clone <repo-url>
cd uniplore-test-framework

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装所有依赖
pip install -r python_modules/requirements.txt
pip install -r python_modules/requirements-dev.txt
pip install -e .

# Node.js（可选）
cd nodejs_modules && npm install && cd ..
```

---

## 代码规范

### Python

遵循 `.qoder/rules/python_style.md` 规范：

- **命名**：类用 PascalCase，方法和变量用 snake_case，常量用 UPPER_SNAKE_CASE
- **类型注解**：所有公开方法必须包含完整类型注解
- **Docstring**：Google 风格，包含 Args / Returns / Raises / Example
- **Import 顺序**：标准库 → 第三方库 → 本地模块（isort 自动排序）
- **行宽**：120 字符

```bash
# 自动格式化
black test_framework/
isort test_framework/

# 类型检查
mypy test_framework/

# 静态分析
flake8 test_framework/
pylint test_framework/
```

### Node.js

遵循 `.qoder/rules/nodejs_style.md` 规范：

- **注释**：所有函数和类包含 JSDoc 注释
- **命名**：类用 PascalCase，函数和变量用 camelCase
- **模块**：CommonJS（require/module.exports）

### Shell

遵循 `.qoder/rules/shell_style.md` 规范：

- **头部**：`#!/usr/bin/env bash` + `set -euo pipefail`
- **注释**：每个函数和关键步骤包含注释
- **变量**：使用 `${VAR}` 格式，避免裸变量

---

## 测试

### 运行测试

```bash
# 全部测试
pytest tests/ -v

# 仅单元测试
pytest tests/unit/ -v

# 仅集成测试
pytest tests/integration/ -v

# 指定模块
pytest tests/unit/test_core/ -v
pytest tests/unit/test_engines/ -v

# 带覆盖率
pytest --cov=test_framework --cov-report=html --cov-report=term

# 运行标记的测试
pytest -m unit        # 仅单元测试
pytest -m integration # 仅集成测试
pytest -m "not slow"  # 排除慢测试
```

### 测试目录结构

```
tests/
├── unit/
│   ├── test_core/           # 核心模块测试
│   │   ├── test_container.py
│   │   ├── test_event_bus.py
│   │   ├── test_pipeline.py
│   │   ├── test_models.py
│   │   └── test_exceptions.py
│   ├── test_engines/        # 引擎测试
│   │   ├── test_web_performance.py
│   │   ├── test_backend_performance.py
│   │   ├── test_rest_api.py
│   │   ├── test_database.py
│   │   ├── test_knowledge_qa.py
│   │   ├── test_penetration.py
│   │   └── test_auth_bypass.py
│   ├── test_adapters/       # 适配器测试
│   │   ├── test_http_adapter.py
│   │   ├── test_database_adapter.py
│   │   └── test_browser_adapter.py
│   └── test_utils/          # 工具类测试
│       ├── test_data_factory.py
│       ├── test_crypto.py
│       └── test_validation.py
├── integration/
│   └── test_end_to_end.py   # 端到端集成测试
└── fixtures/
    ├── sample_configs/      # 样本配置
    │   ├── web_test.yaml
    │   ├── api_test.yaml
    │   └── db_test.yaml
    └── mock_data/           # Mock 数据
```

### 编写测试

```python
import pytest
from unittest.mock import MagicMock

class TestMyFeature:
    """测试我的功能。"""

    def test_basic_case(self):
        """基本场景测试。"""
        from test_framework.my_module import MyClass
        obj = MyClass()
        assert obj.do_something() == "expected"

    def test_error_case(self):
        """异常场景测试。"""
        from test_framework.my_module import MyClass
        obj = MyClass()
        with pytest.raises(ValueError):
            obj.do_something_invalid()

    @pytest.mark.asyncio
    async def test_async_case(self):
        """异步场景测试。"""
        from test_framework.my_module import MyAsyncClass
        obj = MyAsyncClass()
        result = await obj.async_method()
        assert result is not None
```

---

## 项目配置

### pyproject.toml 关键配置

```toml
# pytest
asyncio_mode = "auto"

# black
line-length = 120

# mypy
python_version = "3.10"
disallow_untyped_defs = true

# coverage
source = ["test_framework"]
fail_under = 80
```

### 覆盖率要求

- 框架核心代码覆盖率 ≥ 80%
- 使用 `pytest-cov` 生成覆盖率报告
- CI 中未达标会构建失败

---

## Git 提交规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

**type 类型**：
- `feat` — 新功能
- `fix` — Bug 修复
- `docs` — 文档更新
- `style` — 代码格式
- `refactor` — 重构
- `test` — 测试相关
- `chore` — 构建/工具

**示例**：
```
feat(engines): 添加知识库 QA 引擎的 RAG 评测能力

- 新增 rag_evaluator.py 综合评测模块
- 支持检索相关性和生成质量双维度评估
- 添加对应的单元测试

Closes #42
```

---

## 调试

### 本地调试

```bash
# 设置调试模式
export TF_DEBUG=true
export TF_LOG_LEVEL=DEBUG

# 运行框架
python -m test_framework --env dev --type rest_api
```

### Docker 远程调试

```bash
# 使用开发编排（debugpy 端口 5678）
cd docker
docker compose -f docker-compose.dev.yml up

# IDE 连接 localhost:5678
```

### 日志

日志输出到 `logs/framework.log`，支持控制台和文件双输出：

```python
import logging

logger = logging.getLogger(__name__)
logger.info("这是一条信息日志")
logger.debug("这是一条调试日志")
```
