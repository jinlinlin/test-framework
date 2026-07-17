"""
RAG 综合评估器 — 评估检索增强生成系统的整体表现。

职责：从 faithfulness（忠实度）、answer relevancy（回答相关性）、
      context precision（上下文精确度）三个维度进行 RAG 综合评估。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """
    RAG 综合评估器。

    参考 RAGAS 框架的评估维度，对 RAG 系统的
    忠实度、回答相关性、上下文精确度进行综合评分。

    Attributes:
        _config: 评估配置。
        _weights: 各维度权重。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化 RAG 评估器。

        Args:
            config: 引擎配置字典。
        """
        rag_config = config.get("rag_evaluation", {})
        self._weights = {
            "faithfulness": rag_config.get("faithfulness_weight", 0.4),
            "answer_relevancy": rag_config.get("answer_relevancy_weight", 0.3),
            "context_precision": rag_config.get("context_precision_weight", 0.3),
        }

    def evaluate(
        self,
        response: Any,
        expected: Optional[str] = None,
        expected_context: Optional[List[str]] = None,
    ) -> float:
        """
        RAG 综合评估。

        Args:
            response: QAResponse 对象（含 answer / context / sources）。
            expected: 期望回答文本。
            expected_context: 期望上下文片段列表。

        Returns:
            RAG 综合评分（0.0 ~ 1.0）。
        """
        answer = getattr(response, "answer", "") or ""
        context = getattr(response, "context", []) or []

        scores = {}

        # 1. 忠实度：回答是否被上下文支撑
        scores["faithfulness"] = self._faithfulness(answer, context)

        # 2. 回答相关性：回答与预期回答的相关度
        if expected:
            scores["answer_relevancy"] = self._answer_relevancy(answer, expected)
        else:
            scores["answer_relevancy"] = self._answer_quality_heuristic(answer)

        # 3. 上下文精确度：上下文是否精确匹配查询
        if expected_context:
            scores["context_precision"] = self._context_precision(context, expected_context)
        else:
            scores["context_precision"] = self._context_quality_heuristic(context)

        # 加权汇总
        total = sum(scores[k] * self._weights[k] for k in scores)
        return round(min(1.0, max(0.0, total)), 4)

    def _faithfulness(self, answer: str, context: List[str]) -> float:
        """
        计算忠实度：回答中的声明是否被上下文支撑。

        基于关键词重叠的启发式方法。

        Args:
            answer: 回答文本。
            context: 上下文片段列表。

        Returns:
            忠实度分数（0.0 ~ 1.0）。
        """
        if not answer or not context:
            return 0.0

        # 合并上下文
        all_context = " ".join(context).lower()
        context_tokens = set(re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]{2,}', all_context))

        if not context_tokens:
            return 0.0

        # 提取回答中的关键词
        answer_tokens = set(re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]{2,}', answer.lower()))

        if not answer_tokens:
            return 0.0

        # 检查回答中的词在上下文中的覆盖率
        covered = sum(1 for t in answer_tokens if t in context_tokens)
        faithfulness = covered / len(answer_tokens)

        return round(min(1.0, faithfulness), 4)

    def _answer_relevancy(self, answer: str, expected: str) -> float:
        """
        计算回答相关性：实际回答与期望回答的匹配度。

        Args:
            answer: 实际回答。
            expected: 期望回答。

        Returns:
            相关性分数（0.0 ~ 1.0）。
        """
        if not answer or not expected:
            return 0.0

        # 基于关键词重叠系数
        answer_tokens = set(re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]{2,}', answer.lower()))
        expected_tokens = set(re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]{2,}', expected.lower()))

        if not answer_tokens or not expected_tokens:
            return 0.0

        overlap = answer_tokens & expected_tokens
        union = answer_tokens | expected_tokens

        # Jaccard 相似度 + 覆盖率混合
        jaccard = len(overlap) / len(union) if union else 0
        coverage = len(overlap) / len(expected_tokens) if expected_tokens else 0

        return round(min(1.0, jaccard * 0.4 + coverage * 0.6), 4)

    def _context_precision(self, context: List[str], expected_context: List[str]) -> float:
        """
        计算上下文精确度。

        检查实际上下文与期望上下文的匹配程度。

        Args:
            context: 实际上下文。
            expected_context: 期望上下文。

        Returns:
            精确度分数（0.0 ~ 1.0）。
        """
        if not context or not expected_context:
            return 0.0

        expected_set = set(expected_context)
        matched = 0
        for ctx in context:
            for exp in expected_set:
                if self._text_overlap(ctx, exp) > 0.5:
                    matched += 1
                    break

        precision = matched / len(context) if context else 0
        recall = matched / len(expected_set) if expected_set else 0

        # F1 分数
        if precision + recall == 0:
            return 0.0
        f1 = 2 * precision * recall / (precision + recall)
        return round(min(1.0, f1), 4)

    def _answer_quality_heuristic(self, answer: str) -> float:
        """无期望回答时的启发式回答质量评估。"""
        if not answer:
            return 0.0
        length = len(answer)
        if length < 20:
            return 0.3
        if length < 50:
            return 0.5
        if length > 5000:
            return 0.6
        return 0.7

    def _context_quality_heuristic(self, context: List[str]) -> float:
        """无期望上下文时的启发式上下文质量评估。"""
        if not context:
            return 0.0
        count = len(context)
        if count >= 3:
            return 0.7
        return 0.3 + (count / 3) * 0.4

    @staticmethod
    def _text_overlap(a: str, b: str) -> float:
        """计算两段文本的词重叠系数。"""
        tokens_a = set(re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]{2,}', a.lower()))
        tokens_b = set(re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]{2,}', b.lower()))
        if not tokens_a or not tokens_b:
            return 0.0
        overlap = tokens_a & tokens_b
        return len(overlap) / min(len(tokens_a), len(tokens_b))
