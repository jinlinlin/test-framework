"""项目级共享常量：维度名称映射、断言阈值等，供多模块统一引用。

将分散在 judge_client / deepeval_adapter / langfuse_integration / test_paper_common
中的重复定义收敛到此处，避免多处维护不一致。
"""
from typing import Dict, List

# ── Judge 评分维度 ──

# 主观评估 6 维（不依赖参考原文，仅基于回答本身评估）
SUBJECTIVE_DIMENSIONS: List[str] = [
    "relevance", "completeness", "depth",
    "instruction_follow", "format", "key_concepts",
]

# 全维度列表（主观 6 维 + Claim-Level 忠实度）
ALL_JUDGE_DIMENSIONS: List[str] = SUBJECTIVE_DIMENSIONS + ["faithfulness"]

# 维度中英文名映射（主观 6 维 + Claim-Level 忠实度 + DeepEval 扩展）
DIMENSION_NAMES: Dict[str, str] = {
    "relevance": "相关性",
    "completeness": "完整性",
    "format": "格式规范",
    "depth": "分析深度",
    "key_concepts": "关键概念",
    "instruction_follow": "指令遵循",
    "faithfulness": "忠实度",
    "data_accuracy": "数据准确性",  # DeepEval HallucinationMetric 反向映射
}
