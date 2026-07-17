# Spec 10：工程化支撑 — Docker/K8s/脚本/扩展/框架自测

## 1. 概述

本 Spec 实现框架的工程化运维与部署支撑：  
- **脚本层**：Shell 运维脚本（环境安装/部署/监控/清理）+ Node.js 高性能脚本  
- **扩展层**：服务发现、Kubernetes/Docker 集成、Service Mesh、分布式追踪  
- **Docker 支持**：Dockerfile + docker-compose 编排  
- **Kubernetes 支持**：K8s 部署清单  
- **框架自测**：单元测试 + 集成测试 + Mock 数据  
- **项目配置文件**：requirements.txt / package.json / pyproject.toml / .gitignore 等

**依赖**：Spec 1 ~ Spec 9（本层集成全部上层能力）  
**被依赖**：无

---

## 2. 目标目录结构

```
uniplore-test-framework/
├── scripts/
│   ├── shell/
│   │   ├── run.sh               # 主入口
│   │   ├── setup.sh             # 环境安装
│   │   ├── cleanup.sh           # 清理
│   │   ├── health_check.sh      # 健康检查
│   │   ├── monitor.sh           # 资源监控
│   │   ├── deploy.sh            # 部署
│   │   ├── backup.sh            # 备份
│   │   ├── docker_build.sh      # Docker 构建
│   │   └── k8s_deploy.sh        # K8s 部署
│   └── nodejs/
│       ├── run.js               # Node 主入口
│       ├── api_load_test.js     # API 负载测试
│       ├── websocket_test.js    # WebSocket 测试
│       ├── grpc_test.js         # gRPC 测试
│       └── performance_worker.js # 性能工作器
│
├── extensions/
│   ├── __init__.py
│   ├── service_discovery.py     # 服务发现
│   ├── kubernetes.py            # K8s 集成
│   ├── docker.py                # Docker 集成
│   ├── service_mesh.py          # Service Mesh 集成
│   └── tracing.py               # 分布式追踪
│
├── tests/                       # 框架自测
│   ├── __init__.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_core/
│   │   ├── test_engines/
│   │   ├── test_adapters/
│   │   └── test_utils/
│   ├── integration/
│   │   ├── __init__.py
│   │   └── test_end_to_end.py
│   └── fixtures/
│       ├── __init__.py
│       ├── sample_configs/
│       └── mock_data/
│
├── nodejs_modules/
│   ├── package.json
│   ├── package-lock.json
│   ├── .eslintrc.js
│   └── .prettierrc
│
├── python_modules/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── setup.py
│   ├── pyproject.toml
│   └── .pylintrc
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── .dockerignore
│
├── kubernetes/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── secret.yaml
│
├── logs/
│   └── .keep
├── reports/
│   └── .keep
├── results/
│   └── .keep
├── artifacts/
│   └── .keep
│
├── .env.example
├── .gitignore
├── .flake8
├── .mypy.ini
├── CHANGELOG.md
├── LICENSE
└── README.md
```

---

## 3. 详细设计 — Shell 脚本

### 3.1 scripts/shell/run.sh — 主入口

```bash
#!/usr/bin/env bash
#
# 框架主入口脚本
# 用法：./run.sh [options]
#   -e, --env       环境（dev/test/staging/production）
#   -t, --type      测试类型
#   -c, --config    配置文件路径
#   -p, --plan      测试计划文件
#   --parallel      并行执行
#   --dry-run       仅验证配置，不执行
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

source "$SCRIPT_DIR/../common.sh" 2>/dev/null || true

ENV="dev"
TEST_TYPE=""
CONFIG=""
PLAN=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env) ENV="$2"; shift 2;;
        -t|--type) TEST_TYPE="$2"; shift 2;;
        -c|--config) CONFIG="$2"; shift 2;;
        -p|--plan) PLAN="$2"; shift 2;;
        *) log_error "Unknown option: $1"; exit 1;;
    esac
done

log_info "Starting test framework (env=$ENV, type=$TEST_TYPE)"

# 环境检查
bash "$SCRIPT_DIR/setup.sh" --check-only

# 执行 Python 主框架
python -m uniplore-test-framework \
    --env "$ENV" \
    ${TEST_TYPE:+--type "$TEST_TYPE"} \
    ${CONFIG:+--config "$CONFIG"} \
    ${PLAN:+--plan "$PLAN"}

EXIT_CODE=$?
log_info "Framework exited with code $EXIT_CODE"
exit $EXIT_CODE
```

### 3.2 scripts/shell/setup.sh — 环境安装

```bash
#!/usr/bin/env bash
# 环境安装脚本：检测并安装 Python、Node.js、Playwright 等依赖

check_python() { ... }
check_node() { ... }
install_python_deps() { pip install -r python_modules/requirements.txt; }
install_node_deps() { cd nodejs_modules && npm install; }
install_playwright() { playwright install chromium; }
```

### 3.3 其他 Shell 脚本

| 脚本 | 职责 |
|---|---|
| cleanup.sh | 清理 logs/reports/results/artifacts 下的过期文件 |
| health_check.sh | 检查被测系统连通性、框架核心服务状态 |
| monitor.sh | 持续采集系统 CPU/内存/磁盘/网络指标 |
| deploy.sh | 部署被测系统（支持 Docker / K8s / 裸机） |
| backup.sh | 备份配置和测试结果 |
| docker_build.sh | 构建框架 Docker 镜像 |
| k8s_deploy.sh | 部署到 K8s 集群 |

---

## 4. 详细设计 — Node.js 脚本

### 4.1 scripts/nodejs/run.js

```javascript
/**
 * Node.js 主入口
 * 用法：node run.js --type=api --config=config.json
 */
const { parseArgs } = require('./lib/args');
const { ApiLoadTest } = require('./api_load_test');
const { WebSocketTest } = require('./websocket_test');
const { GrpcTest } = require('./grpc_test');

async function main() {
    const args = parseArgs(process.argv.slice(2));
    const engines = {
        api: ApiLoadTest,
        websocket: WebSocketTest,
        grpc: GrpcTest
    };
    const Engine = engines[args.type];
    if (!Engine) { console.error(`Unknown type: ${args.type}`); process.exit(1); }
    const engine = new Engine(JSON.parse(args.config || '{}'));
    const result = await engine.run();
    console.log(JSON.stringify(result));
}
main().catch(err => { console.error(err); process.exit(1); });
```

### 4.2 scripts/nodejs/api_load_test.js

```javascript
/**
 * 高并发 API 负载测试
 * 使用 axios + 并发控制实现
 */
class ApiLoadTest {
    constructor(config) { ... }
    async run() {
        // 并发发送请求，采集延迟/吞吐量/错误率
    }
}
module.exports = { ApiLoadTest };
```

### 4.3 scripts/nodejs/websocket_test.js

```javascript
/**
 * WebSocket 连接测试：连接建立、消息收发、心跳、断线重连
 */
```

### 4.4 scripts/nodejs/grpc_test.js

```javascript
/**
 * gRPC 测试：基于 @grpc/grpc-js，支持 unary / streaming 调用
 */
```

### 4.5 scripts/nodejs/performance_worker.js

```javascript
/**
 * 性能工作器：被 Python IPC 调度的后台 worker
 * 常驻运行，接收任务，执行后返回 JSON 结果
 */
```

---

## 5. 详细设计 — 扩展层

### 5.1 service_discovery.py

```python
"""职责：服务发现，支持 Consul / Nacos / Eureka"""
class ServiceDiscovery:
    async def discover(self, service_name: str) -> List[Dict]: ...
    async def register(self, service_info: Dict) -> None: ...
    async def deregister(self, service_id: str) -> None: ...
    async def watch(self, service_name: str, callback: Callable) -> None: ...
```

### 5.2 kubernetes.py

```python
"""职责：K8s 集群操作（创建 Pod、获取日志、扩缩容）"""
class KubernetesIntegration:
    async def create_job(self, spec: Dict) -> str: ...
    async def get_pod_logs(self, pod_name: str, namespace: str) -> str: ...
    async def scale(self, deployment: str, replicas: int) -> None: ...
    async def get_metrics(self, pod_name: str) -> Dict[str, float]: ...
```

### 5.3 docker.py

```python
"""职责：Docker 容器操作"""
class DockerIntegration:
    async def build(self, dockerfile: str, tag: str) -> None: ...
    async def run(self, image: str, **kwargs) -> str: ...
    async def stop(self, container_id: str) -> None: ...
    async def logs(self, container_id: str) -> str: ...
    async def stats(self, container_id: str) -> Dict[str, float]: ...
```

### 5.4 service_mesh.py

```python
"""职责：Service Mesh（Istio）集成"""
class ServiceMeshIntegration:
    async def inject_sidecar(self, deployment: str) -> None: ...
    async def get_traffic_stats(self, service: str) -> Dict: ...
```

### 5.5 tracing.py

```python
"""职责：分布式追踪（OpenTelemetry）"""
class DistributedTracing:
    def start_span(self, name: str) -> Any: ...
    def end_span(self, span: Any) -> None: ...
    def inject_context(self, headers: Dict) -> Dict: ...
    def extract_context(self, headers: Dict) -> Any: ...
```

---

## 6. 详细设计 — Docker 支持

### docker/Dockerfile

```dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl nodejs npm && \
    rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY python_modules/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Node.js 依赖
COPY nodejs_modules/package.json nodejs_modules/
RUN cd nodejs_modules && npm ci --production

# 框架代码
COPY . .

# Playwright 浏览器
RUN playwright install --with-deps chromium

ENTRYPOINT ["python", "-m", "uniplore-test-framework"]
```

### docker/docker-compose.yml

```yaml
version: "3.8"
services:
  framework:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    volumes:
      - ./config:/app/config
      - ./reports:/app/reports
    environment:
      - TF_ENV=test
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: test
      POSTGRES_PASSWORD: test
    ports: ["5432:5432"]
```

---

## 7. 详细设计 — Kubernetes 支持

### kubernetes/deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-framework
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-framework
  template:
    metadata:
      labels:
        app: test-framework
    spec:
      containers:
        - name: framework
          image: test-framework:latest
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "2Gi"
          env:
            - name: TF_ENV
              valueFrom:
                configMapKeyRef:
                  name: test-framework-config
                  key: environment
```

---

## 8. 详细设计 — 框架自测

### 8.1 单元测试

```
tests/unit/
├── test_core/
│   ├── test_container.py        # IoC 容器测试
│   ├── test_event_bus.py        # 事件总线测试
│   ├── test_pipeline.py         # 管道引擎测试
│   ├── test_models.py           # 领域模型测试
│   └── test_exceptions.py       # 异常体系测试
├── test_engines/
│   ├── test_web_performance.py
│   ├── test_backend_performance.py
│   ├── test_rest_api.py
│   ├── test_database.py
│   ├── test_knowledge_qa.py
│   ├── test_penetration.py
│   └── test_auth_bypass.py
├── test_adapters/
│   ├── test_http_adapter.py
│   ├── test_database_adapter.py
│   └── test_browser_adapter.py
└── test_utils/
    ├── test_data_factory.py
    ├── test_crypto.py
    └── test_validation.py
```

### 8.2 集成测试

```python
# test_end_to_end.py
"""
端到端集成测试：
1. 加载配置
2. 初始化框架
3. 对 mock 服务执行各类测试
4. 验证报告生成
"""
```

### 8.3 测试数据

```
tests/fixtures/
├── sample_configs/
│   ├── web_test.yaml
│   ├── api_test.yaml
│   └── db_test.yaml
└── mock_data/
    ├── responses/
    └── datasets/
```

---

## 9. 项目配置文件

### python_modules/requirements.txt

```
# 核心依赖
httpx>=0.25.0
aiohttp>=3.9.0
pyyaml>=6.0
pydantic>=2.0
jsonschema>=4.20.0
jinja2>=3.1.0

# 数据库
asyncpg>=0.29.0
aiomysql>=0.2.0
motor>=3.3.0
redis>=5.0.0

# 浏览器
playwright>=1.40.0

# 监控
psutil>=5.9.0
prometheus-client>=0.19.0

# 工具
python-dateutil>=2.8.0
cryptography>=41.0.0
structlog>=23.2.0
```

### .env.example

```
TF_ENV=dev
TF_DEBUG=false
TF_LOG_LEVEL=INFO
TF_REPORTS_DIR=reports
TF_RESULTS_DIR=results
SYSTEM_A_TOKEN=your_token_here
```

### .gitignore

```
__pycache__/
*.pyc
.env
node_modules/
logs/*.log
reports/*.html
results/*.json
artifacts/
*.egg-info/
dist/
.venv/
```

---

## 10. 验收标准

- [ ] `run.sh` 可作为框架总入口正确调度 Python/Node.js
- [ ] `setup.sh` 可检测并安装全部依赖
- [ ] Node.js 脚本可独立运行 API/WebSocket/gRPC 测试
- [ ] Docker 镜像可正确构建并运行框架
- [ ] docker-compose 可一键启动框架 + 依赖服务
- [ ] K8s Deployment 可正确部署框架 Pod
- [ ] 扩展层服务发现/Docker/K8s/追踪接口完整
- [ ] 单元测试覆盖全部 core/engines/adapters/utils
- [ ] 集成测试可端到端验证完整流程
- [ ] 所有配置文件（.gitignore / .env.example / requirements.txt）规范完整
