"""
枚举定义模块 — 框架中所有枚举类型的统一定义。

包含以下枚举：
    - TestType: 测试类型（7 种核心测试能力）
    - TestStatus: 测试用例执行状态
    - Priority: 测试用例优先级
    - Lifecycle: IoC 容器服务生命周期
    - Verdict: 测试报告最终裁定
    - LoadProfileType: 负载曲线类型
    - Severity: 漏洞/问题严重级别
"""
from __future__ import annotations

from enum import Enum, IntEnum


class TestType(str, Enum):
    """
    测试类型枚举 — 框架支持的七大核心测试能力。

    用于引擎工厂创建引擎、配置路由、用例分类等场景。
    """

    # ① 网页性能测试（Playwright + Lighthouse）
    WEB_PERFORMANCE = "web_performance"

    # ② 后端性能测试（HTTP/gRPC 负载施压）
    BACKEND_PERFORMANCE = "backend_performance"

    # ③ REST API 测试（Python/Node.js 双引擎）
    REST_API = "rest_api"

    # ④ 数据库性能测试（MySQL/PostgreSQL/MongoDB/Redis）
    DATABASE = "database"

    # ⑤ 知识库问答测试（RAG 评测）
    KNOWLEDGE_QA = "knowledge_qa"

    # ⑥ 渗透测试（SQL注入/XSS/路径遍历等）
    PENETRATION = "penetration"

    # ⑦ 越权访问测试（角色提升/Token重放/JWT攻击等）
    AUTH_BYPASS = "auth_bypass"

    # ⑧ UI自动化测试（基于Playwright）
    UI_AUTOMATION = "ui_automation"

    # ⑨ Agent 行为测试（SSE 流式 + LLM-as-Judge + DeepEval 混合评分）
    # 实现引擎将在 Phase A 以薄壳 BaseEngine 形式建于 engines/agent_behavior/，
    # 本枚举项为框架侧接入点，支持配置路由与引擎工厂分发。
    AGENT_BEHAVIOR = "agent_behavior"


class TestStatus(str, Enum):
    """
    测试用例执行状态。

    每个测试用例执行完毕后必须标记为以下状态之一。
    """

    PASS = "pass"       # 测试通过
    FAIL = "fail"       # 测试失败（断言不通过）
    ERROR = "error"     # 测试错误（执行异常，非断言失败）
    SKIP = "skip"       # 测试跳过（前置条件不满足或手动跳过）


class Priority(IntEnum):
    """
    测试用例优先级 — 用于调度排序和资源分配。

    数值越大优先级越高。
    """

    LOW = 1         # 低优先级（可延迟执行）
    MEDIUM = 2      # 中优先级（正常执行）
    HIGH = 3        # 高优先级（优先执行）
    CRITICAL = 4    # 关键优先级（必须执行，阻塞发布）


class Lifecycle(str, Enum):
    """
    IoC 容器服务生命周期。

    - SINGLETON: 全局唯一实例，容器缓存后复用
    - TRANSIENT: 每次请求创建新实例
    """

    SINGLETON = "singleton"
    TRANSIENT = "transient"


class Verdict(str, Enum):
    """
    测试报告最终裁定 — 汇总所有测试结果后的整体评判。

    - PASS: 所有关键用例通过
    - FAIL: 存在关键用例失败
    - WARN: 所有用例通过但存在性能/安全警告
    """

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


class LoadProfileType(str, Enum):
    """
    负载曲线类型 — 后端性能测试中的施压模式。

    每种类型对应 strategies/load/ 下的一个策略实现。
    """

    CONSTANT = "constant"   # 恒定负载
    RAMP_UP = "ramp_up"     # 逐步上升
    SPIKE = "spike"         # 尖峰负载
    SOAK = "soak"           # 浸泡负载
    STEP = "step"           # 阶梯负载
    WAVE = "wave"           # 波浪负载


class Severity(str, Enum):
    """
    漏洞/问题严重级别 — 用于渗透测试和安全报告。

    - LOW: 低风险，建议修复
    - MEDIUM: 中风险，应计划修复
    - HIGH: 高风险，需尽快修复
    - CRITICAL: 严重风险，需立即修复
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
