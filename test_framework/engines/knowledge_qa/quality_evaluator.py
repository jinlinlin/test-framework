"""
回答质量评估器 — 评估知识库问答的回答质量。

职责：从相关性、完整性、准确性三个维度评估回答质量，
      支持语义相似度计算和关键词覆盖率分析。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QualityEvaluator:
    """
    回答质量评估器。

    综合语义相似度、关键词覆盖率、回答长度合理性
    三个维度计算回答质量分数（0-1）。

    Attributes:
        _config: 评估配置。
        _weights: 各维度权重。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化质量评估器。

        Args:
            config: 引擎配置字典。
        """
        self._config = config
        quality_config = config.get("quality", {})
        self._weights = {
            "semantic": quality_config.get("semantic_weight", 0.4),
            "keyword": quality_config.get("keyword_weight", 0.3),
            "length": quality_config.get("length_weight", 0.3),
        }
        self._min_answer_length = quality_config.get("min_answer_length", 10)
        self._max_answer_length = quality_config.get("max_answer_length", 5000)

    def evaluate(self, answer: str, expected: Optional[str] = None) -> float:
        """
        评估回答质量。

        综合计算语义相似度、关键词覆盖率、长度合理性，
        返回 0-1 之间的质量分数。

        Args:
            answer: 实际回答文本。
            expected: 期望回答文本（可选，无则跳过语义对比）。

        Returns:
            质量分数（0.0 ~ 1.0）。
        """
        if not answer or not answer.strip():
            return 0.0

        scores = {}

        # 1. 语义相似度
        if expected:
            scores["semantic"] = self._semantic_similarity(answer, expected)
        else:
            # 无期望回答时，默认给中等分
            scores["semantic"] = 0.5

        # 2. 关键词覆盖率
        if expected:
            scores["keyword"] = self._keyword_coverage(answer, expected)
        else:
            scores["keyword"] = 0.5

        # 3. 长度合理性
        scores["length"] = self._length_score(answer)

        # 加权汇总
        total = sum(
            scores[k] * self._weights[k] for k in scores
        )
        return round(min(1.0, max(0.0, total)), 4)

    def _semantic_similarity(self, a: str, b: str) -> float:
        """
        计算两段文本的语义相似度。

        优先使用 sentence-transformers，不可用时回退到
        基于词频的余弦相似度。

        Args:
            a: 文本 A。
            b: 文本 B。

        Returns:
            相似度分数（0.0 ~ 1.0）。
        """
        try:
            # 尝试使用 sentence-transformers
            from sentence_transformers import SentenceTransformer
            import numpy as np

            model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = model.encode([a, b])
            cosine = float(np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]) + 1e-8
            ))
            return max(0.0, cosine)
        except ImportError:
            # 回退到简单词频余弦相似度
            return self._simple_cosine_similarity(a, b)

    def _keyword_coverage(self, answer: str, expected: str) -> float:
        """
        计算关键词覆盖率。

        从期望回答中提取关键词，检查实际回答覆盖了多少。

        Args:
            answer: 实际回答。
            expected: 期望回答。

        Returns:
            覆盖率（0.0 ~ 1.0）。
        """
        # 提取期望回答中的关键词（长度 > 2 的词）
        expected_tokens = set(self._tokenize(expected))
        if not expected_tokens:
            return 0.5

        answer_tokens = set(self._tokenize(answer))
        overlap = expected_tokens & answer_tokens

        return len(overlap) / len(expected_tokens) if expected_tokens else 0.5

    def _length_score(self, answer: str) -> float:
        """
        评估回答长度合理性。

        太短或太长的回答得分较低。

        Args:
            answer: 回答文本。

        Returns:
            长度合理性分数（0.0 ~ 1.0）。
        """
        length = len(answer)
        if length < self._min_answer_length:
            return 0.1
        if length > self._max_answer_length:
            return 0.3
        # 理想长度范围
        ideal_min = max(50, self._min_answer_length)
        ideal_max = min(2000, self._max_answer_length)
        if ideal_min <= length <= ideal_max:
            return 1.0
        # 渐变衰减
        if length < ideal_min:
            return length / ideal_min
        return max(0.3, 1.0 - (length - ideal_max) / ideal_max)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        简单分词（中文按字符，英文按单词）。

        Args:
            text: 待分词文本。

        Returns:
            词元列表。
        """
        # 英文单词 + 中文字符
        tokens = re.findall(r'[a-zA-Z]{2,}|[\u4e00-\u9fff]', text.lower())
        return [t for t in tokens if len(t) >= 2]

    @staticmethod
    def _simple_cosine_similarity(a: str, b: str) -> float:
        """
        基于词频的余弦相似度。

        Args:
            a: 文本 A。
            b: 文本 B。

        Returns:
            相似度（0.0 ~ 1.0）。
        """
        tokens_a = re.findall(r'\w+', a.lower())
        tokens_b = re.findall(r'\w+', b.lower())

        # 词频统计
        freq_a: Dict[str, int] = {}
        freq_b: Dict[str, int] = {}
        for t in tokens_a:
            freq_a[t] = freq_a.get(t, 0) + 1
        for t in tokens_b:
            freq_b[t] = freq_b.get(t, 0) + 1

        # 共同词汇
        all_tokens = set(freq_a) | set(freq_b)
        if not all_tokens:
            return 0.0

        dot_product = sum(freq_a.get(t, 0) * freq_b.get(t, 0) for t in all_tokens)
        norm_a = sum(v ** 2 for v in freq_a.values()) ** 0.5
        norm_b = sum(v ** 2 for v in freq_b.values()) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
