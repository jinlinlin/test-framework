"""通用确定性断言工具：SSE 完整性、首包耗时、工具/检索/任务事件提取与通用校验（业务无关，供各场景用例复用）。

论文场景专属断言与常量（期望章节/要点/工具策略/PDF 匹配/轨迹评分报告/数据点校验）
已下沉至 test_cases/paper_interpret/paper_asserts.py，本模块保持业务无关。
"""
import json  # 解析 OpenAI 格式 tool_calls 的 arguments JSON 字符串
import re  # 正则表达式：解析 Markdown 标题与引用标记
from typing import Any, Dict, List  # 类型标注

SseChunk = Dict[str, Any]  # 原始事件块类型别名：与 core.sse_client 产出的 chunks 元素结构一致（含 event/data/id/ts_ms）


def assert_sse_complete(blocks: List[SseChunk]) -> None:
    """断言 SSE 流完整性：无 error 事件，且有 end 结束标记或已接收大量数据（兼容服务端未正确关闭连接的情况）。

    说明：预发布环境网关可能未正确发送 chunked 终止块，导致 httpx 报错但数据已完整。
    此时 SSE 流可能缺少 end 事件，但已接收大量事件块，视为正常完成。
    """
    assert blocks, "SSE 流未产生任何事件块：可能请求未成功或流为空，无法判定完整收尾"  # 空流直接失败
    error_chunks = [b for b in blocks if b.get("event") == "error"]  # 异常事件块（SseEventPublisher.sendErrorAndComplete：event=error）
    assert not error_chunks, f"SSE 流存在异常中断：error 事件内容 {error_chunks[0].get('data')}"  # 有 error 即失败并附错误详情
    has_end = any(b.get("event") == "end" for b in blocks)  # 结束标记（SseEventPublisher.sendDone：event=end, data=[DONE]）
    has_substantial_data = len(blocks) > 20  # 大量事件块表明数据已基本完整
    assert has_end or has_substantial_data, (
        f"SSE 流缺少结束标记（event: end / data: [DONE]）且事件数不足"
        f"（仅 {len(blocks)} 个事件）：疑似中途断开或服务端未正常收尾"
    )


def assert_md_sections_semantic(
    text: str,
    semantic_sections: Dict[str, List[str]],
) -> List[str]:
    """语义章节匹配：每个章节定义多个同义词，任一命中即视为覆盖。

    适用于 AI 生成内容的章节检查，因为 AI 可能使用不同的但语义等价的标题。

    Args:
        text: Markdown 文本内容。
        semantic_sections: 语义章节定义，格式为 {章节名: [同义词列表]}。
            例如: {"背景": ["背景", "引言", "introduction"]}

    Returns:
        缺失章节列表（空列表=全部覆盖）。

    示例:
        >>> sections = {"背景": ["背景", "引言", "introduction"]}
        >>> missing = assert_md_sections_semantic(text, sections)
        >>> # 若标题包含"引言"或"Introduction"，则"背景"视为已覆盖
    """
    # 提取全部标题并归一化（去空白、转小写）
    headings = re.findall(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", text, flags=re.MULTILINE)
    normalized = [re.sub(r"\s+", "", h).lower() for h in headings]

    missing: List[str] = []
    for section_name, synonyms in semantic_sections.items():
        # 检查任一同义词是否命中任一标题
        covered = False
        for synonym in synonyms:
            key = re.sub(r"\s+", "", synonym).lower()
            if any(key in h for h in normalized):
                covered = True
                break
        if not covered:
            missing.append(section_name)

    return missing


def assert_key_points_covered(
    text: str,
    key_points: Dict[str, List[str]],
) -> Dict[str, Any]:
    """校验回答是否覆盖了期望的关键要点（全文搜索，不限标题）。

    与 assert_md_sections_semantic 的区别：
    - 章节匹配只检查 Markdown 标题
    - 要点匹配在全文中搜索同义词，更宽松

    Args:
        text: 待检查的文本（Agent 回答或生成文档）。
        key_points: 要点定义，格式为 {要点名: [同义词列表]}。

    Returns:
        {
            "covered": [已覆盖的要点名],
            "missing": [缺失的要点名],
            "hit_details": {要点名: 命中的同义词},
            "passed": bool,
        }
    """
    text_lower = text.lower()
    covered = []
    missing = []
    hit_details = {}

    for point_name, synonyms in key_points.items():
        hit_synonym = ""
        for synonym in synonyms:
            if synonym.lower() in text_lower:
                hit_synonym = synonym
                break
        if hit_synonym:
            covered.append(point_name)
            hit_details[point_name] = hit_synonym
        else:
            missing.append(point_name)

    return {
        "covered": covered,
        "missing": missing,
        "hit_details": hit_details,
        "passed": len(missing) == 0,
    }


def extract_first_chunk_time(blocks: List[SseChunk]) -> float:
    """返回首包耗时（毫秒）：取首个事件块的 ts_ms（由 core.sse_client 在分发事件时记录）。"""
    if not blocks:  # 空流无首包可言
        return 0.0
    return float(blocks[0].get("ts_ms", 0.0))  # 首个事件块相对流起点的到达毫秒数


def extract_generated_document(blocks: List[SseChunk]) -> str:
    """从 values 事件中提取 Agent 通过 write_file 工具生成的文档内容。

    Agent 最终输出通常是一个 MD 文档（如论文解读），通过 write_file 工具调用写入。
    该文档才是页面上展示给用户的内容，而非 SSE 原始文本流（含 skill 指令、论文原文等中间内容）。

    策略：遍历所有 values 事件，找到 write_file 工具调用，取第一次调用的 content 字段。
    Agent 首次 write_file 写入的才是页面展示给用户的文档（如论文解读 MD），
    后续 write_file 可能覆盖写入辅助数据（如数据集 JSON），不应作为评估对象。
    兼容两种 tool_calls 格式：
    - LangGraph 格式：顶层 tool_calls，tc["name"] + tc["args"]（dict）
    - OpenAI 格式：additional_kwargs.tool_calls，tc["function"]["name"] + tc["function"]["arguments"]（JSON 字符串）

    Returns:
        文档内容字符串；若未找到则返回空串。
    """
    document_content = ""
    for block in blocks:
        if block.get("event") != "values":
            continue
        data = block.get("data")
        if not isinstance(data, dict):
            continue
        messages = data.get("messages")
        if not isinstance(messages, list):
            continue
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            # 收集两种格式的 tool_calls
            all_tool_calls = []
            # 格式 1：LangGraph 顶层 tool_calls
            top_tc = msg.get("tool_calls") or []
            all_tool_calls.extend(top_tc)
            # 格式 2：OpenAI additional_kwargs.tool_calls
            akw_tc = msg.get("additional_kwargs", {}).get("tool_calls") or []
            all_tool_calls.extend(akw_tc)

            for tc in all_tool_calls:
                if not isinstance(tc, dict):
                    continue
                # 解析工具名（兼容两种格式）
                name = tc.get("name", "") or tc.get("function", {}).get("name", "")
                if name != "write_file":
                    continue
                # 解析参数（兼容 dict 和 JSON 字符串）
                args = tc.get("args")
                if args is None:
                    raw_args = tc.get("function", {}).get("arguments", "")
                    if isinstance(raw_args, str) and raw_args:
                        try:
                            args = json.loads(raw_args)
                        except (json.JSONDecodeError, ValueError):
                            continue
                    elif isinstance(raw_args, dict):
                        args = raw_args
                if not isinstance(args, dict):
                    continue
                content = args.get("content", "")
                if content and not document_content:
                    # 跳过 JSON 格式的辅助数据（验证卡片、数据集等），只提取 Markdown 文档
                    stripped = content.lstrip()
                    if stripped.startswith("{") or stripped.startswith("["):
                        continue
                    document_content = content  # 取第一次 write_file 的 Markdown 内容
    return document_content


def extract_new_generated_document(blocks: List[SseChunk], old_document: str) -> str:
    """从 values 事件中提取追问新生成的文档（排除首次提问的历史文档）。

    多轮会话中，追问 SSE 的 values 快照会携带首轮消息及其 write_file 调用，
    导致 extract_generated_document() 拿到历史文档而非追问新生成的文档。
    本函数遍历所有 write_file 调用，返回第一个与 old_document 不同的内容。

    Args:
        blocks: SSE 事件块（追问轮的 chunks）。
        old_document: 首次提问生成的文档内容（用于排除历史快照）。

    Returns:
        追问新生成的文档内容；若未找到则返回空串。
    """
    if not old_document:
        return extract_generated_document(blocks)
    old_prefix = old_document[:200]
    for block in blocks:
        if block.get("event") != "values":
            continue
        data = block.get("data")
        if not isinstance(data, dict):
            continue
        messages = data.get("messages")
        if not isinstance(messages, list):
            continue
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            all_tool_calls = []
            all_tool_calls.extend(msg.get("tool_calls") or [])
            all_tool_calls.extend(msg.get("additional_kwargs", {}).get("tool_calls") or [])
            for tc in all_tool_calls:
                if not isinstance(tc, dict):
                    continue
                name = tc.get("name", "") or tc.get("function", {}).get("name", "")
                if name != "write_file":
                    continue
                args = tc.get("args")
                if args is None:
                    raw_args = tc.get("function", {}).get("arguments", "")
                    if isinstance(raw_args, str) and raw_args:
                        try:
                            args = json.loads(raw_args)
                        except (json.JSONDecodeError, ValueError):
                            continue
                    elif isinstance(raw_args, dict):
                        args = raw_args
                if not isinstance(args, dict):
                    continue
                content = args.get("content", "")
                if not content:
                    continue
                # 跳过 JSON 格式的辅助数据（验证卡片、数据集等），只提取 Markdown 文档
                stripped = content.lstrip()
                if stripped.startswith("{") or stripped.startswith("["):
                    continue
                # 跳过与历史文档相同的内容
                if content[:200] == old_prefix:
                    continue
                return content
    return ""


def extract_ai_final_response(blocks: List[SseChunk]) -> str:
    """从 messages 事件中提取 AI 的最终回答（排除系统指令、工具结果、思考过程）。

    SSE 流中的 messages 事件包含大量中间内容：
    - <uploaded_files> 系统元数据
    - Skill 指令模板
    - read_file 读出的论文原文
    - Agent 思考过程（thinking/reasoning_content）
    - AI 最终回答（流式分片）

    本函数只提取 AI 的最终回答：最后一个 AIMessage/AIMessageChunk 的文本内容。

    Args:
        blocks: SSE 事件块列表。

    Returns:
        AI 的最终回答文本；若未找到则返回空串。
    """
    # 收集所有 AI 消息的文本
    ai_messages: List[str] = []
    
    for block in blocks:
        if block.get("event") not in ("messages", "message", "messages-tuple"):
            continue
        data = block.get("data")
        if not data:
            continue
        
        # 解析消息结构
        msg = None
        if isinstance(data, dict) and isinstance(data.get("message"), dict):
            # 知识库格式：{"message": {"role": "assistant", "content": "..."}}
            msg = data["message"]
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            # LangGraph messages-tuple：[message, metadata]
            msg = data[0]
        elif isinstance(data, dict) and "content" in data:
            # 单消息直传：{"content": ...}
            msg = data
        
        if not msg:
            continue
        
        # 检查是否是 AI 消息（兼容多种格式）
        msg_type = msg.get("type", "")
        role = msg.get("role", "")
        is_ai_message = (
            msg_type in ("AIMessageChunk", "AIMessage") or
            role == "assistant"
        )
        if not is_ai_message:
            continue
        
        # 跳过工具调用消息
        tool_calls = msg.get("tool_calls") or msg.get("additional_kwargs", {}).get("tool_calls") or []
        if tool_calls:
            continue
        
        # 提取文本内容
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            # 跳过明显是系统指令或中间处理的内容
            if content.startswith("<uploaded_files>"):
                continue
            # 跳过论文原文（通常很长且包含特定标记）
            if len(content) > 1000 and ("Abstract" in content or "Introduction" in content):
                continue
            ai_messages.append(content)
        elif isinstance(content, list):
            # ContentPart 格式：[{"type": "text", "text": "..."}]
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                    text_parts.append(part["text"])
            if text_parts:
                combined = "".join(text_parts)
                # 跳过明显是系统指令或中间处理的内容
                if combined.startswith("<uploaded_files>"):
                    continue
                # 跳过论文原文
                if len(combined) > 1000 and ("Abstract" in combined or "Introduction" in combined):
                    continue
                ai_messages.append(combined)
    
    # 拼接所有 AI 消息（因为流式分片可能分散在多个消息中）
    if ai_messages:
        return "".join(ai_messages)
    return ""


def extract_str_replace_edits(blocks: List[SseChunk]) -> List[Dict[str, str]]:
    """从 values 事件中提取 str_replace 工具调用（Agent 对已有文档的编辑）。

    追问场景下 Agent 可能不创建新文档，而是通过 str_replace 编辑首次提问生成的文档。
    此函数提取所有 str_replace 调用的编辑详情。

    str_replace 参数格式（LangGraph 顶层 tool_calls）：
    - path: 被编辑的文件路径
    - old_str: 被替换的原始文本
    - new_str: 替换后的新文本
    - description: 编辑描述（可选）

    Returns:
        编辑记录列表，每项包含 {path, old_str, new_str, description}。
    """
    edits = []
    seen = set()  # 去重：同一编辑在多个 values 快照中会重复出现
    for block in blocks:
        if block.get("event") != "values":
            continue
        data = block.get("data")
        if not isinstance(data, dict):
            continue
        messages = data.get("messages")
        if not isinstance(messages, list):
            continue
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            # 仅支持 LangGraph 顶层 tool_calls 格式（已确认 str_replace 以此格式出现）
            for tc in msg.get("tool_calls", []):
                if not isinstance(tc, dict):
                    continue
                name = tc.get("name", "")
                if name != "str_replace":
                    continue
                args = tc.get("args")
                if args is None:
                    # 尝试 OpenAI 格式
                    raw_args = tc.get("function", {}).get("arguments", "")
                    if isinstance(raw_args, str) and raw_args:
                        try:
                            args = json.loads(raw_args)
                        except (json.JSONDecodeError, ValueError):
                            continue
                    elif isinstance(raw_args, dict):
                        args = raw_args
                if not isinstance(args, dict):
                    continue
                path = args.get("path", "")
                old_str = args.get("old_str", "")
                new_str = args.get("new_str", "")
                description = args.get("description", "")
                if not new_str:
                    continue
                # 去重键：path + old_str 前 100 字 + new_str 前 100 字
                dedup_key = (path, old_str[:100], new_str[:100])
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                edits.append({
                    "path": path,
                    "old_str": old_str,
                    "new_str": new_str,
                    "description": description,
                })
    return edits


def extract_str_replace_content(blocks: List[SseChunk]) -> str:
    """从 values 事件中提取 str_replace 编辑的新增内容，拼接为完整文本。

    用于追问场景：Agent 通过 str_replace 编辑已有文档，提取所有 new_str 拼接
    作为追问生成的内容，供 Judge 评分。

    Returns:
        所有 str_replace 编辑的 new_str 拼接结果；若无 str_replace 调用则返回空串。
    """
    edits = extract_str_replace_edits(blocks)
    if not edits:
        return ""
    parts = []
    for edit in edits:
        if edit["new_str"]:
            parts.append(edit["new_str"])
    return "\n\n".join(parts)


def extract_pdf_text(pdf_path: str, max_chars: int = 150000) -> str:
    """从 PDF 文件中提取文本内容，作为 Judge 评审的参考依据。

    使用 pypdf 库解析 PDF，逐页提取文本并拼接。
    若提取文本超过 max_chars，则截取前 max_chars 字符。
    默认 150000 字可覆盖绝大多数论文全文（配合 qwen-long 1M 上下文窗口）。

    Args:
        pdf_path: PDF 文件路径（绝对或相对路径）。
        max_chars: 最大返回字符数，默认 150000（配合 qwen-long 可装入全文）。

    Returns:
        提取的文本内容；若解析失败则返回空串。
    """
    try:
        from pypdf import PdfReader  # 延迟导入：仅在实际调用时加载 pypdf
        reader = PdfReader(pdf_path)
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(text)
        full_text = "\n\n".join(pages_text)
        if len(full_text) > max_chars:
            return full_text[:max_chars] + f"\n\n--- [论文原文截取前 {max_chars:,} 字，共 {len(full_text):,} 字] ---"
        return full_text
    except ImportError:
        return ""  # pypdf 未安装，静默降级
    except Exception:
        return ""  # PDF 解析失败，静默降级


# ======================================================================
# Agent 行为断言工具：基于 LangGraph SSE 事件链路分析
# ======================================================================

# LangGraph 事件类型常量（对齐前端 stream.ts 的 LangGraphEventType）
LANGGRAPH_TOOL_EVENTS = ("on_tool_start", "on_tool_end")  # 工具调用事件
LANGGRAPH_RETRIEVER_EVENTS = ("on_retriever_start", "on_retriever_end")  # RAG 检索事件
LANGGRAPH_LLM_EVENTS = ("on_chat_model_start", "on_chat_model_end", "on_llm_start", "on_llm_end")  # LLM 调用事件
LANGGRAPH_CHAIN_EVENTS = ("on_chain_start", "on_chain_end")  # LangGraph 链执行事件
TASK_LIFECYCLE_EVENTS = ("task_started", "task_running", "task_completed", "task_failed", "task_timed_out")  # 子代理任务生命周期


def filter_events(blocks: List[SseChunk], event_types: Any) -> List[SseChunk]:
    """按事件类型过滤 SSE 事件块：支持单个类型（字符串）或多个类型（元组/列表）。"""
    if isinstance(event_types, str):  # 单个类型转为元组
        event_types = (event_types,)
    return [b for b in blocks if b.get("event") in event_types]  # 返回匹配的事件块列表


def extract_tool_calls(blocks: List[SseChunk]) -> List[Dict[str, Any]]:
    """提取全部工具调用事件，返回 [{event, name, data, ts_ms}, ...] 列表。

    解析 LangGraph on_tool_start / on_tool_end 事件，提取工具名与输入/输出。
    """
    tool_events = filter_events(blocks, LANGGRAPH_TOOL_EVENTS)  # 过滤工具调用事件
    result: List[Dict[str, Any]] = []  # 收集解析后的工具调用
    for event in tool_events:  # 逐个解析
        data = event.get("data") or {}  # 事件数据
        name = ""  # 工具名
        if isinstance(data, dict):  # 标准格式：data 为字典
            name = data.get("name", "") or data.get("tool", "")  # 工具名可能在 name 或 tool 字段
        elif isinstance(data, str):  # 某些格式 data 为字符串
            name = data
        result.append({
            "event": event.get("event"),  # on_tool_start 或 on_tool_end
            "name": name,  # 工具名
            "data": data,  # 原始数据（含输入/输出）
            "ts_ms": event.get("ts_ms"),  # 到达时间戳
        })
    return result


def extract_tool_results(blocks: List[SseChunk]) -> Dict[str, Dict[str, Any]]:
    """按 tool_call_id 索引工具返回值（消息流里 type=tool 的 ToolMessage）。

    为什么单独抽：values 快照里 AI 消息的 tool_calls 与紧随其后的 tool 消息通过
    tool_call_id 精确配对，而 extract_tool_calls_from_messages 此前只取「调用」
    不取「返回」——导致 Trace 里看不见“读了哪个文件的哪一段、返回了什么”。
    实测钉（2026-10-28）：单次文献解读的 3 次 read_file 返回内容是 6K~8K 字的
    论文原文，正是判断“张冠李戴”类缺陷的关键证据，不取回等于白跑。

    Returns:
        {tool_call_id: {name, status, result, ts_ms}}；同一 id 出现在多个 values
        快照时保留最后一次（与 usage_metadata 去重同规则）。
    """
    index: Dict[str, Dict[str, Any]] = {}
    # values 快照（累积状态，含完整 ToolMessage）+ messages 事件（流式增量兼容路径）
    for event in filter_events(blocks, ("values", "messages")):
        data = event.get("data")
        if isinstance(data, dict):
            candidates = data.get("messages") or []
        elif isinstance(data, list):
            candidates = data
        else:
            continue
        for msg in candidates:
            if not isinstance(msg, dict) or msg.get("type") != "tool":
                continue
            tc_id = msg.get("tool_call_id")
            if not tc_id:
                continue
            content = msg.get("content")
            if isinstance(content, list):
                # 分块/多态 content：拼接其中的文本部分
                content = "".join(
                    str(p.get("text", p)) if isinstance(p, dict) else str(p) for p in content
                )
            index[tc_id] = {
                "name": msg.get("name", ""),
                "status": msg.get("status", ""),
                "result": "" if content is None else str(content),
                "ts_ms": event.get("ts_ms"),
            }
    return index


def extract_tool_calls_from_messages(blocks: List[SseChunk]) -> List[Dict[str, Any]]:
    """从 SSE blocks 中提取工具调用信息（含完整参数与返回值）。

    提取策略（按优先级）：
    1. 优先从 values 事件提取：values 事件包含 LangGraph 的完整累积状态，
       其中 messages 列表里的 tool_calls 包含完整参数（name + args）。
    2. 回退到 messages 事件：messages 事件中的 tool_calls 是流式增量传输的，
       参数可能不完整（name 和 args 分散在不同事件中）。

    返回值配对：两种策略都通过 extract_tool_results 按 tool_call_id 挂回工具的
    实际返回（result/status）；未命中（服务端未透传 ToolMessage）时不挂该键，
    下游按“无返回值”处理，不会伪造空结果。

    Returns:
        [{name, args, ts_ms, tool_call_id, status?, result?}, ...] 工具调用列表。
    """
    tool_results = extract_tool_results(blocks)  # tool_call_id → 返回内容索引

    # --- 策略 1：从 values 事件提取（完整参数） ---
    values_events = filter_events(blocks, "values")
    if values_events:
        # 取最后一个 values 事件（包含最完整的累积状态）
        last_values = values_events[-1]
        data = last_values.get("data")
        if isinstance(data, dict):
            msgs = data.get("messages", [])
            if isinstance(msgs, list) and msgs:
                result: List[Dict[str, Any]] = []
                seen_ids: set = set()
                for msg in msgs:
                    if not isinstance(msg, dict):
                        continue
                    for tc in (msg.get("tool_calls") or []):
                        if not isinstance(tc, dict):
                            continue
                        name = tc.get("name", "") or tc.get("function", {}).get("name", "")
                        tc_id = tc.get("id", "")
                        if not name:
                            continue
                        # 按 tool call id 去重（values 中同一 tool_call 在多个 messages 事件中重复出现）
                        dedup_key = tc_id if tc_id else f"{name}:{str(tc.get('args', ''))[:80]}"
                        if dedup_key in seen_ids:
                            continue
                        seen_ids.add(dedup_key)
                        args = tc.get("args") or tc.get("function", {}).get("arguments") or {}
                        item: Dict[str, Any] = {
                            "name": name,
                            "args": args,
                            "ts_ms": last_values.get("ts_ms"),
                            "tool_call_id": tc_id,
                        }
                        # 返回值配对：仅命中才挂键，避免未透传时伪造空结果
                        _tr = tool_results.get(tc_id) if tc_id else None
                        if _tr:
                            item["status"] = _tr["status"]
                            item["result"] = _tr["result"]
                        result.append(item)
                if result:
                    return result

    # --- 策略 2：回退到 messages 事件（参数可能不完整） ---
    messages_events = filter_events(blocks, "messages")
    result = []
    seen_tools = set()

    for event in messages_events:
        data = event.get("data")
        if not isinstance(data, list) or not data:
            continue
        msg = data[0]
        if not isinstance(msg, dict):
            continue

        top_level_tcs = msg.get("tool_calls") or []
        kwargs_tcs = msg.get("additional_kwargs", {}).get("tool_calls") or []
        tool_calls = kwargs_tcs if kwargs_tcs else top_level_tcs
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            name = tc.get("name", "") or tc.get("function", {}).get("name", "")
            if not name:
                continue
            args = tc.get("args") or tc.get("function", {}).get("arguments") or {}
            dedup_key = f"{name}:{str(args)[:100]}:{event.get('ts_ms', 0) // 1000}"
            if dedup_key in seen_tools:
                continue
            seen_tools.add(dedup_key)

            item = {
                "name": name,
                "args": args,
                "ts_ms": event.get("ts_ms"),
                "tool_call_id": tc.get("id", ""),
            }
            _tr = tool_results.get(tc.get("id", "")) if tc.get("id") else None
            if _tr:
                item["status"] = _tr["status"]
                item["result"] = _tr["result"]
            result.append(item)

    return result


def extract_retriever_events(blocks: List[SseChunk]) -> List[Dict[str, Any]]:
    """提取 RAG 检索事件，返回 [{event, data, ts_ms}, ...] 列表。

    解析 LangGraph on_retriever_start / on_retriever_end 事件。
    """
    retriever_events = filter_events(blocks, LANGGRAPH_RETRIEVER_EVENTS)  # 过滤检索事件
    return [{
        "event": e.get("event"),  # on_retriever_start 或 on_retriever_end
        "data": e.get("data"),  # 原始数据（含检索到的文档）
        "ts_ms": e.get("ts_ms"),  # 到达时间戳
    } for e in retriever_events]


def extract_task_events(blocks: List[SseChunk]) -> List[Dict[str, Any]]:
    """提取子代理任务生命周期事件，返回 [{event, taskId, data, ts_ms}, ...] 列表。"""
    task_events = filter_events(blocks, TASK_LIFECYCLE_EVENTS)  # 过滤任务事件
    return [{
        "event": e.get("event"),  # task_started / task_running / task_completed / task_failed / task_timed_out
        "data": e.get("data"),  # 原始数据（含 taskId、result、error 等）
        "ts_ms": e.get("ts_ms"),  # 到达时间戳
    } for e in task_events]


def assert_tool_called(blocks: List[SseChunk], tool_name_pattern: str = "") -> List[Dict[str, Any]]:
    """断言 Agent 调用了匹配指定名称模式的工具。

    tool_name_pattern 为大小写不敏感的子串匹配；空串表示任意工具调用即可。
    返回匹配的工具调用事件列表。
    """
    tool_calls = extract_tool_calls(blocks)  # 提取全部工具调用
    assert tool_calls, (
        f"Agent 未调用任何工具：SSE 流中未发现 on_tool_start/on_tool_end 事件。"
        f"全部事件类型：{sorted(set(b.get('event') for b in blocks))}"
    )
    if tool_name_pattern:  # 有名称模式时进一步过滤
        pattern_lower = tool_name_pattern.lower()  # 大小写不敏感
        matched = [t for t in tool_calls if pattern_lower in t["name"].lower()]
        assert matched, (
            f"Agent 未调用匹配 '{tool_name_pattern}' 的工具。"
            f"实际调用的工具：{[t['name'] for t in tool_calls]}"
        )
        return matched
    return tool_calls


def assert_retriever_executed(blocks: List[SseChunk]) -> List[Dict[str, Any]]:
    """断言 Agent 执行了 RAG 检索（知识库/文档检索）。"""
    retriever_events = extract_retriever_events(blocks)  # 提取检索事件
    assert retriever_events, (
        f"Agent 未执行 RAG 检索：SSE 流中未发现 on_retriever_start/on_retriever_end 事件。"
        f"全部事件类型：{sorted(set(b.get('event') for b in blocks))}"
    )
    return retriever_events


def assert_llm_called(blocks: List[SseChunk]) -> List[SseChunk]:
    """断言 Agent 调用了 LLM（大语言模型）。

    支持两种事件协议：
    1. LangGraph 底层事件：on_chat_model_start/end、on_llm_start/end
    2. 应用层事件：messages（AI 增量内容）、values（LangGraph 状态快照含 AI 输出）
    """
    # 优先查找 LangGraph 底层 LLM 事件
    llm_events = filter_events(blocks, LANGGRAPH_LLM_EVENTS)
    if llm_events:
        return llm_events
    # 回退到应用层事件：messages 事件是 AI 生成内容的直接证据
    app_llm_events = filter_events(blocks, ("messages", "values"))
    assert app_llm_events, (
        f"Agent 未调用 LLM：SSE 流中未发现 LLM 调用证据（LangGraph: on_chat_model_start/end；"
        f"应用层: messages/values）。全部事件类型：{sorted(set(b.get('event') for b in blocks))}"
    )
    return app_llm_events


def extract_token_usage(blocks: List[SseChunk]) -> Dict[str, Any]:
    """提取被测 Agent 的 LLM token 用量（服务端随 values 快照透传的 usage_metadata）。

    数据源：values 事件（LangGraph 累积状态快照）中 messages 列表内
    AI 消息的 usage_metadata（LangChain 标准字段，含 input/output/total_tokens）。

    去重（关键）：values 是累积快照，同一条 AI 消息会在多个 values 事件中
    重复出现（实测同一 id 出现 4+ 次），不去重 token 会虚报数倍。按消息 id
    去重，且**保留最后一次出现**——token_usage_attribution.kind（tool_batch /
    final_answer）在后续快照中才补全，首次出现时可能缺失。

    Returns:
        {
            "total_tokens": int, "input_tokens": int, "output_tokens": int,
            "llm_call_count": int,               # 去重后的 LLM 调用轮数
            "tool_batch_tokens": int,            # 工具调用轮 token 合计
            "final_answer_tokens": int,          # 最终回答轮 token
            "per_message": [{id, kind, input_tokens, output_tokens, total_tokens}],
        }
        无任何 usage_metadata 时 total_tokens 为 0（服务端未透传或本轮无 LLM 调用）。
    """
    seen: Dict[str, Dict[str, Any]] = {}  # msg_id -> 最后一次快照中的 usage 记录
    for event in filter_events(blocks, ("values",)):
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        for msg in data.get("messages") or []:
            if not isinstance(msg, dict) or "usage_metadata" not in msg:
                continue
            um = msg.get("usage_metadata") or {}
            if not isinstance(um, dict):
                continue
            mid = msg.get("id") or f"no-id@{event.get('ts_ms', 0)}"
            # 归属标记可能挂在消息顶层、response_metadata 或 additional_kwargs
            attrib = (
                msg.get("token_usage_attribution")
                or (msg.get("response_metadata") or {}).get("token_usage_attribution")
                or (msg.get("additional_kwargs") or {}).get("token_usage_attribution")
            )
            kind = attrib.get("kind", "") if isinstance(attrib, dict) else ""
            # 保留最后一次出现（kind 随快照演进补全）
            seen[mid] = {
                "id": mid,
                "kind": kind,
                "input_tokens": um.get("input_tokens", 0) or 0,
                "output_tokens": um.get("output_tokens", 0) or 0,
                "total_tokens": um.get("total_tokens", 0) or 0,
            }

    per_message = list(seen.values())
    total = sum(m["total_tokens"] for m in per_message)
    return {
        "total_tokens": total,
        "input_tokens": sum(m["input_tokens"] for m in per_message),
        "output_tokens": sum(m["output_tokens"] for m in per_message),
        "llm_call_count": len(per_message),
        "tool_batch_tokens": sum(m["total_tokens"] for m in per_message if m["kind"] == "tool_batch"),
        "final_answer_tokens": sum(m["total_tokens"] for m in per_message if m["kind"] == "final_answer"),
        "per_message": per_message,
    }


def summarize_agent_trace(blocks: List[SseChunk]) -> Dict[str, Any]:
    """汇总 Agent 执行链路摘要，返回 {tool_calls, retriever_events, task_events, llm_events, all_event_types}。

    工具调用提取策略：优先走 on_tool_start/end 事件（标准 LangGraph 格式），
    若为空则回退到 messages 事件的 tool_calls 字段（后端不透传 on_tool_* 时的兼容路径）。
    LLM 事件同理：优先走 on_chat_model_start/end，回退到 messages 事件计数。
    """
    # 工具调用：on_tool_start/end → messages tool_calls 回退
    tool_calls = extract_tool_calls(blocks)
    if not tool_calls:
        tool_calls = extract_tool_calls_from_messages(blocks)
    # LLM 事件：on_chat_model_start/end → messages 事件回退
    llm_events = filter_events(blocks, LANGGRAPH_LLM_EVENTS)
    if not llm_events:
        llm_events = filter_events(blocks, ("messages",))
    return {
        "tool_calls": tool_calls,
        "retriever_events": extract_retriever_events(blocks),
        "task_events": extract_task_events(blocks),
        "llm_events": llm_events,
        "all_event_types": sorted(set(b.get("event") for b in blocks)),
    }


def generate_agent_summary(
    blocks: List[SseChunk],
    text: str,
    timing: Dict[str, float],
    case_name: str = "",
    conversation_id: Any = None,
    model_name: str = "",
    thread_id: str = "",
) -> str:
    """生成 Agent 执行摘要（人类可读的 Markdown 格式）。

    包含：基本信息、执行时间线、统计摘要、关键事件详情。
    输出为 Markdown 文本，可直接保存为 .md 文件供人工查阅。
    """
    lines: List[str] = []  # 输出行收集

    # ── 标题 ──
    title = f"Agent 执行摘要 · {case_name}" if case_name else "Agent 执行摘要"
    lines.append(f"# {title}")
    lines.append("")

    # ── 基本信息 ──
    lines.append("## 基本信息")
    lines.append("")
    if conversation_id:
        lines.append(f"- **会话 ID**：{conversation_id}")
    if thread_id:
        lines.append(f"- **Thread ID**：{thread_id}")
    if model_name:
        lines.append(f"- **模型**：{model_name}")
    lines.append(f"- **SSE 事件总数**：{len(blocks)}")
    lines.append(f"- **AI 回答字数**：{len(text):,}")
    lines.append("")

    # ── 性能统计 ──
    lines.append("## 性能统计")
    lines.append("")
    first_ms = timing.get("first_chunk_ms", 0)
    total_ms = timing.get("total_ms", 0)
    lines.append(f"- **首包耗时**：{first_ms:.0f} ms")
    lines.append(f"- **总耗时**：{total_ms:.0f} ms（{total_ms / 1000:.1f} 秒）")
    if total_ms > 0:
        lines.append(f"- **平均事件间隔**：{total_ms / max(len(blocks), 1):.1f} ms")

    # Token 用量（values 快照透传的 usage_metadata，按消息 id 去重）
    token_usage = extract_token_usage(blocks)
    if token_usage["total_tokens"] > 0:
        lines.append("")
        lines.append("## Token 用量")
        lines.append("")
        lines.append(f"- **总消耗**：{token_usage['total_tokens']:,} tokens（输入 {token_usage['input_tokens']:,} + 输出 {token_usage['output_tokens']:,}）")
        lines.append(f"- **LLM 调用轮数**：{token_usage['llm_call_count']} 轮")
        _tb = token_usage["tool_batch_tokens"]
        _fa = token_usage["final_answer_tokens"]
        if _tb or _fa:
            lines.append(f"- **归属分解**：工具调用轮 {_tb:,} tokens，最终回答轮 {_fa:,} tokens")
    lines.append("")

    # ── 执行时间线 ──
    lines.append("## 执行时间线")
    lines.append("")
    lines.append("```")

    # 提取关键事件（按时间顺序，每类事件只取前 N 个代表性事件）
    timeline_events: List[Dict[str, Any]] = []  # 时间线事件收集
    seen_event_types: Dict[str, int] = {}  # 每种事件类型已添加的计数

    for block in blocks:
        event_name = block.get("event", "unknown")
        ts_ms = block.get("ts_ms", 0)
        data = block.get("data")

        # 关键事件类型：全部加入时间线
        if event_name in ("start", "end", "error"):
            timeline_events.append({"ts_ms": ts_ms, "event": event_name, "data": data})
            continue

        # progress 事件：只加入包含关键字的（文件上传/跳过等）
        if event_name == "progress":
            if isinstance(data, str) and any(kw in data for kw in ("文件上传", "跳过", "完成", "失败")):
                timeline_events.append({"ts_ms": ts_ms, "event": event_name, "data": data})
            continue

        # metadata 事件：加入（含 thread_id 等关键信息）
        if event_name == "metadata":
            timeline_events.append({"ts_ms": ts_ms, "event": event_name, "data": data})
            continue

        # intent_recognition 事件：加入（意图识别）
        if event_name == "intent_recognition":
            timeline_events.append({"ts_ms": ts_ms, "event": event_name, "data": data})
            continue

        # conversation_id / thread_id 事件：加入
        if event_name in ("conversation_id", "thread_id"):
            timeline_events.append({"ts_ms": ts_ms, "event": event_name, "data": data})
            continue

        # messages/values 事件：只取首尾各一个
        if event_name in ("messages", "values", "message"):
            count = seen_event_types.get(event_name, 0)
            if count < 2:  # 取前 2 个
                timeline_events.append({"ts_ms": ts_ms, "event": event_name, "data": "..."})
            seen_event_types[event_name] = count + 1
            continue

        # 其他事件：统计但不加入时间线
        seen_event_types[event_name] = seen_event_types.get(event_name, 0) + 1

    # 找到最后一个 messages 事件（AI 生成完成）
    last_msg_event = None
    for block in reversed(blocks):
        if block.get("event") in ("messages", "values", "message"):
            last_msg_event = {"ts_ms": block.get("ts_ms", 0), "event": block.get("event"), "data": "AI 生成完成"}
            break
    if last_msg_event:
        timeline_events.append(last_msg_event)

    # 按时间排序并输出
    timeline_events.sort(key=lambda x: x.get("ts_ms", 0))
    for evt in timeline_events:
        ts = evt["ts_ms"]
        event_name = evt["event"]
        data = evt.get("data", "")
        # 格式化 data 摘要
        data_str = ""
        if isinstance(data, str):
            data_str = data[:60]  # 截断过长内容
        elif isinstance(data, dict):
            # 提取关键信息
            if "thread_id" in data:
                data_str = f"thread_id={data['thread_id'][:20]}..."
            elif "intent" in data:
                data_str = f"intent={data['intent']}"
            else:
                data_str = str(data)[:60]
        lines.append(f"[{ts:>8.0f}ms]  {event_name:<20}  {data_str}")

    lines.append("```")
    lines.append("")

    # ── 事件类型统计 ──
    lines.append("## 事件类型统计")
    lines.append("")
    lines.append("| 事件类型 | 数量 |")
    lines.append("|----------|------|")
    event_counts: Dict[str, int] = {}
    for block in blocks:
        event_name = block.get("event", "unknown")
        event_counts[event_name] = event_counts.get(event_name, 0) + 1
    for event_name, count in sorted(event_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {event_name} | {count} |")
    lines.append("")

    # ── Agent 行为分析 ──
    trace = summarize_agent_trace(blocks)
    lines.append("## Agent 行为分析")
    lines.append("")

    # LLM 调用
    llm_count = len(trace["llm_events"])
    lines.append(f"- **LLM 调用**：{llm_count} 次")

    # 工具调用
    tool_count = len(trace["tool_calls"])
    if tool_count > 0:
        tool_names = [t.get("name", "unknown") for t in trace["tool_calls"]]
        lines.append(f"- **工具调用**：{tool_count} 次（{', '.join(tool_names[:5])}）")
    else:
        lines.append("- **工具调用**：未检测到（后端可能不透传 on_tool_start/end）")

    # RAG 检索
    retriever_count = len(trace["retriever_events"])
    if retriever_count > 0:
        lines.append(f"- **RAG 检索**：{retriever_count} 次")

    # 任务生命周期
    task_count = len(trace["task_events"])
    if task_count > 0:
        task_types = [t.get("event", "") for t in trace["task_events"]]
        lines.append(f"- **任务生命周期**：{task_count} 个事件（{', '.join(set(task_types))}）")

    lines.append("")

    # ── 文件上传状态 ──
    progress_events = [b for b in blocks if b.get("event") == "progress"]
    upload_completed = any(
        isinstance(b.get("data"), str) and "文件上传完成" in b["data"]
        for b in progress_events
    )
    upload_skipped = any(
        isinstance(b.get("data"), str) and "跳过文件上传" in b["data"]
        for b in progress_events
    )
    if upload_completed or upload_skipped:
        lines.append("## 文件上传状态")
        lines.append("")
        if upload_completed:
            lines.append("- ✅ 文件上传完成")
        if upload_skipped:
            lines.append("- ⏭️ 文件上传已跳过（追问场景，复用已有文件）")
        lines.append("")

    return "\n".join(lines)


# ======================================================================
# 轨迹评分器（Trajectory Scorer）：基于规则的工具调用轨迹验证
# ======================================================================

def assert_no_forbidden_tools(
    blocks: List[SseChunk],
    forbidden_tools: List[str] = None,
) -> List[str]:
    """断言 Agent 未调用禁止工具（规则评分器：一票否决）。

    合并两种工具调用来源（messages 事件 + tool_calls 事件），确保覆盖完整。

    Args:
        blocks: SSE 事件块。
        forbidden_tools: 必填。禁止工具关键字列表（子串匹配，大小写不敏感）。
            论文场景禁止列表见 paper_asserts.FORBIDDEN_TOOLS_PAPER。

    Returns:
        违规工具名称列表（空列表=无违规）。

    断言：
        空列表则通过；非空则抛出 AssertionError。
    """
    if forbidden_tools is None:
        raise ValueError("forbidden_tools 必填：框架不再内置业务默认值（论文场景见 paper_asserts.FORBIDDEN_TOOLS_PAPER）")

    # 合并两种来源（与 INT-001 断言 7 保持一致）
    all_tool_calls = []
    all_tool_calls.extend(extract_tool_calls_from_messages(blocks))
    all_tool_calls.extend(extract_tool_calls(blocks))

    # 去重（按名称）
    seen_names = set()
    unique_tool_calls = []
    for tc in all_tool_calls:
        name = tc.get("name", "")
        if name and name not in seen_names:
            seen_names.add(name)
            unique_tool_calls.append(tc)

    violations = []
    for tc in unique_tool_calls:
        name = tc.get("name", "").lower()
        for forbidden in forbidden_tools:
            if forbidden.lower() in name:
                violations.append(tc.get("name", "unknown"))
                break

    all_tool_names = [tc.get("name", "unknown") for tc in unique_tool_calls]
    assert not violations, (
        f"Agent 调用了禁止工具：{violations}。"
        f"禁止工具列表：{forbidden_tools}。"
        f"实际工具调用：{all_tool_names}"
    )
    return violations


def assert_tool_order(
    blocks: List[SseChunk],
    required_order: List[str],
) -> None:
    """断言工具调用顺序正确（轨迹评分器：严格顺序匹配）。

    合并两种工具调用来源，按时间戳排序后检查顺序。

    Args:
        blocks: SSE 事件块。
        required_order: 期望的工具调用顺序（关键字列表，子串匹配）。
            例如 ["read", "write"] 表示 read 类工具必须在 write 类之前。

    断言：
        顺序正确则通过；否则抛出 AssertionError。
    """
    # 合并两种来源
    all_tool_calls = []
    all_tool_calls.extend(extract_tool_calls_from_messages(blocks))
    all_tool_calls.extend(extract_tool_calls(blocks))

    # 按时间戳排序（如果有）
    all_tool_calls.sort(key=lambda tc: tc.get("ts_ms", tc.get("timestamp", 0) or 0))

    tool_names_lower = [tc.get("name", "").lower() for tc in all_tool_calls]
    tool_names_original = [tc.get("name", "") for tc in all_tool_calls]

    # 找到每个关键字首次出现的位置
    positions = []
    for keyword in required_order:
        found_pos = None
        for i, name in enumerate(tool_names_lower):
            if keyword.lower() in name:
                found_pos = i
                break
        positions.append((keyword, found_pos))

    # 检查缺失
    missing = [k for k, pos in positions if pos is None]
    assert not missing, (
        f"缺少期望的工具调用：{missing}。"
        f"实际工具调用序列：{tool_names_original}"
    )

    # 检查顺序
    for i in range(len(positions) - 1):
        curr_kw, curr_pos = positions[i]
        next_kw, next_pos = positions[i + 1]
        assert curr_pos < next_pos, (
            f"工具调用顺序错误：'{curr_kw}'（第{curr_pos}次调用）"
            f"应在 '{next_kw}'（第{next_pos}次调用）之前。"
            f"实际序列：{tool_names_original}"
        )


def assert_tool_subset(
    blocks: List[SseChunk],
    allowed_tools: List[str] = None,
) -> List[str]:
    """断言 Agent 调用的工具全部在允许白名单内（轨迹评分器：子集匹配）。

    与 assert_no_forbidden_tools（黑名单）互补：
    - 黑名单：检查“有没有调禁止列表里的工具”
    - 白名单：检查“有没有调允许集合以外的工具”
    白名单更安全，因为合法工具数量有限，非法工具理论上无穷。

    Args:
        blocks: SSE 事件块。
        allowed_tools: 必填。允许的工具名白名单（子串匹配，大小写不敏感）。
            论文场景白名单见 paper_asserts.ALLOWED_TOOLS_PAPER。

    Returns:
        违规工具名称列表（空列表=全部在白名单内）。

    断言：
        空列表则通过；非空则抛出 AssertionError。
    """
    if allowed_tools is None:
        raise ValueError("allowed_tools 必填：框架不再内置业务默认值（论文场景见 paper_asserts.ALLOWED_TOOLS_PAPER）")

    # 合并两种来源（与 INT-001 其他轨迹断言保持一致）
    all_tool_calls = []
    all_tool_calls.extend(extract_tool_calls_from_messages(blocks))
    all_tool_calls.extend(extract_tool_calls(blocks))

    # 去重（按名称）
    seen_names: set = set()
    unique_tool_calls = []
    for tc in all_tool_calls:
        name = tc.get("name", "")
        if name and name not in seen_names:
            seen_names.add(name)
            unique_tool_calls.append(tc)

    violations = []
    for tc in unique_tool_calls:
        name = tc.get("name", "").lower()
        matched = any(allowed.lower() in name for allowed in allowed_tools)
        if not matched:
            violations.append(tc.get("name", "unknown"))

    all_tool_names = [tc.get("name", "unknown") for tc in unique_tool_calls]
    assert not violations, (
        f"Agent 调用了白名单以外的工具：{violations}。"
        f"允许工具白名单：{allowed_tools}。"
        f"实际工具调用：{all_tool_names}"
    )
    return violations


def assert_must_pass_tools(
    blocks: List[SseChunk],
    required_tools: List[str] = None,
) -> List[str]:
    """断言 Agent 的执行轨迹中包含所有必经工具（轨迹评分器：必经节点匹配）。

    与 assert_tool_order 的区别：
    - assert_tool_order：检查“A 在 B 之前”（顺序）
    - assert_must_pass_tools：检查“X 必须出现”（存在性，不限顺序）

    Args:
        blocks: SSE 事件块。
        required_tools: 必填。必经工具关键字列表（子串匹配，大小写不敏感）。
            论文场景必经列表见 paper_asserts.MUST_PASS_TOOLS_PAPER。

    Returns:
        缺失的工具关键字列表（空列表=全部必经工具已覆盖）。

    断言：
        空列表则通过；非空则抛出 AssertionError。
    """
    if required_tools is None:
        raise ValueError("required_tools 必填：框架不再内置业务默认值（论文场景见 paper_asserts.MUST_PASS_TOOLS_PAPER）")

    # 合并两种来源（与 INT-001 其他轨迹断言保持一致）
    all_tool_calls = []
    all_tool_calls.extend(extract_tool_calls_from_messages(blocks))
    all_tool_calls.extend(extract_tool_calls(blocks))

    tool_names_lower = [tc.get("name", "").lower() for tc in all_tool_calls]

    missing = []
    for keyword in required_tools:
        found = any(keyword.lower() in name for name in tool_names_lower)
        if not found:
            missing.append(keyword)

    all_tool_names = list(set(tc.get("name", "unknown") for tc in all_tool_calls))
    assert not missing, (
        f"Agent 未调用必经工具：{missing}。"
        f"必经工具列表：{required_tools}。"
        f"实际工具调用：{all_tool_names}"
    )
    return missing

# ── 工具参数校验（工具参数正确性：write_file 内容非空）──

# 已知文件路径参数名（按优先级尝试提取；公共常量供业务断言模块复用）
PATH_PARAM_KEYS = ["file_path", "path", "file", "filename", "filePath", "input_file"]
# 已知文件内容参数名
CONTENT_PARAM_KEYS = ["content", "text", "body", "data", "output"]


def _parse_tool_args(args: Any) -> Dict[str, Any]:
    """将工具参数归一化为 dict：兼容 dict / JSON 字符串 / 其他类型。"""
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def get_tools_by_name(
    blocks: List[SseChunk],
    tool_name_keyword: str,
) -> List[Dict[str, Any]]:
    """从 SSE blocks 中提取匹配关键字的工具调用（含参数），返回 [{name, args_dict}, ...]。

    仅从 messages 事件提取（该来源包含结构化 args）。
    """
    tool_calls = extract_tool_calls_from_messages(blocks)
    keyword_lower = tool_name_keyword.lower()
    matched = []
    for tc in tool_calls:
        if keyword_lower in tc.get("name", "").lower():
            matched.append({
                "name": tc.get("name", ""),
                "args_dict": _parse_tool_args(tc.get("args")),
            })
    return matched


def assert_write_file_non_empty(
    blocks: List[SseChunk],
    min_content_len: int = 50,
) -> Dict[str, Any]:
    """断言 write_file 工具调用的内容参数非空且达到最小长度。

    校验逻辑：提取所有 write_file 调用的内容参数，检查是否存在至少一次非空写入。
    防止 Agent 调用 write_file 但传入空内容或极短占位符。

    Args:
        blocks: SSE 事件块。
        min_content_len: 内容最小长度（字符数，默认 50）。

    Returns:
        {"total_writes": int, "valid_writes": int, "content_lengths": [int]}

    断言：
        至少有一次 write_file 的内容长度 >= min_content_len 则通过。
    """
    write_calls = get_tools_by_name(blocks, "write_file")
    if not write_calls:
        # 没有 write_file：论文场景允许路径 B（不生成独立文档），此处不强制失败
        return {"total_writes": 0, "valid_writes": 0, "content_lengths": []}

    content_lengths = []
    valid_count = 0
    for call in write_calls:
        args = call["args_dict"]
        # 尝试从已知内容参数名中提取
        content = ""
        for key in CONTENT_PARAM_KEYS:
            val = args.get(key, "")
            if val and isinstance(val, str):
                content = val
                break
        # 如果已知参数名都没命中，尝试取最长的字符串值（排除路径类参数）
        if not content:
            path_keys_lower = {k.lower() for k in PATH_PARAM_KEYS}
            candidates = [
                v for k, v in args.items()
                if isinstance(v, str) and k.lower() not in path_keys_lower
            ]
            if candidates:
                content = max(candidates, key=len)

        length = len(content)
        content_lengths.append(length)
        if length >= min_content_len:
            valid_count += 1

    assert valid_count > 0, (
        f"write_file 内容校验失败：{len(write_calls)} 次 write_file 调用的内容均不足 {min_content_len} 字。"
        f"\n各次调用内容长度：{content_lengths}"
        f"\n可能原因：Agent 生成了空文件或占位符，未实际写入有效内容。"
    )
    return {
        "total_writes": len(write_calls),
        "valid_writes": valid_count,
        "content_lengths": content_lengths,
    }


# ======================================================================
# 断言日志格式化输出：提供清晰的期望/实际/结果/原因说明
# ======================================================================

class AssertReporter:
    """断言日志格式化输出：每个断言打印期望、实际值、结果，失败时打印原因。

    用法：
        reporter = AssertReporter("文献解读")
        reporter.check("文件上传", expect="文件上传完成", actual="文件上传完成", passed=True)
        reporter.check("LLM 调用", expect="至少 1 次", actual="392 次", passed=True)
        reporter.check("工具调用", expect="PDF 解析工具", actual="未检测到", passed=False,
                       reason="后端可能不透传 on_tool_start/end 事件")
        reporter.summary()  # 打印汇总
    """

    SEPARATOR = "━" * 62  # 分隔线

    def __init__(self, case_name: str, total: int = 0) -> None:
        """初始化报告器。

        Args:
            case_name: 测试用例名称（如"文献解读"）。
            total: 预期断言总数（可选，用于显示进度 N/M）。
        """
        self.case_name = case_name
        self.total = total
        self.current = 0  # 当前断言序号
        self.passed = 0  # 通过数
        self.failed = 0  # 失败数（硬断言）
        self.warned = 0  # 警告数（软断言）
        self.info_count = 0  # 信息数

    def check(
        self,
        name: str,
        expect: str,
        actual: str,
        passed: bool,
        reason: str = "",
        soft: bool = False,
    ) -> None:
        """打印一个断言结果。

        Args:
            name: 断言名称（如"文件上传验证"）。
            expect: 期望值描述。
            actual: 实际值描述。
            passed: 是否通过。
            reason: 失败原因（仅 passed=False 时显示）。
            soft: 是否为软断言（True=失败仅警告不影响用例结果，False=硬断言失败则用例失败）。
        """
        self.current += 1
        if passed:
            self.passed += 1
            result_icon = "[PASS] 通过"
        elif soft:
            self.warned += 1
            result_icon = "[WARN] 警告（软断言）"
        else:
            self.failed += 1
            result_icon = "[FAIL] 失败"

        # 进度显示
        progress = f"{self.current}/{self.total}" if self.total > 0 else str(self.current)

        print(f"\n{self.SEPARATOR}")
        print(f"[断言 {progress}] {name}")
        print(f"  期望：{expect}")
        print(f"  实际：{actual}")
        print(f"  结果：{result_icon}")
        if not passed and reason:
            print(f"  原因：{reason}")
        print(self.SEPARATOR)

    def info(self, name: str, message: str) -> None:
        """打印信息性输出（不做断言，仅记录）。

        Args:
            name: 信息名称。
            message: 信息内容。
        """
        self.current += 1
        self.info_count += 1
        progress = f"{self.current}/{self.total}" if self.total > 0 else str(self.current)

        print(f"\n{self.SEPARATOR}")
        print(f"[信息 {progress}] {name}")
        print(f"  内容：{message}")
        print(self.SEPARATOR)

    def summary(self) -> None:
        """打印断言汇总。"""
        hard_total = self.passed + self.failed  # 硬断言总数
        print(f"\n{'=' * 62}")
        print(f"[断言汇总] {self.case_name}")
        print(f"  硬断言：{hard_total} 个（通过 {self.passed}，失败 {self.failed}）")
        if self.warned > 0:
            print(f"  软断言警告：{self.warned} 个（不影响用例结果）")
        print(f"  信息：{self.info_count} 个")
        if self.failed > 0:
            print(f"  结论：[FAIL] 用例失败（{self.failed} 个硬断言未通过）")
        else:
            print(f"  结论：[PASS] 用例通过")
        print(f"{'=' * 62}")

    def raise_if_failed(self) -> None:
        """硬断言失败时抛出 AssertionError（用例在 try/finally 之后的正常路径末尾调用）。

        summary() 仅打印结论且通常在 finally 中被 except Exception 吞掉，无法传导到
        pytest 结果；本方法补上这道门禁，确保「汇总 [FAIL]」与 pytest 失败一致。
        """
        if self.failed > 0:
            raise AssertionError(
                f"{self.case_name}：{self.failed} 个硬断言未通过（详见上方断言汇总与 test_output 产物）"
            )


def assert_sse_integrity(reporter: AssertReporter, chunks: List[SseChunk]) -> None:
    """组合断言：SSE 完整性验证（无 error + 有 end 标记或事件数 > 20）。

    先执行 assert_sse_complete 并记录到 AssertReporter，失败时直接抛出
    AssertionError（SSE 不完整属于阻断性缺陷，不进入软断言路径）。

    Args:
        reporter: 断言报告器（记录"SSE 完整性验证"断言结果）。
        chunks: SSE 事件块。

    断言：
        流无 error 事件且（有 end 标记或事件数 > 20）则通过。
    """
    try:
        assert_sse_complete(chunks)
    except AssertionError as e:
        reporter.check(
            name="SSE 完整性验证",
            expect="无 error 事件 + 有 end 标记或事件数 > 20",
            actual=f"事件数={len(chunks)}，有 end={any(b.get('event') == 'end' for b in chunks)}",
            passed=False,
            reason=str(e),
        )
        raise
    reporter.check(
        name="SSE 完整性验证",
        expect="无 error 事件 + 有 end 标记或事件数 > 20",
        actual=f"事件数={len(chunks)}，有 end={any(b.get('event') == 'end' for b in chunks)}",
        passed=True,
    )
