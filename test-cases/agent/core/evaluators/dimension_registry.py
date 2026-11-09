"""维度→评估后端注册表：声明每个评分维度由哪个后端产出、失败时回退到谁。

背景（源仓缺陷的定点改造）：deepeval_adapter 内部把 depth/key_concepts/format/
instruction_follow 四个 judge 专属维度写死为默认常数（3.5/4.0），DeepEval 路径
一旦启用，这四个维度的"分数"实为常量占位——非等价指标，也非实测。本模块把
维度归属从两处硬编码（adapter 常量、agent.yaml scoring.dimensions）收敛为单一
声明表，由 evaluation_orchestrator 按表分发，缺维回退真实 Judge。

配置链路（与框架 config/defaults/agent.yaml 的 scoring.dimensions 同构）：
    {维度英文名: "deepeval" | "judge"}，缺省维度按 fallback 规则回退 judge。
用例侧不直接读框架 YAML（跨进程松耦合），编排配置由用例显式传参注入；
框架 defaults → 用例侧的传递接线随真实 rag 环境用例移植落地。
"""
from typing import Dict, Optional

# 后端合法取值（与 test_type.json schema 的 dimensions enum 对齐）
VALID_BACKENDS = ("deepeval", "judge")

# 默认注册表：与 config/defaults/agent.yaml scoring.dimensions 逐项一致
# （DeepEval 四维有等价指标：AnswerRelevancy/Faithfulness/Hallucination/
#   ContextualRecall；业务定制四维无等价指标必须保留自建 Judge）
DEFAULT_REGISTRY: Dict[str, str] = {
    "relevance": "deepeval",
    "faithfulness": "deepeval",
    "data_accuracy": "deepeval",
    "completeness": "deepeval",
    "depth": "judge",
    "key_concepts": "judge",
    "format": "judge",
    "instruction_follow": "judge",
}


class RegistryError(ValueError):
    """注册表配置非法时抛出（错误信息给出违例维度与合法取值）。"""


def resolve_registry(dimensions: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """归一化路由表：用例传参覆盖默认表，逐项校验后端取值。

    Args:
        dimensions: 用例/编排侧显式声明的路由（None 或缺项按 DEFAULT_REGISTRY 补齐）。

    Returns:
        完整 {维度: backend} 字典。

    Raises:
        RegistryError: 出现非 deepeval/judge 的后端取值，或维度名不在默认词表
            （新维度须先入 DEFAULT_REGISTRY 或随路由表显式声明后端）。
    """
    merged = dict(DEFAULT_REGISTRY)
    for dim, backend in (dimensions or {}).items():
        if backend not in VALID_BACKENDS:
            raise RegistryError(
                f"维度 {dim!r} 的后端 {backend!r} 非法，合法取值：{VALID_BACKENDS}"
            )
        merged[dim] = backend
    return merged


def backend_for(registry: Dict[str, str], dimension: str) -> str:
    """取单维度后端；词表外维度一律按 judge 兜底（未知维度不得静默丢弃）。"""
    return registry.get(dimension, "judge")
