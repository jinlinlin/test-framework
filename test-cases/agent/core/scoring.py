"""Judge 评分聚合工具：统一平均分计算、维度值归一化逻辑。

将散落在 judge_client / test_paper_common / langfuse_integration / deepeval_adapter
中的重复计算收敛到此处，确保全链路平均分一致。
"""
from typing import Any, Dict, List, Optional

from core.constants import ALL_JUDGE_DIMENSIONS


def normalize_dimension_scores(scores: Dict[str, Any]) -> Dict[str, float]:
    """归一化维度分数：兼容新旧格式（数字 / dict 对象）。

    Judge 模型可能返回两种格式：
    - 旧格式：{"relevance": 4.5, "completeness": 3.8, ...}
    - 新格式：{"relevance": {"score": 4.5, "name": "相关性", "reason": "..."}, ...}

    本函数统一提取数值，返回 {维度: 数值} 字典。

    Args:
        scores: 原始维度分数字典。

    Returns:
        归一化后的 {维度名: 数值} 字典（仅含可识别数值的维度）。
    """
    normalized = {}
    for key, val in scores.items():
        if key.startswith("_"):  # 跳过元数据字段（_judge_model, _all_runs 等）
            continue
        if isinstance(val, dict):
            score = val.get("score", 0)
        else:
            score = val
        try:
            normalized[key] = float(score)
        except (TypeError, ValueError):
            continue
    return normalized


def compute_average(
    judge_result: Dict[str, Any],
    dimensions: Optional[List[str]] = None,
) -> float:
    """从 judge_result 中计算指定维度的算术平均分。

    自动归一化维度值格式（数字 / dict 对象），不信任 LLM 自报的 average 字段。

    Args:
        judge_result: Judge 评估结果字典。
        dimensions: 参与计算的维度列表；为 None 时使用 ALL_JUDGE_DIMENSIONS。

    Returns:
        平均分（保留 1 位小数）；无有效维度分数时返回 0.0。
    """
    dims = dimensions or ALL_JUDGE_DIMENSIONS
    scores = []
    for d in dims:
        val = judge_result.get(d)
        if val is None:
            continue
        if isinstance(val, dict):
            val = val.get("score", 0)
        try:
            scores.append(float(val))
        except (TypeError, ValueError):
            continue
    return round(sum(scores) / len(scores), 1) if scores else 0.0


def get_dimension_scores(
    judge_result: Dict[str, Any],
    dimensions: Optional[List[str]] = None,
) -> List[float]:
    """提取指定维度的分数列表（供打印 / 中位数等二次计算）。

    Args:
        judge_result: Judge 评估结果字典。
        dimensions: 维度列表；为 None 时使用 ALL_JUDGE_DIMENSIONS。

    Returns:
        各维度分数列表（顺序与 dimensions 一致，跳过不存在的维度）。
    """
    dims = dimensions or ALL_JUDGE_DIMENSIONS
    scores = []
    for d in dims:
        val = judge_result.get(d)
        if val is None:
            continue
        if isinstance(val, dict):
            val = val.get("score", 0)
        try:
            scores.append(float(val))
        except (TypeError, ValueError):
            continue
    return scores
