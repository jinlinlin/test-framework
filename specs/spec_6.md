# Spec 6：安全与智能测试引擎 — 渗透测试 + 越权访问测试 + 知识库问答测试

## 1. 概述

本 Spec 实现框架剩余三个测试引擎：  
- **⑤ 知识库问答测试引擎**：面向 RAG 智能问答，提供检索效果、向量嵌入、问答质量、上下文有效性评测  
- **⑥ 渗透测试引擎**：内置 SQL 注入/XSS/路径遍历/命令注入/SSRF/XXE 攻击载荷，自动化漏洞扫描  
- **⑦ 越权访问测试引擎**：覆盖角色提升/会话固定/Token 重放/JWT 攻击/OAuth 攻击/IDOR 等越权检测

**依赖**：Spec 1, Spec 2, Spec 3  
**被依赖**：无（叶子模块）

---

## 2. 目标目录结构

```
uniplore-test-framework/
└── engines/
    ├── knowledge_qa/            # ⑤ 知识库问答测试
    │   ├── __init__.py
    │   ├── engine.py
    │   ├── qa_client.py
    │   ├── quality_evaluator.py
    │   ├── retrieval_tester.py
    │   ├── embedding_analyzer.py
    │   ├── rag_evaluator.py
    │   ├── context_validator.py
    │   └── config_schema.py
    │
    ├── penetration/             # ⑥ 渗透测试
    │   ├── __init__.py
    │   ├── engine.py
    │   ├── scanner.py
    │   ├── payloads/
    │   │   ├── __init__.py
    │   │   ├── base.py
    │   │   ├── sql_injection.py
    │   │   ├── xss.py
    │   │   ├── path_traversal.py
    │   │   ├── command_injection.py
    │   │   ├── ssrf.py
    │   │   └── xxe.py
    │   ├── detector.py
    │   ├── reporter.py
    │   └── config_schema.py
    │
    └── auth_bypass/             # ⑦ 越权访问测试
        ├── __init__.py
        ├── engine.py
        ├── strategies/
        │   ├── __init__.py
        │   ├── base.py
        │   ├── role_escalation.py
        │   ├── session_fixation.py
        │   ├── token_replay.py
        │   ├── jwt_attack.py
        │   ├── oauth_attack.py
        │   └── idor.py
        ├── auth_bypass_detector.py
        └── config_schema.py
```

---

## 3. 详细设计

### 3.1 知识库问答测试引擎

#### knowledge_qa/engine.py

```python
"""
职责：RAG 知识库问答测试主引擎
流程：构建测试问题集 → 调用问答接口 → 评估检索质量 → 评估回答质量 → 生成报告
"""
class KnowledgeQAEngine(BaseEngine):
    engine_type = TestType.KNOWLEDGE_QA

    async def setup(self, target: TargetSystem) -> None:
        self._client = QAClient(target.base_url, target.auth)
        self._quality_eval = QualityEvaluator(self._config)
        self._retrieval_tester = RetrievalTester(self._config)
        self._rag_eval = RAGEvaluator(self._config)
        self._context_validator = ContextValidator(self._config)

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        question = case.config["question"]
        expected = case.config.get("expected_answer")
        expected_context = case.config.get("expected_context")

        # 1. 调用问答接口
        qa_response = await self._client.ask(question)
        # 2. 检索质量评估
        retrieval_score = await self._retrieval_tester.evaluate(question, qa_response.sources)
        # 3. 回答质量评估
        quality_score = self._quality_eval.evaluate(qa_response.answer, expected)
        # 4. RAG 综合评估
        rag_score = self._rag_eval.evaluate(qa_response, expected, expected_context)
        # 5. 上下文有效性
        context_valid = self._context_validator.validate(qa_response.context)

        passed = rag_score >= self._config.get("thresholds", {}).get("min_score", 0.7)
        return TestResult(
            case_id=case.id,
            status=TestStatus.PASS if passed else TestStatus.FAIL,
            duration=qa_response.latency,
            details={
                "answer": qa_response.answer,
                "retrieval_score": retrieval_score,
                "quality_score": quality_score,
                "rag_score": rag_score,
                "context_valid": context_valid
            },
            metrics=TestMetrics(custom={"rag_score": rag_score, "retrieval": retrieval_score}),
            timestamp=datetime.now()
        )
```

#### knowledge_qa/qa_client.py

```python
"""职责：封装问答 API 调用"""
@dataclass
class QAResponse:
    answer: str
    sources: List[str]
    context: List[str]
    latency: float

class QAClient:
    def __init__(self, base_url: str, auth: Dict = None): ...
    async def ask(self, question: str, **kwargs) -> QAResponse: ...
```

#### knowledge_qa/quality_evaluator.py

```python
"""职责：评估回答质量（相关性、完整性、准确性）"""
class QualityEvaluator:
    def evaluate(self, answer: str, expected: str = None) -> float: ...
    def _semantic_similarity(self, a: str, b: str) -> float: ...
    def _keyword_coverage(self, answer: str, expected: str) -> float: ...
```

#### knowledge_qa/retrieval_tester.py

```python
"""职责：评估检索召回质量（Recall@K、MRR、NDCG）"""
class RetrievalTester:
    async def evaluate(self, question: str, retrieved_sources: List[str]) -> float: ...
```

#### knowledge_qa/embedding_analyzer.py

```python
"""职责：分析向量嵌入质量（相似度分布、离群点检测）"""
class EmbeddingAnalyzer:
    async def analyze(self, embeddings: List[List[float]]) -> Dict[str, float]: ...
```

#### knowledge_qa/rag_evaluator.py

```python
"""职责：RAG 综合评估（faithfulness、answer relevancy、context precision）"""
class RAGEvaluator:
    def evaluate(self, response: 'QAResponse', expected: str, expected_context: List[str]) -> float: ...
```

#### knowledge_qa/context_validator.py

```python
"""职责：验证上下文是否充分支撑回答"""
class ContextValidator:
    def validate(self, context: List[str]) -> Dict[str, Any]: ...
```

---

### 3.2 渗透测试引擎

#### penetration/engine.py

```python
"""
职责：渗透测试主引擎
流程：加载攻击载荷 → 对目标各端点逐一扫描 → 检测漏洞 → 生成安全报告
"""
class PenetrationEngine(BaseEngine):
    engine_type = TestType.PENETRATION

    async def setup(self, target: TargetSystem) -> None:
        self._scanner = Scanner(target, self._config)
        self._detector = VulnerabilityDetector(self._config)
        self._reporter = SecurityReporter()
        self._payloads = self._load_payloads()

    def _load_payloads(self) -> List['Payload']:
        """从 payloads/ 目录加载所有攻击载荷"""

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        endpoint = case.config["endpoint"]
        payload_types = case.config.get("payload_types", ["sql_injection", "xss"])
        findings = []
        for ptype in payload_types:
            payload = next(p for p in self._payloads if p.name == ptype)
            scan_result = await self._scanner.scan(endpoint, payload)
            vulns = self._detector.detect(scan_result)
            findings.extend(vulns)

        status = TestStatus.FAIL if any(f.severity in ("high", "critical") for f in findings) else TestStatus.PASS
        return TestResult(
            case_id=case.id, status=status, duration=0,
            details={"findings": [f.to_dict() for f in findings]},
            timestamp=datetime.now()
        )
```

#### penetration/scanner.py

```python
"""职责：对目标端点发送带有攻击载荷的请求"""
class Scanner:
    async def scan(self, endpoint: str, payload: 'Payload') -> ScanResult: ...
    async def scan_all_params(self, endpoint: str, payload: 'Payload') -> List[ScanResult]: ...
```

#### penetration/payloads/base.py

```python
"""策略模式基类"""
class Payload(ABC):
    name: str
    severity: str  # low / medium / high / critical

    @abstractmethod
    def generate(self, params: Dict = None) -> List[str]: ...

    @abstractmethod
    def get_detection_patterns(self) -> List[str]: ...
```

#### penetration/payloads/sql_injection.py

```python
class SQLInjectionPayload(Payload):
    name = "sql_injection"
    severity = "critical"

    def generate(self, params=None) -> List[str]:
        return [
            "' OR '1'='1", "' OR 1=1--", "'; DROP TABLE users;--",
            "1' UNION SELECT NULL,NULL,NULL--", "' AND SLEEP(5)--", ...
        ]

    def get_detection_patterns(self) -> List[str]:
        return ["sql syntax", "mysql_fetch", "ORA-", "SQLite3::", "pg_query"]
```

#### penetration/payloads/xss.py

```python
class XSSPayload(Payload):
    name = "xss"
    def generate(self, params=None) -> List[str]:
        return ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", ...]
    def get_detection_patterns(self) -> List[str]:
        return ["<script>", "onerror=", "javascript:"]
```

#### 其他载荷（结构同上）

- `path_traversal.py`：`../../../etc/passwd` 等
- `command_injection.py`：`; cat /etc/passwd` 等
- `ssrf.py`：内网 IP 探测载荷
- `xxe.py`：XML 外部实体注入载荷

#### penetration/detector.py

```python
"""职责：根据响应内容检测漏洞是否存在"""
@dataclass
class Vulnerability:
    type: str
    severity: str
    endpoint: str
    payload: str
    evidence: str
    recommendation: str

class VulnerabilityDetector:
    def detect(self, scan_result: ScanResult) -> List[Vulnerability]: ...
    def _match_patterns(self, response_body: str, patterns: List[str]) -> bool: ...
    def _check_status_code(self, response: Any) -> bool: ...
    def _check_timing(self, response: Any, expected_delay: float) -> bool: ...
```

#### penetration/reporter.py

```python
"""职责：生成安全测试专项报告（含漏洞分级、修复建议）"""
class SecurityReporter:
    def generate(self, findings: List[Vulnerability]) -> Dict[str, Any]: ...
```

---

### 3.3 越权访问测试引擎

#### auth_bypass/engine.py

```python
"""
职责：越权访问测试主引擎
流程：加载越权策略 → 依次执行各策略 → 汇总检测结果
"""
class AuthBypassEngine(BaseEngine):
    engine_type = TestType.AUTH_BYPASS

    async def setup(self, target: TargetSystem) -> None:
        self._detector = AuthBypassDetector(target, self._config)
        self._strategies = self._load_strategies()

    def _load_strategies(self) -> List['AuthBypassStrategy']:
        """加载所有已注册的越权策略"""

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        strategy_names = case.config.get("strategies", ["role_escalation", "token_replay"])
        findings = []
        for name in strategy_names:
            strategy = next(s for s in self._strategies if s.name == name)
            result = await self._detector.run_strategy(strategy, case.config)
            findings.extend(result)
        status = TestStatus.FAIL if findings else TestStatus.PASS
        return TestResult(case_id=case.id, status=status, ...)
```

#### auth_bypass/strategies/base.py

```python
"""策略模式基类"""
class AuthBypassStrategy(ABC):
    name: str

    @abstractmethod
    async def execute(self, target: 'TargetSystem', context: Dict) -> List['AuthBypassFinding']: ...
```

#### auth_bypass/strategies/role_escalation.py

```python
"""角色提升：低权限用户尝试访问高权限接口"""
class RoleEscalationStrategy(AuthBypassStrategy):
    name = "role_escalation"
    async def execute(self, target, context) -> List[AuthBypassFinding]:
        # 使用低权限 token 访问管理员接口，检测是否返回 200
        ...
```

#### auth_bypass/strategies/session_fixation.py

```python
"""会话固定：登录后 session ID 是否变更"""
class SessionFixationStrategy(AuthBypassStrategy):
    name = "session_fixation"
```

#### auth_bypass/strategies/token_replay.py

```python
"""Token 重放：过期/已注销 token 是否仍可使用"""
class TokenReplayStrategy(AuthBypassStrategy):
    name = "token_replay"
```

#### auth_bypass/strategies/jwt_attack.py

```python
"""JWT 攻击：算法混淆（none/HS256→RS256）、密钥爆破、过期验证"""
class JWTAttackStrategy(AuthBypassStrategy):
    name = "jwt_attack"
```

#### auth_bypass/strategies/oauth_attack.py

```python
"""OAuth 攻击：redirect_uri 篡改、state 参数缺失、scope 提升"""
class OAuthAttackStrategy(AuthBypassStrategy):
    name = "oauth_attack"
```

#### auth_bypass/strategies/idor.py

```python
"""IDOR（不安全的直接对象引用）：遍历资源 ID 检测越权访问"""
class IDORStrategy(AuthBypassStrategy):
    name = "idor"
```

#### auth_bypass/auth_bypass_detector.py

```python
"""职责：统一越权检测调度"""
@dataclass
class AuthBypassFinding:
    strategy: str
    severity: str
    endpoint: str
    description: str
    evidence: str

class AuthBypassDetector:
    async def run_strategy(self, strategy: AuthBypassStrategy, context: Dict) -> List[AuthBypassFinding]: ...
```

---

## 4. 验收标准

- [ ] 知识库引擎可调用问答接口并评估 RAG 综合分数
- [ ] 检索质量指标（Recall@K、NDCG）可正确计算
- [ ] 渗透引擎可对目标端点执行全部 6 类攻击载荷
- [ ] 漏洞检测可正确识别 SQL 注入/XSS/路径遍历/命令注入/SSRF/XXE
- [ ] 安全报告包含漏洞分级和修复建议
- [ ] 越权引擎可执行全部 6 类越权策略
- [ ] IDOR 策略可遍历资源 ID 检测越权
- [ ] 三个引擎均输出标准化 `TestReport`
- [ ] 全模块有完整单元测试覆盖
