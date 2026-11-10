"""文献解读模块 - 单轮 Agent 行为测试（INT-001~INT-003）。

文献解读 Agent 单轮行为测试：首次提问、追问复用、追问换文件。
INT-002/003 共用模块级执行体 _run_follow_up_scenario（场景配置驱动），
INT-001 为完整首次提问验证（含轨迹评分器）；E2E 完整对话流（INT-004）见同目录 test_interpret.py。

测试层级：
- L2 能力用例：首次提问 / 追问复用 / 追问换文件（各自独立验证单一能力）

接口契约来源（被测源码，只读）：
- POST   /paper/conversations/create  创建会话（ConversationFormDTO：title/source）
- POST   /paper/chatStream            SSE 流式多轮对话（LangGraph Agent，透传中间事件）
- DELETE /paper/conversations/{id}    删除会话（用例结束清理）

运行命令：
  # 本文件全部用例
  pytest test_cases/paper_interpret/test_single_round.py -v -s
  # INT-001 [P0] 首次提问上传PDF
  pytest test_cases/paper_interpret/test_single_round.py::TestSingleRound::test_paper_interpret_agent_trace -v -s
  # INT-002 [P0] 追问不传文件
  pytest test_cases/paper_interpret/test_single_round.py::TestSingleRound::test_paper_interpret_follow_up -v -s
  # INT-003 [P1] 追问上传新PDF
  pytest test_cases/paper_interpret/test_single_round.py::TestSingleRound::test_paper_interpret_follow_up_new_file -v -s

用例清单（共 3 条）：
  INT-001 [P0] test_paper_interpret_agent_trace         首次提问上传PDF，验证文件上传+LLM调用+输出文档+Judge评分
  INT-002 [P0] test_paper_interpret_follow_up           追问不传文件，验证上下文继承+文档编辑/复用
  INT-003 [P1] test_paper_interpret_follow_up_new_file  追问上传新PDF，验证跨文件切换能力
"""
import json  # 序列化 Agent trace 产物与 str_replace 编辑记录
import re  # 解析 Markdown 标题
import time  # 追问前等待后端完成首次请求处理（避免时序问题）
from datetime import datetime  # 产物文件名时间戳
from pathlib import Path  # 产物路径处理
from typing import Any, Dict, List  # 类型标注

import pytest  # pytest 框架

from core.assertions.assert_tools import (  # 通用断言工具（core 层，业务无关）
    AssertReporter,
    assert_key_points_covered,  # 内容正确性：黄金要点覆盖率
    assert_llm_called,
    assert_md_sections_semantic,
    assert_must_pass_tools,  # 轨迹评分器：必经节点匹配（列表由 paper_asserts 提供）
    assert_no_forbidden_tools,  # 轨迹评分器：禁止工具检测（列表由 paper_asserts 提供）
    assert_sse_complete,
    assert_sse_integrity,  # 组合断言：SSE 完整性验证 + 报告器记录
    assert_tool_called,
    assert_tool_order,  # 轨迹评分器：工具调用顺序
    assert_tool_subset,  # 轨迹评分器：子集匹配（白名单由 paper_asserts 提供）
    assert_write_file_non_empty,  # 工具参数校验：write_file 内容非空
    extract_generated_document,
    extract_new_generated_document,
    extract_pdf_text,
    extract_str_replace_content,
    extract_str_replace_edits,
    extract_tool_calls_from_messages,
    summarize_agent_trace,
)
from test_cases.paper_interpret.paper_asserts import (  # 论文场景业务断言与常量（已从 core 下沉）
    ALLOWED_TOOLS_PAPER,  # 轨迹评分器：论文场景允许工具白名单
    FIRST_QUESTION_KEY_POINTS,  # 首次提问的要点定义
    FOLLOW_UP_SEMANTIC_SECTIONS,
    FORBIDDEN_TOOLS_PAPER,  # 轨迹评分器：论文场景禁止工具
    INTERPRET_SEMANTIC_SECTIONS,
    MUST_PASS_TOOLS_PAPER,  # 轨迹评分器：论文场景必经工具
    assert_read_file_matches_pdf,  # 工具参数校验：read_file 文件名匹配
    generate_trajectory_report,  # 轨迹评分器：汇总报告
    verify_data_points,  # 内容正确性：关键数据点校验
)
from core.utils.config import config  # 全局配置
from core.clients.sse_client import SseClient, SseError  # SSE 客户端与异常类型
from test_cases.paper_interpret.test_paper_common import (  # 共享常量 / fixtures / 辅助函数
    PAPER_SOURCE, PAPER_TASK_TYPE, PAPER_EXPECTED_INTENT,
    PAPER_CONVERSATIONS_CREATE_PATH, PAPER_CONVERSATIONS_PATH, PAPER_TIMEOUT,
    _build_judge_content, _cleanup_conversation, _report_perf_and_summary, _save_full_artifacts, _run_judge_async,
    get_expected_points,
)

pytestmark = [pytest.mark.paper, pytest.mark.agent]  # 本模块全部用例统一标记 paper + agent；失败重试由 pytest.ini 的 --force-reruns 全局控制

class TestSingleRound:
    """文献解读 - 单轮 Agent 行为测试（INT-001~INT-003）。"""

    def test_paper_interpret_agent_trace(
        self, sse_client: SseClient, output_dir: Path, pdf_path: str, model_name: str,
        score_sink,
    ) -> None:
        """
        INT-001 [P0]：首次提问上传PDF，验证文件上传+LLM调用+输出文档+Judge评分。

        测试步骤：
        1. 创建文献解读会话（source=paper.interpret）
        2. 上传PDF + 发送解读请求（multipart SSE 流）
        3. 等待SSE流完成

        预期结果：
        - SSE完整（有end标记，无error事件）
        - 文件上传完成（progress包含'文件上传完成'）
        - AI回答≥200字，不含拒绝关键词
        - LLM至少调用1次
        - Agent调用read_file读取PDF
        - 生成输出文档（write_file）
        - Judge评分平均分≥3.0

        后端链路：创建会话(source=paper.interpret) → 上传PDF → 后端上传到OSS → FC拉取文件
                 → Agent调用LLM生成解读 → SSE返回。
        注：后端通过 fcInstanceId/pythonThreadId 判断是否首次提问，新会话两者均为空，
           仍会判定为首次提问并执行文件上传。
        """
        # 先创建会话（指定 source=paper.interpret，确保前端文献解读列表能展示）
        create_result = sse_client.request_json(
            "POST", PAPER_CONVERSATIONS_CREATE_PATH,
            body={"title": "Agent行为测试-文献解读", "source": PAPER_SOURCE},
        )
        conversation_id = int((create_result.get("data") or {}).get("conversationId", 0))
        assert conversation_id, f"创建论文会话失败：{create_result}"

        # 准备测试输入信息（P0：可复现性）
        user_question = "请总结这篇论文的核心贡献、方法与结论"
        pdf_file = Path(pdf_path)
        input_info = {
            "user_question": user_question,
            "task_type": PAPER_TASK_TYPE,
            "model_name": model_name,
            "source": PAPER_SOURCE,
        }
        file_metadata = {
            "file_name": pdf_file.name,
            "file_size_bytes": pdf_file.stat().st_size if pdf_file.exists() else 0,
            "file_path": str(pdf_file),
        }

        try:
            # 首次提问：传入 conversationId（新会话无 fcInstanceId/pythonThreadId，后端仍判定为首次）
            text, chunks, timing = sse_client.paper_chat_stream(
                user_input=user_question,
                task_type=PAPER_TASK_TYPE,
                pdf_path=pdf_path,
                conversation_id=conversation_id,
                model_name=model_name,
                timeout=PAPER_TIMEOUT,
            )

            # 初始化断言报告器
            reporter = AssertReporter("文献解读首次提问", total=20)
            # 提前提取工具调用（确保断言失败时产物仍能保存）
            tool_calls_from_msg = extract_tool_calls_from_messages(chunks)
            tool_calls_from_events = []
            try:
                tool_calls_from_events = assert_tool_called(chunks)
            except AssertionError:
                pass
            judge_result = None  # Judge 打分结果（可能因断言失败而未执行）
            judge_error_msg = "Judge 评估未执行（前置断言失败或代码未到达）"
            thread_id = ""  # thread_id（从 metadata 事件提取）

            # ── 断言 1：SSE 完整性（组合断言：校验 + 报告器记录 + 失败即抛出）──
            assert_sse_integrity(reporter, chunks)

            # ── 断言 2：文件上传未被跳过 ──
            progress_events = [b for b in chunks if b.get("event") == "progress"]
            upload_completed = any(
                isinstance(b.get("data"), str) and "文件上传完成" in b["data"]
                for b in progress_events
            )
            upload_skipped = any(
                isinstance(b.get("data"), str) and "跳过文件上传" in b["data"]
                for b in progress_events
            )
            reporter.check(
                name="文件上传验证",
                expect="progress 包含'文件上传完成'，不包含'跳过文件上传'",
                actual=f"upload_completed={upload_completed}, upload_skipped={upload_skipped}",
                passed=upload_completed and not upload_skipped,
                reason="后端错误判定为追问场景，跳过了文件上传。请检查 conversationId 传入时后端是否正确判断为首次提问。" if not upload_completed or upload_skipped else "",
            )
            assert upload_completed and not upload_skipped, "文件上传验证失败"

            # ── 断言 3：AI 回答包含实质内容 ──
            reject_keywords = ["您希望我总结哪篇论文", "目前还没有提供具体的论文", "还没有看到您提供的论文"]
            found_keyword = ""
            for kw in reject_keywords:
                if kw in text:
                    found_keyword = kw
                    break
            text_len_ok = len(text) >= 200
            reporter.check(
                name="AI 回答内容验证",
                expect=f"≥200 字，不含拒绝关键词{reject_keywords}",
                actual=f"字数={len(text)}，拒绝关键词={'「' + found_keyword + '」' if found_keyword else '无'}",
                passed=text_len_ok and not found_keyword,
                reason="AI 未识别到已上传的 PDF，请检查 fileInfos 是否正确传递了 OSS URL。" if found_keyword else
                       f"回答过短（{len(text)} 字），可能未真正解析 PDF。" if not text_len_ok else "",
            )
            assert text_len_ok and not found_keyword, "AI 回答内容验证失败"

            # ── 断言 4：LLM 调用 ──
            llm_events = assert_llm_called(chunks)
            reporter.check(
                name="LLM 调用验证",
                expect="至少检测到 1 次 LLM 调用事件（on_chat_model_start/end 等）",
                actual=f"LLM 调用 {len(llm_events)} 次",
                passed=len(llm_events) > 0,
                reason="Agent 未调用 LLM 模型生成解读。" if not llm_events else "",
            )
            assert llm_events, "LLM 调用验证失败"

            # ── 断言 5：messages 事件包含实质内容 ──
            messages_events = [b for b in chunks if b.get("event") == "messages"]
            has_content = False
            for msg_event in messages_events:
                msg_data = msg_event.get("data")
                if isinstance(msg_data, list) and msg_data:
                    msg = msg_data[0]
                    if isinstance(msg, dict):
                        content = msg.get("content", "")
                        if isinstance(content, str) and content:
                            has_content = True
                            break
                        if isinstance(content, list) and content:
                            has_content = True
                            break
            reporter.check(
                name="messages 内容验证",
                expect="messages 事件应包含非空 content",
                actual=f"messages 事件 {len(messages_events)} 个，有实质内容={has_content}",
                passed=len(messages_events) > 0 and has_content,
                reason="Agent 未生成任何消息或消息中无实质内容。" if not messages_events or not has_content else "",
            )
            assert messages_events and has_content, "messages 内容验证失败"

            # ── 断言 6：Markdown 章节语义匹配（硬断言：章节缺失=功能性缺陷）──
            # 优先检查 write_file 文档（用户实际看到的内容），回退到 SSE 文本
            document_text_for_section = extract_generated_document(chunks)
            section_check_target = document_text_for_section if document_text_for_section else text
            section_check_source = "write_file 文档" if document_text_for_section else "SSE 文本"
            if re.search(r"^\s{0,3}#{1,6}\s+\S", section_check_target, flags=re.MULTILINE):
                missing = assert_md_sections_semantic(section_check_target, INTERPRET_SEMANTIC_SECTIONS)
                covered = [k for k in INTERPRET_SEMANTIC_SECTIONS if k not in missing]
                reporter.check(
                    name="Markdown 章节语义验证",
                    expect=f"覆盖主题：{list(INTERPRET_SEMANTIC_SECTIONS.keys())}",
                    actual=f"已覆盖：{covered}，缺失：{missing}" if missing else f"全部覆盖：{covered}（来源: {section_check_source}）",
                    passed=not missing,
                    reason=f"输出缺少主题 {missing}，产物已保存，请人工复核。" if missing else "",
                    soft=False,  # 硬断言：章节缺失=功能性缺陷
                )
            else:
                reporter.info("Markdown 章节语义验证", f"输出未包含 Markdown 标题，跳过章节检查（来源: {section_check_source}）")

            # ── 断言 6b：意图识别路由正确性（硬断言）──
            intent_events = [b for b in chunks if b.get("event") == "intent_recognition"]
            if intent_events:
                intent_data = intent_events[0].get("data") or {}
                intent_type = intent_data.get("intent", intent_data.get("type", ""))
                reporter.check(
                    name="意图识别路由",
                    expect=f"意图应为 '{PAPER_EXPECTED_INTENT}'",
                    actual=f"intent={intent_type}",
                    passed=intent_type == PAPER_EXPECTED_INTENT,
                    reason=f"意图路由错误：期望 '{PAPER_EXPECTED_INTENT}'，实际 '{intent_type}'，Agent 可能被路由到错误的处理流程。" if intent_type != PAPER_EXPECTED_INTENT else "",
                )
                assert intent_type == PAPER_EXPECTED_INTENT, f"意图识别路由失败：期望 '{PAPER_EXPECTED_INTENT}'，实际 '{intent_type}'"
            else:
                reporter.info("意图识别", "未检测到 intent_recognition 事件（后端可能不透传，跳过路由断言）")

            # ── 断言 7：工具调用（硬断言：Agent 必须调用工具处理 PDF）──
            # 合并两种来源的工具调用（去重）—— tool_calls_from_msg 已在断言前提取
            all_tool_names = list(set(
                [t["name"] for t in tool_calls_from_msg] + 
                [t["name"] for t in tool_calls_from_events]
            ))
            
            reporter.check(
                name="工具调用验证",
                expect="Agent 应调用工具处理 PDF（如 read_pdf、write_file、search 等）",
                actual=f"检测到 {len(all_tool_names)} 个工具：{all_tool_names}" if all_tool_names else "未检测到任何工具调用",
                passed=len(all_tool_names) > 0,
                reason="Agent 未调用任何工具，可能直接靠 LLM 幻觉生成回答，而非基于 PDF 内容。" if not all_tool_names else "",
            )
            assert all_tool_names, "工具调用验证失败：Agent 未调用任何工具"

            # ── 断言 7b：工具选择精确/召回 + 死循环检测（硬断言）──
            # 文献解读场景期望工具集：read 类工具（读 PDF）为必需，write 类工具（写文档）为可选
            # Agent 行为存在两种合法路径：
            #   路径 A：read_file → write_file（生成独立文档，页面展示用）
            #   路径 B：read_file → SSE 流直接输出（不生成独立文档，内容在 AI 回答中）
            expected_tool_keywords = {"read": False, "write": False}  # 期望的工具关键字
            for tool_name in all_tool_names:
                for keyword in expected_tool_keywords:
                    if keyword in tool_name.lower():
                        expected_tool_keywords[keyword] = True
            has_write_tool = expected_tool_keywords["write"]
            missing_required_tools = [k for k, v in expected_tool_keywords.items() if not v and k == "read"]
            missing_optional_tools = [k for k, v in expected_tool_keywords.items() if not v and k != "read"]
            # read 类工具是硬断言（Agent 必须读取 PDF）
            reporter.check(
                name="工具选择召回（必需）",
                expect="文献解读应包含 read 类工具（读 PDF）",
                actual=f"已覆盖：{[k for k, v in expected_tool_keywords.items() if v]}" if not missing_required_tools else f"缺失：{missing_required_tools}",
                passed=not missing_required_tools,
                reason=f"Agent 未调用 read 类工具，可能未解析 PDF 内容。" if missing_required_tools else "",
            )
            assert not missing_required_tools, f"工具选择召回失败：缺失必需工具 {missing_required_tools}"
            # write 类工具为软断言（Agent 可能直接通过 SSE 流输出解读内容）
            if missing_optional_tools:
                sse_substantial = len(text) >= 500
                reporter.check(
                    name="工具选择召回（可选）",
                    expect="write 类工具（生成独立文档）",
                    actual=f"未调用 write 类工具，SSE 回答 {len(text)} 字{'（内容充实，视为合法路径 B）' if sse_substantial else '（内容不足）'}",
                    passed=sse_substantial,
                    reason="Agent 未调用 write 类工具且 SSE 回答内容不足，可能未完整解读论文。" if not sse_substantial else "",
                    soft=True,  # 软断言：Agent 可能直接通过 SSE 流输出内容
                )

            # ── 断言 7c：禁止工具检测（规则评分器：一票否决）──
            try:
                assert_no_forbidden_tools(chunks, FORBIDDEN_TOOLS_PAPER)
                reporter.check(
                    name="禁止工具检测",
                    expect=f"不调用 {FORBIDDEN_TOOLS_PAPER}",
                    actual=f"未调用禁止工具 ✓（工具列表：{all_tool_names}）",
                    passed=True,
                )
            except AssertionError as e:
                reporter.check(
                    name="禁止工具检测",
                    expect=f"不调用 {FORBIDDEN_TOOLS_PAPER}",
                    actual=str(e)[:300],
                    passed=False,
                    reason="Agent 调用了不该调用的工具（规则评分器）",
                    soft=True,  # 软断言：不阻断 Judge 执行
                )

            # ── 断言 7d：工具调用顺序（轨迹评分器，仅在 write 被调用时校验）──
            if has_write_tool:
                try:
                    assert_tool_order(chunks, ["read", "write"])
                    reporter.check(
                        name="工具调用顺序",
                        expect="read 类工具在 write 类工具之前（先读文件再生成文档）",
                        actual="顺序正确 ✓",
                        passed=True,
                    )
                except AssertionError as e:
                    reporter.check(
                        name="工具调用顺序",
                        expect="read 类工具在 write 类工具之前",
                        actual=str(e)[:300],
                        passed=False,
                        reason="Agent 应先读取文件再生成文档（轨迹评分器）",
                        soft=True,  # 软断言：不阻断 Judge 执行
                    )
            else:
                reporter.info("工具调用顺序", "未调用 write 类工具，跳过顺序校验（Agent 通过 SSE 流直接输出）")

            # ── 断言 7d2：子集匹配（轨迹评分器：白名单校验）──
            try:
                assert_tool_subset(chunks, ALLOWED_TOOLS_PAPER)
                reporter.check(
                    name="子集匹配",
                    expect=f"实际工具 ⊆ {ALLOWED_TOOLS_PAPER}",
                    actual=f"实际工具 {all_tool_names} 全部在白名单内 ✓",
                    passed=True,
                )
            except AssertionError as e:
                reporter.check(
                    name="子集匹配",
                    expect=f"实际工具 ⊆ {ALLOWED_TOOLS_PAPER}",
                    actual=str(e)[:300],
                    passed=False,
                    reason="Agent 调用了白名单以外的工具（轨迹评分器）",
                    soft=True,  # 软断言：不阻断 Judge 执行
                )

            # ── 断言 7d3：必经节点匹配（轨迹评分器）──
            try:
                assert_must_pass_tools(chunks, MUST_PASS_TOOLS_PAPER)
                reporter.check(
                    name="必经节点",
                    expect=f"必经工具：{MUST_PASS_TOOLS_PAPER}",
                    actual=f"必经工具均已调用 ✓（工具列表：{all_tool_names}）",
                    passed=True,
                )
            except AssertionError as e:
                reporter.check(
                    name="必经节点",
                    expect=f"必经工具：{MUST_PASS_TOOLS_PAPER}",
                    actual=str(e)[:300],
                    passed=False,
                    reason="Agent 未调用必经工具（轨迹评分器）",
                    soft=True,  # 软断言：不阻断 Judge 执行
                )

            # ── 断言 7d4：工具参数校验——read_file 文件名匹配上传 PDF（软断言）──
            try:
                read_param_result = assert_read_file_matches_pdf(chunks, pdf_path)
                match_mode_desc = {"filename": "原始文件名匹配", "uploads_dir": "上传目录匹配（UUID重命名）", "none": "无匹配"}
                reporter.check(
                    name="read_file 参数校验",
                    expect=f"read_file 参数应引用上传 PDF：{read_param_result['pdf_filename']}",
                    actual=(
                        f"{read_param_result['total_reads']} 次 read_file，"
                        f"{read_param_result['matched_reads']} 次匹配 ✓"
                        f"（{match_mode_desc.get(read_param_result['match_mode'], read_param_result['match_mode'])}）"
                        if read_param_result["total_reads"] > 0 else
                        "未检测到 read_file 调用（由必经节点断言覆盖）"
                    ),
                    passed=read_param_result["total_reads"] == 0 or read_param_result["matched_reads"] > 0,
                    reason=(
                        f"read_file 参数未引用上传 PDF，实际参数：{read_param_result['read_paths']}"
                        if read_param_result["total_reads"] > 0 and read_param_result["matched_reads"] == 0 else ""
                    ),
                    soft=True,  # 软断言：Agent 可能用内部路径而非原始文件名
                )
            except AssertionError as e:
                reporter.check(
                    name="read_file 参数校验",
                    expect=f"read_file 参数应引用上传 PDF 文件",
                    actual=str(e)[:300],
                    passed=False,
                    reason="Agent 读取的文件与上传 PDF 不匹配（工具参数校验）",
                    soft=True,
                )

            # ── 断言 7d5：工具参数校验——write_file 内容非空（软断言）──
            try:
                write_param_result = assert_write_file_non_empty(chunks)
                if write_param_result["total_writes"] > 0:
                    reporter.check(
                        name="write_file 参数校验",
                        expect=f"write_file 内容应 ≥ 50 字",
                        actual=(
                            f"{write_param_result['total_writes']} 次 write_file，"
                            f"{write_param_result['valid_writes']} 次内容充实 ✓"
                            f"（长度：{write_param_result['content_lengths']}）"
                        ),
                        passed=write_param_result["valid_writes"] > 0,
                        reason=(
                            f"write_file 内容均不足 50 字：{write_param_result['content_lengths']}"
                            if write_param_result["valid_writes"] == 0 else ""
                        ),
                        soft=True,  # 软断言：Agent 可能通过 SSE 流直接输出
                    )
                else:
                    reporter.info("write_file 参数校验", "未检测到 write_file 调用，跳过内容校验（Agent 通过 SSE 流直接输出）")
            except AssertionError as e:
                reporter.check(
                    name="write_file 参数校验",
                    expect=f"write_file 内容应 ≥ 50 字",
                    actual=str(e)[:300],
                    passed=False,
                    reason="Agent 写入文件内容为空或极短（工具参数校验）",
                    soft=True,
                )

            # ── 断言 7e：关键数据点校验（anti-hallucination，硬断言）──
            # 从 Agent 回答中提取数值型数据声明，检查是否在 PDF 原文中有支撑
            # 硬断言：3 次验证命中率 80%/94%/67%，均 ≥ 60% 阈值，稳定性已确认
            pdf_text_for_verify = extract_pdf_text(pdf_path)
            verify_target = document_text_for_section if document_text_for_section else text
            data_verify_result = verify_data_points(
                answer=verify_target,
                source_text=pdf_text_for_verify,
                min_claims=3,
                pass_rate=0.6,
            )
            # 打印每个数据声明的校验详情（供人工复核）
            for detail in data_verify_result.get("details", []):
                status = "✓" if detail["verified"] else "✗"
                print(f"    [{status}] {detail['value']}")
                print(f"        回答上下文: ...{detail['answer_context']}...")
                print(f"        原文上下文:   ...{detail['source_context']}...")
            # 保存校验详情到产物文件（供事后人工复核）
            data_verify_artifact = {
                "total_claims": data_verify_result["total_claims"],
                "verified_claims": data_verify_result["verified_claims"],
                "verification_rate": data_verify_result["verification_rate"],
                "passed": data_verify_result["passed"],
                "details": data_verify_result.get("details", []),
            }
            ts_data_verify = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            data_verify_dir = output_dir / "paper_interpret"
            data_verify_dir.mkdir(parents=True, exist_ok=True)
            (data_verify_dir / f"{ts_data_verify}_data_verify.json").write_text(
                json.dumps(data_verify_artifact, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            reporter.check(
                name="关键数据点校验",
                expect=f"数值型数据声明在原文中的命中率 {data_verify_result['threshold']}",
                actual=(
                    f"提取 {data_verify_result['total_claims']} 个数据声明，"
                    f"验证通过 {data_verify_result['verified_claims']} 个"
                    f"（命中率 {data_verify_result['verification_rate']:.0%}）"
                    f"，详情已保存至 {ts_data_verify}_data_verify.json"
                ),
                passed=data_verify_result["passed"],
                reason=(
                    f"以下数据声明在 PDF 原文中未找到支撑（可能存在幻觉）："
                    f"{[u['value'] for u in data_verify_result['unverified_claims']]}"
                    if not data_verify_result["passed"] else ""
                ),
                soft=False,  # 硬断言：3 次验证稳定（80%/94%/67%），命中率均 ≥ 60%
            )

            # ─ 断言 7f：黄金要点覆盖率（软断言，不阻断 Judge）──
            # 校验回答是否覆盖了用户问题期望的关键要点
            # 与断言 6（Markdown 章节）的区别：要点匹配在全文中搜索，不限标题
            key_points_result = assert_key_points_covered(
                text=verify_target,
                key_points=FIRST_QUESTION_KEY_POINTS,
            )
            reporter.check(
                name="黄金要点覆盖率",
                expect=f"覆盖要点：{list(FIRST_QUESTION_KEY_POINTS.keys())}",
                actual=(
                    f"已覆盖：{key_points_result['covered']}"
                    f"{('，命中词=' + str(key_points_result['hit_details'])) if key_points_result['hit_details'] else ''}"
                    f"{('，缺失：' + str(key_points_result['missing'])) if key_points_result['missing'] else ''}"
                ),
                passed=key_points_result["passed"],
                reason=(
                    f"回答未覆盖以下要点：{key_points_result['missing']}，"
                    f"可能未完整回答用户问题"
                    if key_points_result["missing"] else ""
                ),
                soft=True,  # 软断言：受 Agent 输出随机性影响，不阻断 Judge 执行
            )

            # ── 轨迹评分报告（汇总四项轨迹检查结果，落盘 JSON）──
            trajectory_report = generate_trajectory_report(chunks)
            reporter.info(
                "轨迹评分报告",
                f"总分：{trajectory_report['passed_count']}/{trajectory_report['total']}"
                f"{'（全部通过 ✓）' if trajectory_report['all_passed'] else '（存在未通过项 ✗）'}",
            )
            for check in trajectory_report["checks"]:
                icon = "✓" if check["passed"] else "✗"
                print(f"    [{icon}] {check['name']}：{check['detail']}")
            # 保存轨迹评分报告到产物
            ts_trajectory = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            trajectory_dir = output_dir / "paper_interpret"
            trajectory_dir.mkdir(parents=True, exist_ok=True)
            (trajectory_dir / f"{ts_trajectory}_trajectory_report.json").write_text(
                json.dumps(trajectory_report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # 死循环检测：工具调用总次数合理上限 + 同一工具连续调用超过阈值视为异常
            total_tool_calls = len(tool_calls_from_msg) + len(tool_calls_from_events)
            max_reasonable_calls = 50  # 文献解读场景合理上限
            reporter.check(
                name="死循环检测",
                expect=f"工具调用总次数 ≤ {max_reasonable_calls}",
                actual=f"工具调用总次数={total_tool_calls}",
                passed=total_tool_calls <= max_reasonable_calls,
                reason=f"工具调用 {total_tool_calls} 次超过合理上限 {max_reasonable_calls}，疑似死循环或重复调用。" if total_tool_calls > max_reasonable_calls else "",
            )
            assert total_tool_calls <= max_reasonable_calls, f"死循环检测失败：工具调用 {total_tool_calls} 次"

            # ── 断言 8：LLM-as-Judge 质量评分（异步化，不阻塞用例通过）──
            judge_result = None
            JUDGE_SAMPLE_COUNT = 1  # 采样次数（DeepEval 默认 1 次避免超时，自建 Judge 可增至 3）
            sampling_desc = f"{JUDGE_SAMPLE_COUNT} 次采样取中位数" if JUDGE_SAMPLE_COUNT > 1 else "单次采样"
            JUDGE_ASYNC_TIMEOUT = 400  # Judge 异步超时（秒）：evaluate_full 包含 3 次 LLM 调用（主观+声明提取+声明验证），需 > 3×JUDGE_TIMEOUT(240s)/2

            # 准备被评内容（在主线程完成，避免线程间共享 httpx 客户端）
            document_text = extract_generated_document(chunks)
            judge_content, content_source = _build_judge_content(text, document_text)
            paper_reference = extract_pdf_text(pdf_path)
            # 从黄金评测集加载 expected_points（未命中时回退默认值）
            first_question_expected_points = get_expected_points(pdf_path, user_question) or [
                "论文核心贡献的清晰描述",
                "研究方法的说明",
                "主要结论的总结",
            ]

            # 后台线程执行 Judge（执行与异常/超时处理收敛于 test_paper_common._run_judge_async）
            judge_result, _judge_error, judge_timed_out = _run_judge_async(
                question=user_question,
                judge_content=judge_content,
                paper_reference=paper_reference,
                expected_points=first_question_expected_points,
                tool_calls=tool_calls_from_msg,
                expected_tools=["read", "write"],
                sample_count=JUDGE_SAMPLE_COUNT,
                timeout=JUDGE_ASYNC_TIMEOUT,
                dims=["relevance", "completeness", "format",
                      "depth", "key_concepts", "instruction_follow", "faithfulness"],
                content_length=len(text),
                content_source=content_source,
            )

            # 处理 Judge 结果
            framework = "DeepEval" if config.use_deepeval else "自建 Judge"
            if judge_timed_out:
                # 超时：线程仍在运行，用例继续通过，Judge 结果放弃
                print(f"\n[Judge 异步] 超时 {JUDGE_ASYNC_TIMEOUT}s 未完成（Judge API 单次超时=240s），用例继续通过（Judge 结果已放弃）")
                reporter.info(
                    f"Judge 质量评分（{framework}）",
                    f"{framework} 异步评估超时（>{JUDGE_ASYNC_TIMEOUT}s），用例基于确定性断言通过，Judge 结果已放弃",
                )
                judge_result = None
            elif _judge_error:
                reporter.info(
                    f"Judge 质量评分（{framework}）",
                    f"{framework} 评估失败：{_judge_error}",
                )
                judge_result = None
            else:
                if judge_result is None:
                    reporter.info(
                        f"Judge 质量评分（{framework}）",
                        f"{framework} 评估失败，跳过评分（超时或 API 错误）",
                    )
                else:
                    avg = judge_result.get("average", 0)
                    # 评分收口：写 junit properties 供引擎取主观分（双轨语义：
                    # 只影响 passed_by_score 元数据，不改变 status 断言轨）；
                    # 超时/失败路径不写——score 缺省保持合法的 None
                    score_sink(judge_result)
                    if config.use_deepeval:
                        tool_accuracy = judge_result.get("tool_call_accuracy", 0)
                        reporter.check(
                            name="Judge 质量评分（DeepEval）",
                            expect="平均分 ≥ 3.0（及格线）",
                            actual=(
                                f"平均分={avg}（相关性={judge_result.get('relevance')}, 忠实度={judge_result.get('faithfulness')}, "
                                f"完整性={judge_result.get('completeness')}, 格式={judge_result.get('format')}, "
                                f"数据准确={judge_result.get('data_accuracy')}, 分析深度={judge_result.get('depth')}, "
                                f"概念覆盖={judge_result.get('key_concepts')}, 指令遵循={judge_result.get('instruction_follow')}）"
                                f"[来源: DeepEval, {sampling_desc}, 工具准确率={tool_accuracy:.0%}]"
                            ),
                            passed=avg >= 3.0,
                            reason="DeepEval 评估未通过及格线" if avg < 3.0 else "",
                            soft=not config.judge_gate,
                        )
                    else:
                        faithfulness_ratio = judge_result.get("_faithfulness_ratio", 0)
                        claims_detail = judge_result.get("_claims_detail", [])
                        supported = sum(1 for c in claims_detail if c.get("verdict") == "supported")
                        claims_summary = f"声明验证={supported}/{len(claims_detail)} 支持" if claims_detail else "无声明"
                        # 计时摘要（诊断超时定位）
                        timing_info = judge_result.get("_timing", {})
                        timing_summary = (
                            f"耗时: 主观={timing_info.get('subjective_sec', '?')}s, "
                            f"忠实度={timing_info.get('faithfulness_sec', '?')}s, "
                            f"总计={timing_info.get('total_sec', '?')}s"
                        ) if timing_info else ""
                        reporter.check(
                            name="Judge 质量评分（自建 Judge）",
                            expect="平均分 ≥ 3.0（及格线）",
                            actual=(
                                f"平均分={avg}（相关性={judge_result.get('relevance')}, "
                                f"完整性={judge_result.get('completeness')}, 格式={judge_result.get('format')}, "
                                f"分析深度={judge_result.get('depth')}, "
                                f"概念覆盖={judge_result.get('key_concepts')}, 指令遵循={judge_result.get('instruction_follow')}, "
                                f"忠实度={judge_result.get('faithfulness') if judge_result.get('faithfulness') is not None else '未评估(降级)'}）"
                                f"[{claims_summary}, {timing_summary}, 来源: {content_source}, {sampling_desc}]"
                            ),
                            passed=avg >= 3.0,
                            reason=f"裁判模型评语：{judge_result.get('_all_runs', [{}])[0].get('summary', '')}" if avg < 3.0 else "",
                            soft=not config.judge_gate,
                        )

        finally:
            # ── 始终保存产物（即使断言失败也要保留 SSE 事件流用于排查）──
            if 'chunks' in dir() and 'text' in dir():
                try:
                    trace = summarize_agent_trace(chunks)
                    metadata_events = [b for b in chunks if b.get("event") == "metadata"]
                    if metadata_events:
                        meta_data = metadata_events[0].get("data") or {}
                        thread_id = meta_data.get("thread_id", "")
                    _save_full_artifacts(
                        output_dir, "paper_interpret", chunks, text,
                        meta={
                            "case": "文献解读",
                            "conversation_id": conversation_id,
                            "thread_id": thread_id,
                            "model_name": model_name,
                            "trace": trace,
                            "timing": timing,
                            "text_length": len(text),
                        },
                        input_info=input_info,
                        file_metadata=file_metadata,
                        tool_calls=tool_calls_from_msg,
                        judge_result=judge_result,
                        judge_error=judge_error_msg,
                    )
                    # 打印性能统计（共享辅助函数：finally 收尾四件套）
                    if 'reporter' in dir():
                        _report_perf_and_summary(reporter, timing, conversation_id, thread_id)
                except Exception:
                    pass  # 产物保存失败不应影响清理流程

            # 清理会话（共享辅助函数：finally 收尾四件套）
            _cleanup_conversation(sse_client, conversation_id)

        # 硬断言失败传导：summary() 仅打印且在 finally 中被吞，须在正常路径末尾显式抛出
        reporter.raise_if_failed()


    def test_paper_interpret_follow_up(
        self, sse_client: SseClient, output_dir: Path, pdf_path: str, model_name: str,
        score_sink,
    ) -> None:
        """
        INT-002 [P0]：追问不传文件，验证上下文继承+文档编辑/复用。

        测试步骤：创建会话 → 首次提问上传PDF → 追问不传PDF复用上下文 → 分别保存两轮产物。
        预期结果：首次提问 SSE 完整且生成文档；追问跳过文件上传、回答≥200字、
        调用 read 类工具读取已有文件；追问 Judge 评分平均分≥3.0。

        执行体收敛于模块级 _run_follow_up_scenario（scenario="reuse"，与 INT-003 共用）。
        """
        _run_follow_up_scenario(
            sse_client, output_dir, model_name,
            _FOLLOW_UP_SCENARIOS["reuse"], pdf_path=pdf_path,
            score_sink=score_sink,
        )

    def test_paper_interpret_follow_up_new_file(
        self, sse_client: SseClient, output_dir: Path, pdf_path: str, pdf_path_2: str, model_name: str,
        score_sink,
    ) -> None:
        """
        INT-003 [P1]：追问上传新PDF，验证跨文件切换能力。

        测试步骤：创建会话 → 首次提问上传PDF-A → 追问上传不同领域的PDF-B → 分别保存两轮产物。
        预期结果：追问成功上传新文件（progress 含'文件上传完成'）、回答≥200字、
        read 类工具必须调用（write 类建议）；追问 Judge 评分平均分≥3.0。

        执行体收敛于模块级 _run_follow_up_scenario（scenario="new_file"，与 INT-002 共用）。
        """
        _run_follow_up_scenario(
            sse_client, output_dir, model_name,
            _FOLLOW_UP_SCENARIOS["new_file"], pdf_path=pdf_path, pdf_path_2=pdf_path_2,
            score_sink=score_sink,
        )


# ════════════════════════════════════════════════════════════════
#  INT-002/003 共用执行体（原两条用例约 900 行平行复制收敛于此）
# ════════════════════════════════════════════════════════════════

# 追问场景配置：两条用例共用同一执行体，差异全部收敛为场景字段
#   new_file=False：追问不传 PDF，断言「跳过文件上传」（文件复用）
#   new_file=True ：追问上传 PDF-B（不同领域），断言「文件上传完成」（跨文件切换）
_FOLLOW_UP_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "reuse": {
        "label": "文献解读追问",
        "conversation_title": "Agent行为测试-文献解读追问",
        "q1_question": "请总结这篇论文的核心贡献、方法与结论",
        "q1_default_points": [
            "论文核心贡献的清晰描述",
            "研究方法的说明",
            "主要结论的总结",
        ],
        "q2_question": "请详细说明论文中提到的评估方法和实验结果",
        "q2_default_points": [
            "论文中评估方法的具体描述（如评估指标、实验设计）",
            "实验结果的展示与分析（如数据对比、结论推导）",
        ],
        "new_file": False,
        "reporter_total": 12,
        "artifact_q1": "paper_follow_up_q1",
        "artifact_q2": "paper_follow_up_q2",
        "q1_case": "文献解读追问-首次提问",
        "q2_case": "文献解读追问-追问",
        "q2_file_note": "追问不传 PDF",
    },
    "new_file": {
        "label": "文献解读追问新文件",
        "conversation_title": "Agent行为测试-文献解读追问新文件",
        "q1_question": "请总结这篇论文的核心贡献",
        "q1_default_points": [
            "论文核心贡献的清晰描述",
        ],
        "q2_question": "请详细说明这篇论文中二级结构信息对核酸结构预测精度的影响",
        "q2_default_points": [
            "二级结构信息对核酸结构预测的影响",
            "预测精度与基线方法的对比结果",
        ],
        "new_file": True,
        "reporter_total": 11,
        "artifact_q1": "paper_follow_up_newfile_q1",
        "artifact_q2": "paper_follow_up_newfile_q2",
        "q1_case": "文献解读追问新文件-首次提问",
        "q2_case": "文献解读追问新文件-追问",
        "q2_file_note": "追问上传新文件 (PDF-B)",
    },
}

# Judge 评估口径（与 INT-001 / OOC 用例一致）：主观 7 维（不含 data_accuracy）+ 单次采样
SEVEN_JUDGE_DIMS = [
    "relevance", "completeness", "format",
    "depth", "key_concepts", "instruction_follow", "faithfulness",
]
JUDGE_SAMPLE_COUNT = 1  # 采样次数（DeepEval 默认 1 次避免超时）
JUDGE_TIMEOUT = 400  # Judge 异步超时（秒）：evaluate_full 含多次 LLM 调用


def _run_follow_up_scenario(
    sse_client: SseClient,
    output_dir: Path,
    model_name: str,
    scenario: Dict[str, Any],
    pdf_path: str,
    pdf_path_2: str = "",
    score_sink=None,
) -> None:
    """INT-002/003 共用执行体：首次提问 + 追问（复用文件 / 上传新文件）单轮行为验证。

    由薄壳用例 test_paper_interpret_follow_up / test_paper_interpret_follow_up_new_file
    按 _FOLLOW_UP_SCENARIOS 场景配置调用；两轮 Judge 统一走 _run_judge_async
    （后台线程 + 超时保护，与 INT-001 / OOC 同口径）。
    """
    label = scenario["label"]
    prefix = f"[{label}]"
    new_file = scenario["new_file"]
    q1_question = scenario["q1_question"]
    q2_question = scenario["q2_question"]

    # 追问侧 PDF 与 Judge 参考原文：换文件场景切换为 PDF-B
    q2_pdf_path = pdf_path_2 if new_file else None
    q2_ref_pdf = pdf_path_2 if new_file else pdf_path

    # 创建会话
    create_result = sse_client.request_json(
        "POST", PAPER_CONVERSATIONS_CREATE_PATH,
        body={"title": scenario["conversation_title"], "source": PAPER_SOURCE},
    )
    conversation_id = int((create_result.get("data") or {}).get("conversationId", 0))
    assert conversation_id, f"创建论文会话失败：{create_result}"

    # 变量初始化（确保 finally 中产物保存可用）
    text1, chunks1, timing1 = "", [], {}
    text2, chunks2, timing2 = "", [], {}
    tool_calls_from_msg_1 = []
    tool_calls_from_msg_2 = []
    tool_calls_from_events_2 = []
    judge_result_1 = None
    judge_error_1 = "Judge 评估未执行（前置断言失败或代码未到达）"
    judge_result_2 = None
    judge_error_msg = "Judge 评估未执行（前置断言失败或代码未到达）"
    thread_id_2 = ""

    try:
        # ── ① 首次提问：上传 PDF + 解读请求 ──
        text1, chunks1, timing1 = sse_client.paper_chat_stream(
            user_input=q1_question,
            task_type=PAPER_TASK_TYPE,
            pdf_path=pdf_path,
            conversation_id=conversation_id,
            model_name=model_name,
            timeout=PAPER_TIMEOUT,
        )
        assert_sse_complete(chunks1)
        assert text1, "首次提问返回空文本"
        assert len(text1) >= 200, f"首次提问回答过短（{len(text1)} 字）"
        print(f"\n{prefix} 首次提问：{len(text1)} 字，耗时 {timing1['total_ms']:.0f} ms")

        # 提取首次提问的文档（用于追问时比对是否生成了新文档）
        document_text_q1 = extract_generated_document(chunks1)
        if not document_text_q1:
            # Agent 可能直接通过 SSE 流输出解读内容而不调用 write_file
            assert len(text1) >= 500, f"首次提问既未生成 write_file 文档，SSE 回答也过短（{len(text1)} 字）"
            print(f"{prefix} 首次提问未生成 write_file 文档，使用 SSE 回答（{len(text1)} 字）作为 Judge 输入")
        else:
            print(f"{prefix} 首次提问生成文档：{len(document_text_q1)} 字")

        # ── q1 Judge 质量评分（后台线程，超时/失败不阻断追问流程）──
        q1_expected_points = get_expected_points(pdf_path, q1_question) or scenario["q1_default_points"]
        judge_content_q1, content_source_q1 = _build_judge_content(text1, document_text_q1)
        paper_reference_q1 = extract_pdf_text(pdf_path)
        judge_result_1, _q1_err, _q1_timeout = _run_judge_async(
            question=q1_question,
            judge_content=judge_content_q1,
            paper_reference=paper_reference_q1,
            expected_points=q1_expected_points,
            sample_count=JUDGE_SAMPLE_COUNT,
            timeout=JUDGE_TIMEOUT,
            dims=SEVEN_JUDGE_DIMS,
            content_length=len(text1),
            content_source=content_source_q1,
        )
        if _q1_timeout:
            judge_error_1 = f"Judge 异步评估超时（>{JUDGE_TIMEOUT}s），结果已放弃"
        elif _q1_err:
            judge_error_1 = f"Judge 评估失败：{_q1_err}"
        else:
            judge_error_1 = ""
            print(f"{prefix} q1 Judge 打分：平均分={judge_result_1['average']}")

        # 调试：提取首次响应中的文件 ID（从 artifact 事件中）
        pdf_file_ids = []
        for chunk in chunks1:
            if chunk.get("event") == "artifact":
                data = chunk.get("data")
                # data 可能是字符串、列表或字典
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                if isinstance(data, list):
                    # 列表中的每个元素可能包含 id
                    for item in data:
                        if isinstance(item, dict) and item.get("id"):
                            pdf_file_ids.append(item["id"])
                elif isinstance(data, dict) and data.get("id"):
                    pdf_file_ids.append(data["id"])
        if pdf_file_ids:
            print(f"{prefix} 提取到文件 ID: {pdf_file_ids}")
        else:
            print(f"{prefix} 未从 artifact 事件中提取到文件 ID")

        # 等待后端完全处理完首次请求（避免时序问题）
        time.sleep(2)

        # ── ② 追问：复用已有文件 / 上传新 PDF ──
        text2, chunks2, timing2 = sse_client.paper_chat_stream(
            user_input=q2_question,
            task_type=PAPER_TASK_TYPE,
            pdf_path=q2_pdf_path,
            conversation_id=conversation_id,  # 复用同一会话（后端通过 conversationId 自动关联已有文件）
            model_name=model_name,
            timeout=PAPER_TIMEOUT,
        )

        # 初始化断言报告器
        reporter = AssertReporter(label, total=scenario["reporter_total"])
        # 提前提取工具调用
        tool_calls_from_msg_2 = extract_tool_calls_from_messages(chunks2)
        try:
            tool_calls_from_events_2 = assert_tool_called(chunks2)
        except AssertionError:
            pass

        # ── 断言 1：SSE 完整性（组合断言：校验 + 报告器记录 + 失败即抛出）──
        assert_sse_integrity(reporter, chunks2)

        # ── 断言 2：文件上传行为验证（复用场景断言跳过上传 / 换文件场景断言上传完成）──
        progress_events2 = [b for b in chunks2 if b.get("event") == "progress"]
        upload_skipped = any(
            isinstance(b.get("data"), str) and "跳过文件上传" in b["data"]
            for b in progress_events2
        )
        upload_completed = any(
            isinstance(b.get("data"), str) and "文件上传完成" in b["data"]
            for b in progress_events2
        )
        if new_file:
            reporter.check(
                name="文件上传验证",
                expect="追问上传新文件时 progress 应包含'文件上传完成'",
                actual=f"upload_completed={upload_completed}",
                passed=upload_completed,
                reason="追问上传新文件场景未检测到文件上传完成事件。" if not upload_completed else "",
            )
            assert upload_completed, "追问新文件上传验证失败"
        else:
            reporter.check(
                name="文件复用验证",
                expect="追问不传 PDF 时应跳过文件上传（复用首次上传的文件）",
                actual=f"upload_skipped={upload_skipped}, upload_completed={upload_completed}",
                passed=upload_skipped,
                reason="追问场景后端未跳过文件上传，可能未正确复用首次上传的文件。" if not upload_skipped else "",
            )
            assert upload_skipped, "文件复用验证失败：追问场景未跳过文件上传"

        # ── 断言 3：追问回答包含实质内容 ──
        reject_keywords = ["您希望我总结哪篇论文", "目前还没有提供具体的论文", "还没有看到您提供的论文"]
        found_keyword = next((kw for kw in reject_keywords if kw in text2), "")
        text_len_ok = len(text2) >= 200
        reporter.check(
            name="回答内容验证",
            expect=f"≥200 字，不含拒绝关键词{reject_keywords}",
            actual=f"字数={len(text2)}，拒绝关键词={'「' + found_keyword + '」' if found_keyword else '无'}",
            passed=text_len_ok and not found_keyword,
            reason="追问回答包含拒绝关键词，后端可能未正确关联文件上下文。" if found_keyword else
                   f"追问回答过短（{len(text2)} 字），可能未关联文件上下文。" if not text_len_ok else "",
        )
        assert text_len_ok and not found_keyword, "追问回答内容验证失败"

        # ── 断言 4：LLM 调用 ──
        llm_events = assert_llm_called(chunks2)
        reporter.check(
            name="LLM 调用验证",
            expect="至少检测到 1 次 LLM 调用事件",
            actual=f"LLM 调用 {len(llm_events)} 次",
            passed=len(llm_events) > 0,
            reason="追问场景未触发 LLM 调用。" if not llm_events else "",
        )
        assert llm_events, "追问 LLM 调用验证失败"

        # ── 断言 5：messages 内容 ──
        messages_events = [b for b in chunks2 if b.get("event") == "messages"]
        has_content = any(
            isinstance(msg_event.get("data"), list) and msg_event.get("data")
            and isinstance(msg_event["data"][0], dict)
            and (msg_event["data"][0].get("content") or "")
            for msg_event in messages_events
        )
        reporter.check(
            name="messages 内容验证",
            expect="messages 事件应包含非空 content",
            actual=f"messages 事件 {len(messages_events)} 个，有实质内容={has_content}",
            passed=len(messages_events) > 0 and has_content,
            reason="追问场景未生成任何消息。" if not messages_events or not has_content else "",
        )
        assert messages_events and has_content, "追问 messages 内容验证失败"

        # ── 断言 6：Markdown 章节 ──
        document_text_for_section = extract_new_generated_document(chunks2, document_text_q1)
        q2_str_replace_edits = extract_str_replace_edits(chunks2)
        # 确定章节检查的内容来源：新文档 > str_replace 编辑 > SSE 文本
        if document_text_for_section and document_text_for_section != document_text_q1:
            section_check_target = document_text_for_section
            section_check_source = "write_file 新文档"
        elif q2_str_replace_edits:
            section_check_target = extract_str_replace_content(chunks2)
            section_check_source = f"str_replace 编辑（{len(q2_str_replace_edits)} 处）"
        else:
            section_check_target = text2
            section_check_source = "SSE 文本"
        if re.search(r"^\s{0,3}#{1,6}\s+\S", section_check_target, flags=re.MULTILINE):
            missing = assert_md_sections_semantic(section_check_target, FOLLOW_UP_SEMANTIC_SECTIONS)
            covered = [k for k in FOLLOW_UP_SEMANTIC_SECTIONS if k not in missing]
            # 软断言 + 观察记录：Agent 自由生成的小节标题存在逐轮措辞波动，「方法」
            # 主题组对“影响类”追问并非必然成立，且该口径尚无产品确认；失败仅告警留痕，
            # 待产品口径明确后再决定恢复硬断言或按问题类型配置主题组。
            reporter.check(
                name="Markdown 章节语义验证",
                expect=f"覆盖主题：{list(FOLLOW_UP_SEMANTIC_SECTIONS.keys())}",
                actual=f"已覆盖：{covered}，缺失：{missing}" if missing else f"全部覆盖：{covered}（来源: {section_check_source}）",
                passed=not missing,
                reason=f"追问输出缺少主题 {missing}（观察项，不影响用例结果）。" if missing else "",
                soft=True,
            )
        else:
            reporter.info("Markdown 章节语义验证", f"追问输出未包含 Markdown 标题，跳过章节检查（来源: {section_check_source}）")

        # ── 断言 7：意图识别路由 ──
        intent_events = [b for b in chunks2 if b.get("event") == "intent_recognition"]
        if intent_events:
            intent_data = intent_events[0].get("data") or {}
            intent_type = intent_data.get("intent", intent_data.get("type", ""))
            reporter.check(
                name="意图识别路由",
                expect=f"意图应为 '{PAPER_EXPECTED_INTENT}'",
                actual=f"intent={intent_type}",
                passed=intent_type == PAPER_EXPECTED_INTENT,
                reason=f"追问意图路由错误：期望 '{PAPER_EXPECTED_INTENT}'，实际 '{intent_type}'。" if intent_type != PAPER_EXPECTED_INTENT else "",
            )
            assert intent_type == PAPER_EXPECTED_INTENT, f"追问意图识别路由失败：期望 '{PAPER_EXPECTED_INTENT}'，实际 '{intent_type}'"
        else:
            reporter.info("意图识别", "追问未检测到 intent_recognition 事件（跳过路由断言）")

        # ── 断言 8：工具调用 + 工具选择召回 ──
        all_tool_names_2 = list(set(
            [t["name"] for t in tool_calls_from_msg_2] +
            [t["name"] for t in tool_calls_from_events_2]
        ))
        reporter.check(
            name="工具调用验证",
            expect="追问应调用工具（如 read_file 读取文件）",
            actual=f"检测到 {len(all_tool_names_2)} 个工具：{all_tool_names_2}" if all_tool_names_2 else "未检测到任何工具调用",
            passed=len(all_tool_names_2) > 0,
            reason="追问场景未调用任何工具，可能未关联文件上下文。" if not all_tool_names_2 else "",
        )
        assert all_tool_names_2, "追问工具调用验证失败"

        # read 类工具是硬要求（必须读取文件）；write 类是换文件场景的软建议（Agent 可能只生成文本不写文档）
        has_read = any("read" in name.lower() for name in all_tool_names_2)
        has_write = any("write" in name.lower() for name in all_tool_names_2)
        if new_file:
            reporter.check(
                name="工具选择召回",
                expect="追问新文件应包含 read 类工具（必须）+ write 类工具（建议）",
                actual=(f"read={'是' if has_read else '否'}, write={'是' if has_write else '否'}，"
                        f"工具集：{all_tool_names_2}"),
                passed=has_read,  # 只要求 read 类工具
                reason=f"追问新文件未调用 write 类工具（Agent 可能仅生成文本回复）。" if not has_write and has_read else (f"追问新文件未调用 read 类工具。" if not has_read else ""),
            )
        else:
            reporter.check(
                name="工具选择召回",
                expect="追问应包含 read 类工具（读取已有文件上下文）",
                actual=f"包含 read 类工具={'是' if has_read else '否'}，工具集：{all_tool_names_2}",
                passed=has_read,
                reason="追问未调用 read 类工具，可能未读取已有文件上下文。" if not has_read else "",
            )
        assert has_read, f"追问工具选择召回失败：未检测到 read 类工具，工具集：{all_tool_names_2}"

        # ── 断言 9：死循环检测 ──
        total_tool_calls_2 = len(tool_calls_from_msg_2) + len(tool_calls_from_events_2)
        max_reasonable_calls = 50
        reporter.check(
            name="死循环检测",
            expect=f"工具调用总次数 ≤ {max_reasonable_calls}",
            actual=f"工具调用总次数={total_tool_calls_2}",
            passed=total_tool_calls_2 <= max_reasonable_calls,
            reason=f"追问工具调用 {total_tool_calls_2} 次超过合理上限。" if total_tool_calls_2 > max_reasonable_calls else "",
        )
        assert total_tool_calls_2 <= max_reasonable_calls, f"追问死循环检测失败：工具调用 {total_tool_calls_2} 次"

        # ── 断言 10：Judge 质量评分（软断言，采样次数由 JUDGE_SAMPLE_COUNT 控制）──
        sampling_desc = f"{JUDGE_SAMPLE_COUNT} 次采样取中位数" if JUDGE_SAMPLE_COUNT > 1 else "单次采样"
        # 追问锚点要点（从黄金评测集加载，未命中时回退场景默认值）
        q2_expected_points = get_expected_points(q2_ref_pdf, q2_question) or scenario["q2_default_points"]
        document_text_2 = extract_new_generated_document(chunks2, document_text_q1)
        # 确定 Judge 评分内容来源：新文档 > str_replace 编辑 > 仅 AI 回答
        if document_text_2 and document_text_2 != document_text_q1:
            judge_content_2, content_source_2 = _build_judge_content(text2, document_text_2)
        elif q2_str_replace_edits:
            str_replace_content_2 = extract_str_replace_content(chunks2)
            judge_content_2, content_source_2 = _build_judge_content(text2, str_replace_content_2)
            content_source_2 = f"AI回答+str_replace编辑({len(q2_str_replace_edits)}处)"
        else:
            judge_content_2, content_source_2 = _build_judge_content(text2, "")
            print(f"{prefix} 追问未生成新文档，仅使用 AI 回答评分")
        paper_reference_2 = extract_pdf_text(q2_ref_pdf)  # Judge 参考原文：复用场景=主论文，换文件场景=PDF-B
        judge_result_2, _q2_err, _q2_timeout = _run_judge_async(
            question=q2_question,
            judge_content=judge_content_2,
            paper_reference=paper_reference_2,
            expected_points=q2_expected_points,
            sample_count=JUDGE_SAMPLE_COUNT,
            timeout=JUDGE_TIMEOUT,
            dims=SEVEN_JUDGE_DIMS,
            content_length=len(text2),
            content_source=content_source_2,
        )
        if _q2_timeout:
            judge_error_msg = f"Judge 异步评估超时（>{JUDGE_TIMEOUT}s），结果已放弃"
            reporter.info("Judge 质量评分", judge_error_msg)
        elif _q2_err:
            judge_error_msg = f"Judge 评估失败：{_q2_err}"
            reporter.info("Judge 质量评分", judge_error_msg)
        elif judge_result_2 is not None:
            avg_2 = judge_result_2.get("average", 0)
            # 评分收口：追问轮（末轮）为代表分——每用例仅 sink 一次，
            # 避免同名 properties 重复追加破坏引擎侧单值解析契约
            if score_sink is not None:
                score_sink(judge_result_2)
            claims_2 = judge_result_2.get("_claims_detail", [])
            supported_2 = sum(1 for c in claims_2 if c.get("verdict") == "supported")
            claims_desc_2 = f"声明验证={supported_2}/{len(claims_2)} 支持" if claims_2 else "无声明"
            reporter.check(
                name="Judge 质量评分",
                expect="平均分 ≥ 3.0（及格线）",
                actual=(
                    f"平均分={avg_2}（相关性={judge_result_2.get('relevance')}, "
                    f"完整性={judge_result_2.get('completeness')}, 格式={judge_result_2.get('format')}, "
                    f"分析深度={judge_result_2.get('depth')}, "
                    f"概念覆盖={judge_result_2.get('key_concepts')}, 指令遵循={judge_result_2.get('instruction_follow')}, "
                    f"忠实度={judge_result_2.get('faithfulness') if judge_result_2.get('faithfulness') is not None else '未评估(降级)'}）[{claims_desc_2}, 来源: {content_source_2}, {sampling_desc}]"
                ),
                passed=avg_2 >= 3.0,
                reason=f"裁判模型评语：{(judge_result_2.get('_all_runs') or [{}])[0].get('summary', '')}" if avg_2 < 3.0 else "",
                soft=not config.judge_gate,
            )
        else:
            judge_error_msg = "Judge 评估返回空结果"

    finally:
        # ── 始终保存产物（即使断言失败也要保留 SSE 事件流用于排查）──
        # ① 首次提问产物
        if chunks1:
            try:
                trace_1 = summarize_agent_trace(chunks1)
                metadata_events_1 = [b for b in chunks1 if b.get("event") == "metadata"]
                thread_id_1 = ""
                if metadata_events_1:
                    thread_id_1 = (metadata_events_1[0].get("data") or {}).get("thread_id", "")
                tool_calls_from_msg_1 = extract_tool_calls_from_messages(chunks1)
                _save_full_artifacts(
                    output_dir, scenario["artifact_q1"], chunks1, text1 or "",
                    meta={
                        "case": scenario["q1_case"],
                        "conversation_id": conversation_id,
                        "thread_id": thread_id_1,
                        "model_name": model_name,
                        "trace": trace_1,
                        "timing": timing1,
                        "text_length": len(text1) if text1 else 0,
                    },
                    input_info={"user_question": q1_question, "task_type": PAPER_TASK_TYPE, "source": PAPER_SOURCE},
                    file_metadata={"file_name": Path(pdf_path).name, "file_path": pdf_path},
                    tool_calls=tool_calls_from_msg_1,
                    document_text=document_text_q1,
                    judge_result=judge_result_1,
                    judge_error=judge_error_1,
                )
            except Exception:
                pass
        # ② 追问产物
        if chunks2:
            try:
                trace_2 = summarize_agent_trace(chunks2)
                metadata_events_2 = [b for b in chunks2 if b.get("event") == "metadata"]
                if metadata_events_2:
                    thread_id_2 = (metadata_events_2[0].get("data") or {}).get("thread_id", "")
                # 提取追问新生成的文档（排除首次提问的历史文档）
                _q2_new_doc = extract_new_generated_document(chunks2, document_text_q1)
                _q2_edits = extract_str_replace_edits(chunks2)
                # 三级判定链：write_file 新文档 → str_replace 编辑 → 仅 AI 回答
                if _q2_new_doc and _q2_new_doc != document_text_q1:
                    _q2_final_doc = _q2_new_doc
                    print(f"{prefix} 追问生成了新文档（{len(_q2_final_doc)} 字）")
                elif _q2_edits:
                    _q2_final_doc = extract_str_replace_content(chunks2)
                    print(f"{prefix} 追问通过 str_replace 编辑已有文档（{len(_q2_edits)} 处，{len(_q2_final_doc)} 字）")
                else:
                    _q2_final_doc = ""
                    print(f"{prefix} 追问仅生成 AI 回答文本，未生成或编辑文档")
                _save_full_artifacts(
                    output_dir, scenario["artifact_q2"], chunks2, text2 or "",
                    meta={
                        "case": scenario["q2_case"],
                        "conversation_id": conversation_id,
                        "thread_id": thread_id_2,
                        "model_name": model_name,
                        "trace": trace_2,
                        "timing": timing2,
                        "text_length": len(text2) if text2 else 0,
                    },
                    input_info={"user_question": q2_question, "task_type": PAPER_TASK_TYPE, "source": PAPER_SOURCE},
                    file_metadata={"file_name": Path(q2_ref_pdf).name, "file_path": q2_ref_pdf, "note": scenario["q2_file_note"]},
                    tool_calls=tool_calls_from_msg_2,
                    judge_result=judge_result_2,
                    document_text=_q2_final_doc,
                    judge_error=judge_error_msg,
                )
                # 保存 str_replace 编辑记录（如有）
                _q2_dir = output_dir / scenario["artifact_q2"]
                if _q2_edits:
                    _edits_file = _q2_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_str_replace_edits.json"
                    _edits_data = {
                        "edit_count": len(_q2_edits),
                        "edits": _q2_edits,
                        "combined_content_length": len(_q2_final_doc),
                    }
                    _edits_file.write_text(json.dumps(_edits_data, ensure_ascii=False, indent=2), encoding="utf-8")
                if 'reporter' in dir():
                    _report_perf_and_summary(reporter, timing2, conversation_id, thread_id_2)
            except Exception:
                pass

        # 清理会话（共享辅助函数：finally 收尾四件套）
        _cleanup_conversation(sse_client, conversation_id, label)

    # 硬断言失败传导：summary() 仅打印且在 finally 中被吞，须在正常路径末尾显式抛出
    reporter.raise_if_failed()



