"""
agent_behavior 包 — Agent 行为测试薄壳引擎。

职责：通过 subprocess 委托 pytest 批量执行 test-cases/agent/ 下的
行为用例，将结果收口为框架 TestResult（含评分制字段），并经
JSONReporter 产出 Layer 2 契约产物 summary.json。
"""
from .engine import AgentBehaviorEngine

__all__ = [
    "AgentBehaviorEngine",
]
