"""
上下文有效性验证器 — 验证上下文是否充分支撑回答。

职责：检查知识库问答返回的上下文片段的完整性、
      相关性、非冗余性和信息充分性。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ContextValidator:
    """
    上下文有效性验证器。

    验证问答系统返回的上下文片段是否：
    - 非空且有内容
    - 片段间无严重重复
    - 长度合理
    - 包含有意义信息

    Attributes:
        _config: 验证配置。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化上下文验证器。

        Args:
            config: 引擎配置字典。
        """
        ctx_config = config.get("context_validation", {})
        self._min_context_count = ctx_config.get("min_context_count", 1)
        self._max_context_count = ctx_config.get("max_context_count", 10)
        self._min_chunk_length = ctx_config.get("min_chunk_length", 20)
        self._max_duplicate_ratio = ctx_config.get("max_duplicate_ratio", 0.3)

    def validate(self, context: List[str]) -> Dict[str, Any]:
        """
        验证上下文有效性。

        Args:
            context: 上下文片段列表。

        Returns:
            验证结果字典：
            - valid: 是否通过验证
            - score: 有效性分数（0-1）
            - issues: 发现的问题列表
            - stats: 统计信息
        """
        issues: List[str] = []
        stats: Dict[str, Any] = {}

        if not context:
            return {
                "valid": False,
                "score": 0.0,
                "issues": ["上下文为空"],
                "stats": {"count": 0},
            }

        count = len(context)
        stats["count"] = count

        # 1. 数量检查
        if count < self._min_context_count:
            issues.append(f"上下文数量不足: {count} < {self._min_context_count}")
        if count > self._max_context_count:
            issues.append(f"上下文数量过多: {count} > {self._max_context_count}")

        # 2. 空片段检查
        empty_count = sum(1 for c in context if not c or not c.strip())
        if empty_count > 0:
            issues.append(f"存在 {empty_count} 个空上下文片段")
        stats["empty_count"] = empty_count

        # 3. 长度检查
        lengths = [len(c) for c in context if c and c.strip()]
        short_count = sum(1 for l in lengths if l < self._min_chunk_length)
        if short_count > 0:
            issues.append(f"存在 {short_count} 个过短的上下文片段（<{self._min_chunk_length} 字符）")
        stats["avg_length"] = sum(lengths) / len(lengths) if lengths else 0
        stats["min_length"] = min(lengths) if lengths else 0
        stats["max_length"] = max(lengths) if lengths else 0

        # 4. 重复度检查
        dup_ratio = self._duplicate_ratio(context)
        if dup_ratio > self._max_duplicate_ratio:
            issues.append(f"上下文重复率过高: {dup_ratio:.1%}")
        stats["duplicate_ratio"] = round(dup_ratio, 4)

        # 5. 信息充分性
        info_score = self._information_sufficiency(context)
        stats["information_score"] = round(info_score, 4)

        # 计算综合分数
        score = 1.0
        if issues:
            score -= len(issues) * 0.15
        score = max(0.0, min(1.0, score))

        return {
            "valid": score >= 0.6 and not issues,
            "score": round(score, 4),
            "issues": issues,
            "stats": stats,
        }

    def _duplicate_ratio(self, context: List[str]) -> float:
        """
        计算上下文片段间的重复率。

        基于词集合的 Jaccard 相似度。

        Args:
            context: 上下文片段列表。

        Returns:
            重复率（0.0 ~ 1.0）。
        """
        if len(context) < 2:
            return 0.0

        token_sets = []
        for c in context:
            if c and c.strip():
                tokens = set(re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]{2,}', c.lower()))
                token_sets.append(tokens)

        if len(token_sets) < 2:
            return 0.0

        # 计算所有相邻对的 Jaccard 相似度
        similarities = []
        for i in range(len(token_sets) - 1):
            union = token_sets[i] | token_sets[i + 1]
            if union:
                jaccard = len(token_sets[i] & token_sets[i + 1]) / len(union)
                similarities.append(jaccard)

        return sum(similarities) / len(similarities) if similarities else 0.0

    def _information_sufficiency(self, context: List[str]) -> float:
        """
        评估上下文信息充分性。

        基于有效内容量和多样性。

        Args:
            context: 上下文片段列表。

        Returns:
            信息充分性分数（0.0 ~ 1.0）。
        """
        valid_chunks = [c for c in context if c and c.strip()]
        if not valid_chunks:
            return 0.0

        # 总有效字符数
        total_chars = sum(len(c) for c in valid_chunks)
        # 唯一词数
        all_tokens = set()
        for c in valid_chunks:
            tokens = re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]{2,}', c.lower())
            all_tokens.update(tokens)

        unique_tokens = len(all_tokens)

        # 评分：有效字符 > 200 且唯一词 > 30 为满分
        char_score = min(1.0, total_chars / 500)
        token_score = min(1.0, unique_tokens / 50)

        return char_score * 0.5 + token_score * 0.5
