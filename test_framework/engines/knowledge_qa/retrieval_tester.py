"""
检索质量测试器 — 评估检索召回质量。

职责：计算 Recall@K、MRR（Mean Reciprocal Rank）、
      NDCG（Normalized Discounted Cumulative Gain）等检索指标。
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RetrievalTester:
    """
    检索质量测试器。

    评估知识库检索系统返回的文档列表质量，
    支持 Recall@K、MRR、NDCG 等标准指标。

    Attributes:
        _config: 检索测试配置。
        _default_k: 默认 Recall@K 的 K 值。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化检索测试器。

        Args:
            config: 引擎配置字典。
        """
        retrieval_config = config.get("retrieval", {})
        self._default_k = retrieval_config.get("default_k", 5)
        self._ground_truth = retrieval_config.get("ground_truth", {})

    async def evaluate(
        self,
        question: str,
        retrieved_sources: List[str],
        ground_truth: Optional[List[str]] = None,
    ) -> float:
        """
        评估检索质量。

        综合 Recall@K 和 NDCG 计算检索质量分数。

        Args:
            question: 查询问题。
            retrieved_sources: 检索返回的文档 ID 列表。
            ground_truth: 相关文档 ID 列表（可选）。

        Returns:
            检索质量分数（0.0 ~ 1.0）。
        """
        # 获取基准答案
        relevant = ground_truth or self._ground_truth.get(question, [])

        if not relevant:
            # 无基准答案，基于检索结果数量给出启发式评分
            return self._heuristic_score(retrieved_sources)

        # 计算 Recall@K
        recall = self.recall_at_k(retrieved_sources, relevant, self._default_k)

        # 计算 NDCG@K
        ndcg = self.ndcg_at_k(retrieved_sources, relevant, self._default_k)

        # 计算 MRR
        mrr = self.mrr(retrieved_sources, relevant)

        # 综合分数：Recall 40% + NDCG 40% + MRR 20%
        score = recall * 0.4 + ndcg * 0.4 + mrr * 0.2
        return round(min(1.0, max(0.0, score)), 4)

    def recall_at_k(
        self,
        retrieved: List[str],
        relevant: List[str],
        k: int = 5,
    ) -> float:
        """
        计算 Recall@K。

        前 K 个检索结果中，相关文档占全部相关文档的比例。

        Args:
            retrieved: 检索结果列表。
            relevant: 相关文档列表。
            k: K 值。

        Returns:
            Recall@K 值。
        """
        if not relevant:
            return 0.0
        top_k = set(retrieved[:k])
        relevant_set = set(relevant)
        hits = top_k & relevant_set
        return len(hits) / len(relevant_set)

    def ndcg_at_k(
        self,
        retrieved: List[str],
        relevant: List[str],
        k: int = 5,
    ) -> float:
        """
        计算 NDCG@K。

        归一化折损累积增益，衡量相关文档的排序质量。

        Args:
            retrieved: 检索结果列表。
            relevant: 相关文档列表。
            k: K 值。

        Returns:
            NDCG@K 值（0.0 ~ 1.0）。
        """
        relevant_set = set(relevant)
        if not relevant_set:
            return 0.0

        # DCG
        dcg = 0.0
        for i, doc_id in enumerate(retrieved[:k]):
            rel = 1.0 if doc_id in relevant_set else 0.0
            dcg += rel / math.log2(i + 2)  # i+2 因为 i 从 0 开始

        # 理想排序的 DCG
        ideal_hits = min(len(relevant_set), k)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

        if idcg == 0:
            return 0.0
        return dcg / idcg

    def mrr(self, retrieved: List[str], relevant: List[str]) -> float:
        """
        计算 MRR（Mean Reciprocal Rank）。

        第一个相关文档出现的位置的倒数。

        Args:
            retrieved: 检索结果列表。
            relevant: 相关文档列表。

        Returns:
            MRR 值。
        """
        relevant_set = set(relevant)
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant_set:
                return 1.0 / (i + 1)
        return 0.0

    def _heuristic_score(self, retrieved: List[str]) -> float:
        """
        无基准答案时的启发式评分。

        基于检索结果数量和多样性给出估计分。

        Args:
            retrieved: 检索结果列表。

        Returns:
            启发式评分（0.0 ~ 1.0）。
        """
        if not retrieved:
            return 0.0
        count = len(retrieved)
        # 至少返回 1 个给 0.3，5 个以上给 0.7
        if count >= 5:
            return 0.7
        return 0.3 + (count / 5) * 0.4
