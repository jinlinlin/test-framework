"""文献解读业务断言与常量：论文场景专属校验（从 core.assertions 下沉）。

core.assertions 保持业务无关的通用断言原语；本模块承载文献解读场景的
期望章节/要点/工具策略常量与专用断言（read_file 匹配 PDF、轨迹评分报告、
数据点忠实度校验），供 paper_interpret 包内用例复用。

依赖方（详见同目录 README.md）：
- test_single_round.py（INT-001~003 单轮能力）
- test_ooc_refusal.py（INT-005 OOC 拒答）
- test_paper_common.py（re-export 枢纽）
"""
import os  # PDF 文件名解析（read_file 参数匹配）
import re  # 数据声明提取正则
from typing import Any, Dict, List  # 类型标注

from core.assertions.assert_tools import (  # 通用断言原语（core 层）
    PATH_PARAM_KEYS,
    SseChunk,
    assert_must_pass_tools,
    assert_no_forbidden_tools,
    assert_tool_order,
    assert_tool_subset,
    extract_tool_calls,
    extract_tool_calls_from_messages,
    get_tools_by_name,
)

# ════════════════════════════════════════════════════════════════
#  语义章节与要点定义（论文场景业务数据）
# ════════════════════════════════════════════════════════════════

# 语义章节定义：每个章节关键词对应多个同义词/别名（用于 AI 输出的模糊匹配）
# 格式：{章节名: [同义词列表]}，匹配时任一同义词命中即视为该章节已覆盖
# 首轮解读期望章节：与提问范围（核心贡献/方法/结论）对齐；「背景」类动机内容由
# FIRST_QUESTION_KEY_POINTS 全文要点断言覆盖（本断言仅匹配 Markdown 标题，正文不参与匹配）
INTERPRET_SEMANTIC_SECTIONS: Dict[str, List[str]] = {
    "贡献": ["贡献", "核心贡献", "主要贡献", "创新", "创新点", "contribution", "novelty"],
    "方法": ["方法", "方法论", "研究方法", "技术路线", "研究设计", "methodology", "method", "approach", "模型"],
    "结论": ["结论", "总结", "研究结论", "结语", "主要结论", "conclusion", "summary", "发现"],
}

# 追问场景期望章节：追问通常要求补充评估方法/实验结果，不要求重复「背景」
FOLLOW_UP_SEMANTIC_SECTIONS: Dict[str, List[str]] = {
    "评估": ["评估", "评价", "实验", "结果", "性能", "对比", "evaluation", "experiment", "result", "基线"],
    "方法": ["方法", "方法论", "研究方法", "技术路线", "methodology", "method", "approach", "模型"],
}

# 黄金要点定义：每个要点对应多个同义词/别名（用于全文模糊匹配）
# 与 INTERPRET_SEMANTIC_SECTIONS 的区别：要点匹配不限标题，全文搜索
# 格式：{要点名: [同义词列表]}
FIRST_QUESTION_KEY_POINTS: Dict[str, List[str]] = {
    "核心贡献": [
        "核心贡献", "主要贡献", "创新点", "创新", "贡献", "核心思路", "核心思想",
        "contribution", "novel", "novelty",
    ],
    "方法": [
        "方法", "方法论", "技术路线", "模型架构", "模型设计",
        "methodology", "method", "approach", "architecture",
    ],
    "结论": [
        "结论", "总结", "研究结论", "主要结论", "关键发现", "核心发现",
        "conclusion", "finding", "summary",
    ],
}


# ════════════════════════════════════════════════════════════════
#  工具策略常量（轨迹评分器的论文场景默认参数）
# ════════════════════════════════════════════════════════════════

# 论文场景禁止工具列表（Agent 不应调用这些工具处理论文解读任务）
FORBIDDEN_TOOLS_PAPER = [
    "search_web", "search_knowledge", "execute_code",
    "delete_file", "run_command", "browser",
]

# 论文场景允许工具白名单（Agent 调用的工具必须在此集合内，子集匹配）
ALLOWED_TOOLS_PAPER = [
    "read_file", "write_file", "str_replace", "present_files",
]

# 论文场景必经工具列表（Agent 必须调用这些工具，缺一不可，必经节点匹配）
MUST_PASS_TOOLS_PAPER = [
    "read_file",
]


# ════════════════════════════════════════════════════════════════
#  工具参数校验：read_file 文件名匹配上传的 PDF
# ════════════════════════════════════════════════════════════════

def assert_read_file_matches_pdf(
    blocks: List[SseChunk],
    pdf_path: str,
) -> Dict[str, Any]:
    """断言 read_file 工具调用的文件参数与上传的 PDF 文件匹配。

    校验逻辑（按优先级）：
    1. 精确匹配：read_file 路径包含原始 PDF 文件名（后端保留文件名时适用）。
    2. 上传目录匹配：read_file 路径指向 /mnt/user-data/uploads/ 目录
       （后端将 PDF 转为 UUID 命名的 .md 文件存放于此目录）。
    如果两种方式都未匹配，视为 Agent 可能读了错误的文件。

    Args:
        blocks: SSE 事件块。
        pdf_path: 上传的 PDF 文件路径（如 "test_data/pdfs/xxx.pdf" 或绝对路径）。

    Returns:
        {"total_reads": int, "matched_reads": int, "read_paths": [str],
         "pdf_filename": str, "match_mode": str}

    断言：
        至少有一次 read_file 匹配则通过。
    """
    pdf_filename = os.path.basename(pdf_path)
    pdf_stem = os.path.splitext(pdf_filename)[0]
    # 上传目录标识（后端将 PDF 转为 .md 后存放于此）
    uploads_dir_marker = "/mnt/user-data/uploads/"

    read_calls = get_tools_by_name(blocks, "read_file")
    if not read_calls:
        return {"total_reads": 0, "matched_reads": 0, "read_paths": [],
                "pdf_filename": pdf_filename, "match_mode": "none"}

    read_paths = []
    matched_count = 0
    match_mode = "none"
    for call in read_calls:
        args = call["args_dict"]
        file_ref = ""
        for key in PATH_PARAM_KEYS:
            val = args.get(key, "")
            if val and isinstance(val, str):
                file_ref = val
                break
        if not file_ref:
            for v in args.values():
                if isinstance(v, str) and ("." in v or "/" in v or "\\" in v):
                    file_ref = v
                    break

        read_paths.append(file_ref or "(empty)")

        # 匹配判定 1：原始文件名/主名出现在路径中
        if file_ref and (pdf_filename in file_ref or pdf_stem in file_ref):
            matched_count += 1
            match_mode = "filename"
        # 匹配判定 2：路径指向上传目录（后端 UUID 重命名场景）
        elif file_ref and uploads_dir_marker in file_ref:
            matched_count += 1
            match_mode = "uploads_dir"

    assert matched_count > 0, (
        f"read_file 参数校验失败：{len(read_calls)} 次 read_file 调用均未引用上传的 PDF 文件。"
        f"\n期望包含：{pdf_filename} 或路径指向 {uploads_dir_marker}"
        f"\n实际 read_file 参数：{read_paths}"
    )
    return {
        "total_reads": len(read_calls),
        "matched_reads": matched_count,
        "read_paths": read_paths,
        "pdf_filename": pdf_filename,
        "match_mode": match_mode,
    }


# ════════════════════════════════════════════════════════════════
#  轨迹评分报告：汇总禁止工具/白名单/必经节点/调用顺序四项检查
# ════════════════════════════════════════════════════════════════

def generate_trajectory_report(
    blocks: List[SseChunk],
    forbidden_tools: List[str] = None,
    allowed_tools: List[str] = None,
    required_tools: List[str] = None,
    required_order: List[str] = None,
) -> Dict[str, Any]:
    """生成轨迹评分报告：汇总全部轨迹检查结果。

    将禁止工具、白名单子集、必经节点、调用顺序四项检查整合为一份报告。

    Args:
        blocks: SSE 事件块。
        forbidden_tools: 禁止工具黑名单（默认 FORBIDDEN_TOOLS_PAPER）。
        allowed_tools: 允许工具白名单（默认 ALLOWED_TOOLS_PAPER）。
        required_tools: 必经工具列表（默认 MUST_PASS_TOOLS_PAPER）。
        required_order: 期望的工具调用顺序（默认 ["read", "write"]）。

    Returns:
        {
            "checks": [
                {"name": "禁止工具", "passed": bool, "detail": str},
                {"name": "子集匹配", "passed": bool, "detail": str},
                {"name": "必经节点", "passed": bool, "detail": str},
                {"name": "调用顺序", "passed": bool, "detail": str},
            ],
            "total": int,
            "passed_count": int,
            "all_passed": bool,
            "tool_names": [实际调用的去重工具名列表],
        }
    """
    if forbidden_tools is None:
        forbidden_tools = FORBIDDEN_TOOLS_PAPER
    if allowed_tools is None:
        allowed_tools = ALLOWED_TOOLS_PAPER
    if required_tools is None:
        required_tools = MUST_PASS_TOOLS_PAPER
    if required_order is None:
        required_order = ["read", "write"]

    # 合并工具调用来源
    all_tool_calls = []
    all_tool_calls.extend(extract_tool_calls_from_messages(blocks))
    all_tool_calls.extend(extract_tool_calls(blocks))
    tool_names = list(set(tc.get("name", "unknown") for tc in all_tool_calls))

    checks: List[Dict[str, Any]] = []

    # 1. 禁止工具检测
    try:
        assert_no_forbidden_tools(blocks, forbidden_tools)
        checks.append({"name": "禁止工具", "passed": True, "detail": f"未调用禁止工具"})
    except AssertionError as e:
        checks.append({"name": "禁止工具", "passed": False, "detail": str(e)[:200]})

    # 2. 子集匹配
    try:
        assert_tool_subset(blocks, allowed_tools)
        checks.append({"name": "子集匹配", "passed": True, "detail": f"实际工具 ⊆ 白名单"})
    except AssertionError as e:
        checks.append({"name": "子集匹配", "passed": False, "detail": str(e)[:200]})

    # 3. 必经节点
    try:
        assert_must_pass_tools(blocks, required_tools)
        checks.append({"name": "必经节点", "passed": True, "detail": f"必经工具均已调用"})
    except AssertionError as e:
        checks.append({"name": "必经节点", "passed": False, "detail": str(e)[:200]})

    # 4. 调用顺序
    try:
        assert_tool_order(blocks, required_order)
        checks.append({"name": "调用顺序", "passed": True, "detail": f"顺序正确：{' → '.join(required_order)}"})
    except AssertionError as e:
        checks.append({"name": "调用顺序", "passed": False, "detail": str(e)[:200]})

    passed_count = sum(1 for c in checks if c["passed"])
    return {
        "checks": checks,
        "total": len(checks),
        "passed_count": passed_count,
        "all_passed": passed_count == len(checks),
        "tool_names": tool_names,
    }


# ════════════════════════════════════════════════════════════════
#  内容正确性校验：关键数据点校验（anti-hallucination）
# ════════════════════════════════════════════════════════════════

def extract_data_claims(text: str) -> List[Dict[str, str]]:
    """从文本中提取关键数据声明（数值型 + 上下文），用于忠实度校验。

    提取模式（按优先级排列）：
    1. 百分比：95.3%、约30%、超过50%
    2. 小数：3.14、0.95
    3. 千分位整数：1,500,000
    4. 带中文单位的数：1.5万、3亿
    5. 四位以上大整数：1500、20000

    排除规则：
    - 纯年份（1900-2099）：几乎必然命中，无校验价值
    - 模型版本号（如 "Llama 3.2" 中的 "3.2"）：不是数据指标

    Returns:
        去重后的数据声明列表，每项为 {"value": "65.81", "context": "LightGBM 基线 | 65.81"}。
        value 是数值本身，context 是该数值在原文中的前后 30 字符（供人工复核）。
    """
    patterns = [
        r'[约超]?(?:\d+\.?\d*)\s*%',          # 百分比
        r'(?<!\d)\d+\.\d+(?!\d)',               # 小数（排除整数中的点号）
        r'\d{1,3}(?:,\d{3})+',                   # 千分位格式
        r'\d+\.?\d*\s*[万亿]',                    # 带中文单位
        r'(?<!\d)\d{4,}(?!\d)',                   # 四位以上整数
    ]
    # 模型版本号前缀（排除 "Llama 3.2"、"GPT-4" 等模型名中的数字）
    version_prefix_pattern = re.compile(
        r'(?:llama|gpt|claude|qwen|bert|glm|chatglm|mistral|phi)\s*[- ]?\s*$',
        re.IGNORECASE,
    )
    claims = []
    seen_values = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            cleaned = match.group(0).strip()
            # 排除纯年份（1900-2099）
            if re.match(r'^(19|20)\d{2}$', cleaned):
                continue
            # 排除模型版本号：检查数值前面的文本是否匹配模型名前缀
            start = max(0, match.start() - 20)
            preceding = text[start:match.start()]
            if version_prefix_pattern.search(preceding):
                continue
            if cleaned in seen_values:
                continue
            seen_values.add(cleaned)
            # 提取上下文（前后各 80 字符，供人工复核）
            ctx_start = max(0, match.start() - 80)
            ctx_end = min(len(text), match.end() + 80)
            raw_context = text[ctx_start:ctx_end].replace('\n', ' ').strip()
            # 在上下文中用【】标记命中的数值，方便肉眼定位
            context = raw_context.replace(cleaned, f'【{cleaned}】', 1)
            claims.append({"value": cleaned, "context": context})
    return claims


def _normalize_for_comparison(s: str) -> str:
    """归一化字符串用于比对：去逗号、空白，统一中文数字单位。"""
    return s.replace(',', '').replace(' ', '').replace('，', '')


def verify_data_points(
    answer: str,
    source_text: str,
    min_claims: int = 3,
    pass_rate: float = 0.6,
    window_size: int = 300,
) -> Dict[str, Any]:
    """校验回答中的数值型数据声明是否在原文中有支撑。

    原理：从回答中提取数值型数据声明，在原文的滑动窗口中查找
    归一化后的子串匹配。命中率低于阈值则视为存在幻觉风险。

    Args:
        answer: Agent 回答文本。
        source_text: 参考原文（如 PDF 提取文本）。
        min_claims: 回答中至少包含多少个数据声明才启动校验
            （少于此数说明回答偏定性描述，无数值可校验，直接跳过）。
        pass_rate: 数据声明的最低命中率（0.0-1.0），低于此值则 failed=True。
        window_size: 原文滑动窗口大小（字符数），在每个窗口内独立查找匹配。

    Returns:
        {
            "total_claims": int,        # 提取到的数据声明总数
            "verified_claims": int,     # 在原文中找到支撑的声明数
            "unverified_claims": list,  # 未找到支撑的声明列表（含上下文，最多 10 个）
            "verification_rate": float, # 命中率（0.0-1.0）
            "passed": bool,             # 是否通过校验
            "threshold": str,           # 阈值描述（如 "≥60.0%"）
            "details": list,            # 每个数据声明的校验详情（供人工复核）
        }
    """
    claims = extract_data_claims(answer)
    if len(claims) < min_claims:
        return {
            "total_claims": len(claims),
            "verified_claims": 0,
            "unverified_claims": [],
            "verification_rate": 1.0,
            "passed": True,
            "threshold": f"需≥{min_claims}个数据声明才启动校验，实际仅{len(claims)}个",
            "details": [],
        }

    verified = 0
    unverified_list = []
    details = []  # 每个声明的校验详情

    for claim in claims:
        value = claim["value"]
        norm_value = _normalize_for_comparison(value)
        detail = {"value": value, "answer_context": claim["context"], "verified": False, "source_context": ""}

        if len(norm_value) < 2:
            # 过短的声明无校验价值，视为通过
            verified += 1
            detail["verified"] = True
            detail["source_context"] = "(过短，跳过校验)"
            details.append(detail)
            continue

        found = False
        best_source_context = ""
        # 滑动窗口扫描原文
        for i in range(0, max(1, len(source_text) - window_size + 1), window_size // 2):
            window = source_text[i:i + window_size]
            norm_window = _normalize_for_comparison(window)
            if norm_value in norm_window:
                found = True
                # 提取原文中的上下文（数值前后各 80 字符）
                norm_idx = norm_window.find(norm_value)
                # 映射回原文位置（近似）
                raw_start = max(0, i + norm_idx - 80)
                raw_end = min(len(source_text), i + norm_idx + len(norm_value) + 80)
                raw_ctx = source_text[raw_start:raw_end].replace('\n', ' ').strip()
                # 用【】标记命中的数值，方便肉眼定位
                best_source_context = raw_ctx.replace(value, f'【{value}】', 1)
                break

        detail["verified"] = found
        detail["source_context"] = best_source_context if found else "(原文中未找到)"
        details.append(detail)

        if found:
            verified += 1
        else:
            unverified_list.append({"value": value, "answer_context": claim["context"]})

    rate = verified / len(claims) if claims else 1.0
    passed = rate >= pass_rate

    return {
        "total_claims": len(claims),
        "verified_claims": verified,
        "unverified_claims": unverified_list[:10],
        "verification_rate": round(rate, 2),
        "passed": passed,
        "threshold": f"≥{pass_rate * 100:.0f}%",
        "details": details,
    }
