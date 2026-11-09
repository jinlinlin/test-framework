"""裁判模型客户端：主观维度评分 + Claim-Level 忠实度验证（行业对齐）。

评估架构（对齐 DeepEval FaithfulnessMetric 做法）：
1. 主观维度（evaluate）：6 维 LLM 评分，不依赖参考原文
   - relevance, completeness, depth, instruction_follow, format, key_concepts
2. 事实核验（evaluate_faithfulness）：Claim-Level 声明级分解
   - 从回答提取事实声明 → 在参考原文中定位对应段落 → 逐条验证
   - score = 被支持声明数 / 总声明数
3. 综合评估（evaluate_full）：合并 1+2 的结果
"""
import json  # 解析裁判模型返回的 JSON 评分
import re  # 声明关键词提取（跨语言上下文定位）
import time  # 分步计时（诊断超时定位）
from pathlib import Path  # 读取评分标准文件
from typing import Any, Dict, List, Optional, Tuple  # 类型标注

import httpx  # HTTP 客户端（调用 OpenAI 兼容 API）

from core.utils.config import config  # 全局配置（JUDGE_BASE_URL / JUDGE_API_KEY / JUDGE_MODEL）
from core.constants import SUBJECTIVE_DIMENSIONS  # 主观评估维度（共享常量）

RUBRIC_PATH = Path(__file__).resolve().parent.parent.parent / "judge" / "rubric.md"  # 评分标准文件路径
JUDGE_TIMEOUT = 240.0  # 裁判模型请求超时（秒）：单次 LLM 调用上限
JUDGE_MAX_RETRIES = 2  # 重试次数上限（仅对超时和 5xx 重试，配额耗尽不重试）


class JudgeError(RuntimeError):
    """裁判模型调用失败时抛出的异常。"""


class JudgeClient:
    """裁判模型客户端：主观维度评分 + Claim-Level 忠实度验证。

    评估架构（对齐 DeepEval FaithfulnessMetric 做法）：
    1. evaluate()：6 维主观评分，不依赖参考原文
    2. evaluate_faithfulness()：Claim-Level 声明级分解验证
    3. evaluate_full()：合并 1+2，返回完整评估结果
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """初始化裁判客户端：从 config 读取配置（可覆盖）。未配置时抛出 JudgeError。"""
        self.base_url = (base_url or config.judge_base_url or "").rstrip("/")  # 裁判模型服务地址
        self.api_key = api_key or config.judge_api_key  # API Key
        self.model = model or config.judge_model  # 模型名称
        self.temperature = config.judge_temperature  # 采样温度（None 表示该模型不支持，请求不传）
        # 检查必填配置
        if not self.base_url or not self.api_key or not self.model:
            raise JudgeError(
                "Judge 评审模型未配置。请在 config/.env 中填写：\n"
                "JUDGE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1\n"
                "JUDGE_API_KEY=sk-你的密钥\n"
                "JUDGE_MODEL=qwen-plus"
            )
        self.rubric = self._load_rubric()  # 加载评分标准
        # 裁判自身 token 开销累计器（每次 _call_llm 成功后累加，
        # evaluate/evaluate_full 入口重置、出口取出，供 Langfuse/产物透传）
        self._usage_total: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "llm_calls": 0}

    def _reset_usage(self) -> None:
        """重置 token 开销累计器（evaluate/evaluate_full 入口调用）。"""
        self._usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "llm_calls": 0}

    def _take_usage(self) -> Dict[str, int]:
        """取出当前累计的 token 开销（不重置）。"""
        return dict(self._usage_total)

    @staticmethod
    def _load_rubric() -> str:
        """读取评分标准文件（judge/rubric.md）。"""
        if not RUBRIC_PATH.is_file():  # 文件不存在
            raise JudgeError(f"评分标准文件不存在：{RUBRIC_PATH}")
        return RUBRIC_PATH.read_text(encoding="utf-8")  # 返回 Markdown 文本

    # ── 主观维度评估（6 维，不依赖参考原文）──

    def _build_subjective_prompt(
        self, question: str, answer: str, expected_points: Optional[List[str]] = None,
    ) -> str:
        """构造主观维度评分 prompt（6 维，不含参考原文）。

        忠实度与数据准确性由独立的 evaluate_faithfulness() 通过
        Claim-Level 声明级分解处理（对齐 DeepEval FaithfulnessMetric）。
        expected_points 传入时插入「锚点要点核对」区块，裁判在 instruction_follow
        维度逐条核对覆盖情况（黄金集样本的预期要点）。
        """
        anchor_block = ""
        if expected_points:
            points_text = "\n".join(f"  {i + 1}. {p}" for i, p in enumerate(expected_points))
            anchor_block = f"""
## 锚点要点核对（instruction_follow 维度评分依据）

以下为该问题的标准答案要点清单，请在「指令遵循」维度评分时逐条核对 Agent 回答的覆盖情况：
{points_text}

核对要求：
- 每条要点须在 details 中 instruction_follow 的 reason 里说明覆盖状态（已覆盖/部分覆盖/未覆盖）
- 要点全部覆盖且无偏离 → instruction_follow 高分；遗漏或偏离越多 → 分越低
- 标注【拒答口径】的要点按字面核对拒答行为是否达成（如：明确表示未提及、不给出具体数值）
"""
        return f"""你是一位专业的 AI 响应质量评估专家。请根据以下评分标准，对用户问题和 Agent 回答进行打分。

## 评分标准

{self.rubric}

注意：本评估仅关注 6 个主观维度：相关性、完整性、分析深度、指令遵循、格式规范、关键概念覆盖。
忠实度与数据准确性由独立的声明级验证模块（Claim-Level Verification）处理，请勿在本评估中打分。

## 用户问题

{question}
{anchor_block}
## Agent 回答

注意：以下回答可能经过采样截取（包含"--- [中间采样] ---"或"--- [尾部采样] ---"标记），这是从完整回答中抽取的代表性片段。请基于实际内容进行评分，忽略采样标记本身。

{answer}

## 评分要求

1. 严格按照评分标准的 6 个主观维度（相关性、完整性、格式、分析深度、关键概念覆盖、指令遵循）分别打分（1-5 分）。
2. 计算 6 个维度的算术平均值作为总分（保留 1 位小数）。
3. 在 details 数组中为每个维度给出评分理由，须引用回答中的具体内容作为依据。
4. 在 summary 字段中用 1-3 句话总结整体评价，指出主要优点与不足。
5. **只输出 JSON，不要输出任何其他内容**。

## 输出格式

```json
{{{{
  "relevance": <1-5>,
  "completeness": <1-5>,
  "format": <1-5>,
  "depth": <1-5>,
  "key_concepts": <1-5>,
  "instruction_follow": <1-5>,
  "average": <平均值，保留1位小数>,
  "details": [
    {{{{"dimension": "<维度英文名>", "reason": "<评分理由，引用具体例证>"}}}}
  ],
  "summary": "<1-3句话整体评价>"
}}}}
```"""

    def evaluate(
        self,
        question: str,
        answer: str,
        expected_points: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """主观维度评估（6 维）：不依赖参考原文。

        评估维度：相关性、完整性、格式、分析深度、关键概念覆盖、指令遵循。
        忠实度与数据准确性请使用 evaluate_faithfulness()。

        Args:
            question: 用户问题。
            answer: Agent 回答内容。
            expected_points: 可选锚点要点列表（黄金集样本），传入后裁判在
                instruction_follow 维度逐条核对覆盖情况。
            **kwargs: 向后兼容（reference 等旧参数被忽略，reference 请走 evaluate_full）。
        """
        prompt = self._build_subjective_prompt(question, answer, expected_points)
        self._reset_usage()  # 独立调用 evaluate 时也返回本次开销
        result = self._call_llm(
            system="你是一位专业的 AI 响应质量评估专家，只输出 JSON 格式的评分结果。",
            user_content=prompt,
        )
        # 兼容 flash 模型返回数组的异常情况
        if isinstance(result, list):
            raise JudgeError("裁判模型输出为数组格式，期望对象格式")
        # 校验必填字段
        for key in SUBJECTIVE_DIMENSIONS:
            if key not in result:
                raise JudgeError(f"裁判模型输出缺少字段：{key}")
        # 兼容新旧格式：如果维度值是 dict（新格式），提取 score 字段
        normalized_scores = {}
        for d in SUBJECTIVE_DIMENSIONS:
            val = result[d]
            if isinstance(val, dict):
                normalized_scores[d] = val.get("score", 0)
            else:
                normalized_scores[d] = val
        # 将 normalized_scores 写回 result，统一后续使用
        for d in SUBJECTIVE_DIMENSIONS:
            result[d] = normalized_scores[d]
        # 用代码重算 average，覆盖 LLM 自己填的值（LLM 常算错）
        from core.scoring import compute_average
        result["average"] = compute_average(result, SUBJECTIVE_DIMENSIONS)
        result["_judge_usage"] = self._take_usage()  # 本次主观评估的 token 开销
        return result

    # ── Claim-Level 忠实度验证（对齐 DeepEval FaithfulnessMetric）──

    def evaluate_faithfulness(
        self,
        answer: str,
        reference: str,
        context_window: int = 500,
        max_claims: int = 10,
    ) -> Dict[str, Any]:
        """Claim-Level 忠实度验证（对齐 DeepEval FaithfulnessMetric 算法）。

        三步流程：
        1. 从回答中提取事实声明（claims），上限 max_claims 条
        2. 在参考原文中为每条声明定位对应段落
        3. 逐条验证声明是否被参考原文支持

        Args:
            answer: Agent 回答内容。
            reference: 参考原文（如论文 PDF 提取文本）。
            context_window: 声明上下文截取窗口（字符数），默认 500（±500=每条1K，10条≈10K）。
            max_claims: 最大声明数量上限，默认 10（控制验证 prompt 大小避免超时）。

        Returns:
            {
                "faithfulness": <1-5 或 None>,    # 映射到 1-5 评分尺度；未评估时为 None
                "faithfulness_ratio": <0-1 或 None>,  # 原始比率；未评估时为 None
                "supported_claims": <int>,    # 被支持的声明数
                "total_claims": <int>,        # 总声明数
                "claims_detail": [...],       # 每条声明的验证详情
                "degraded": <bool>,           # True 表示忠实度未真实评估（降级，分数为 None）
                "degraded_reason": "<str>"    # 降级原因（仅降级时存在）
            }
        """
        if not reference or not answer:
            return {
                "faithfulness": None, "faithfulness_ratio": None,
                "supported_claims": 0, "total_claims": 0, "claims_detail": [],
                "degraded": True,
                "degraded_reason": "reference 或 answer 为空，忠实度未评估",
            }

        # Step 1: 提取声明（截断到 max_claims 条，避免验证 prompt 过大导致超时）
        t_extract = time.perf_counter()
        claims = self._extract_claims(answer, max_claims)
        print(f"[Judge] 声明提取完成：{round(time.perf_counter() - t_extract, 1)}s，提取 {len(claims)} 条")
        if claims and len(claims) > max_claims:
            print(f"[Judge] 声明数={len(claims)}，截断到 max_claims={max_claims}")
            claims = claims[:max_claims]
        if not claims:
            return {
                "faithfulness": None, "faithfulness_ratio": None,
                "supported_claims": 0, "total_claims": 0, "claims_detail": [],
                "degraded": True,
                "degraded_reason": "声明提取结果为空，忠实度未评估",
            }

        # Step 2+3: 定位上下文 + 批量验证
        t_verify = time.perf_counter()
        verification, verify_error = self._verify_claims(claims, reference, context_window)
        print(f"[Judge] 声明验证完成：{round(time.perf_counter() - t_verify, 1)}s")
        if verify_error:
            # 声明验证调用失败：忠实度未评估，降级标记（不返回伪装分数污染均值/基线）
            print(f"[Judge] 声明验证失败，忠实度降级：{verify_error}")
            return {
                "faithfulness": None, "faithfulness_ratio": None,
                "supported_claims": 0, "total_claims": len(claims),
                "claims_detail": verification,
                "degraded": True,
                "degraded_reason": f"声明验证调用失败：{verify_error}",
            }
        supported = sum(1 for c in verification if c.get("verdict") == "supported")
        # 结构性无法定位的声明数（中文声明 + 英文原文且无 ASCII 术语）：
        # 它们计入分母（口径不变，宁严勿宽），但必须在理由里单独披露，
        # 否则 unknown 会被误读为“原文不支持”而冤枉回答
        unlocated = sum(1 for c in verification if not c.get("located", True))
        ratio = supported / len(claims) if claims else 0.0
        faithfulness_score = round(1.0 + ratio * 4.0, 1)  # 0-1 → 1-5

        return {
            "faithfulness": faithfulness_score,
            "faithfulness_ratio": round(ratio, 3),
            "supported_claims": supported,
            "total_claims": len(claims),
            "unlocated_claims": unlocated,
            "claims_detail": verification,
        }

    def _extract_claims(self, answer: str, max_claims: int = 20) -> List[str]:
        """Step 1: 使用 LLM 从回答中提取事实声明列表。

        提取范围：具体数据（数字、百分比）、方法描述、因果关系、对比结论等可验证的事实性声明。
        """
        prompt = f"""请从以下文本中提取最多 {max_claims} 条事实性声明（factual claims）。
每条声明应是一个独立的、可验证的陈述句。
包括：具体数据（数字、百分比、模型名称、数据集规模等）、方法描述、因果关系、对比结论等。
不包括：主观评价、格式描述、过渡性语句。
优先提取最重要的、最具代表性的声明，不超过 {max_claims} 条。

## 文本

{answer}

请输出 JSON 格式：
```json
{{{{
  "claims": ["声明1", "声明2", ...]
}}}}
```
只输出 JSON，不要输出其他内容。"""
        result = self._call_llm(
            system="你是一位精确的事实提取专家，只输出 JSON。",
            user_content=prompt,
        )
        # 兼容 flash 模型直接返回数组而非 {"claims": [...]} 的情况
        raw = result if isinstance(result, list) else result.get("claims", [])
        # 清洗 LLM 切句残留的前导标点：实测一轮 10/10 声明带前导 "."（".RelBench基准…"），
        # 污染落盘展示，也让关键词提取的首字符判断失真（2026-11-05 核查修复）
        return [
            c.strip().lstrip(".。,，;；:：、-–—·*").strip()
            for c in raw
            if isinstance(c, str) and c.strip()
        ]

    @staticmethod
    def _best_window_pos(
        reference: str, keyword: str, claim: str, context_window: int = 500, max_hits: int = 20
    ) -> int:
        """关键词多候选定位：在全部出现位置中选“数字密度”最高的那个窗口。

        高频术语的首命中位置往往在摘要/引言，±500 窗口里没有数据段，导致 LLM 只能判 unknown。
        实测（Tackling prediction tasks… 论文）：声明“RelBench 含 7 个库、30 个任务”的首命中在
        位置 707（摘要），窗口内无 7/30；全文 RelBench 出现 22 次，位置 2169 的窗口才含数据描述。
        故对声明中的数字 token 逐个候选位置打分，取最高；无数字 token 或全部为 0 时回退首命中
        （保持原行为，不额外调用 LLM）。
        """
        first = reference.find(keyword)
        if first < 0:
            return -1
        nums = re.findall(r"\d+(?:\.\d+)?", claim)
        if not nums:
            return first
        best_pos, best_score = first, 0
        start = 0
        for _ in range(max_hits):
            i = reference.find(keyword, start)
            if i < 0:
                break
            start = i + len(keyword)
            seg = reference[max(0, i - context_window): i + len(keyword) + context_window]
            score = sum(1 for n in nums if n in seg)
            if score > best_score:
                best_pos, best_score = i, score
        return best_pos

    def _verify_claims(
        self, claims: List[str], reference: str, context_window: int = 500
    ) -> Tuple[List[Dict[str, str]], Optional[str]]:
        """Step 2+3: 在参考原文中定位上下文，批量验证声明。

        上下文定位策略（跨语言兼容）：
        1. 从中文声明中提取英文关键词（专有名词、数字、术语）
        2. 按长度降序搜索（越长越具体）
        3. 匹配位置 ± context_window 作为上下文
        4. 全部未命中时回退到 reference 首部摘要

        Returns:
            (验证结果列表, 验证错误信息)。验证 LLM 调用失败时错误信息非 None（由调用方判定降级）。
        """
        # Step 2: 为每条声明定位上下文段落
        claims_with_context = []
        for claim in claims:
            # 提取声明中的英文关键词（ASCII 子串 ≥3 字符：专有名词、数字、术语）
            keywords = [kw for kw in re.findall(r'[A-Za-z0-9][A-Za-z0-9._\-]{2,}', claim)
                        if len(kw) >= 3]
            # 定位优先级：首字符为数字的 token（0.404、0.545、8WT6、19.6）区分度最高，
            # 直接锚定数据所在段落；含字母术语（TM-score、OFoldNA-SS2TS 等）在全文高频出现，
            # “命中即停”会定位到任意首次出现位置，导致 ±500 窗口错开数据表格（实测
            # 10 条声明 9 条因此误判 unknown）。故：数字开头 → 再按长度降序。
            # 注意区分“首字符为数字”与“含数字”：OFoldNA-SS2TS 含版本号 '2' 但首字符为字母，
            # 仍属泛锚点，不得越过 8WT6 这类唯一的 PDB ID。
            def _kw_sort_key(kw: str):
                digit_leading = kw[0].isdigit()
                return (0 if digit_leading else 1, -len(kw))
            keywords.sort(key=_kw_sort_key)

            pos = -1
            matched_kw = ""
            # 策略 1: 关键词搜索（跨语言：中文声明 → 英文 reference），高频词取数字密度最高窗口
            for kw in keywords[:5]:  # 最多尝试 5 个关键词
                pos = self._best_window_pos(reference, kw, claim, context_window)
                if pos >= 0:
                    matched_kw = kw
                    break
            # 策略 2: 中文子串搜索（声明与 reference 同语言时可用）
            if pos == -1:
                zh_parts = [p for p in re.findall(r'[\u4e00-\u9fff]{2,}', claim) if len(p) >= 3]
                for part in zh_parts[:3]:
                    pos = self._best_window_pos(reference, part, claim, context_window)
                    if pos >= 0:
                        matched_kw = part
                        break
            # 提取上下文窗口
            if pos >= 0:
                start = max(0, pos - context_window)
                end = min(len(reference), pos + len(matched_kw) + context_window)
                context = reference[start:end]
                located = True
            else:
                # 未匹配到相关段落，让 LLM 基于自身知识判定
                context = "（未在参考原文中找到相关内容）"
                # located=False：结构性无法定位（典型：中文声明 + 英文原文且声明不含 ASCII 术语），
                # 这类 unknown 不是“原文不支持”，必须与真 unknown 区分，否则忠实度被系统性低估
                located = False
            claims_with_context.append(
                {"claim": claim, "context": context, "located": located}
            )

        # Step 3: 批量验证（单次 LLM 调用）
        claims_text = "\n".join(
            f"{i+1}. 声明：{item['claim']}\n   上下文：{item['context']}"
            for i, item in enumerate(claims_with_context)
        )
        verify_prompt = f"""请逐条验证以下声明是否被提供的上下文支持。

判定标准：
- "supported"：上下文明确支持该声明，数据/描述一致
- "contradicted"：上下文与该声明矛盾或数据不一致
- "unknown"：上下文未提及该内容，或无法判定

{claims_text}

请输出 JSON 格式：
```json
{{{{
  "verdicts": [
    {{{{"claim_index": 1, "verdict": "supported/contradicted/unknown", "reason": "简要理由"}}}}
  ]
}}}}
```
只输出 JSON，不要输出其他内容。"""

        verify_error = None
        try:
            result = self._call_llm(
                system="你是一位严谨的事实核查专家，只输出 JSON。",
                user_content=verify_prompt,
            )
            # 兼容 flash 模型直接返回数组而非 {"verdicts": [...]} 的情况
            if isinstance(result, list):
                verdicts = result
            else:
                verdicts = result.get("verdicts", [])
        except JudgeError as exc:
            # 验证失败时全部标记为 unknown（verify_error 供调用方判定降级）
            verify_error = str(exc) or type(exc).__name__
            verdicts = [
                {"claim_index": i + 1, "verdict": "unknown", "reason": "验证过程异常"}
                for i in range(len(claims))
            ]

        # 合并声明与验证结果
        output = []
        for i, item in enumerate(claims_with_context):
            v = next(
                (v for v in verdicts if v.get("claim_index") == i + 1),
                {"verdict": "unknown", "reason": "未返回验证结果"},
            )
            output.append({
                "claim": item["claim"],
                "verdict": v.get("verdict", "unknown"),
                "reason": v.get("reason", ""),
                # 上下文是否在原文定位成功；False + unknown = 无法验证（非原文不支持）
                "located": item.get("located", True),
            })
        return output, verify_error

    # ── 综合评估（主观维度 + Claim-Level 忠实度）──

    def evaluate_full(
        self,
        question: str,
        answer: str,
        reference: str = "",
        expected_points: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """综合评估：主观维度（6 维）+ Claim-Level 忠实度验证。

        Args:
            question: 用户问题。
            answer: Agent 回答内容。
            reference: 可选参考原文（用于忠实度验证）。
            expected_points: 可选锚点要点列表（黄金集样本），传入后裁判在
                instruction_follow 维度逐条核对覆盖情况。

        Returns:
            完整评估结果，包含 6 个主观维度分数 + faithfulness 分数 + 合并平均分。
        """
        # 主观维度评估
        t0 = time.perf_counter()
        result = self.evaluate(question, answer, expected_points=expected_points)
        t_subjective = round(time.perf_counter() - t0, 1)
        print(f"[Judge] 主观 6 维评估完成：{t_subjective}s（answer={len(answer):,} 字）")

        # Claim-Level 忠实度验证
        faithfulness_result = {}
        t_faithfulness = 0
        if reference:
            t1 = time.perf_counter()
            faithfulness_result = self.evaluate_faithfulness(answer, reference)
            t_faithfulness = round(time.perf_counter() - t1, 1)
            print(f"[Judge] Claim-Level 忠实度验证完成：{t_faithfulness}s"
                  f"（声明数={faithfulness_result.get('total_claims', 0)}，"
                  f"reference={len(reference):,} 字）")
            result["faithfulness"] = faithfulness_result.get("faithfulness")  # 未评估时为 None（降级，勿填兜底假分）
            result["faithfulness_ratio"] = faithfulness_result.get("faithfulness_ratio")
            result["claims_detail"] = faithfulness_result.get("claims_detail", [])
            # 声明计数一并合并：上报侧（build_faithfulness_reason）与 judge.json 落盘都要用。
            # 此前只带 claims_detail 不带计数，中位数聚合路径又改键名为 _claims_detail，
            # 导致 Langfuse 忠实度理由回退成 0/0 而分数却是真实比率算出的（2026-11-05 二次修复）
            result["supported_claims"] = faithfulness_result.get("supported_claims", 0)
            result["total_claims"] = faithfulness_result.get("total_claims", 0)
            result["unlocated_claims"] = faithfulness_result.get("unlocated_claims", 0)
            # 透传降级标记：忠实度未评估时 average 由 compute_average 自动跳过 None 维度
            if faithfulness_result.get("degraded"):
                result["degraded"] = True
                result["degraded_reason"] = faithfulness_result.get("degraded_reason", "忠实度未评估")

        # 用 6 主观维度 + faithfulness 重算平均分（7 维）
        from core.scoring import compute_average
        all_dims = SUBJECTIVE_DIMENSIONS + (["faithfulness"] if reference else [])
        result["average"] = compute_average(result, all_dims)
        # 汇总裁判自身的 token 开销：evaluate() 入口已重置累计器，
        # 此处累计器已包含主观评估 + 声明提取 + 声明验证的全部 LLM 调用
        result.pop("_judge_usage", None)  # 避免单独 evaluate 的中间值残留
        result["_judge_usage"] = self._take_usage()
        result["_timing"] = {
            "subjective_sec": t_subjective,
            "faithfulness_sec": t_faithfulness,
            "total_sec": round(t_subjective + t_faithfulness, 1),
        }
        return result

    # ── LLM 调用辅助方法 ──

    def _call_llm(self, system: str, user_content: str) -> Dict[str, Any]:
        """调用 LLM 并解析 JSON 响应（统一封装，支持重试）。

        重试策略：
        - 超时（TimeoutException）：重试，最多 JUDGE_MAX_RETRIES 次
        - HTTP 5xx：重试，最多 JUDGE_MAX_RETRIES 次
        - HTTP 403（配额耗尽）：不重试，直接抛出带明确提示的异常
        - HTTP 4xx（其他）：不重试，参数错误无意义
        - JSON 解析失败：不重试，模型输出格式问题
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }
        if self.temperature is not None:
            # kimi-k3 等推理模型不支持 temperature（DashScope 返回 HTTP 400 InvalidParameter），
            # 配 JUDGE_TEMPERATURE=none 时不传该字段；请求体组装契约见 test_derivation_offline.py
            body["temperature"] = self.temperature
        last_error = None
        for attempt in range(1 + JUDGE_MAX_RETRIES):
            try:
                with httpx.Client(timeout=JUDGE_TIMEOUT) as client:
                    resp = client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=body,
                    )
                if resp.status_code == 200:
                    result = resp.json()
                    # 记录 token 用量（OpenAI 兼容接口必返；含重试时为多次调用累加）
                    u = result.get("usage") or {}
                    self._usage_total["prompt_tokens"] += u.get("prompt_tokens", 0) or 0
                    self._usage_total["completion_tokens"] += u.get("completion_tokens", 0) or 0
                    self._usage_total["total_tokens"] += u.get("total_tokens", 0) or 0
                    self._usage_total["llm_calls"] += 1
                    content = result["choices"][0]["message"]["content"]
                    content = content.strip()
                    if content.startswith("```"):  # 去除 markdown 代码块标记
                        content = content.split("\n", 1)[-1]
                        content = content.rsplit("```", 1)[0]
                    return json.loads(content)
                elif resp.status_code == 403:
                    # 配额耗尽：不重试，明确提示
                    resp_text = resp.text[:300]
                    if "quota" in resp_text.lower() or "FreeTierOnly" in resp_text:
                        raise JudgeError(
                            f"裁判模型配额耗尽（HTTP 403）：请充值或切换付费模式。"
                            f"响应：{resp_text}"
                        )
                    raise JudgeError(f"裁判模型请求被拒绝：HTTP 403，响应：{resp_text}")
                elif resp.status_code >= 500:
                    # 服务端错误：可重试
                    last_error = f"HTTP {resp.status_code}，响应：{resp.text[:300]}"
                    if attempt < JUDGE_MAX_RETRIES:
                        wait = 3 * (attempt + 1)
                        print(f"[Judge] 服务端错误 {resp.status_code}，{wait}s 后重试（{attempt+1}/{JUDGE_MAX_RETRIES}）...")
                        time.sleep(wait)
                        continue
                    raise JudgeError(f"裁判模型请求失败（重试 {JUDGE_MAX_RETRIES} 次后仍失败）：{last_error}")
                else:
                    # 其他 4xx：不重试
                    raise JudgeError(f"裁判模型请求失败：HTTP {resp.status_code}，响应：{resp.text[:500]}")
            except httpx.TimeoutException:
                last_error = f"裁判模型请求超时（{JUDGE_TIMEOUT}s）"
                if attempt < JUDGE_MAX_RETRIES:
                    wait = 5 * (attempt + 1)
                    print(f"[Judge] 超时，{wait}s 后重试（{attempt+1}/{JUDGE_MAX_RETRIES}）...")
                    time.sleep(wait)
                    continue
                raise JudgeError(f"{last_error}（重试 {JUDGE_MAX_RETRIES} 次后仍超时）")
        # 不应到达此处，但防御性抛出
        raise JudgeError(f"裁判模型调用失败：{last_error}")


# 全局单例（惰性初始化，避免未配置时导入报错）
_judge_client: Optional[JudgeClient] = None


def get_judge_client() -> JudgeClient:
    """获取裁判客户端单例。"""
    global _judge_client
    if _judge_client is None:
        _judge_client = JudgeClient()
    return _judge_client
