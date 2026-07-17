"""
知识库问答测试引擎 — RAG 智能问答评测主引擎。

职责：面向 RAG 智能问答系统，评估检索效果、向量嵌入质量、
      回答质量、上下文有效性，生成综合评测报告。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ...core.models import TestCase, TestMetrics, TestResult, TargetSystem
from ...core.models.enums import TestStatus, TestType
from ..base import BaseEngine
from .context_validator import ContextValidator
from .qa_client import QAClient
from .quality_evaluator import QualityEvaluator
from .rag_evaluator import RAGEvaluator
from .retrieval_tester import RetrievalTester

logger = logging.getLogger(__name__)


class KnowledgeQAEngine(BaseEngine):
    """
    知识库问答测试引擎。

    执行流程：构建测试问题集 → 调用问答接口 →
    评估检索质量 → 评估回答质量 → RAG 综合评估 → 生成报告。

    Attributes:
        _client: 问答 API 客户端。
        _quality_eval: 回答质量评估器。
        _retrieval_tester: 检索质量测试器。
        _rag_eval: RAG 综合评估器。
        _context_validator: 上下文验证器。
    """

    @property
    def engine_type(self) -> TestType:
        """引擎类型。"""
        return TestType.KNOWLEDGE_QA

    async def setup(self, target: TargetSystem) -> None:
        """
        初始化知识库问答引擎。

        Args:
            target: 目标系统对象。
        """
        base_url = getattr(target, "base_url", "")
        auth = getattr(target, "auth", None) or {}
        timeout = self._config.get("timeout", 60)

        self._client = QAClient(base_url, auth, timeout)
        await self._client.initialize()

        self._quality_eval = QualityEvaluator(self._config)
        self._retrieval_tester = RetrievalTester(self._config)
        self._rag_eval = RAGEvaluator(self._config)
        self._context_validator = ContextValidator(self._config)

        logger.info(f"知识库问答引擎已初始化: {base_url}")

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        """
        执行单个知识库问答测试用例。

        用例配置格式::

            {
                "question": "什么是机器学习？",
                "expected_answer": "机器学习是...",
                "expected_context": ["doc_001", "doc_002"],
                "ground_truth_sources": ["doc_001"],
                "top_k": 5,
                "endpoint": "/api/qa/ask"
            }

        Args:
            case: 测试用例。
            target: 目标系统。

        Returns:
            测试结果。
        """
        try:
            question = case.config.get("question", "")
            expected_answer = case.config.get("expected_answer")
            expected_context = case.config.get("expected_context")
            ground_truth = case.config.get("ground_truth_sources")

            if not question:
                return TestResult(
                    case_id=case.id,
                    status=TestStatus.FAIL,
                    duration=0,
                    details={"error": "问题不能为空"},
                    metrics=TestMetrics(),
                    timestamp=datetime.now(),
                )

            # 1. 调用问答接口
            qa_response = await self._client.ask(
                question,
                top_k=case.config.get("top_k", 5),
                endpoint=case.config.get("endpoint", "/api/qa/ask"),
            )

            # 2. 检索质量评估
            retrieval_score = await self._retrieval_tester.evaluate(
                question, qa_response.sources, ground_truth
            )

            # 3. 回答质量评估
            quality_score = self._quality_eval.evaluate(
                qa_response.answer, expected_answer
            )

            # 4. RAG 综合评估
            rag_score = self._rag_eval.evaluate(
                qa_response, expected_answer, expected_context
            )

            # 5. 上下文有效性
            context_result = self._context_validator.validate(qa_response.context)

            # 判断是否通过
            min_score = self._config.get("thresholds", {}).get("min_score", 0.7)
            passed = rag_score >= min_score

            return TestResult(
                case_id=case.id,
                status=TestStatus.PASS if passed else TestStatus.FAIL,
                duration=qa_response.latency,
                details={
                    "answer": qa_response.answer[:500],
                    "retrieval_score": retrieval_score,
                    "quality_score": quality_score,
                    "rag_score": rag_score,
                    "context_valid": context_result["valid"],
                    "context_issues": context_result["issues"],
                    "latency": qa_response.latency,
                },
                metrics=TestMetrics(
                    latency_avg=qa_response.latency * 1000,
                    custom={
                        "rag_score": rag_score,
                        "retrieval": retrieval_score,
                        "quality": quality_score,
                    },
                ),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"知识库问答测试异常: {e}")
            return TestResult(
                case_id=case.id,
                status=TestStatus.ERROR,
                duration=0,
                details={"error": str(e)},
                metrics=TestMetrics(),
                timestamp=datetime.now(),
            )

    async def collect_metrics(self) -> TestMetrics:
        """汇总问答测试指标。"""
        if not self._results:
            return TestMetrics()
        avg_latency = sum(r.metrics.latency_avg for r in self._results) / len(self._results)
        return TestMetrics(
            total_cases=len(self._results),
            passed=sum(1 for r in self._results if r.status == TestStatus.PASS),
            failed=sum(1 for r in self._results if r.status == TestStatus.FAIL),
            latency_avg=avg_latency,
        )

    async def teardown(self) -> None:
        """关闭客户端连接。"""
        if hasattr(self, "_client"):
            await self._client.close()
            logger.info("知识库问答引擎已关闭")
