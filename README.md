<div align="center">

<img src="docs/images/logo.svg" alt="Uniplore Test Framework" width="120" height="120" />

<h1>Uniplore Test Framework</h1>

<p>
  <b>全维度工程化测试框架</b><br/>
  <sub>性能 · 接口 · 数据库 · 智能问答 · 安全测试 — 一站式解决方案</sub>
</p>

<p>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python" /></a>
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/Node.js-18%2B-green.svg" alt="Node.js" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License" /></a>
  <a href="docker/"><img src="https://img.shields.io/badge/Docker-ready-blue.svg" alt="Docker" /></a>
  <a href="kubernetes/"><img src="https://img.shields.io/badge/K8s-ready-326ce5.svg" alt="Kubernetes" /></a>
</p>

<p>
  <a href="docs/quickstart.md">🚀 快速开始</a> •
  <a href="docs/architecture.md">📐 架构设计</a> •
  <a href="docs/engines.md">⚙️ 测试引擎</a> •
  <a href="docs/playwright-ui.md">🖥 UI 自动化</a> •
  <a href="docs/deployment.md">🐳 部署指南</a> •
  <a href="docs/development.md">🛠 开发者指南</a>
</p>

</div>

---

## 概述

Uniplore Test Framework 是一套 **工程化、模块化、配置驱动、多语言协同** 的全场景自动化测试框架，统一支撑八大测试类型：

| 测试类型 | 说明 | 核心技术 |
|---------|------|--------|
| UI 自动化测试 | Page Object + 组件复用 + 多浏览器支持 | Playwright + Selenium |
| 网页性能测试 | LCP / FID / CLS / TTFB 等 Web Vitals | Playwright + Lighthouse |
| 后端性能测试 | HTTP / gRPC 负载施压与资源监控 | asyncio + gRPC |
| REST API 测试 | 功能回归 + 契约测试 + Schema 校验 | Python / Node.js 双引擎 |
| 数据库测试 | SQL 性能 + EXPLAIN + 索引建议 | asyncpg / aiomysql / motor |
| 知识库问答测试 | RAG 评测 + 检索质量 + 上下文验证 | Embedding + QA 评估 |
| 渗透测试 | SQL 注入 / XSS / SSRF / XXE 等 | 多 Payload 生成器 |
| 越权访问测试 | 角色提升 / 会话固定 / JWT / OAuth | 策略模式 |

---

## 技术栈

- **Python 3.10+** — 核心主框架（asyncio 异步优先、dataclass + ABC 抽象基类）
- **Node.js 18+** — 高性能辅助引擎（HTTP 压测、WebSocket、gRPC）
- **Shell** — 工程运维层（部署、监控、清理）
- **Docker + Kubernetes** — 容器化部署与编排

---

## 快速开始

```bash
# 1. 克隆仓库
git clone <repo-url> && cd uniplore-test-framework

# 2. 安装 Python 依赖
pip install -r python_modules/requirements.txt
pip install -e .

# 3. 安装 Node.js 依赖（可选）
cd nodejs_modules && npm install && cd ..

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际值

# 5. 运行测试
bash scripts/shell/run.sh --env dev --type rest_api --config config/test.yaml

# 或使用 Docker
cd docker && docker compose up --build
```

详细步骤请参阅 [快速开始指南](docs/quickstart.md)。

---

## 项目结构

```
uniplore-test-framework/
├── test_framework/          # Python 核心框架
│   ├── bootstrap/           #   启动引导（环境检测、依赖检查）
│   ├── core/                #   核心基础设施
│   │   ├── container/       #     IoC 容器（依赖注入）
│   │   ├── interfaces/      #     接口契约（ITestable/IAdaptable/...）
│   │   ├── models/          #     领域模型（TestCase/TestResult/...）
│   │   ├── pipeline/        #     管道引擎（责任链）
│   │   ├── events/          #     事件总线（发布/订阅）
│   │   └── exceptions/      #     异常体系
│   ├── engines/             #   八大测试引擎
│   │   ├── ui_automation/   #     UI 自动化引擎
│   │   ├── web_performance/ #     网页性能引擎
│   │   ├── backend_performance/ # 后端性能引擎
│   │   ├── rest_api/        #     REST API 引擎
│   │   ├── database/        #     数据库引擎
│   │   ├── knowledge_qa/    #     知识库 QA 引擎
│   │   ├── penetration/     #     渗透测试引擎
│   │   └── auth_bypass/     #     越权测试引擎
│   ├── adapters/            #   适配器层
│   │   ├── http/            #     HTTP 适配器（requests/httpx/aiohttp）
│   │   ├── browser/         #     浏览器适配器（Playwright/Selenium）
│   │   ├── database/        #     数据库适配器（asyncpg/motor/redis）
│   │   ├── messaging/       #     消息队列适配器（Kafka/RabbitMQ）
│   │   └── load_generator/  #     负载生成器（JMeter/Locust/k6）
│   ├── config/              #   配置管理
│   ├── strategies/          #   策略层（负载/验证/重试）
│   ├── reporters/           #   报告层（HTML/JSON/Allure/External）
│   ├── schedulers/          #   调度器（顺序/并行/定时/分布式）
│   ├── plugins/             #   插件系统
│   ├── decorators/          #   装饰器（计时/重试/限流/熔断/缓存）
│   ├── languages/           #   多语言桥接
│   └── utils/               #   工具类
├── extensions/              # 扩展层（服务发现/K8s/Docker/追踪）
├── scripts/
│   ├── shell/               # Shell 运维脚本
│   └── nodejs/              # Node.js 高性能引擎
├── config/                  # 运行时配置（YAML）
├── docker/                  # Docker 部署配置
├── kubernetes/              # Kubernetes 部署配置
├── tests/                   # 框架自测
│   ├── unit/                #   单元测试
│   ├── integration/         #   集成测试
│   └── fixtures/            #   测试夹具
├── specs/                   # 设计规范文档
├── docs/                    # 使用文档
├── logs/                    # 日志输出
├── reports/                 # 测试报告
├── results/                 # 测试结果
└── artifacts/               # 构建产物
```

---

## 核心特性

### 配置驱动

通过 YAML 配置文件即可定义完整的测试计划，无需修改代码：

```yaml
test:
  name: "API 冒烟测试"
  type: rest_api
  target:
    base_url: https://api.example.com/v1
  endpoints:
    - path: /users
      method: GET
      expected_status: 200
```

### IoC 容器

基于控制反转的依赖注入，解耦所有组件：

```python
container = Container()
container.register(IEventBus, EventBus, Lifecycle.SINGLETON)
bus = container.resolve(IEventBus)
```

### 事件驱动

基于发布/订阅的事件总线，支持跨模块通信：

```python
event_bus = EventBus()
event_bus.subscribe("test.completed", on_test_complete)
event_bus.publish("test.completed", {"test_id": "TC-001", "status": "passed"})
```

### 插件化

内置插件 + 自定义插件，支持完整生命周期管理：

```python
manager = PluginManager()
manager.discover("./plugins")
manager.activate("web_test_plugin")
```

### 装饰器切面

一行代码添加计时、重试、限流、熔断等横切关注点：

```python
@timing
@retry(max_retries=3, delay=1.0)
@rate_limit(max_calls=10, period=60)
@circuit_breaker(failure_threshold=5)
async def call_api():
    ...
```

---

## 八大测试引擎

| 引擎 | 入口 | 说明 |
|------|------|------|
| UI 自动化 | `engines/ui_automation/` | Playwright/Selenium 多浏览器，Page Object + 组件库 |
| Web 性能 | `engines/web_performance/` | Playwright 驱动，采集 LCP/FID/CLS/TTFB |
| 后端性能 | `engines/backend_performance/` | HTTP/gRPC 负载，JVM/Go/Node/Container 监控 |
| REST API | `engines/rest_api/` | 请求建造者 + 响应验证 + Schema 校验 |
| 数据库 | `engines/database/` | 连接池 + EXPLAIN 分析 + 索引建议 |
| 知识库 QA | `engines/knowledge_qa/` | RAG 检索质量 + 上下文验证 |
| 渗透测试 | `engines/penetration/` | SQL/XSS/路径遍历/命令注入/SSRF/XXE |
| 越权访问 | `engines/auth_bypass/` | 角色提升/会话固定/Token重放/JWT/OAuth |

详见 [测试引擎文档](docs/engines.md)。

---

## 文档清单

| 文档 | 说明 |
|------|------|
| [架构设计](docs/architecture.md) | 分层架构、设计模式、模块关系 |
| [快速开始](docs/quickstart.md) | 安装、配置、首次运行 |
| [配置管理](docs/configuration.md) | 配置文件格式、环境覆盖、Schema 验证 |
| [测试引擎](docs/engines.md) | 八大引擎使用指南与配置示例 |
| [Playwright UI 自动化](docs/playwright-ui.md) | Page Object、组件库、操作链、网络拦截、Web 性能 |
| [适配器](docs/adapters.md) | 适配器模式、自定义适配器开发 |
| [部署指南](docs/deployment.md) | Docker / Kubernetes 部署与运维 |
| [插件开发](docs/plugins.md) | 插件生命周期、自定义插件开发 |
| [开发者指南](docs/development.md) | 代码规范、测试、贡献指南 |

---

## 环境要求

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.10 | 3.11+ |
| Node.js | 18.0 | 20 LTS |
| Docker | 20.10 | 24+ |
| Kubernetes | 1.24 | 1.28+ |

---

## 开发

```bash
# 安装开发依赖
pip install -r python_modules/requirements-dev.txt

# 运行单元测试
pytest tests/unit -v

# 运行集成测试
pytest tests/integration -v

# 代码格式化
black test_framework/
isort test_framework/

# 类型检查
mypy test_framework/

# 覆盖率
pytest --cov=test_framework --cov-report=html
```

详见 [开发者指南](docs/development.md)。

---

## License

[MIT](LICENSE) — Copyright (c) Uniplore Team
