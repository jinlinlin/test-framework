"""Langfuse 集成：Agent Trace 可视化、评分趋势、实验管理。

通过 conftest.py 的 pytest 钩子 + _save_full_artifacts() 自动接入，用例代码无需修改。
每次测试运行自动上报：
- Trace（用例级）：用例名、状态、耗时、模型
- Span（步骤级）：SSE 调用、工具调用链路
- Score（评分）：Judge 八维分数、断言通过率
- Event（事件）：产物文件引用

未配置 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY 时静默禁用，不影响测试运行。
"""
import os  # 检测空值环境变量对 dotenv 加载的阻断
import re  # 黄金集版本号提取（dataset 标签）
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.utils.config import config
from core.utils.golden_dataset import find_golden_samples  # 黄金集匹配（与用例侧同源）
from core.constants import DIMENSION_NAMES, ALL_JUDGE_DIMENSIONS
from core.scoring import compute_average, get_dimension_scores


# ── Trace 维度标签与黄金集锚点（conftest 钩子与 report_trace 共用）──

# 黄金评测集文件名（与 test_cases/paper_interpret/test_paper_common.py 的
# GOLDEN_DATASET_FILENAME 保持一致；此处独立声明是为避免 core → test_cases 反向依赖）
_TRACE_GOLDEN_FILENAME = "paper_golden_v1.json"


def build_trace_tags(markers: Optional[List[str]] = None) -> List[str]:
    """构建 Trace 标签：pytest markers + 环境/模型/数据集版本。

    此前只有 markers（agent/paper/offline），多次运行混在一起无法区分口径；补上
    env / model / judge / dataset 四个前缀标签后，Langfuse 侧才能按环境、按被测
    模型、按黄金集版本横向对比分数趋势（同一模型换数据集版本也不会串味）。

    标签值统一 `key:value` 形式，Langfuse 侧可直接按 tag 过滤。
    """
    tags: List[str] = [m for m in (markers or []) if m]
    try:
        env_name = config.current_env
        if env_name:
            tags.append(f"env:{env_name}")
    except Exception:  # 配置异常不影响上报
        pass
    for cfg_key, tag_prefix in (("MODEL_NAME", "model"), ("JUDGE_MODEL", "judge")):
        value = config.get(cfg_key)
        if value:
            tags.append(f"{tag_prefix}:{value}")
    _ver = re.search(r"(v\d+)", _TRACE_GOLDEN_FILENAME)
    tags.append(f"dataset:golden_{_ver.group(1)}" if _ver else "dataset:unknown")
    # 去重保序（markers 里可能有重复项）
    seen, uniq = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def lookup_golden_anchor(
    pdf_path: Optional[str], question: Optional[str]
) -> Dict[str, Any]:
    """按「PDF + 问题」回查黄金集锚点（expected_points / 样本 id）。

    为什么在上报侧回查：expected_points 已打通到 Judge，但 Trace Input 里没有，
    失败时在 Langfuse 无法直接对照「预期要点 vs 实际回答」，得回本地翻 JSON。
    用例侧传锚点要改 10 个调用点，而锚点的单一事实源就是黄金集文件本身——
    此处按同样规则回查即可补齐信息，用例代码零改动。

    匹配必须与用例侧走同一个 find_golden_samples（归一化 PDF + 问题精确），
    不得自行放宽：实测黄金集内问题文本会跨论文重复（20 条中“请总结这篇论文的
    核心贡献、方法与结论”重复 2 次，expected_points 条数还一样），只按问题匹会
    给报告写进另一篇论文的要点，而 Judge 用的是当前论文那份——报告里的锚点变成
    误导（已真实发生过一次）。“仅问题命中”“问题子串”这类放宽同理不可用：用例
    侧此时并未命中（已回退内置默认要点），报告却展示 Judge 从未用过的要点。
    未命中一律返回 {}（追问等自定义问题本就不在黄金集里，属正常情况）。
    """
    if not question or not pdf_path:
        # 两者缺一都不能查：丢了 PDF 就退化成“仅问题匹配”，而问题文本在黄金集内
        # 会跨论文重复，拿到的必然是文件顺序上第一条（即另一篇论文的要点）。
        return {}
    try:
        # 严格模式（GOLDEN_STRICT=true）下文件缺失会抛错，上报链路不得因此中断测试
        hits = find_golden_samples(
            _TRACE_GOLDEN_FILENAME, pdf_path=pdf_path, question=question
        )
    except Exception as exc:  # noqa: BLE001 - 取锚点失败仅降级为无锚点上报
        print(f"[Langfuse] 黄金锚点回查跳过：{exc}")
        return {}
    if not hits:
        return {}
    hit = hits[0]
    points = hit.get("expected_points") or []
    return {
        "golden_sample_id": hit.get("id", ""),
        "expected_points": points,
        "expected_points_count": len(points),
        "golden_dataset": _TRACE_GOLDEN_FILENAME,
    }


def build_faithfulness_reason(judge_result: Dict[str, Any]) -> str:
    """合成忠实度维度的评分理由（该维度由 Claim-Level 代码计算，裁判 LLM 不产出 reason）。

    主观 6 维的 reason 来自裁判 LLM 返回的 details 数组；faithfulness 是
    supported/total 比率算出来的，LLM 从不给它写理由，此前上报到 Langfuse
    "Judge 评分" Event 的评分详情里恒为空串（2026-11-05 在 Trace 页发现
    "忠实度的理由没有输出"）。理由由四个数据源合成：
    - 命中率概览（X/Y 条声明被原文支持）；
    - 未支持声明摘录（verdict != supported，最多 3 条，扣分的直接证据）；
    - 无法定位声明的披露（unlocated_claims，计入分母但不等于原文不支持）；
    - 降级说明（degraded_reason，忠实度未真实评估时）。
    """
    if "faithfulness" not in judge_result:
        return ""
    # 取数兼容两种形态：evaluate_full 直出（claims_detail / supported_claims / total_claims）
    # 与 _run_judge_async 中位数聚合（meta 键带下划线前缀 _claims_detail 等，取 last_run）。
    # 此前只认无前缀键，中位数路径下全部落空，理由回退成 0/0 而分数却是真实比率（2026-11-05）。
    claims = (
        judge_result.get("claims_detail")
        or judge_result.get("_claims_detail")
        or []
    )
    supported = judge_result.get(
        "supported_claims",
        judge_result.get(
            "_supported_claims", sum(1 for c in claims if c.get("verdict") == "supported")
        ),
    )
    total = judge_result.get(
        "total_claims", judge_result.get("_total_claims", len(claims))
    )
    parts = [f"Claim-Level 声明级验证：{supported}/{total} 条声明被原文支持"]
    unsupported = [c for c in claims if c.get("verdict") != "supported"]
    if unsupported:
        briefs = [
            f"「{(c.get('claim') or '')[:60]}」→{c.get('verdict', 'unknown')}"
            f"{'' if c.get('located', True) else '（原文未定位到相关段落）'}"
            for c in unsupported[:3]
        ]
        more = f"（其余 {len(unsupported) - 3} 条见 claims_detail）" if len(unsupported) > 3 else ""
        parts.append("未支持声明：" + "；".join(briefs) + more)
    # 无法定位的声明单独披露：它们仍计入分母（口径不变，宁严勿宽），但成因是检索落空
    # （典型：中文声明 + 英文原文且声明不含 ASCII 术语），不是“原文不支持”。
    # 不披露会把这部分 unknown 读成事实性错误，从而低估回答质量（2026-11-05 核查）。
    unlocated = judge_result.get("unlocated_claims", judge_result.get("_unlocated_claims"))
    if unlocated is None:
        unlocated = sum(1 for c in claims if c.get("located") is False)
    if unlocated:
        parts.append(
            f"其中 {unlocated} 条声明无法在原文定位（检索落空，计入分母但不等于原文不支持）"
        )
    # 降级标记同样兼容中位数路径的下划线 meta 键
    if judge_result.get("degraded") or judge_result.get("_degraded"):
        reason = (
            judge_result.get("degraded_reason")
            or judge_result.get("_degraded_reason")
            or "忠实度未评估"
        )
        parts.append(f"降级：{reason}")
    return "；".join(parts)


class LangfuseReporter:
    """Langfuse 报告器：管理 pytest session 的 Trace 上报。

    用法：
        reporter = LangfuseReporter()
        trace = reporter.start_trace("paper_interpret", metadata={...})
        reporter.add_sse_span(trace, timing={...}, event_count=156)
        reporter.add_tool_calls_span(trace, tool_calls=[...])
        reporter.add_judge_scores(trace, judge_result={...})
        reporter.flush()
    """

    def __init__(self) -> None:
        """初始化 Langfuse 客户端。未配置时静默禁用（不影响测试运行）。"""
        self._enabled = False
        self._client = None
        # 当前尝试序号（pytest-rerunfailures 重试时由 conftest 钩子递增设置）。
        # 一次重试 = 完整 protocol 再跑一遍，多条尝试的证据（Span/Event）会累积在
        # 同一条 Trace 上；不带序号就分不清哪个失败是最终判定、哪个已被重试覆盖。
        self._attempt = 1
        try:
            public_key = config.get("LANGFUSE_PUBLIC_KEY")
            secret_key = config.get("LANGFUSE_SECRET_KEY")
            host = config.get("LANGFUSE_HOST") or "http://localhost:3000"
            if public_key and secret_key:
                from langfuse import Langfuse
                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                self._enabled = True
                try:
                    import langfuse as _lf
                    _ver = getattr(_lf, "__version__", "unknown")
                except Exception:  # pragma: no cover - 仅用于打印诊断信息
                    _ver = "unknown"
                # 打印 SDK 版本与实际入口，用于快速判定"上报没生效"是不是 API 名对不上
                print(f"[Langfuse] 已启用：{host}（SDK {_ver}，入口 client.trace()）")
            else:
                # dotenv 的规则是"已存在的环境变量优先、不覆盖"（含空值）——
                # IDE 运行配置若注入过空的 LANGFUSE_* 变量，会静默阻断 .env 里的 Key。
                # 此处显式检出这种情况，避免"为什么没上报"变成无理由可查的静默禁用。
                _blocked = sorted(
                    k for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")
                    if k in os.environ and not os.environ[k].strip()
                )
                if _blocked:
                    print(
                        f"[Langfuse] 环境变量 {_blocked} 存在但值为空，"
                        f"阻止了 config/.env 的 Key 加载（dotenv 不覆盖已有变量）——"
                        f"请在运行配置中清除这些变量后重跑"
                    )
                print("[Langfuse] 未配置 Key，Trace 上报已禁用（不影响测试）")
        except ImportError:
            print("[Langfuse] langfuse 未安装，请 pip install langfuse")
        except Exception as e:
            print(f"[Langfuse] 初始化失败，Trace 上报已禁用：{e}")

    @property
    def enabled(self) -> bool:
        """是否已启用。"""
        return self._enabled

    def set_attempt(self, attempt: int) -> None:
        """设置当前尝试序号（由 conftest 的 pytest_runtest_setup 钩子按尝试递增调用）。"""
        try:
            self._attempt = max(1, int(attempt or 1))
        except (TypeError, ValueError):
            self._attempt = 1

    def _n(self, base: str) -> str:
        """节点名：首次尝试保持原名，重试轮加 ` ·#N` 后缀。

        用命名后缀而非改结构，是为了让单尝试场景（当前 pytest.ini 的
        --force-reruns=0）产出与历史完全一致的 Trace，不引入任何视觉噪音。
        """
        return base if self._attempt <= 1 else f"{base} ·#{self._attempt}"

    @property
    def _attempt_md(self) -> Dict[str, Any]:
        """重试场景才附加的 metadata 键（单尝试返回空 dict，不污染既有结构）。"""
        return {"attempt": self._attempt} if self._attempt > 1 else {}

    def start_trace(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        input: Optional[Any] = None,
    ) -> Any:
        """创建一个 Trace（对应一个测试用例运行）。

        Args:
            name: 用例名称（如 paper_interpret）。
            metadata: 附加信息（conversation_id、model_name 等）。
            tags: 标签列表（如 ["paper", "agent"]）。
            input: 输入内容（如用户提问）。

        Returns:
            Langfuse Trace 对象；未启用时返回 None。
        """
        if not self._enabled:
            return None
        try:
            # 实测钉：langfuse SDK 2.60.10 的 Trace 创建入口是 client.trace()，
            # client.start_trace() 不存在（那是 v3/v4 的命名）。本文件曾误写为
            # start_trace()，被下面
            # 的 AttributeError 分支静默吞掉，表现为"Langfuse 里什么都看不到但用例全绿"。
            return self._client.trace(
                name=name,
                input=input,
                metadata=metadata or {},
                tags=tags or [],
            )
        except AttributeError as e:
            # SDK 版本与入口方法名不匹配：禁用必须留痕，否则整条上报链路会无声自我关闭
            self._enabled = False
            print(f"[Langfuse] 当前 SDK 无 trace() 入口，Trace 上报已禁用（不影响测试）：{e}")
            return None
        except Exception as e:
            print(f"[Langfuse] 创建 Trace 失败：{e}")
            return None

    def add_sse_span(
        self,
        trace: Any,
        name: str = "SSE 调用",
        timing: Optional[Dict[str, float]] = None,
        event_count: int = 0,
        text_length: int = 0,
        request_info: Optional[Dict[str, Any]] = None,
        text_content: Optional[str] = None,
    ) -> None:
        """记录 SSE 调用步骤（耗时、事件数、输出内容）。

        Args:
            trace: Langfuse Trace 对象。
            name: Span 名称。
            timing: 耗时信息（first_chunk_ms、total_ms）。
            event_count: SSE 事件总数。
            text_length: AI 回答文本长度。
            request_info: 请求信息（用户输入、模型等），显示在 Input 区域。
            text_content: SSE 流式输出的实际内容（AI 回答），显示在 Output 区域。
        """
        if not trace or not self._enabled:
            return
        try:
            timing = timing or {}
            # Input: 请求信息（显示在 Langfuse Input 区域）
            input_data = request_info or {
                "event": "SSE 流式请求",
                "note": "请求详情见 Trace 元数据",
            }
            # Output: 实际输出内容 + 统计（显示在 Langfuse Output 区域）
            # 截断到 50000 字（SSE 事件流通常几千~几万字，50K 足够覆盖绝大多数场景）
            output_preview = text_content[:50000] + "\n...(截断)" if text_content and len(text_content) > 50000 else text_content
            output_data = {
                "content": output_preview or "(无内容)",
                "stats": {
                    "first_chunk_ms": timing.get("first_chunk_ms", 0),
                    "total_ms": timing.get("total_ms", 0),
                    "event_count": event_count,
                    "text_length": text_length,
                },
            }
            # Metadata: 完整元数据（显示在 Langfuse Metadata 区域）
            metadata = {
                "type": "sse_stream",
                "first_chunk_ms": timing.get("first_chunk_ms", 0),
                "total_ms": timing.get("total_ms", 0),
                "event_count": event_count,
                "text_length": text_length,
            }
            trace.span(
                name=name,
                input=input_data,
                output=output_data,
                metadata=metadata,
            )
        except Exception as e:
            print(f"[Langfuse] 添加 SSE Span 失败：{e}")

    def add_tool_calls_span(
        self,
        trace: Any,
        tool_calls: List[Dict[str, Any]],
    ) -> None:
        """记录工具调用链路（工具名、参数、返回结果）。

        Args:
            trace: Langfuse Trace 对象。
            tool_calls: 工具调用列表，每项含 name/args/result 等字段。
        """
        if not trace or not self._enabled:
            return
        try:
            tool_names = [t.get("name", "unknown") for t in tool_calls]
            tools_detail = []
            for t in tool_calls:
                args = t.get("args", {})
                detail = {"name": t.get("name", "")}
                if isinstance(args, dict):
                    # 参数值一律上报（此前非 content 工具只留键名，"读了哪个文件、
                    # 什么范围"看不见，正是"张冠李戴"定位不了的原因）；
                    # 按类型分档截断：content（write_file 正文）5000 字，其余 1000 字。
                    detail["args_preview"] = {
                        k: (
                            (v[:5000] + "...") if isinstance(v, str) and len(v) > 5000 else v
                        ) if k == "content" else (
                            (v[:1000] + "...") if isinstance(v, str) and len(v) > 1000 else v
                        )
                        for k, v in args.items()
                    }
                elif args:
                    detail["args_preview"] = str(args)[:1000]
                if t.get("status"):
                    # 工具执行状态（success/error）：失败的工具调用是回答不准的直接成因
                    detail["status"] = t["status"]
                if "result" in t:
                    # 返回值 200 字基本看不全论文片段，放宽到 2000 字并记录原始长度
                    _res = str(t["result"])
                    detail["result_preview"] = (_res[:2000] + "...") if len(_res) > 2000 else _res
                    detail["result_length"] = len(_res)
                tools_detail.append(detail)
            trace.span(
                name=self._n("工具调用"),
                input={"tool_count": len(tool_calls), "tool_names": tool_names},
                output=tools_detail,
                metadata={
                    "tool_count": len(tool_calls),
                    "tool_names": tool_names,
                    **self._attempt_md,
                },
            )
        except Exception as e:
            print(f"[Langfuse] 添加工具调用 Span 失败：{e}")

    def add_token_usage_span(
        self,
        trace: Any,
        token_usage: Dict[str, Any],
    ) -> None:
        """记录被测 Agent 的 LLM token 用量（服务端随 values 快照透传的 usage_metadata）。

        Args:
            trace: Langfuse Trace 对象。
            token_usage: extract_token_usage() 的返回值（total/input/output/llm_call_count/
                tool_batch_tokens/final_answer_tokens/per_message）。
        """
        if not trace or not self._enabled:
            return
        total = token_usage.get("total_tokens", 0)
        if not total:
            print("[Langfuse] Token 用量：跳过（无 usage_metadata 数据）")
            return
        try:
            # Input/Output/Metadata 三者内容互不重复（否则页面三区显示相同）
            input_data = {
                "说明": "被测 Agent 各轮 LLM 调用的 token 消耗（按消息 id 去重）",
                "LLM 调用轮数": token_usage.get("llm_call_count", 0),
            }
            output_data = {
                "总消耗": total,
                "输入 tokens": token_usage.get("input_tokens", 0),
                "输出 tokens": token_usage.get("output_tokens", 0),
                "归属分解": {
                    "工具调用轮": token_usage.get("tool_batch_tokens", 0),
                    "最终回答轮": token_usage.get("final_answer_tokens", 0),
                },
                "逐轮明细": [
                    {
                        "轮次": i + 1,
                        "归属": m.get("kind") or "未知",
                        "输入": m.get("input_tokens", 0),
                        "输出": m.get("output_tokens", 0),
                        "合计": m.get("total_tokens", 0),
                    }
                    for i, m in enumerate(token_usage.get("per_message", []))
                ],
            }
            metadata = {
                "source": "values_snapshot.usage_metadata",
                "dedup_key": "message_id",
                **self._attempt_md,
            }
            trace.span(name=self._n("Token 用量"), input=input_data, output=output_data, metadata=metadata)
            print(f"[Langfuse] Token 用量：总计 {total:,} tokens（{token_usage.get('llm_call_count', 0)} 轮 LLM 调用）")
        except Exception as e:
            print(f"[Langfuse] 添加 Token 用量 Span 失败：{e}")

    def add_judge_usage(
        self,
        trace: Any,
        judge_usage: Dict[str, Any],
        judge_model: str = "",
    ) -> None:
        """记录裁判模型自身的 token 开销（Judge 是测试框架自己的 LLM 消耗）。

        优先用 Generation 节点（Langfuse 语义化 LLM 调用观测，页面可展示 usage），
        当前 SDK 无 generation 入口时降级为 Span（沿用“API 名存在性”探测原则）。

        Args:
            trace: Langfuse Trace 对象。
            judge_usage: {prompt_tokens, completion_tokens, total_tokens, llm_calls}。
            judge_model: 裁判模型名称。
        """
        if not trace or not self._enabled:
            return
        total = judge_usage.get("total_tokens", 0)
        if not total:
            print("[Langfuse] Judge 开销：跳过（无 usage 数据）")
            return
        try:
            usage_payload = {
                "input": judge_usage.get("prompt_tokens", 0),
                "output": judge_usage.get("completion_tokens", 0),
                "total": total,
                "unit": "TOKENS",
                "llm_calls": judge_usage.get("llm_calls", 0),
            }
            gen_method = getattr(trace, "generation", None)
            if callable(gen_method):
                # v2 SDK 的 StatefulTraceClient.generation：LLM 调用专用观测节点
                gen_method(
                    name=self._n("Judge 评审"),
                    model=judge_model or "unknown",
                    input={"说明": "裁判模型评分调用（主观 6 维 + 忠实度声明验证）"},
                    output={"token 用量": usage_payload},
                    usage=usage_payload,
                )
                print(f"[Langfuse] Judge 开销：{total:,} tokens（Generation 节点，{judge_usage.get('llm_calls', 0)} 次调用）")
            else:
                # 无 generation 入口时降级为 Span，usage 放 output/metadata
                trace.span(
                    name=self._n("Judge 评审"),
                    input={"裁判模型": judge_model, "调用次数": judge_usage.get("llm_calls", 0)},
                    output=usage_payload,
                    metadata={"node_type": "generation_fallback", **self._attempt_md},
                )
                print(f"[Langfuse] Judge 开销：{total:,} tokens（Span 降级，{judge_usage.get('llm_calls', 0)} 次调用）")
        except Exception as e:
            print(f"[Langfuse] 添加 Judge 开销节点失败：{e}")

    def add_judge_scores(
        self,
        trace: Any,
        judge_result: Dict[str, Any],
    ) -> None:
        """记录 Judge 七维评分为 Langfuse Score（主观 6 维 + Claim-Level 忠实度）。"""
        if not trace or not self._enabled:
            return
        try:
            for dim in ALL_JUDGE_DIMENSIONS:
                if dim in judge_result:
                    val = judge_result[dim]
                    score = val.get("score") if isinstance(val, dict) else val
                    trace.score(name=dim, value=float(score))
            # 用代码重算 average，不信任 LLM/DeepEval 自报值
            _recalc_avg = compute_average(judge_result)
            if _recalc_avg > 0:
                trace.score(name="judge_average", value=_recalc_avg)
        except Exception as e:
            print(f"[Langfuse] 添加 Judge 评分失败：{e}")

    def add_test_result(
        self,
        trace: Any,
        passed: bool,
        assert_reporter: Any = None,
        failure_message: str = None,
        attempt: Optional[int] = None,
    ) -> None:
        """记录测试通过/失败结果与断言统计（重试场景按尝试序号区分）。

        Args:
            trace: Langfuse Trace 对象。
            passed: 本次尝试是否通过。
            assert_reporter: AssertReporter 对象（可选）。
            failure_message: 失败原因（可选），记录到 Trace output 和 Event 中。
            attempt: 第几次尝试（1 起）；None 时沿用 set_attempt 设置的当前值。

        重试语义说明（2026-10-28 定位）：pytest-rerunfailures 的每次重试都会再触发
        一遍 makereport，所以同一条 Trace 上会有 N 个结果事件。`test_passed` 分数是
        后写覆盖前写——由于只对失败重试，最后一次写入恰好等于最终判定，分数语义正确；
        真正的缺陷是失败 Event 无法与"已被重试覆盖的中间失败"区分，故此处给事件带序号，
        并在"重试后通过"时补一条收尾事件，让失败次数与最终结论一眼对齐。
        """
        if not trace or not self._enabled:
            return
        if attempt is not None:
            self.set_attempt(attempt)
        try:
            trace.score(name="test_passed", value=1.0 if passed else 0.0)
            # 尝试次数（含首次）：最后一次写入即总尝试数；>1 可筛出 flaky 通过，
            # 避免"绿色但不知道它失败了两次才过"
            trace.score(name="attempt_count", value=float(self._attempt))
            if assert_reporter:
                trace.score(name="assert_passed", value=float(assert_reporter.passed))
                trace.score(name="assert_failed", value=float(assert_reporter.failed))
            # 测试失败时记录失败原因到 Trace output + Event（事件名带尝试序号）
            if not passed and failure_message:
                trace.update(output={"test_failed": failure_message, "attempt": self._attempt})
                trace.event(
                    name=self._n("测试失败"),
                    input={
                        "失败原因": failure_message,
                        "第几次尝试": self._attempt,
                    },
                    output={"status": "FAILED"},
                    metadata={
                        "attempt": self._attempt,
                        "note": "若配置了重试，后续尝试会再写一条结果事件，以最后一条为最终判定",
                    },
                )
                print(f"[Langfuse] 测试失败已记录（第 {self._attempt} 次尝试）：{failure_message[:200]}")
            elif passed and self._attempt > 1:
                # 重试后通过：补收尾事件，前面 N-1 条失败事件的含义（中间态）由此明确
                trace.event(
                    name="重试后通过",
                    input={"说明": f"前 {self._attempt - 1} 次尝试失败，第 {self._attempt} 次通过"},
                    output={"status": "PASSED_AFTER_RERUN"},
                    metadata={"attempt": self._attempt, "flaky": True},
                )
                print(f"[Langfuse] 重试后通过：共 {self._attempt} 次尝试")
        except Exception as e:
            print(f"[Langfuse] 添加测试结果失败：{e}")

    def update_trace_input(
        self,
        trace: Any,
        input: Any,
    ) -> None:
        """更新 Trace 的 Input（conftest 创建 Trace 时未传 input，在此补上）。

        Args:
            trace: Langfuse Trace 对象。
            input: 输入内容（如用户提问）。
        """
        if not trace or not self._enabled:
            return
        try:
            trace.update(input=input)
            print(f"[Langfuse] Trace Input 已更新：{type(input).__name__}")
        except Exception as e:
            print(f"[Langfuse] 更新 Trace Input 失败：{e}")

    def add_artifact_event(
        self,
        trace: Any,
        name: str,
        file_path: Path,
        content_preview: Optional[str] = None,
    ) -> None:
        """记录产物文件引用（文件名、大小、内容预览）。

        Args:
            trace: Langfuse Trace 对象。
            name: 产物名称（如"生成文档"）。
            file_path: 产物文件路径。
            content_preview: 内容预览文本（可选，写入 Event output）。
        """
        if not trace or not self._enabled:
            return
        try:
            if file_path.is_file():
                size = file_path.stat().st_size
                # Input: 描述性信息（产物类型 + 内容长度），文件路径仅在 Metadata 中
                event_input = {"产物类型": name, "内容长度": f"{size:,} 字节"}
                # Output: 内容预览前 10000 字
                event_output = content_preview[:10000] if content_preview else None
                # Metadata: 文件路径 + 大小（完整技术信息）
                metadata = {"file": str(file_path), "size_bytes": size}
                trace.event(
                    name=name,
                    input=event_input,
                    output=event_output,
                    metadata=metadata,
                )
        except Exception as e:
            print(f"[Langfuse] 添加产物事件失败：{e}")

    def flush(self) -> None:
        """刷新所有待上报数据到 Langfuse 服务端。"""
        if not self._enabled:
            return
        try:
            self._client.flush()
            print("[Langfuse] Trace 数据已上报")
        except Exception as e:
            print(f"[Langfuse] 上报失败：{e}")

    def report_trace(
        self,
        trace: Any,
        *,
        case_name: str,
        case_dir: Any,
        ts: str,
        chunks: List[Dict[str, Any]],
        text: str,
        ai_response: str = "",
        document_text: str = "",
        timing: Optional[Dict[str, float]] = None,
        input_info: Optional[Dict[str, Any]] = None,
        file_metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        judge_result: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """向 Langfuse Trace 上报一个用例的完整执行数据。

        由 _save_full_artifacts() 调用，负责 Trace 树的全部节点添加：
        执行摘要、测试输入（含黄金集锚点）、SSE Span、工具调用 Span、Token 用量 Span、AI 回答、生成文档、Judge 评分（含裁判自身 token 开销）。
        重试场景下所有节点名带 ·#N 序号后缀（attempt>1 时），可区分哪次尝试产生。

        Args:
            trace: Langfuse Trace 对象。
            case_name: 用例名称。
            case_dir: 产物目录 Path。
            ts: 时间戳字符串。
            chunks: SSE 事件块列表。
            text: AI 回答原始拼接文本。
            ai_response: 从 SSE 流提取的最终 AI 回答。
            document_text: write_file 生成的文档内容。
            timing: 耗时信息（first_chunk_ms, total_ms）。
            input_info: 测试输入信息。
            file_metadata: 上传文件元数据。
            tool_calls: 工具调用列表。
            judge_result: Judge 评分结果。
            meta: 元数据（conversation_id, model_name, thread_id 等）。
        """
        if not trace or not self._enabled:
            return
        import json as _json
        timing = timing or {}
        meta = meta or {}

        # 1. 执行摘要（概览优先，排在树形列表最前）
        sm_file = case_dir / f"{ts}_summary.md"
        sm_preview = sm_file.read_text(encoding="utf-8") if sm_file.is_file() else None
        self.add_artifact_event(trace, self._n("执行摘要"), sm_file, content_preview=sm_preview)
        print(f"[Langfuse] ① 执行摘要：{sm_file.name} ({len(sm_preview):,} 字)" if sm_preview else f"[Langfuse] ① 执行摘要：{sm_file.name} (无内容)")

        # 2. 测试输入 Event（含黄金集锚点，便于失败时在 Langfuse 内直接对照预期要点）
        enriched_input = dict(input_info) if input_info else {}
        _anchor = lookup_golden_anchor(
            (file_metadata or {}).get("file_path"),
            enriched_input.get("user_question") or "",
        )
        if _anchor:
            enriched_input.update(_anchor)
            print(
                f"[Langfuse] ② 黄金锚点命中：{len(_anchor['expected_points'])} 条预期要点"
                f"（sample={_anchor['golden_sample_id'] or '无 id'}）"
            )
        elif input_info:
            # 未命中也可见，但两种原因不能混为一谈：无 PDF（OOC/拒答类本就不适用）
            # 与问法未收录（追问自定义）排查方向完全不同
            _why = (
                "未提供 PDF 路径，锚点不适用" if not (file_metadata or {}).get("file_path")
                else "问法未收录（追问等自定义问题属正常）"
            )
            print(f"[Langfuse] ② 黄金锚点：未命中（{_why}）")
        if enriched_input:
            test_input_content = {
                "user_question": enriched_input.get("user_question", ""),
                "task_type": enriched_input.get("task_type", ""),
                "model_name": enriched_input.get("model_name", ""),
            }
            # 锚点直接进"测试输入"事件：失败时不用回本地翻黄金集 JSON
            if _anchor:
                test_input_content["golden_sample_id"] = _anchor["golden_sample_id"]
                test_input_content["expected_points"] = _anchor["expected_points"]
            # 用例附带的其余非空口径（source / case_id 等）一并带上，setdefault 不覆盖已显式写入的键
            for _k, _v in (input_info or {}).items():
                if _v is not None and _v != "":
                    test_input_content.setdefault(_k, _v)
            if file_metadata:
                test_input_content["file_metadata"] = file_metadata
            trace.event(
                name=self._n("测试输入"),
                input=test_input_content,
                output={"note": "详见 Trace Input"},
            )
            # Trace Input 用增强后的版本（含 expected_points + 黄金样本 id）
            self.update_trace_input(trace, enriched_input)
        else:
            print("[Langfuse] ② 测试输入：跳过（input_info 为空）")

        # 3. SSE Span
        request_info = {
            "event": "SSE 流式请求",
            "task_type": meta.get("task_type", "interpret"),
            "model_name": meta.get("model_name", ""),
            "conversation_id": meta.get("conversation_id"),
        }
        sse_event_lines = []
        for chunk in chunks:
            event_name = chunk.get("event", "")
            event_data = chunk.get("data", "")
            chunk_ts = chunk.get("ts_ms", 0)
            if event_name == "heartbeat":
                continue
            if isinstance(event_data, (dict, list)):
                data_str = _json.dumps(event_data, ensure_ascii=False)[:2000]
            else:
                data_str = str(event_data)[:2000]
            sse_event_lines.append(f"[{chunk_ts:,.0f}ms] {event_name}: {data_str}")
        sse_output_content = "\n".join(sse_event_lines) if sse_event_lines else "(无事件)"
        self.add_sse_span(
            trace, name=self._n("SSE 调用"), timing=timing,
            event_count=len(chunks), text_length=len(text),
            request_info=request_info,
            text_content=sse_output_content,
        )
        print(f"[Langfuse] ③ SSE 调用：{len(chunks)} 个事件，文本长度={len(text):,} 字，事件流内容={len(sse_output_content):,} 字")

        # 4. 工具调用 Span
        if tool_calls:
            self.add_tool_calls_span(trace, tool_calls)
            print(f"[Langfuse] ④ 工具调用：{len(tool_calls)} 次")

        # 4b. Token 用量 Span（被测 Agent 各轮 LLM 调用的消耗，按消息 id 去重）
        from core.assertions.assert_tools import extract_token_usage
        self.add_token_usage_span(trace, extract_token_usage(chunks))

        # 5. AI 回答事件
        if ai_response:
            self.add_artifact_event(
                trace, self._n("AI 回答"), case_dir / f"{ts}_response.md",
                content_preview=ai_response,
            )
            print(f"[Langfuse] ⑤ AI 回答：{len(ai_response):,} 字")

        # 6. 生成文档事件
        if document_text:
            self.add_artifact_event(
                trace, self._n("生成文档"), case_dir / f"{ts}_document.md",
                content_preview=document_text,
            )
            print(f"[Langfuse] ⑥ 生成文档：{len(document_text):,} 字")

        # 7. Judge 打分（Score + Event + 裁判自身 token 开销）
        if judge_result:
            # 裁判模型自己的 LLM 消耗（测试框架侧成本，区别于被测 Agent 的 Token 用量 Span）
            _judge_usage = judge_result.get("_judge_usage") or {}
            if _judge_usage.get("total_tokens"):
                self.add_judge_usage(trace, _judge_usage, judge_model=judge_result.get("_judge_model", ""))
            self.add_judge_scores(trace, judge_result)
            # 提取各维度打分理由
            _all_runs = judge_result.get("_all_runs", [])
            _details_map = {}
            if _all_runs:
                for _detail in _all_runs[0].get("details", []):
                    _d = _detail.get("dimension", "")
                    _r = _detail.get("reason", "")
                    if _d:
                        _details_map[_d] = _r
            # 忠实度不经 LLM 打 reason（Claim-Level 代码计算），details 里没有它，
            # 此前恒为空串；由声明验证结果合成（见 build_faithfulness_reason）
            if "faithfulness" in judge_result and "faithfulness" not in _details_map:
                _details_map["faithfulness"] = build_faithfulness_reason(judge_result)
            # 平均分
            _ev_scores = get_dimension_scores(judge_result)
            _avg = compute_average(judge_result)
            print(f"[Langfuse] ⑦ Judge 评分：平均分={_avg}，维度数={len(_ev_scores)}，裁判模型={judge_result.get('_judge_model', '')}")
            # 构建有序详情列表
            judge_details_ordered = [
                {"维度": "平均分", "分数": _avg},
            ] + [
                {"维度": DIMENSION_NAMES.get(_dim, _dim), "分数": judge_result[_dim], "理由": _details_map.get(_dim, "")}
                for _dim in ALL_JUDGE_DIMENSIONS
                if _dim in judge_result
            ]
            _summary = _all_runs[0].get("summary", "") if _all_runs else ""
            try:
                trace.event(
                    name=self._n("Judge 评分"),
                    input={"被评估内容": ai_response[:10000] + "..." if ai_response and len(ai_response) > 10000 else (ai_response or "无")},
                    output={
                        "评分详情": judge_details_ordered,
                        "裁判评语": _summary[:5000] if _summary else "无",
                    },
                    metadata={
                        "judge_model": judge_result.get("_judge_model", ""),
                        "content_source": judge_result.get("_content_source", ""),
                        "reference_length": judge_result.get("_reference_length", 0),
                        # 锚点回指：评分理由与预期要点在同一 Trace 内对齐，便于失败定位
                        **({"golden_sample_id": _anchor["golden_sample_id"]} if _anchor else {}),
                        **self._attempt_md,
                    },
                )
            except Exception as _e:
                print(f"[Langfuse] 添加 Judge 事件失败：{_e}")

        # 设置 Trace Output
        trace_output_parts = []
        if ai_response:
            trace_output_parts.append(f"【AI 回答】\n{ai_response}")
        if document_text:
            trace_output_parts.append(f"\n【生成文档】({len(document_text):,} 字)\n{document_text[:10000]}")
        if trace_output_parts:
            trace.update(output="\n".join(trace_output_parts))
        print(f"[Langfuse] Trace Output：AI回答={len(ai_response):,} 字，生成文档={len(document_text):,} 字" if ai_response or document_text else "[Langfuse] Trace Output：无内容")


# ── 全局单例（conftest.py 中 session 级复用）──

_langfuse_reporter: Optional[LangfuseReporter] = None
_current_trace: Optional[Any] = None  # 当前用例的 Trace（conftest.py 设置，_save_full_artifacts 读取）


def get_langfuse_reporter() -> LangfuseReporter:
    """获取全局 LangfuseReporter 单例。"""
    global _langfuse_reporter
    if _langfuse_reporter is None:
        _langfuse_reporter = LangfuseReporter()
    return _langfuse_reporter


def set_current_trace(trace: Any) -> None:
    """设置当前用例的 Trace（由 conftest.py 钩子调用）。"""
    global _current_trace
    _current_trace = trace


def get_current_trace() -> Optional[Any]:
    """获取当前用例的 Trace（由 _save_full_artifacts 调用）。"""
    return _current_trace
