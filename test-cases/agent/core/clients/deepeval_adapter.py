"""DeepEval 适配层：将自建 Judge 7 维评分映射到 DeepEval 指标体系。

设计目标：
1. 复用现有 Judge 配置（DashScope qwen-plus），无需额外配置
2. 输出格式与自建 Judge 兼容，产物 JSON 结构不变
3. 支持渐进式替换：USE_DEEPEVAL=false 时完全回退到自建 Judge
4. 新增自建 Judge 没有的指标（ToolCallAccuracy 等）

指标映射关系：
┌─────────────────┬──────────────────────────────┬─────────────────────────┐
│ 自建 Judge 维度  │ DeepEval 指标                 │ 说明                    │
├─────────────────┼──────────────────────────────┼─────────────────────────┤
│ relevance       │ AnswerRelevancyMetric        │ 答案相关性               │
│ faithfulness    │ FaithfulnessMetric           │ 忠实度（基于参考原文）    │
│ data_accuracy   │ HallucinationMetric          │ 幻觉检测（反向映射）      │
│ completeness    │ ContextualRecallMetric       │ 上下文召回率             │
│ depth           │ 保留自建 Judge                │ DeepEval 无直接等价指标   │
│ key_concepts    │ 保留自建 Judge                │ DeepEval 无直接等价指标   │
│ format          │ 保留自建 Judge                │ DeepEval 无直接等价指标   │
│ (新增)          │ ToolCallAccuracy             │ 工具调用准确率           │
└─────────────────┴──────────────────────────────┴─────────────────────────┘
"""
# ⚠️ 必须在所有导入之前设置 DeepEval 环境变量，因为 DeepEval 在导入时读取这些配置
import os
os.environ["DEEPEVAL_DISABLE_TIMEOUTS"] = "false"  # 不禁用超时，避免无限卡住
os.environ["DEEPEVAL_PER_TASK_TIMEOUT_SECONDS"] = "600"  # 10 分钟超时（DashScope 慢速 API）
os.environ["DEEPEVAL_RETRY_MAX_ATTEMPTS"] = "1"  # 不重试，避免叠加等待
os.environ.setdefault("PYTHONIOENCODING", "utf-8")  # 修复 Windows GBK 编码问题

import json  # 序列化评估结果
import statistics  # 多次采样取中位数
from typing import Any, Dict, List, Optional  # 类型标注

from core.utils.config import config  # 全局配置（复用 Judge 配置）
from core.constants import DIMENSION_NAMES  # 维度中英文名映射（共享常量）


class DeepEvalError(RuntimeError):
    """DeepEval 评估失败时抛出的异常。"""


class DeepEvalAdapter:
    """DeepEval 指标适配器：复用现有 Judge 配置，提供 DeepEval 指标评估。

    使用示例：
        adapter = DeepEvalAdapter()
        result = adapter.evaluate_quality(
            question="请总结这篇论文",
            answer="这是一篇关于...",
            reference="论文原文...",
            tool_calls=[{"name": "read_file", ...}],
            expected_tools=["read", "write"],
        )
    """

    # DeepEval 指标阈值（可配置）
    DEFAULT_THRESHOLDS = {
        "answer_relevancy": 0.7,      # 答案相关性阈值
        "faithfulness": 0.7,          # 忠实度阈值
        "hallucination": 0.8,         # 幻觉检测阈值（新版：1=通过，0=失败，阈值是最低通过分数）
        "contextual_recall": 0.7,     # 上下文召回率阈值
        "tool_call_accuracy": 0.8,    # 工具调用准确率阈值
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """初始化 DeepEval 适配器：复用 Judge 配置（可覆盖）。

        Args:
            base_url: 模型服务地址（默认复用 JUDGE_BASE_URL）
            api_key: API Key（默认复用 JUDGE_API_KEY）
            model: 模型名称（优先 DEEPEVAL_MODEL，未配置时回退 JUDGE_MODEL）
        """
        self.base_url = base_url or config.judge_base_url or ""
        self.api_key = api_key or config.judge_api_key or ""
        # 评估模型与 Judge 模型分离：第三方指标需严格 JSON 服从性，
        # 选型不受 Judge 历史基线约束；DEEPEVAL_MODEL 未配置时保持旧行为
        self.model = model or config.deepeval_model or config.judge_model or ""

        # 检查必填配置
        if not self.base_url or not self.api_key or not self.model:
            raise DeepEvalError(
                "DeepEval 需要模型配置。请在 config/.env 中填写：\n"
                "JUDGE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1\n"
                "JUDGE_API_KEY=sk-你的密钥\n"
                "DEEPEVAL_MODEL=严格JSON输出服从性好的模型（可选，未配置时回退 JUDGE_MODEL）"
            )

        # 导入 DeepEval（延迟导入，避免未安装时导入报错）
        try:
            from deepeval.metrics import (
                AnswerRelevancyMetric,
                FaithfulnessMetric,
                HallucinationMetric,
                ContextualRecallMetric,
            )
            from deepeval.test_case import LLMTestCase
            from deepeval.models import OpenAIModel

            self._AnswerRelevancyMetric = AnswerRelevancyMetric
            self._FaithfulnessMetric = FaithfulnessMetric
            self._HallucinationMetric = HallucinationMetric
            self._ContextualRecallMetric = ContextualRecallMetric
            self._LLMTestCase = LLMTestCase
            
            # 创建自定义模型实例（使用 DashScope/阿里云）
            self._model_instance = OpenAIModel(
                model=self.model,
                base_url=self.base_url,
                api_key=self.api_key,
            )
        except ImportError as e:
            raise DeepEvalError(
                f"DeepEval 未安装：{e}。请执行 pip install deepeval"
            )

    def evaluate_quality(
        self,
        question: str,
        answer: str,
        reference: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        expected_tools: Optional[List[str]] = None,
        n_runs: int = 1,  # 默认 1 次（避免 DashScope API 超时），需要稳定性时可增至 3
    ) -> Dict[str, Any]:
        """执行 DeepEval 质量评估，返回与自建 Judge 兼容的结果格式。

        Args:
            question: 用户问题
            answer: Agent 回答内容
            reference: 参考原文（如论文 PDF 提取文本）
            tool_calls: 工具调用列表（用于 ToolCallAccuracy 评估）
            expected_tools: 期望的工具关键字列表（如 ["read", "write"]）
            n_runs: 多次采样次数（默认 1 次避免 DashScope API 超时；>1 时各维度取中位数）

        Returns:
            与自建 Judge 兼容的评分结果字典，包含：
            - relevance: 相关性分数（0-1 映射到 1-5）
            - faithfulness: 忠实度分数（0-1 映射到 1-5）
            - data_accuracy: 数据准确性分数（幻觉率反向映射）
            - completeness: 完整性分数（上下文召回率映射）
            - depth: 分析深度（保留自建 Judge 逻辑，暂用默认值）
            - key_concepts: 关键概念覆盖（保留自建 Judge 逻辑，暂用默认值）
            - format: 格式评分（保留自建 Judge 逻辑，暂用默认值）
            - average: 平均分
            - tool_call_accuracy: 工具调用准确率（新增指标）
            - _judge_model: 使用的模型名称
            - _sample_count: 采样次数
            - _content_length: 内容长度
            - _sampled_length: 采样长度
            - _content_source: 内容来源
            - _reference_length: 参考原文长度
            - _all_runs: 所有轮次的完整结果
        """
        # 构建测试用例
        test_case = self._LLMTestCase(
            input=question,
            actual_output=answer,
            expected_output=reference if reference else answer,  # ContextualRecallMetric 需要 expected_output
            context=[reference] if reference else None,  # HallucinationMetric 需要 context
            retrieval_context=[reference] if reference else None,
        )

        # 定义 DeepEval 指标
        metrics = self._build_metrics(reference)

        # 多次采样评估
        all_runs = []
        all_reasons = []  # 收集每轮的评分理由
        dimension_scores = {}

        for run_idx in range(n_runs):
            run_result = self._run_evaluation(test_case, metrics)
            
            # 评估失败，跳过评分
            if run_result is None:
                print(f"[DeepEval] 第 {run_idx + 1} 次评估失败，跳过 Judge 评分")
                return None
            
            run_scores = run_result.get("scores", {})
            run_reasons = run_result.get("reasons", {})
            all_runs.append(run_scores)
            all_reasons.append(run_reasons)

            # 收集每个维度的分数
            for dim in ["relevance", "faithfulness", "data_accuracy", "completeness"]:
                if dim in run_scores:
                    dimension_scores.setdefault(dim, []).append(run_scores[dim])

        # 计算各维度中位数
        median_scores = {}
        for dim, scores_list in dimension_scores.items():
            median_scores[dim] = statistics.median(scores_list)

        # 保留自建 Judge 的维度（暂用默认值，后续可增强）
        median_scores["depth"] = 3.5  # 默认中等深度
        median_scores["key_concepts"] = 3.5  # 默认中等覆盖
        median_scores["format"] = 4.0  # 默认格式良好
        median_scores["instruction_follow"] = 4.0  # 默认指令遵循良好

        # 计算平均分
        from core.scoring import compute_average
        avg_dimensions = ["relevance", "faithfulness", "completeness", "format",
                         "data_accuracy", "depth", "key_concepts", "instruction_follow"]
        median_scores["average"] = compute_average(median_scores, avg_dimensions)

        # 合并所有轮次的评分理由（取最后一轮的理由作为代表）
        final_reasons = all_reasons[-1] if all_reasons else {}

        # 构建最终结果（与自建 Judge 格式兼容）
        result = {
            **median_scores,
            "_judge_model": self.model,
            "_sample_count": n_runs,
            "_content_length": len(answer),
            "_sampled_length": len(answer[:12000]),
            "_content_source": "DeepEval",
            "_reference_length": len(reference) if reference else 0,
            "_all_runs": all_runs,
            "_reasons": final_reasons,  # 新增：各维度评分理由
        }

        # 如果有工具调用数据，添加 ToolCallAccuracy
        if tool_calls and expected_tools:
            tool_accuracy = self._evaluate_tool_calls(tool_calls, expected_tools)
            result["tool_call_accuracy"] = tool_accuracy

        return result

    def _build_metrics(self, reference: str) -> List:
        """构建 DeepEval 指标列表。

        Args:
            reference: 参考原文（用于 FaithfulnessMetric 和 ContextualRecallMetric）

        Returns:
            DeepEval 指标列表
        """
        metrics = []

        # 答案相关性
        metrics.append(
            self._AnswerRelevancyMetric(
                threshold=self.DEFAULT_THRESHOLDS["answer_relevancy"],
                model=self._model_instance,
            )
        )

        # 忠实度（需要参考原文）
        if reference:
            metrics.append(
                self._FaithfulnessMetric(
                    threshold=self.DEFAULT_THRESHOLDS["faithfulness"],
                    model=self._model_instance,
                )
            )

            # 上下文召回率（完整性）
            metrics.append(
                self._ContextualRecallMetric(
                    threshold=self.DEFAULT_THRESHOLDS["contextual_recall"],
                    model=self._model_instance,
                )
            )

        # 幻觉检测
        metrics.append(
            self._HallucinationMetric(
                threshold=self.DEFAULT_THRESHOLDS["hallucination"],
                model=self._model_instance,
            )
        )

        return metrics

    def _run_evaluation(self, test_case, metrics: List, max_retries: int = 2) -> Optional[Dict[str, Any]]:
        """执行单次评估，返回各维度分数和评分理由。

        Args:
            test_case: LLMTestCase 测试用例
            metrics: DeepEval 指标列表
            max_retries: 最大重试次数（默认 2 次）

        Returns:
            包含 scores（各维度分数）和 reasons（各维度评分理由）的字典，
            或 None（评估失败时）
        """
        from deepeval import evaluate
        import time

        for attempt in range(max_retries + 1):
            try:
                # 执行评估
                results = evaluate([test_case], metrics)

                # 提取分数和理由（DeepEval 4.x 结构：results.test_results[0].metrics_data）
                scores = {}
                reasons = {}
                if results.test_results:
                    test_result = results.test_results[0]
                    if hasattr(test_result, 'metrics_data'):
                        for metric_data in test_result.metrics_data:
                            metric_name = metric_data.name
                            score = metric_data.score if hasattr(metric_data, 'score') else 0.0
                            reason = metric_data.reason if hasattr(metric_data, 'reason') else ""

                            # 映射到自建 Judge 维度
                            if "Answer Relevancy" in metric_name:
                                scores["relevance"] = self._scale_01_to_15(score)
                                reasons["relevance"] = reason
                            elif "Faithfulness" in metric_name:
                                scores["faithfulness"] = self._scale_01_to_15(score)
                                reasons["faithfulness"] = reason
                            elif "Hallucination" in metric_name:
                                # 新版 HallucinationMetric: 1=通过，0=失败，无需反向映射
                                scores["data_accuracy"] = self._scale_01_to_15(score)
                                reasons["data_accuracy"] = reason
                            elif "Contextual Recall" in metric_name:
                                scores["completeness"] = self._scale_01_to_15(score)
                                reasons["completeness"] = reason

                # 翻译理由为中文并扩充为详细分析
                translated_reasons = self._translate_reasons(reasons)
                return {"scores": scores, "reasons": translated_reasons}
            except Exception as e:
                if attempt < max_retries:
                    # 重试前等待 5 秒
                    wait_time = 5
                    print(f"[DeepEval] 第 {attempt + 1} 次评估失败，{wait_time}秒后重试：{e}")
                    time.sleep(wait_time)
                else:
                    # 最后一次仍失败，跳过评分
                    print(f"[DeepEval] 评估失败（已重试{max_retries}次），跳过评分：{e}")
                    return None

    def _translate_reasons(self, reasons: Dict[str, str]) -> Dict[str, str]:
        """将 DeepEval 英文评分理由翻译为中文，并扩充为详细分析。

        Args:
            reasons: 英文理由字典 {维度名: 英文理由}

        Returns:
            中文理由字典 {维度名: 中文理由}
        """
        if not reasons:
            return reasons

        try:
            from openai import OpenAI

            client = OpenAI(
                base_url=config.judge_base_url,
                api_key=config.judge_api_key,
            )

            # 构建翻译请求
            dimension_names = {
                k: v for k, v in DIMENSION_NAMES.items()
                if k in ("relevance", "faithfulness", "completeness", "data_accuracy")
            }

            translated = {}
            for dim, reason in reasons.items():
                dim_cn = dimension_names.get(dim, dim)
                prompt = f"""请将以下 AI 评估理由从英文翻译为中文，并扩充为详细分析（包含具体例证）。

维度：{dim_cn}
原始理由：{reason}

要求：
1. 准确翻译原意
2. 扩充为 2-3 句话，包含具体的评分依据
3. 引用文档中的具体内容作为例证
4. 使用专业、客观的评估语言

请直接输出中文理由，不要添加额外说明。"""

                response = client.chat.completions.create(
                    model=config.judge_model,
                    messages=[
                        {"role": "system", "content": "你是专业的 AI 评估分析师，擅长将评估理由翻译为中文并提供详细分析。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=500,
                )

                translated[dim] = response.choices[0].message.content.strip()

            return translated

        except Exception as e:
            print(f"[DeepEval] 理由翻译失败，保留英文原文：{e}")
            return reasons  # 翻译失败时保留原文

    def _evaluate_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        expected_tools: List[str],
    ) -> float:
        """评估工具调用准确率。

        Args:
            tool_calls: 实际工具调用列表
            expected_tools: 期望的工具关键字列表

        Returns:
            工具调用准确率（0-1）
        """
        if not tool_calls or not expected_tools:
            return 0.0

        # 提取实际工具名称
        actual_tools = [t.get("name", "").lower() for t in tool_calls]

        # 检查每个期望工具是否被调用
        matched = 0
        for expected in expected_tools:
            for actual in actual_tools:
                if expected.lower() in actual:
                    matched += 1
                    break

        return matched / len(expected_tools)

    @staticmethod
    def _scale_01_to_15(score_01: float) -> float:
        """将 0-1 范围的分数映射到 1-5 范围。

        Args:
            score_01: 0-1 范围的分数

        Returns:
            1-5 范围的分数（保留 1 位小数）
        """
        return round(1.0 + score_01 * 4.0, 1)

    @staticmethod
    def _scale_15_to_01(score_15: float) -> float:
        """将 1-5 范围的分数映射到 0-1 范围（反向操作）。

        Args:
            score_15: 1-5 范围的分数

        Returns:
            0-1 范围的分数
        """
        return max(0.0, min(1.0, (score_15 - 1.0) / 4.0))


# 全局单例（惰性初始化，避免未配置时导入报错）
_deepeval_adapter: Optional[DeepEvalAdapter] = None


def get_deepeval_adapter() -> DeepEvalAdapter:
    """获取 DeepEval 适配器单例。"""
    global _deepeval_adapter
    if _deepeval_adapter is None:
        _deepeval_adapter = DeepEvalAdapter()
    return _deepeval_adapter
