"""DeepEval 路由编排契约用例：fake backend 注入，离线验证混合评估机制。

覆盖 dimension_registry + evaluation_orchestrator 的全部编排语义：
开关语义、按表分发、缺维/整体失败回退、Judge 调用量减半、配置校验，
以及与 score_sink 收口链的集成（编排结果 → junit properties）。

本用例不需要 deepeval 包与任何凭证——后端全部为注入的假对象，
真实 DeepEvalAdapter 接线验证随 rag 环境用例（凭证就位后）落地。
"""
import json  # 校验 dimensions 属性序列化形态

import pytest  # pytest 标记与断言

from core.evaluators.dimension_registry import (
    RegistryError,
    resolve_registry,
)
from core.evaluators.evaluation_orchestrator import (
    EvaluationError,
    EvaluationOrchestrator,
)

# judge 路由维固定标记分（3.0），deepeval 路由维固定标记分（5.0），
# 两套可区分标记使"分数来自哪个后端"直接可断言
JUDGE_MARK = 3.0
DEEPEVAL_MARK = 5.0

JUDGE_SUBJECTIVE = {
    "relevance": JUDGE_MARK, "completeness": JUDGE_MARK, "depth": JUDGE_MARK,
    "instruction_follow": JUDGE_MARK, "format": JUDGE_MARK, "key_concepts": JUDGE_MARK,
}
DEEPEVAL_OUTPUT = {
    "relevance": DEEPEVAL_MARK, "faithfulness": DEEPEVAL_MARK,
    "data_accuracy": DEEPEVAL_MARK, "completeness": DEEPEVAL_MARK,
    "tool_call_accuracy": DEEPEVAL_MARK,  # 词表外扩展指标，模拟 adapter 新增维度
    "_content_source": "DeepEval",
}


class RecordingJudge:
    """假 Judge 后端：返回主观 6 维标记分并记录调用次数（验证调用量减半）。"""

    def __init__(self, scores=None):
        self.scores = dict(scores or JUDGE_SUBJECTIVE)
        self.calls = 0

    def evaluate(self, question, answer, expected_points=None):
        self.calls += 1
        return dict(self.scores)


class FakeDeepEval:
    """假 DeepEval adapter：按 mode 返回分数 / None（重试耗尽）/ 抛异常。

    额外关键字参数（tool_calls 等）记录到 last_kwargs 供透传契约断言。
    """

    def __init__(self, mode="ok", scores=None):
        self.mode = mode
        self.scores = dict(scores or DEEPEVAL_OUTPUT)
        self.calls = 0
        self.last_kwargs = None  # 最近一次透传的额外关键字参数

    def evaluate_quality(self, question, answer, reference="", **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self.mode == "none":
            return None
        if self.mode == "raise":
            raise RuntimeError("fake deepeval down")
        return dict(self.scores)


pytestmark = pytest.mark.offline


class TestRoutingSwitch:
    """USE_DEEPEVAL 开关语义：默认纯 Judge，与 A′-4 收口链行为一致。"""

    def test_switch_off_pure_judge(self):
        judge, deepeval = RecordingJudge(), FakeDeepEval()
        result = EvaluationOrchestrator(
            judge_client=judge, deepeval_adapter=deepeval, use_deepeval=False
        ).evaluate("q", "a")
        assert deepeval.calls == 0  # 开关关闭绝不触碰 deepeval
        assert all(v == JUDGE_MARK for k, v in result.items() if not k.startswith("_") and isinstance(v, float) and k != "average")
        assert set(result["_evaluation_backend"].values()) == {"judge"}

    def test_no_backend_raises(self):
        with pytest.raises(EvaluationError):
            EvaluationOrchestrator().evaluate("q", "a")


class TestHybridRouting:
    """按注册表分发：deepeval 维优先、judge 维保留、缺维/失败回退。"""

    def test_deepeval_dims_win_and_judge_once(self):
        judge, deepeval = RecordingJudge(), FakeDeepEval()
        result = EvaluationOrchestrator(
            judge_client=judge, deepeval_adapter=deepeval, use_deepeval=True
        ).evaluate("q", "a")
        assert deepeval.calls == 1 and judge.calls == 1  # Judge 调用量 2→1
        backend = result["_evaluation_backend"]
        assert backend["relevance"] == "deepeval"  # 重叠维由 deepeval 胜出
        assert backend["depth"] == "judge"  # 业务定制维必须 judge 实测
        assert backend["tool_call_accuracy"] == "deepeval"  # 词表外扩展维如实收口
        assert result["relevance"] == DEEPEVAL_MARK
        assert result["depth"] == JUDGE_MARK

    def test_deepeval_missing_dim_falls_back_per_dim(self):
        partial = {"relevance": DEEPEVAL_MARK, "faithfulness": DEEPEVAL_MARK}
        judge, deepeval = RecordingJudge(), FakeDeepEval(scores=partial)
        result = EvaluationOrchestrator(
            judge_client=judge, deepeval_adapter=deepeval, use_deepeval=True
        ).evaluate("q", "a")
        assert result["_evaluation_backend"]["completeness"] == "judge"  # 缺维回补

    # parametrize id 保持 ASCII：非 ASCII ids 会被 pytest asciiescape，
    # 导致 nodeid 不稳定且 selection 失败时整个子进程 exit 4 连坐全部用例
    @pytest.mark.parametrize("mode", ["none", "raise"])
    def test_deepeval_total_failure_falls_back_to_judge(self, mode):
        judge, deepeval = RecordingJudge(), FakeDeepEval(mode=mode)
        result = EvaluationOrchestrator(
            judge_client=judge, deepeval_adapter=deepeval, use_deepeval=True
        ).evaluate("q", "a")
        assert result["_evaluation_backend"]["relevance"] == "judge"  # 整体回退
        assert "_deepeval_fallback" in result  # 回退必须显式标注，不静默

    def test_deepeval_kwargs_passthrough(self):
        # 用例直连路径（test_paper_common deepeval 形态）依赖 tool_calls/n_runs
        # 透传 adapter：编排器不解释含义，原样转发
        judge, deepeval = RecordingJudge(), FakeDeepEval()
        EvaluationOrchestrator(
            judge_client=judge, deepeval_adapter=deepeval, use_deepeval=True
        ).evaluate("q", "a", deepeval_kwargs={
            "tool_calls": [{"name": "read"}], "expected_tools": ["read", "write"], "n_runs": 3,
        })
        assert deepeval.last_kwargs == {
            "tool_calls": [{"name": "read"}], "expected_tools": ["read", "write"], "n_runs": 3,
        }


class TestRegistryConfig:
    """路由表配置驱动：传参覆盖默认、非法值 fail-fast。"""

    def test_explicit_routing_override(self):
        judge, deepeval = RecordingJudge(), FakeDeepEval()
        result = EvaluationOrchestrator(
            judge_client=judge, deepeval_adapter=deepeval, use_deepeval=True,
            dimensions={"relevance": "judge"},  # 用例显式把重叠维改回 judge
        ).evaluate("q", "a")
        assert result["relevance"] == JUDGE_MARK

    def test_invalid_backend_rejected(self):
        with pytest.raises(RegistryError):
            resolve_registry({"relevance": "langfuse"})


class TestScoreSinkIntegration:
    """编排结果直接喂 score_sink：收口链对混合模式零改造兼容。"""

    def test_orchestrated_result_scores_through_sink(self, score_sink, request):
        judge, deepeval = RecordingJudge(), FakeDeepEval()
        result = EvaluationOrchestrator(
            judge_client=judge, deepeval_adapter=deepeval, use_deepeval=True
        ).evaluate("q", "a")
        score = score_sink(result)
        # ALL_JUDGE_DIMENSIONS 7 维：5+5+5(deepeval) + 3+3+3+3(judge) = 27/7
        # → compute_average 先舍 1 位小数得 3.9，再 ÷5 归一得 0.78
        assert score == 0.78
        props = dict(request.node.user_properties)
        dims = json.loads(props["dimensions"])
        assert "average" not in dims  # 元数据键不混入 dimensions
        assert not any(k.startswith("_") for k in dims)  # 后端映射不入维度 JSON


class TestReasonPassthrough:
    """评语透传契约：混合模式下 _all_runs/details 不丢，且按分数来源对齐。

    背景：Langfuse「Judge 评分」节点与 judge.json 落盘的理由均读
    _all_runs[0].details；编排器曾只合并分数导致六个主观维理由恒为空串。
    """

    def test_hybrid_reasons_aligned_with_score_source(self):
        # Judge 对 relevance 写了评语，但该维分数被 DeepEval 覆盖——
        # 评语必须改用 adapter 的，防止分数与解释来自不同裁判
        judge = RecordingJudge(scores={
            **JUDGE_SUBJECTIVE,
            "details": [
                {"dimension": "relevance", "reason": "Judge 的相关性评语"},
                {"dimension": "depth", "reason": "Judge 的深度评语"},
            ],
            "summary": "整体评价",
        })
        deepeval = FakeDeepEval(scores={
            "scores": {"relevance": DEEPEVAL_MARK, "faithfulness": DEEPEVAL_MARK},
            "reasons": {"relevance": "DeepEval 的相关性评语"},
        })
        result = EvaluationOrchestrator(
            judge_client=judge, deepeval_adapter=deepeval, use_deepeval=True
        ).evaluate("q", "a")
        assert result["_evaluation_backend"]["relevance"] == "deepeval"  # 前提：分数已覆盖
        reason_map = {d["dimension"]: d["reason"] for d in result["_all_runs"][0]["details"]}
        assert reason_map["relevance"] == "DeepEval 的相关性评语"  # 随分数来源切换
        assert reason_map["depth"] == "Judge 的深度评语"  # judge 路由维用 judge 评语
        assert result["_all_runs"][0]["summary"] == "整体评价"

    def test_reasons_from_real_adapter_flat_shape(self):
        # 真实 adapter 最终形态：扁平分数 dict + 理由放下划线键 "_reasons"；
        # 只认包装形态 "reasons" 会使 deepeval 维评语真实链路半截丢失
        judge = RecordingJudge(scores={
            **JUDGE_SUBJECTIVE,
            "details": [{"dimension": "relevance", "reason": "Judge 评语（分数已被覆盖，不应采用）"}],
        })
        deepeval = FakeDeepEval(scores={
            "relevance": DEEPEVAL_MARK, "faithfulness": DEEPEVAL_MARK,
            "_reasons": {"relevance": "DeepEval 的相关性评语", "faithfulness": "DeepEval 的忠实度评语"},
        })
        result = EvaluationOrchestrator(
            judge_client=judge, deepeval_adapter=deepeval, use_deepeval=True
        ).evaluate("q", "a")
        reason_map = {d["dimension"]: d["reason"] for d in result["_all_runs"][0]["details"]}
        assert reason_map["relevance"] == "DeepEval 的相关性评语"
        assert reason_map["faithfulness"] == "DeepEval 的忠实度评语"

    def test_pure_judge_details_kept(self):
        # 纯 Judge 路径（USE_DEEPEVAL 关）同样要带出 details/summary
        judge = RecordingJudge(scores={
            **JUDGE_SUBJECTIVE,
            "details": [{"dimension": "depth", "reason": "Judge 的深度评语"}],
            "summary": "整体评价",
        })
        result = EvaluationOrchestrator(
            judge_client=judge, use_deepeval=False
        ).evaluate("q", "a")
        details = result["_all_runs"][0]["details"]
        assert {d["dimension"]: d["reason"] for d in details}["depth"] == "Judge 的深度评语"

    def test_no_details_no_fake_all_runs(self):
        # 后端未产出评语时不伪造 _all_runs（消费方保持现有降级行为）
        judge, deepeval = RecordingJudge(), FakeDeepEval()
        result = EvaluationOrchestrator(
            judge_client=judge, deepeval_adapter=deepeval, use_deepeval=True
        ).evaluate("q", "a")
        assert "_all_runs" not in result

    def test_all_runs_not_leaking_into_sink(self, score_sink, request):
        # _all_runs 是下划线元数据键，不得混入 junit dimensions 属性
        judge = RecordingJudge(scores={
            **JUDGE_SUBJECTIVE,
            "details": [{"dimension": "depth", "reason": "x"}],
            "summary": "s",
        })
        result = EvaluationOrchestrator(
            judge_client=judge, use_deepeval=False
        ).evaluate("q", "a")
        assert "_all_runs" in result  # 评语已带出
        score_sink(result)
        dims = json.loads(dict(request.node.user_properties)["dimensions"])
        assert not any(k.startswith("_") for k in dims)
