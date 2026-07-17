"""
向量嵌入分析器 — 分析向量嵌入质量。

职责：分析嵌入向量的相似度分布、离群点检测、
      维度一致性、聚类分布等指标。
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EmbeddingAnalyzer:
    """
    向量嵌入分析器。

    对一组嵌入向量进行质量分析，包括：
    - 相似度分布统计
    - 离群点检测
    - 维度一致性检查
    - 向量范数分布

    Attributes:
        _config: 分析配置。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化嵌入分析器。

        Args:
            config: 分析配置（可选）。
        """
        self._config = config or {}
        self._outlier_threshold = self._config.get("outlier_threshold", 2.0)

    async def analyze(self, embeddings: List[List[float]]) -> Dict[str, float]:
        """
        分析一组嵌入向量的质量。

        Args:
            embeddings: 嵌入向量列表，每个向量为浮点数列表。

        Returns:
            分析指标字典，包含：
            - dimension: 向量维度
            - dimension_consistent: 维度是否一致
            - avg_norm: 平均范数
            - norm_std: 范数标准差
            - avg_pairwise_similarity: 平均成对相似度
            - outlier_ratio: 离群点比例
            - quality_score: 综合质量分（0-1）
        """
        if not embeddings:
            return {"quality_score": 0.0, "error": "无嵌入向量"}

        # 维度检查
        dimensions = [len(v) for v in embeddings]
        dim_consistent = len(set(dimensions)) == 1
        dimension = dimensions[0] if dimensions else 0

        # 范数统计
        norms = [self._vector_norm(v) for v in embeddings]
        avg_norm = sum(norms) / len(norms)
        norm_std = self._std(norms) if len(norms) > 1 else 0.0

        # 成对相似度（采样避免 O(n²)）
        avg_sim = self._avg_pairwise_similarity(embeddings)

        # 离群点检测
        outlier_count = self._detect_outliers(norms)
        outlier_ratio = outlier_count / len(embeddings) if embeddings else 0

        # 综合质量评分
        quality = self._compute_quality(
            dim_consistent, avg_norm, norm_std, avg_sim, outlier_ratio
        )

        return {
            "dimension": dimension,
            "dimension_consistent": dim_consistent,
            "avg_norm": round(avg_norm, 4),
            "norm_std": round(norm_std, 4),
            "avg_pairwise_similarity": round(avg_sim, 4),
            "outlier_ratio": round(outlier_ratio, 4),
            "outlier_count": outlier_count,
            "total_vectors": len(embeddings),
            "quality_score": round(quality, 4),
        }

    def _vector_norm(self, vec: List[float]) -> float:
        """计算向量的 L2 范数。"""
        return math.sqrt(sum(x * x for x in vec))

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算两个向量的余弦相似度。"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = self._vector_norm(a)
        norm_b = self._vector_norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _avg_pairwise_similarity(self, embeddings: List[List[float]]) -> float:
        """
        计算平均成对相似度（采样最多 100 对）。

        Args:
            embeddings: 嵌入向量列表。

        Returns:
            平均相似度。
        """
        n = len(embeddings)
        if n < 2:
            return 0.0

        # 采样最多 100 对
        pairs = []
        max_pairs = 100
        step = max(1, (n * (n - 1) // 2) // max_pairs)
        count = 0
        for i in range(n):
            for j in range(i + 1, n):
                count += 1
                if count % step == 0:
                    pairs.append(self._cosine_similarity(embeddings[i], embeddings[j]))
                if len(pairs) >= max_pairs:
                    break
            if len(pairs) >= max_pairs:
                break

        return sum(pairs) / len(pairs) if pairs else 0.0

    def _detect_outliers(self, norms: List[float]) -> int:
        """
        基于 Z-score 检测离群点。

        Args:
            norms: 范数列表。

        Returns:
            离群点数量。
        """
        if len(norms) < 3:
            return 0

        mean = sum(norms) / len(norms)
        std = self._std(norms)
        if std == 0:
            return 0

        return sum(1 for n in norms if abs(n - mean) / std > self._outlier_threshold)

    @staticmethod
    def _std(values: List[float]) -> float:
        """计算标准差。"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    def _compute_quality(
        self,
        dim_consistent: bool,
        avg_norm: float,
        norm_std: float,
        avg_sim: float,
        outlier_ratio: float,
    ) -> float:
        """
        计算综合质量评分。

        Args:
            dim_consistent: 维度是否一致。
            avg_norm: 平均范数。
            norm_std: 范数标准差。
            avg_sim: 平均相似度。
            outlier_ratio: 离群点比例。

        Returns:
            质量评分（0.0 ~ 1.0）。
        """
        score = 1.0

        # 维度不一致严重扣分
        if not dim_consistent:
            score *= 0.3

        # 范数过小（接近零向量）扣分
        if avg_norm < 0.01:
            score *= 0.2

        # 范数标准差过大扣分
        if norm_std > avg_norm * 0.5 and avg_norm > 0:
            score *= 0.7

        # 平均相似度太高（缺乏区分度）扣分
        if avg_sim > 0.95:
            score *= 0.6

        # 离群点过多扣分
        if outlier_ratio > 0.1:
            score *= 0.7

        return max(0.0, min(1.0, score))
