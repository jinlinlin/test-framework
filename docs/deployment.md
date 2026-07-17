# 部署指南

## Docker 部署

### 镜像构建

基于 `python:3.11-slim`，内置 Python + Node.js + Playwright：

```bash
cd docker
docker build -t test-framework:latest -f Dockerfile ..
```

### Docker Compose 编排

**生产环境**（`docker-compose.yml`）：

```bash
docker compose up -d
```

编排服务：
- `framework` — 测试框架主容器
- `redis` — Redis 7 缓存
- `postgres` — PostgreSQL 16 数据库

**开发环境**（`docker-compose.dev.yml`）：

```bash
docker compose -f docker-compose.dev.yml up
```

额外特性：
- 源码热挂载（`..:/app`）
- debugpy 远程调试端口 `5678`

### 环境变量

通过 `docker-compose.yml` 或 `.env` 注入：

| 变量 | 默认值 | 说明 |
|------|-------|------|
| `TF_ENV` | `test` | 运行环境 |
| `TF_LOG_LEVEL` | `INFO` | 日志级别 |
| `REDIS_URL` | `redis://redis:6379/0` | Redis 连接 |
| `POSTGRES_URL` | `postgresql://test:test@postgres:5432/test` | PostgreSQL 连接 |

### 数据卷

```yaml
volumes:
  - ../config:/app/config    # 配置文件
  - ../reports:/app/reports  # 报告输出
  - ../results:/app/results  # 结果输出
  - ../logs:/app/logs        # 日志输出
```

---

## Kubernetes 部署

### 资源清单

```
kubernetes/
├── deployment.yaml    # Pod 配置（资源限制 + 健康检查）
├── service.yaml       # Service（ClusterIP + NodePort）
├── configmap.yaml     # 非敏感配置
└── secret.yaml        # 敏感配置（Base64 编码）
```

### 部署步骤

```bash
# 1. 创建命名空间（可选）
kubectl create namespace test-framework

# 2. 部署 ConfigMap 和 Secret
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/secret.yaml

# 3. 部署 Service
kubectl apply -f kubernetes/service.yaml

# 4. 构建并推送镜像
docker build -t registry.example.com/test-framework:v1 -f docker/Dockerfile .
docker push registry.example.com/test-framework:v1

# 5. 更新 Deployment 镜像并部署
kubectl apply -f kubernetes/deployment.yaml

# 6. 验证部署
kubectl get pods -l app=test-framework
kubectl get svc test-framework
```

### 资源配置

| 资源 | 请求 | 限制 |
|------|------|------|
| CPU | 500m | 2000m |
| 内存 | 512Mi | 2Gi |

### 健康检查

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5

livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
```

### 敏感配置管理

**生产环境建议使用 Sealed Secrets 或外部密钥管理**：

```bash
# 更新 Secret
kubectl create secret generic test-framework-secrets \
  --from-literal=redis_url=redis://prod-redis:6379/0 \
  --from-literal=postgres_url=postgresql://user:pass@prod-pg:5432/prod \
  --from-literal=api_token=your-real-token \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## 运维脚本

`scripts/shell/` 提供完整的运维脚本集：

| 脚本 | 功能 | 用法 |
|------|------|------|
| `run.sh` | 框架主入口 | `./run.sh -e test -t rest_api` |
| `setup.sh` | 环境安装 | `./setup.sh` |
| `cleanup.sh` | 过期文件清理 | `./cleanup.sh --days 30` |
| `health_check.sh` | 健康检查 | `./health_check.sh` |
| `monitor.sh` | 资源监控 | `./monitor.sh --interval 5` |
| `deploy.sh` | 部署（docker/k8s/bare） | `./deploy.sh --mode docker` |
| `backup.sh` | 数据备份 | `./backup.sh` |
| `docker_build.sh` | Docker 镜像构建 | `./docker_build.sh --tag v1.0` |
| `k8s_deploy.sh` | K8s 部署 | `./k8s_deploy.sh --namespace test` |

---

## 扩展层集成

### 服务发现

支持 Consul 和 Nacos 服务发现：

```python
from extensions import ServiceDiscovery

# Consul
discovery = ConsulDiscovery(host="localhost", port=8500)
instances = await discovery.discover("my-service")

# Nacos
discovery = NacosDiscovery(host="localhost", port=8848)
instances = await discovery.discover("my-service")
```

### Kubernetes 集成

```python
from extensions import KubernetesIntegration

k8s = KubernetesIntegration()
await k8s.create_job("test-job", image="test-framework:latest")
logs = await k8s.get_pod_logs("test-pod")
```

### Docker 集成

```python
from extensions import DockerIntegration

docker = DockerIntegration()
container = await docker.run("test-framework:latest", ports={"8080": "8080"})
stats = await docker.stats(container.id)
```

### 分布式追踪

```python
from extensions import DistributedTracing

tracing = DistributedTracing(service_name="test-framework")
tracer = tracing.get_tracer()
with tracer.start_span("test_execution") as span:
    span.set_attribute("test.type", "rest_api")
```
