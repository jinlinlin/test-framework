"""文献解读测试共享代码：常量、fixtures、辅助函数。

供同包模块导入使用（依赖方与资源清单详见同目录 README.md）：
- test_single_round.py（INT-001~003 单轮能力）
- test_interpret.py（INT-004 E2E 完整对话流）
- test_ooc_refusal.py（INT-005 OOC 拒答）
"""
import json  # 序列化 Agent trace 产物
import re  # 解析 Markdown 标题
import statistics  # Judge 多次采样取中位数
import threading  # Judge 异步化：后台线程执行，不阻塞用例通过
from datetime import datetime  # 产物文件名时间戳
from pathlib import Path  # 产物路径处理
from typing import Any, Dict, List, Optional, Tuple  # 类型标注

from core.assertions.assert_tools import (  # 断言工具
    AssertReporter,
    assert_llm_called,
    assert_md_sections_semantic,
    assert_retriever_executed,
    assert_sse_complete,
    assert_tool_called,
    extract_ai_final_response,
    extract_first_chunk_time,
    extract_generated_document,
    extract_new_generated_document,
    extract_pdf_text,
    extract_str_replace_content,
    extract_str_replace_edits,
    extract_tool_calls_from_messages,
    extract_token_usage,
    generate_agent_summary,
    summarize_agent_trace,
)
from core.utils.config import config  # 全局配置
from core.utils.golden_dataset import find_golden_samples, warn_golden_miss  # 黄金集样本筛选与未命中告警
from core.constants import DIMENSION_NAMES, ALL_JUDGE_DIMENSIONS  # 维度名称映射、维度列表
from core.scoring import compute_average, get_dimension_scores  # 平均分计算
from core.clients.judge_client import JudgeClient, JudgeError  # LLM-as-Judge 裁判模型
from core.clients.deepeval_adapter import DeepEvalAdapter, DeepEvalError  # DeepEval 质量评估
from core.clients.langfuse_integration import build_faithfulness_reason  # 忠实度理由合成（落盘与 Langfuse 上报同源）
from core.clients.sse_client import (  # SSE 客户端与异常类型
    SseClient, SseError,
    PAPER_CONVERSATIONS_CREATE_PATH, PAPER_CONVERSATIONS_PATH,  # 接口路径（单一事实源，re-export 给同包用例）
)

# ── 论文场景常量 ──
PAPER_SOURCE = "paper.interpret"
PAPER_TASK_TYPE = "interpret"
PAPER_EXPECTED_INTENT = "academic-summary-agent"
# 接口路径常量已收敛至 core.clients.sse_client（被测系统契约单一事实源），此处 re-export（见头部导入）
PAPER_TIMEOUT = 300.0

# 测试后清理策略
CLEANUP_AFTER_TEST = config.cleanup_after_test  # 直接复用 Config 属性（此前此处与 robust 各自重算布尔值）

# ── 黄金评测集加载 ──
GOLDEN_DATASET_FILENAME = "paper_golden_v1.json"


def load_golden_samples(pdf_path: str = None, question: str = None) -> list:
    """从黄金评测集 JSON 加载匹配样本。

    读取、路径归一化与匹配规则全部走 core/utils/golden_dataset.py 的
    find_golden_samples（单一事实源）——Langfuse 上报侧也调同一函数，
    保证报告里的锚点必然等于 Judge 实际用的那条样本。

    Args:
        pdf_path: 按 PDF 路径筛选（相对/绝对路径均可，内部已归一化）
        question: 按问题精确匹配

    Returns:
        匹配的样本列表（含 id, question, expected_points）；文件缺失时返回 []（非严格模式）
    """
    return find_golden_samples(GOLDEN_DATASET_FILENAME, pdf_path=pdf_path, question=question)


def get_expected_points(pdf_path: str, question: str) -> list:
    """获取指定 PDF + 问题的 expected_points，未命中时告警并返回空列表。

    未命中不再静默：非严格模式打印警告后返回 []（调用方回退内置默认值时降级可见），
    严格模式（GOLDEN_STRICT=true）直接抛 LookupError 使用例失败。

    两个筛选项缺一即视为未命中：find_golden_samples 对空值是不筛选，问题为空会返回
    该论文的第一条样本（锚点张冠李戴且无任何异常可观察）。
    """
    if not pdf_path or not question:
        warn_golden_miss(GOLDEN_DATASET_FILENAME, pdf_path=pdf_path, question=question)
        return []
    matches = load_golden_samples(pdf_path=pdf_path, question=question)
    if matches:
        return matches[0].get("expected_points", [])
    warn_golden_miss(GOLDEN_DATASET_FILENAME, pdf_path=pdf_path, question=question)
    return []


# ── Fixtures 已迁移到包级 conftest.py（pdf_path / pdf_path_2，与 robust 共用）──
# 本包用例仍可从 test_paper_common 导入其余常量与辅助函数；PDF fixtures 由
# test_cases/conftest.py 自动注入，无需显式导入。


# ── 辅助函数 ──

def _extract_judge_content(text: str, max_chars: int = 12000) -> str:
    """从 AI 回答中智能采样，供裁判模型评估。

    策略：优先找 Markdown 标题区域，从实际内容的前/中/后三段采样。
    """
    if len(text) <= max_chars:
        return text
    first_heading = re.search(r"^\s{0,3}#{1,6}\s+\S", text, flags=re.MULTILINE)
    content_start = first_heading.start() if first_heading else 0
    content_text = text[content_start:]
    if len(content_text) <= max_chars:
        return content_text
    seg1_chars = int(max_chars * 0.4)
    seg2_chars = int(max_chars * 0.2)
    seg3_chars = max_chars - seg1_chars - seg2_chars
    seg1 = content_text[:seg1_chars]
    mid_point = len(content_text) // 2
    seg2_start = max(mid_point - seg2_chars // 2, seg1_chars)
    seg2 = content_text[seg2_start:seg2_start + seg2_chars]
    seg3 = content_text[-seg3_chars:]
    return (
        f"{seg1}\n\n"
        f"--- [中间采样，原文位置 {seg2_start:,}-{seg2_start + seg2_chars:,} / {len(content_text):,} 字] ---\n\n"
        f"{seg2}\n\n"
        f"--- [尾部采样，原文位置 {len(content_text) - seg3_chars:,}-{len(content_text):,} 字] ---\n\n"
        f"{seg3}"
    )


def _build_judge_content(text: str, document_text: str = "", max_chars: int = 12000) -> tuple:
    """组合 AI 回答与 write_file 文档作为 Judge 评分输入。

    Returns:
        (combined_content, source_label) 元组
    """
    if document_text:
        ai_budget = min(4000, max_chars // 3)
        doc_budget = max_chars - ai_budget
        ai_part = _extract_judge_content(text, max_chars=ai_budget)
        doc_part = document_text[:doc_budget]
        combined = f"【AI 回答】\n{ai_part}\n\n【生成文档】\n{doc_part}"
        return combined, "AI回答+文档"
    else:
        return _extract_judge_content(text, max_chars=max_chars), "AI回答"


def build_optimized_scores(judge_result: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """组装 judge.json 的 scores 结构（平均分置顶 + 各维 分数/中文名/理由）。

    理由来源分两类：
      - 主观 6 维：裁判 LLM 的 _all_runs[0].details（按 dimension 映射）；
      - faithfulness：Claim-Level 代码计算、LLM 不写 reason，用 build_faithfulness_reason 合成。
    提为模块级纯函数便于离线回归（2026-11-05 核查发现落盘忠实度理由为空，此前只修了上报侧）。
    """
    all_runs = judge_result.get("_all_runs", [])
    details_map = {}
    summary_text = ""
    if all_runs:
        first_run = all_runs[0]
        # 构建维度 -> 原因的映射
        for detail in first_run.get("details", []):
            dim = detail.get("dimension", "")
            reason = detail.get("reason", "")
            if dim:
                details_map[dim] = reason
        summary_text = first_run.get("summary", "")

    # 忠实度不经 LLM 打 reason，details 里没有它；与 Langfuse 上报侧同源合成
    if "faithfulness" in judge_result and "faithfulness" not in details_map:
        details_map["faithfulness"] = build_faithfulness_reason(judge_result)

    # 平均分置顶，再按固定维度顺序补各维详情（降级维度 score 为 None = 未评估，勿回退为 0）
    optimized_scores: Dict[str, Any] = {"average": compute_average(judge_result)}
    for dim in ALL_JUDGE_DIMENSIONS:
        optimized_scores[dim] = {
            "score": judge_result.get(dim, 0),
            "name": DIMENSION_NAMES.get(dim, dim),
            "reason": details_map.get(dim, ""),
        }
    return optimized_scores, summary_text


def _save_full_artifacts(
    output_dir: Path,
    case_name: str,
    chunks: List[Dict[str, Any]],
    text: str,
    meta: Dict[str, Any],
    input_info: Dict[str, Any] = None,
    file_metadata: Dict[str, Any] = None,
    tool_calls: List[Dict[str, Any]] = None,
    judge_result: Dict[str, Any] = None,
    document_text: str = None,
    judge_error: str = None,
) -> None:
    """保存 Agent 测试完整产物：按用例名组织子目录。

    产物目录结构：
    - {case_name}/{ts}_input.json       测试输入信息
    - {case_name}/{ts}_chunks.json      原始 SSE 事件流（调试用）
    - {case_name}/{ts}_response.md      AI 最终回答（排除系统指令、工具结果、思考过程）
    - {case_name}/{ts}_document.md      write_file 生成的输出文档
    - {case_name}/{ts}_tool_calls.json  工具调用详情
    - {case_name}/{ts}_judge.json       LLM-as-Judge 打分结果
    - {case_name}/{ts}_summary.md       Agent 执行摘要
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    case_dir = output_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    # 1. 测试输入信息
    if input_info:
        input_data = {
            "timestamp": ts, "case_name": case_name,
            "input": input_info, "file_metadata": file_metadata or {},
        }
        (case_dir / f"{ts}_input.json").write_text(
            json.dumps(input_data, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    # 2. 原始 SSE 事件流
    (case_dir / f"{ts}_chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 3. AI 最终回答（从 SSE 事件流中提取，排除系统指令、工具结果、思考过程）
    ai_response = extract_ai_final_response(chunks)
    if ai_response:
        (case_dir / f"{ts}_response.md").write_text(ai_response, encoding="utf-8")
    else:
        # 兜底：如果提取不到，保存原始 text（可能是空或包含中间内容）
        (case_dir / f"{ts}_response.md").write_text(text or "", encoding="utf-8")

    # 3b. write_file 生成的文档
    if document_text is None:
        document_text = extract_generated_document(chunks)
    if document_text:
        (case_dir / f"{ts}_document.md").write_text(document_text, encoding="utf-8")

    # 3c. 裁判实际被评内容：用与用例主体相同的纯函数重建（同 text + 同
    # document_text 产出逐字一致），供 Langfuse「Judge 评分」展示与评分
    # 对象对齐；q2 等编辑重建场景由调用方传入的 document_text 保证同源。
    judge_content, _judge_content_src = _build_judge_content(text or "", document_text or "")

    # 4. 工具调用详情
    if tool_calls:
        tool_data = {
            "timestamp": ts, "case_name": case_name,
            "total_calls": len(tool_calls), "tool_calls": tool_calls,
        }
        (case_dir / f"{ts}_tool_calls.json").write_text(
            json.dumps(tool_data, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    # 5. Judge 打分结果（优化结构：中文名 + 分数 + 原因）
    if judge_result:
        optimized_scores, summary_text = build_optimized_scores(judge_result)
        
        # 构建 judge_data（扁平化结构）
        judge_data = {
            "timestamp": ts,
            "case_name": case_name,
            "judge_model": judge_result.get("_judge_model", ""),
            "scores": optimized_scores,
            "summary": summary_text,
            "_meta": {
                "_judge_model": judge_result.get("_judge_model", ""),
                "_sample_count": judge_result.get("_sample_count", 1),
                "_content_length": judge_result.get("_content_length", 0),
                "_sampled_length": judge_result.get("_sampled_length", 0),
                "_content_source": judge_result.get("_content_source", ""),
                "_reference_length": judge_result.get("_reference_length", 0),
                "_faithfulness_ratio": judge_result.get("_faithfulness_ratio", 0),
                # 裁判模型自身的 token 开销（测试框架侧成本，区别于被测 Agent 的 Token 用量）
                "_judge_usage": judge_result.get("_judge_usage", {}),
            },
            # Claim-Level 声明验证详情
            **({"_claims_detail": judge_result.get("_claims_detail", [])} if judge_result.get("_claims_detail") else {}),
            # 降级标记：存在未真实评估的维度时显式标注（供基线收集剔除、报告区分真伪分数）
            **({"degraded": True,
                "degraded_reason": judge_result.get("degraded_reason") or judge_result.get("_degraded_reason") or ""
               } if (judge_result.get("degraded") or judge_result.get("_degraded")) else {}),
        }
    else:
        judge_data = {
            "timestamp": ts,
            "case_name": case_name,
            "error": judge_error or "Judge 评估未执行（结果为空）",
        }
    (case_dir / f"{ts}_judge.json").write_text(
        json.dumps(judge_data, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    # 6. 执行摘要
    timing = meta.get("timing", {})
    summary = generate_agent_summary(
        blocks=chunks, text=text, timing=timing,
        case_name=meta.get("case", case_name),
        conversation_id=meta.get("conversation_id"),
        model_name=meta.get("model_name", ""),
        thread_id=meta.get("thread_id", ""),
    )
    (case_dir / f"{ts}_summary.md").write_text(summary, encoding="utf-8")

    # 7. 打印产物路径
    print(f"[产物保存] {case_name}：chunks={len(chunks)} 个事件，AI回答={len(ai_response):,} 字")
    # Token 用量（被测 Agent 各轮 LLM 调用消耗，按消息 id 去重；服务端未透传时为 0）
    _token_usage = extract_token_usage(chunks)
    if _token_usage["total_tokens"]:
        print(f"  Token 用量：{_token_usage['total_tokens']:,} tokens"
              f"（{_token_usage['llm_call_count']} 轮 LLM 调用，输入 {_token_usage['input_tokens']:,} + 输出 {_token_usage['output_tokens']:,}）")
    print(f"  产物目录：{case_dir}")
    if input_info:
        print(f"  测试输入：{case_dir / f'{ts}_input.json'}")
    print(f"  SSE 事件流：{case_dir / f'{ts}_chunks.json'}")
    print(f"  AI 回答：{case_dir / f'{ts}_response.md'} ({len(ai_response):,} 字)")
    if document_text:
        print(f"  输出文档：{case_dir / f'{ts}_document.md'} ({len(document_text):,} 字)")
    if tool_calls:
        print(f"  工具调用：{case_dir / f'{ts}_tool_calls.json'} ({len(tool_calls)} 次)")
    if judge_result:
        _print_avg = compute_average(judge_result)
        _degraded = bool(judge_result.get("degraded") or judge_result.get("_degraded"))
        _degraded_note = "，含降级维度（忠实度未评估，平均分仅基于已评估维度）" if _degraded else ""
        # 声明验证摘要
        _claims = judge_result.get("_claims_detail", [])
        _supported = sum(1 for c in _claims if c.get("verdict") == "supported")
        _claims_desc = f", 声明验证={_supported}/{len(_claims)}" if _claims else ""
        print(f"  Judge 打分：{case_dir / f'{ts}_judge.json'} (平均分={_print_avg}{_claims_desc}{_degraded_note})")
    elif judge_error:
        print(f"  Judge 未执行：{case_dir / f'{ts}_judge.json'} ({judge_error})")
    print(f"  执行摘要：{case_dir / f'{ts}_summary.md'}")

    # ── 9. Langfuse Trace 上报（产物保存后自动同步，未配置时静默跳过）──
    try:
        from core.clients.langfuse_integration import get_langfuse_reporter, get_current_trace
        lf = get_langfuse_reporter()
        if lf.enabled:
            timing = meta.get("timing", {})
            # 使用 conftest.py 创建的 Trace
            trace = get_current_trace()
            if not trace:
                trace = lf.start_trace(
                    name=case_name,
                    input=input_info,
                    metadata={
                        "conversation_id": meta.get("conversation_id"),
                        "model_name": meta.get("model_name", ""),
                        "thread_id": meta.get("thread_id", ""),
                    },
                    tags=["paper"],
                )
            if trace:
                lf.report_trace(
                    trace,
                    case_name=case_name, case_dir=case_dir, ts=ts,
                    chunks=chunks, text=text,
                    ai_response=ai_response, document_text=document_text,
                    judge_content=judge_content,
                    timing=timing, input_info=input_info,
                    file_metadata=file_metadata,
                    tool_calls=tool_calls, judge_result=judge_result,
                    meta=meta,
                )
    except Exception as e:
        print(f"[Langfuse] 上报失败（不影响测试）：{e}")


def _run_judge_async(
    *,
    question: str,
    judge_content: str,
    paper_reference: str,
    expected_points: Optional[list] = None,
    tool_calls: Optional[list] = None,
    expected_tools: Optional[list] = None,
    sample_count: int = 1,
    timeout: float = 400.0,
    use_deepeval: Optional[bool] = None,
    dims: Optional[list] = None,
    spread_style: bool = False,
    content_length: int = 0,
    content_source: str = "",
) -> Tuple[Optional[Dict[str, Any]], Optional[str], bool]:
    """后台线程执行 Judge 评估，返回 (result, error_msg, timed_out)。

    由 test_single_round.py（INT-001）与 test_ooc_refusal.py 原先两份嵌套 _run_judge
    复制收敛而来，三种执行形态由参数区分，行为与原实现逐项对齐：
    - use_deepeval=True：DeepEvalAdapter.evaluate_quality（需要 tool_calls/expected_tools）
    - spread_style=True：自建 Judge 单次 evaluate_full，结果以 **_rs 展开包装（OOC 拒答口径）
    - 否则：自建 Judge sample_count 次采样，按 dims 逐维度取中位数，average 用代码重算

    异常统一捕获：error_msg 非空且 result 为空表示评估失败；timed_out=True 表示超时放弃。
    """
    use_deepeval = config.use_deepeval if use_deepeval is None else use_deepeval
    dims = dims or ALL_JUDGE_DIMENSIONS

    _judge_out: Dict[str, Any] = {"result": None, "error": None}

    def _runner() -> None:
        try:
            if use_deepeval:
                # 混合路由改走 orchestrator：deepeval 四维走第三方真指标、
                # judge 四维走真 Judge 单次调用——切除 adapter 把 judge 四维
                # 写死 3.5/4.0 常数的占位缺陷（框架侧 evaluation_orchestrator
                # 设计本意；tool_calls/expected_tools/n_runs 原样透传 adapter，
                # tool_call_accuracy 等扩展维由收口逻辑如实保留）。
                from core.evaluators.evaluation_orchestrator import EvaluationOrchestrator
                orch = EvaluationOrchestrator(
                    judge_client=JudgeClient(),
                    deepeval_adapter=DeepEvalAdapter(),
                    use_deepeval=True,
                )
                _judge_out["result"] = orch.evaluate(
                    question=question,
                    answer=judge_content,
                    reference=paper_reference,
                    expected_points=expected_points,
                    deepeval_kwargs={
                        "tool_calls": tool_calls,
                        "expected_tools": expected_tools,
                        "n_runs": sample_count,
                    },
                )
                return
            judge_client = JudgeClient()
            if spread_style:
                rs = judge_client.evaluate_full(
                    question=question, answer=judge_content,
                    reference=paper_reference, expected_points=expected_points,
                )
                # 包装 _save_full_artifacts 需要的 meta 键（_all_runs 携带裁判 details，
                # 否则锚点核对理由与 summary 在 judge.json 落盘时被丢弃）
                _judge_out["result"] = {
                    **rs,
                    "_all_runs": [rs],
                    "_judge_model": judge_client.model,
                    "_content_length": content_length,
                    "_sampled_length": len(judge_content),
                    "_content_source": content_source,
                    "_reference_length": len(paper_reference) if paper_reference else 0,
                }
                return
            all_runs: list = []
            dimension_scores: Dict[str, list] = {}
            for _ in range(sample_count):
                run_scores = judge_client.evaluate_full(
                    question=question, answer=judge_content,
                    reference=paper_reference, expected_points=expected_points,
                )
                all_runs.append(run_scores)
                for dim in dims:
                    # 降级维度值为 None（未评估），不参与中位数聚合
                    if run_scores.get(dim) is not None:
                        dimension_scores.setdefault(dim, []).append(run_scores[dim])
            median_scores = {d: statistics.median(s) for d, s in dimension_scores.items()}
            # 平均分只按维度算术均值重算（与落盘 judge.json / 基线 / DeepEval 链路同一口径）。
            # 中位数会淹没弱项，实测 7 维 (5,5,5,4,5,4,1.8) 取中位数得 5，算术均值是 4.3，
            # 而 passed 判据用的正是这个数 —— JUDGE_GATE 打开后忠实度崩塌也能过门禁。
            median_scores["average"] = compute_average(median_scores)
            last_run = all_runs[-1] if all_runs else {}
            _judge_out["result"] = {
                **median_scores,
                "_judge_model": judge_client.model,
                "_sample_count": sample_count,
                "_content_length": content_length,
                "_sampled_length": len(judge_content),
                "_content_source": content_source,
                "_reference_length": len(paper_reference) if paper_reference else 0,
                "_all_runs": all_runs,
                "_faithfulness_ratio": last_run.get("faithfulness_ratio", 0),
                "_claims_detail": last_run.get("claims_detail", []),
                # 声明计数透传（evaluate_full 已合并）：上报侧忠实度理由合成用，
                # 缺了它会回退 0/0 而分数却是真实比率（2026-11-05 二次修复）
                "_supported_claims": last_run.get("supported_claims", 0),
                "_total_claims": last_run.get("total_claims", 0),
                # 无法定位声明数透传：理由里需区分“原文不支持”与“检索落空”
                "_unlocated_claims": last_run.get("unlocated_claims", 0),
                "_timing": last_run.get("_timing", {}),
                "_degraded": last_run.get("degraded", False),
                "_degraded_reason": last_run.get("degraded_reason", ""),
            }
        except Exception as e:
            _judge_out["error"] = str(e) or type(e).__name__

    judge_thread = threading.Thread(target=_runner, daemon=True)
    judge_thread.start()
    judge_thread.join(timeout=timeout)
    if judge_thread.is_alive():
        return None, None, True
    if _judge_out["error"]:
        return None, _judge_out["error"], False
    return _judge_out["result"], None, False


def _run_e2e_judge(question: str, judge_content: str, pdf_path: str, expected_points: list) -> tuple:
    """L3 E2E 辅助：运行单次 Judge 质量评估，返回 (result_dict, error_msg)。

    使用 evaluate_full()：主观 6 维 + Claim-Level 忠实度验证（共 7 维）。
    expected_points 为该轮提问的黄金集锚点要点，由裁判在 instruction_follow
    维度逐条核对覆盖情况。
    异常处理策略：
    - 捕获所有异常并返回 (None, error_msg)，不向调用方抛出
    - error_msg 始终保证非空，避免下游误判为"未执行"
    - 对 dimension_scores 为空的情况做防御性处理
    """
    try:
        paper_reference = extract_pdf_text(pdf_path)
        judge_client = JudgeClient()
        all_runs, dimension_scores = [], {}
        for _ in range(1):
            rs = judge_client.evaluate_full(
                question=question, answer=judge_content,
                reference=paper_reference,
                expected_points=expected_points or None,
            )
            all_runs.append(rs)
            for dim in ALL_JUDGE_DIMENSIONS:
                # 降级维度值为 None（未评估），不参与中位数聚合
                if rs.get(dim) is not None:
                    dimension_scores.setdefault(dim, []).append(rs[dim])
        # 防御性检查：如果 Judge 返回的维度与预期不匹配，dimension_scores 为空
        if not dimension_scores:
            # 检查 rs 中实际包含哪些键，用于诊断
            actual_keys = list(all_runs[0].keys()) if all_runs else []
            return None, (
                f"Judge 返回中无预期维度键。"
                f"预期: relevance/completeness/.../faithfulness，"
                f"实际键: {actual_keys}"
            )
        median = {d: statistics.median(s) for d, s in dimension_scores.items()}
        # 平均分按维度算术均值重算，与落盘 judge.json / 基线 / 单轮用例同一口径；
        # 对“各维度取值”再取中位数会让强项淹没弱项（实测 4 个 ≥3 即可抬到 5）
        median["average"] = compute_average(median)
        # 保留最后一次运行的声明验证详情
        last_run = all_runs[-1] if all_runs else {}
        return {
            **median, "_judge_model": judge_client.model, "_sample_count": 1,
            "_content_length": len(judge_content),
            "_reference_length": len(paper_reference) if paper_reference else 0,
            "_all_runs": all_runs,
            "_faithfulness_ratio": last_run.get("faithfulness_ratio", 0),
            "_claims_detail": last_run.get("claims_detail", []),
            # 声明计数与无法定位数透传：与 _run_judge_async 同一口径，缺了它
            # build_faithfulness_reason 会回退 0/0 而分数却是真实比率（2026-11-05）
            "_supported_claims": last_run.get("supported_claims", 0),
            "_total_claims": last_run.get("total_claims", 0),
            "_unlocated_claims": last_run.get("unlocated_claims", 0),
            "_degraded": last_run.get("degraded", False),
            "_degraded_reason": last_run.get("degraded_reason", ""),
        }, None
    except Exception as e:
        # 保证 error_msg 始终非空：str(e) 为空时回退到异常类型名
        error_msg = str(e).strip()
        if not error_msg:
            error_msg = f"{type(e).__name__}（无详细消息）"
        return None, error_msg


def _report_perf_and_summary(
    reporter: AssertReporter,
    timing: Dict[str, Any],
    conversation_id: int,
    thread_id: str,
) -> None:
    """打印性能统计并输出断言汇总（用例 finally 收尾四件套之一）。

    三处同构复制（INT-001 / 追问场景 / OOC）已收敛至本函数。
    """
    reporter.info(
        "性能统计",
        f"首包耗时={timing.get('first_chunk_ms', 0):.0f}ms，总耗时={timing.get('total_ms', 0):.0f}ms，"
        f"conversation_id={conversation_id}，thread_id={thread_id}",
    )
    reporter.summary()


def _cleanup_conversation(sse_client: SseClient, conversation_id: int, label: str = "文献解读") -> None:
    """根据 CLEANUP_AFTER_TEST 配置决定是否清理会话（用例 finally 收尾四件套之一）。

    清理失败（如会话已不存在）不阻断用例结果；未开启清理时打印保留提示。
    """
    if CLEANUP_AFTER_TEST:
        try:
            sse_client.request_json("DELETE", f"{PAPER_CONVERSATIONS_PATH}/{conversation_id}")
        except SseError:
            pass
    else:
        print(f"[保留数据] {label}会话未清理：conversation_id={conversation_id}")
