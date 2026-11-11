"""评估编排器：按 dimension_registry 路由表分发后端，合并为统一 judge_result。

混合模式落地（第三方指标优先 + 自建 Judge 兜底/不可替代维度）：
- USE_DEEPEVAL 关闭（默认）→ 纯 Judge 路径，与 A′-4 收口链行为完全一致；
- 开启 → deepeval 路由维取 DeepEval 分数，judge 路由维合并一次 JudgeClient
  .evaluate 调用（调用量 2→1，约降一半——本编排的核心收益点）；缺维用 judge
  同维补全，deepeval 整体失败（返回 None / 抛异常）整体回退 judge 并在
  _evaluation_backend 元数据中显式标注，不静默。
- faithfulness 例外：Judge 侧走 Claim-Level 独立通道 evaluate_faithfulness
  （签名与主观 6 维不同，无法并入合并调用），本编排单后端调用不合并，
  真实接线验证随 rag 环境用例落地。

后端全部构造注入（契约测试用 fake backend 零凭证离线跑），本模块不
import deepeval 包——对 adapter 的依赖由调用方传入实例承接。
"""
import os  # 读取 USE_DEEPEVAL 开关
from typing import Any, Dict, List, Optional  # 类型标注

from core.constants import SUBJECTIVE_DIMENSIONS  # 主观 6 维词表
from core.evaluators.dimension_registry import (  # 路由表
    backend_for,
    resolve_registry,
)


class EvaluationError(RuntimeError):
    """编排失败（所有可用后端均未产出任何维度分数）。"""


def _extract_scores(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从后端返回中取维度分数子字典。

    deepeval_adapter 返回 {"relevance": 4.0, ...} 平铺 dict；兼容个别后端
    返回 {"scores": {...}} 包装形态（fake backend 同构即可）。
    """
    if not result:
        return {}
    scores = dict(result)
    if "scores" in scores and isinstance(scores["scores"], dict):
        scores = dict(scores["scores"])
    # 剔除元数据键与非法分数值（float/int 之外的评分词表键不可能是维度分数）
    return {
        k: v for k, v in scores.items()
        if not k.startswith("_") and isinstance(v, (int, float))
    }


class EvaluationOrchestrator:
    """评估编排器：judge_client / deepeval_adapter 注入式后端 + 路由表分发。

    使用示例：
        orch = EvaluationOrchestrator(judge_client=judge, deepeval_adapter=adapter)
        result = orch.evaluate(question, answer, reference=ref)
        score = score_sink(result, threshold=0.75)
    """

    def __init__(
        self,
        judge_client: Any = None,
        deepeval_adapter: Any = None,
        dimensions: Optional[Dict[str, str]] = None,
        use_deepeval: Optional[bool] = None,
    ) -> None:
        """注入后端；路由表与开关缺省按环境/默认表解析。

        Args:
            judge_client: 实现 evaluate(question, answer, expected_points) 的对象
            deepeval_adapter: 实现 evaluate_quality(...) 的对象（失败返回 None）
            dimensions: 显式路由表，覆盖默认注册表
            use_deepeval: 开关显式传参；None 时读 USE_DEEPEVAL 环境变量；
                开了但没有 deepeval 后端 → 按未开启处理（不视为错误）
        """
        self._judge = judge_client
        self._deepeval = deepeval_adapter
        self._registry = resolve_registry(dimensions)
        if use_deepeval is None:
            use_deepeval = os.getenv("USE_DEEPEVAL", "false").lower() == "true"
        self._use_deepeval = bool(use_deepeval and deepeval_adapter is not None)

    def evaluate(
        self,
        question: str,
        answer: str,
        reference: str = "",
        expected_points: Optional[List[str]] = None,
        deepeval_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """按路由表评估并合并为 judge_result 形态（5 分制平铺 dict）。

        Args:
            deepeval_kwargs: 透传给 adapter.evaluate_quality 的额外关键字参数
                （如 tool_calls/expected_tools/n_runs）；本编排不解释其含义，
                缺维时由路由分发逻辑自然回退（无该维产出 → 不参与 deepeval 维优先）。

        Returns:
            合并结果 dict：维度分数 + 非下划线键（average）+ 元数据
            （_evaluation_backend / _deepeval_fallback 等，score_sink 会跳过）。

        Raises:
            EvaluationError: 所有可用后端均未产出任何维度分数。
        """
        merged: Dict[str, Any] = {}
        backend_map: Dict[str, str] = {}

        # judge 主观调用只做一次，deepeval 缺维补全与 judge 路由维共用同一份
        judge_scores: Dict[str, Any] = {}
        judge_raw: Dict[str, Any] = {}
        if self._judge is not None:
            try:
                judge_raw = self._judge.evaluate(question, answer, expected_points) or {}
                judge_scores = _extract_scores(judge_raw)
            except Exception as e:  # judge 失败不立即抛出，deepeval 可能兜住
                print(f"[orchestrator] Judge 主观评估失败：{e}")

        deepeval_scores: Dict[str, Any] = {}
        deepeval_reasons: Dict[str, Any] = {}
        deepeval_failed = False
        if self._use_deepeval:
            try:
                raw = self._deepeval.evaluate_quality(
                    question=question, answer=answer, reference=reference,
                    **(deepeval_kwargs or {}),
                )
                if raw is None:  # adapter 重试耗尽的显式失败语义
                    deepeval_failed = True
                else:
                    deepeval_scores = _extract_scores(raw)
                    # 理由两种形态都要收：真实 adapter 最终形态放下划线键
                    # "_reasons"，_run_evaluation 中间层包装形态放 "reasons"，
                    # 只认其一会导致混合模式评语半截失效（2026-11-11）
                    if isinstance(raw, dict):
                        _r = raw.get("reasons") or raw.get("_reasons")
                        if isinstance(_r, dict):
                            deepeval_reasons = dict(_r)
            except Exception as e:
                deepeval_failed = True
                print(f"[orchestrator] DeepEval 评估异常：{e}")

        # 路由分发：deepeval 维优先，缺维回退 judge；整体失败回退全 judge
        dims_in_play = set(self._registry.keys()) | set(judge_scores) | set(deepeval_scores)
        for dim in dims_in_play:
            backend = backend_for(self._registry, dim)
            if (
                self._use_deepeval
                and backend == "deepeval"
                and not deepeval_failed
                and dim in deepeval_scores
            ):
                merged[dim] = deepeval_scores[dim]
                backend_map[dim] = "deepeval"
            elif dim in judge_scores:
                merged[dim] = judge_scores[dim]
                backend_map[dim] = "judge"
        # 词表外但仅 deepeval 产出的维（如 tool_call_accuracy 扩展指标）如实收口
        for dim, score in deepeval_scores.items():
            if dim not in merged and not deepeval_failed:
                merged[dim] = score
                backend_map[dim] = "deepeval"

        if not merged:
            raise EvaluationError("编排失败：judge 与 deepeval 均未产出任何维度分数")

        from core.scoring import compute_average  # 延迟导入避免循环

        avg_dimensions = [d for d in SUBJECTIVE_DIMENSIONS if d in merged] or None
        merged["average"] = compute_average(merged, avg_dimensions)
        merged["_evaluation_backend"] = backend_map
        if deepeval_failed:
            merged["_deepeval_fallback"] = "deepeval 整体失败，已回退全 Judge"
        # 评语与元信息透传：消费方（report_trace / build_optimized_scores）按
        # 纯 Judge 路径的 _all_runs 形态读 details/summary，此前 _extract_scores
        # 只收数值，混合模式下评语与裁判 token 开销全部静默丢失（2026-11-11）。
        # 评语按分数来源对齐：Judge 打的分用 Judge 的评语，DeepEval 打的分用
        # adapter（已中文化）的评语，防止评语与被覆盖的分数错位。
        details: List[Dict[str, str]] = []
        for d in (judge_raw.get("details") or []):
            if isinstance(d, dict) and backend_map.get(d.get("dimension")) == "judge":
                details.append({"dimension": d["dimension"], "reason": d.get("reason", "")})
        for dim, reason in deepeval_reasons.items():
            if backend_map.get(dim) == "deepeval" and reason:
                details.append({"dimension": dim, "reason": str(reason)})
        if details or judge_raw.get("summary"):
            merged["_all_runs"] = [
                {"details": details, "summary": str(judge_raw.get("summary", ""))}
            ]
        if judge_raw.get("_judge_usage"):
            merged["_judge_usage"] = judge_raw["_judge_usage"]
        _judge_model = getattr(self._judge, "model", "") if self._judge is not None else ""
        if _judge_model:
            merged["_judge_model"] = str(_judge_model)
        return merged
