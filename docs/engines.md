# 测试引擎

## 引擎总览

所有引擎继承自 `BaseEngine`（模板方法模式），通过 `EngineFactory` 统一创建：

```python
from test_framework.engines import EngineFactory
from test_framework.core.models.enums import TestType

engine = EngineFactory.create(TestType.REST_API, config, container)
result = await engine.run()
```

---

## 1. 网页性能引擎

**目录**：`engines/web_performance/`

### 核心能力

- Playwright 驱动真实浏览器
- 采集 Core Web Vitals（LCP / FID / CLS / TTFB）
- 资源加载分析（JS/CSS/图片/字体）
- Lighthouse 集成评分

### 配置示例

```yaml
test:
  type: web_performance
  target:
    url: https://example.com
    pages: ["/", "/products", "/checkout"]
  browser:
    type: chromium       # chromium / firefox / webkit
    headless: true
    viewport: { width: 1920, height: 1080 }
  thresholds:
    lcp_ms: 2500
    fid_ms: 100
    cls: 0.1
    ttfb_ms: 600
  network_conditions:
    preset: fast_3g      # fast_3g / slow_3g / 4g / wifi
  concurrency: 5
```

### 模块说明

| 文件 | 职责 |
|------|------|
| `engine.py` | WebPerformanceEngine 主引擎 |
| `playwright_client.py` | Playwright 浏览器客户端封装 |
| `page_analyzer.py` | 页面资源分析 |
| `resource_monitor.py` | 资源加载监控 |
| `web_vitals.py` | Web Vitals 指标采集 |
| `lighthouse_integration.py` | Lighthouse 集成 |

---

## 2. 后端性能引擎

**目录**：`engines/backend_performance/`

### 核心能力

- HTTP / gRPC 负载施压
- JVM / Go / Node.js / Python / Container 资源监控
- 多协议支持（HTTP/1.1, HTTP/2, gRPC）

### 配置示例

```yaml
test:
  type: backend_performance
  target:
    protocol: http
    url: https://api.example.com/v1/data
    method: GET
  load:
    concurrent_users: 100
    duration_seconds: 60
    ramp_up_seconds: 10
  monitoring:
    jvm: true
    container: true
    interval_seconds: 5
```

### 模块说明

| 文件 | 职责 |
|------|------|
| `engine.py` | BackendPerformanceEngine 主引擎 |
| `http_loader.py` | HTTP 负载生成 |
| `grpc_loader.py` | gRPC 负载生成 |
| `resource_collector.py` | 资源指标收集 |
| `jvm_monitor.py` | JVM 监控（JMX） |
| `go_monitor.py` | Go 运行时监控 |
| `node_monitor.py` | Node.js 进程监控 |
| `python_monitor.py` | Python 进程监控 |
| `container_monitor.py` | Docker/K8s 容器监控 |

---

## 3. REST API 引擎

**目录**：`engines/rest_api/`

### 核心能力

- 建造者模式构建请求
- 策略模式验证响应
- JSON Schema 校验
- 契约测试
- Python / Node.js 双引擎

### 配置示例

```yaml
test:
  type: rest_api
  target:
    base_url: https://api.example.com/v1
    auth:
      type: bearer
      token_env: API_TOKEN
  endpoints:
    - path: /users
      method: GET
      expected_status: 200
      schema:
        type: array
        items: { type: object, required: [id, name] }
    - path: /users
      method: POST
      body: { name: "test", email: "t@t.com" }
      expected_status: 201
  rate_limit:
    requests_per_second: 10
```

---

## 4. 数据库引擎

**目录**：`engines/database/`

### 核心能力

- 多数据库支持（PostgreSQL / MySQL / MongoDB / Redis）
- 连接池管理（对象池模式）
- EXPLAIN 查询分析
- 索引建议

### 支持的数据库方言

| 方言 | 驱动 | 文件 |
|------|------|------|
| PostgreSQL | asyncpg | `dialect/postgresql.py` |
| MySQL | aiomysql | `dialect/mysql.py` |
| MongoDB | motor | `dialect/mongodb.py` |
| Redis | redis-py | `dialect/redis.py` |

---

## 5. 知识库问答引擎

**目录**：`engines/knowledge_qa/`

### 核心能力

- RAG（检索增强生成）质量评测
- 检索相关性测试
- Embedding 向量分析
- 上下文验证

### 模块说明

| 文件 | 职责 |
|------|------|
| `engine.py` | KnowledgeQAEngine 主引擎 |
| `qa_client.py` | QA 服务客户端 |
| `quality_evaluator.py` | 回答质量评估 |
| `retrieval_tester.py` | 检索质量测试 |
| `embedding_analyzer.py` | Embedding 向量分析 |
| `rag_evaluator.py` | RAG 综合评测 |
| `context_validator.py` | 上下文验证 |

---

## 6. 渗透测试引擎

**目录**：`engines/penetration/`

### 核心能力

- 多类型 Payload 生成（SQL 注入 / XSS / 路径遍历 / 命令注入 / SSRF / XXE）
- 漏洞扫描与检测
- 安全报告生成

### Payload 类型

| Payload | 文件 | 说明 |
|---------|------|------|
| SQL 注入 | `payloads/sql_injection.py` | 联合查询/盲注/时间注入 |
| XSS | `payloads/xss.py` | 反射型/存储型/DOM型 |
| 路径遍历 | `payloads/path_traversal.py` | 目录穿越攻击 |
| 命令注入 | `payloads/command_injection.py` | OS 命令注入 |
| SSRF | `payloads/ssrf.py` | 服务端请求伪造 |
| XXE | `payloads/xxe.py` | XML 外部实体注入 |

---

## 7. 越权访问引擎

**目录**：`engines/auth_bypass/`

### 核心能力

- 多种越权策略（策略模式）
- 自动化越权检测

### 攻击策略

| 策略 | 文件 | 说明 |
|------|------|------|
| 角色提升 | `strategies/role_escalation.py` | 低权限用户访问高权限接口 |
| 会话固定 | `strategies/session_fixation.py` | 会话 ID 固定攻击 |
| Token 重放 | `strategies/token_replay.py` | 过期/失效 Token 重放 |
| JWT 攻击 | `strategies/jwt_attack.py` | JWT 篡改/算法切换 |
| OAuth 攻击 | `strategies/oauth_attack.py` | OAuth 流程漏洞 |
| IDOR | `strategies/idor.py` | 不安全直接对象引用 |

---

## 8. Agent 行为测试引擎

**目录**：`engines/agent_behavior/`（薄壳引擎已落地：subprocess 委托 pytest + junit 收口 + Layer 2 产物）

### 核心能力

- 薄壳模式：自身不执行用例，通过 subprocess 委托 **pytest** 运行 `test-cases/agent/` 下的行为用例（保留 conftest fixture 原生机制）
- SSE 流式响应测试（断流恢复、首包耗时、chunk 拼接）
- 评分制结果：自建 Judge 已接入（`test-cases/agent/core/clients/judge_client.py`）；收口契约为用例侧
  `score_sink` 夹具写 junit `<properties>` 的 `score/threshold/dimensions`，引擎解析为
  `TestResult.score/dimensions/threshold`（score 为 0~1 归一比，与 `default_threshold` 同标度；
  双轨语义：status 由 pytest 断言决定，`passed_by_score` 为报告元数据）。DeepEval 路由已
  落地（`test-cases/agent/core/evaluators/`：dimension_registry 声明表 + evaluation_orchestrator
  按表分发，第三方指标优先、失败显式回退 Judge）；Langfuse 上报尚未接入（见下节遗留）
- 产物契约：Layer 1 原生产物落 `artifacts/agent_behavior/{run_id}/`，Layer 2 经 JSONReporter 输出统一 `summary.json`
- 可选 Langfuse Trace 上报（开关在配置，密钥走环境变量）

### 目录约定

| 路径 | 职责 |
|------|------|
| `test-cases/agent/` | 业务用例（conftest.py / pytest.ini / 用例子目录），与框架自测 `tests/` 分离，不参与 pip 打包 |
| `test-data/` | 跨引擎共享测试数据（Golden Dataset / PDF 等） |
| `artifacts/agent_behavior/{run_id}/` | 单次运行产物（junit.xml / allure-results / judge.json / summary.json） |

### 配置示例

```yaml
agent_behavior:
  executor: pytest               # 执行内核
  cases_dir: test-cases/agent
  pytest:
    timeout: 1800                # SSE 流式用例耗时较长
    markers: ["rag"]             # 只跑 rag 标记用例
  scoring:
    default_threshold: 0.75
    use_deepeval: true           # DeepEval 优先，异常回退自建 Judge
    dimensions:
      relevance: deepeval
      depth: judge
```

完整默认值见 `config/defaults/agent.yaml`，校验规则见 `config/schema/test_type.json` 的 `agent_behavior_config`。

### 当前状态与遗留（Phase A）

- 已落地：离线 SSE 请求契约用例 12 条 + 评分收口链契约用例 4 条 + DeepEval 路由编排
  契约用例 9 条（均带 `offline` 标记，本地假网关/假裁判/注入式假后端，零凭证零网络），
  经引擎 subprocess 委托全链路验证
- 已落地：dimension_registry/evaluation_orchestrator 配置驱动路由（用例侧默认表与
  `scoring.dimensions` 同构；编排结果直接喂 score_sink，收口链零改造兼容）
- 待接入：rag/paper 真实环境用例（需 `config/.env` 凭证，真实 DeepEvalAdapter 接线验证
  同批）、框架 `scoring.use_deepeval` → 用例侧的传递接线（当前用 USE_DEEPEVAL 环境变量
  或缺省构造传参）、token 登录链与 Langfuse 钩子
  （回补清单见 `test-cases/agent/conftest.py` 文件头）、跨引擎统一环境配置（归 M1，见迁移文档裁决记录）

---

## 自定义引擎

继承 `BaseEngine` 实现自定义引擎：

```python
from test_framework.engines.base import BaseEngine

class MyCustomEngine(BaseEngine):
    @property
    def engine_type(self) -> str:
        return "custom"

    async def _setup(self):
        """初始化资源。"""
        ...

    async def _execute(self):
        """执行测试逻辑。"""
        ...

    async def _teardown(self):
        """清理资源。"""
        ...

# 注册到工厂
EngineFactory.register(TestType.CUSTOM, MyCustomEngine)
```
