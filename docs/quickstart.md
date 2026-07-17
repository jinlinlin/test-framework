# 快速开始

## 环境要求

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.10+ | 核心框架运行时 |
| Node.js | 18+ | 高性能辅助引擎（可选） |
| Docker | 20.10+ | 容器化部署（可选） |
| Git | 2.30+ | 版本控制 |

---

## 安装

### 方式一：本地安装

```bash
# 克隆仓库
git clone <repo-url>
cd uniplore-test-framework

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# 安装 Python 依赖
pip install -r python_modules/requirements.txt

# 安装开发依赖（可选）
pip install -r python_modules/requirements-dev.txt

# 安装框架（editable 模式）
pip install -e .

# 安装 Node.js 依赖（可选，用于高性能压测）
cd nodejs_modules
npm install
cd ..

# 安装 Playwright 浏览器（可选，用于网页性能测试）
playwright install chromium
```

### 方式二：Docker 安装

```bash
cd docker
docker compose build
docker compose up
```

---

## 配置

### 1. 环境变量

复制 `.env.example` 为 `.env`，填入实际值：

```bash
cp .env.example .env
```

关键变量：

| 变量 | 默认值 | 说明 |
|------|-------|------|
| `TF_ENV` | `dev` | 运行环境（dev/test/staging/production） |
| `TF_LOG_LEVEL` | `INFO` | 日志级别 |
| `TF_REPORTS_DIR` | `reports` | 报告输出目录 |
| `POSTGRES_DSN` | — | PostgreSQL 连接串 |
| `REDIS_URL` | — | Redis 连接串 |

### 2. 测试配置

在 `config/` 目录下创建 YAML 配置文件：

```yaml
# config/my_test.yaml
test:
  name: "我的首次测试"
  type: rest_api
  target:
    base_url: https://jsonplaceholder.typicode.com
  endpoints:
    - path: /posts
      method: GET
      expected_status: 200
    - path: /posts/1
      method: GET
      expected_status: 200
```

---

## 首次运行

### 命令行运行

```bash
# 运行 REST API 测试
bash scripts/shell/run.sh --env dev --type rest_api --config config/my_test.yaml

# 试运行（仅验证配置）
bash scripts/shell/run.sh --env dev --dry-run --config config/my_test.yaml

# 并行执行
bash scripts/shell/run.sh --env test --type rest_api --parallel
```

### Python 模块运行

```bash
python -m test_framework --env dev --type rest_api --config config/my_test.yaml
```

### Node.js 独立运行

```bash
# API 负载测试
node scripts/nodejs/run.js --type=api --config='{"url":"http://localhost:8080","concurrency":10,"total":100}'

# WebSocket 测试
node scripts/nodejs/run.js --type=websocket --config='{"url":"ws://localhost:8080/ws"}'

# gRPC 测试
node scripts/nodejs/run.js --type=grpc --config='{"host":"localhost","port":50051}'
```

### Docker 运行

```bash
cd docker

# 构建并启动
docker compose up --build

# 仅启动框架（依赖服务自动启动）
docker compose up framework

# 开发模式（含调试端口）
docker compose -f docker-compose.dev.yml up
```

---

## 查看结果

测试完成后，结果和报告输出到：

- `reports/` — HTML / JSON 格式的测试报告
- `results/` — 原始测试数据（JSON）
- `logs/` — 框架运行日志

---

## 下一步

- [配置管理](configuration.md) — 了解多层配置和环境覆盖
- [测试引擎](engines.md) — 各引擎详细使用指南
- [适配器](adapters.md) — 自定义适配器开发
- [部署指南](deployment.md) — Docker / K8s 生产部署
