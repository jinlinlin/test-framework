# Spec 2：配置管理层

## 1. 概述

本 Spec 实现框架的配置驱动体系，包含配置管理器（单例）、多格式加载器、Schema 验证器、多环境配置和默认配置。  
框架"全量配置驱动"特性由本层承载：测试场景、施压策略、校验规则、引擎参数均通过配置控制，无需修改代码。

**依赖**：Spec 1（core/exceptions/config.py, core/interfaces/configurable.py）  
**被依赖**：Spec 3 ~ Spec 10 所有引擎和组件

---

## 2. 目标目录结构

```
uniplore-test-framework/
└── config/
    ├── __init__.py
    ├── manager.py              # 配置管理器（单例模式）
    ├── loader.py               # 配置加载器（工厂模式）
    ├── validator.py            # 配置验证器
    ├── schema/
    │   ├── __init__.py
    │   ├── global.json         # 全局配置 Schema
    │   ├── test_type.json      # 测试类型 Schema
    │   ├── adapter.json        # 适配器 Schema
    │   └── strategy.json       # 策略 Schema
    ├── environments/
    │   ├── __init__.py
    │   ├── base.yaml           # 基础配置（所有环境共享）
    │   ├── dev.yaml
    │   ├── test.yaml
    │   ├── staging.yaml
    │   └── production.yaml
    ├── defaults/
    │   ├── __init__.py
    │   ├── web.yaml            # 网页性能默认配置
    │   ├── backend.yaml        # 后端性能默认配置
    │   ├── api.yaml            # REST API 默认配置
    │   ├── database.yaml       # 数据库默认配置
    │   ├── knowledge.yaml      # 知识库问答默认配置
    │   ├── penetration.yaml    # 渗透测试默认配置
    │   └── auth_bypass.yaml    # 越权测试默认配置
    └── targets/
        ├── __init__.py
        ├── system_a.yaml       # 被测系统 A 配置示例
        ├── system_b.yaml       # 被测系统 B 配置示例
        └── templates/
            ├── web_target.yaml
            ├── api_target.yaml
            └── db_target.yaml
```

---

## 3. 详细设计

### 3.1 manager.py — 配置管理器（单例模式）

```python
"""
设计模式：单例模式
职责：全局统一配置入口，支持层级合并、热重载、按路径访问
配置优先级：环境变量 > 命令行参数 > 环境配置 > 默认配置
"""
class ConfigManager:
    _instance: Optional['ConfigManager'] = None
    _config: Dict[str, Any]

    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = {}
            cls._instance._env = "dev"
        return cls._instance

    def load(self, env: str = "dev", config_dir: str = None) -> None:
        """
        加载流程：
        1. 加载 schema/global.json
        2. 加载 defaults/ 下所有 yaml
        3. 加载 environments/base.yaml
        4. 加载 environments/{env}.yaml（深度合并覆盖）
        5. 加载环境变量覆盖（TF_ 前缀）
        """

    def get(self, path: str, default: Any = None) -> Any:
        """支持点号路径访问：config.get('engines.web_performance.timeout')"""

    def set(self, path: str, value: Any) -> None:
        """运行时动态设置，不影响文件"""

    def get_section(self, section: str) -> Dict[str, Any]:
        """获取整个配置区块，如 'engines.rest_api'"""

    def reload(self) -> None:
        """热重载：重新读取配置文件并合并"""

    def validate(self) -> List[str]:
        """调用 validator 验证当前配置，返回错误列表"""

    def export(self, path: str) -> None:
        """将当前生效配置导出为 yaml 文件"""

    @property
    def environment(self) -> str: ...
```

### 3.2 loader.py — 配置加载器（工厂模式）

```python
"""
设计模式：工厂模式
职责：根据文件扩展名自动选择对应解析器（YAML / JSON / TOML / .env）
"""
class ConfigLoaderFactory:
    _loaders: Dict[str, Type['ConfigLoader']] = {
        '.yaml': YamlLoader,
        '.yml': YamlLoader,
        '.json': JsonLoader,
        '.toml': TomlLoader,
        '.env': EnvLoader,
    }

    @classmethod
    def get_loader(cls, file_path: str) -> 'ConfigLoader': ...

    @classmethod
    def register_loader(cls, ext: str, loader_cls: Type['ConfigLoader']) -> None: ...

class ConfigLoader(ABC):
    @abstractmethod
    def load(self, file_path: str) -> Dict[str, Any]: ...

    @abstractmethod
    def dump(self, data: Dict[str, Any], file_path: str) -> None: ...

class YamlLoader(ConfigLoader): ...
class JsonLoader(ConfigLoader): ...
class TomlLoader(ConfigLoader): ...
class EnvLoader(ConfigLoader): ...

def deep_merge(base: Dict, override: Dict) -> Dict:
    """深度合并两个字典，override 优先，嵌套字典递归合并"""
```

### 3.3 validator.py — 配置验证器

```python
"""
职责：基于 JSON Schema 验证配置完整性和类型正确性
"""
class ConfigValidator:
    def __init__(self, schema_dir: str): ...

    def validate(self, config: Dict, schema_name: str) -> ValidationResult: ...

    def validate_all(self, config: Dict) -> ValidationResult:
        """依次验证 global / test_type / adapter / strategy 四个 Schema"""

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
```

### 3.4 Schema 定义

#### global.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["framework", "logging", "output"],
  "properties": {
    "framework": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "version": { "type": "string" },
        "debug": { "type": "boolean", "default": false }
      }
    },
    "logging": {
      "type": "object",
      "properties": {
        "level": { "enum": ["DEBUG", "INFO", "WARNING", "ERROR"] },
        "file": { "type": "string" },
        "max_size_mb": { "type": "integer", "minimum": 1 },
        "backup_count": { "type": "integer", "minimum": 1 }
      }
    },
    "output": {
      "type": "object",
      "properties": {
        "reports_dir": { "type": "string" },
        "results_dir": { "type": "string" },
        "logs_dir": { "type": "string" }
      }
    }
  }
}
```

#### test_type.json（节选，完整含7类）

```json
{
  "properties": {
    "engines": {
      "type": "object",
      "properties": {
        "web_performance": { "$ref": "#/definitions/web_perf_config" },
        "backend_performance": { "$ref": "#/definitions/backend_perf_config" },
        "rest_api": { "$ref": "#/definitions/rest_api_config" },
        "database": { "$ref": "#/definitions/database_config" },
        "knowledge_qa": { "$ref": "#/definitions/knowledge_qa_config" },
        "penetration": { "$ref": "#/definitions/penetration_config" },
        "auth_bypass": { "$ref": "#/definitions/auth_bypass_config" }
      }
    }
  }
}
```

### 3.5 环境配置示例

#### environments/base.yaml

```yaml
framework:
  name: uniplore-test-framework
  version: "1.0.0"
  debug: false

logging:
  level: INFO
  file: logs/framework.log
  max_size_mb: 50
  backup_count: 5

output:
  reports_dir: reports
  results_dir: results
  logs_dir: logs
```

#### environments/dev.yaml

```yaml
framework:
  debug: true

logging:
  level: DEBUG
```

### 3.6 默认配置示例

#### defaults/web.yaml

```yaml
web_performance:
  browser: chromium
  headless: true
  timeout: 30000
  viewport:
    width: 1920
    height: 1080
  lighthouse:
    enabled: true
    categories:
      - performance
      - accessibility
      - best-practices
  web_vitals:
    metrics:
      - FCP
      - LCP
      - CLS
      - FID
      - INP
    thresholds:
      LCP: 2500
      FID: 100
      CLS: 0.1
```

#### defaults/api.yaml

```yaml
rest_api:
  timeout: 30
  max_retries: 3
  verify_ssl: true
  rate_limit:
    enabled: false
    requests_per_second: 100
  auth:
    type: none          # none / basic / bearer / oauth2
  validation:
    schema_check: true
    contract_check: false
```

#### defaults/database.yaml

```yaml
database:
  pool:
    min_size: 5
    max_size: 20
    idle_timeout: 300
  query:
    timeout: 60
    explain: true
  index_advisor:
    enabled: true
    min_improvement_pct: 10
```

### 3.7 被测系统配置示例

#### targets/system_a.yaml

```yaml
target:
  id: system_a
  name: "System A - Web Application"
  base_url: http://localhost:8080
  host: localhost
  port: 8080
  protocol: http
  auth:
    type: bearer
    token_env: SYSTEM_A_TOKEN   # 从环境变量读取
  metadata:
    tech_stack: [python, fastapi]
    environment: test
```

#### targets/templates/api_target.yaml

```yaml
# 模板：复制后修改 target.id / base_url / auth 即可
target:
  id: ${TARGET_ID}
  name: ${TARGET_NAME}
  base_url: ${BASE_URL}
  host: ${HOST}
  port: ${PORT}
  protocol: ${PROTOCOL}
  auth:
    type: ${AUTH_TYPE}
    token_env: ${AUTH_TOKEN_ENV}
```

---

## 4. 验收标准

- [ ] `ConfigManager` 单例可正确加载并按优先级合并配置
- [ ] `ConfigLoaderFactory` 可解析 YAML / JSON / TOML / .env 四种格式
- [ ] `deep_merge` 函数可正确递归合并嵌套字典
- [ ] `ConfigValidator` 可基于 JSON Schema 检测配置错误并输出清晰错误信息
- [ ] 环境变量覆盖（`TF_` 前缀）正确生效
- [ ] `ConfigManager.reload()` 热重载后配置正确更新
- [ ] 7类测试引擎均有完整默认配置，可零配置启动
- [ ] 被测系统配置模板可正确实例化
- [ ] 全模块有完整单元测试覆盖
