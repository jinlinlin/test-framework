"""请求侧契约离线回归：断言 SSE 客户端**发出去的请求**长什么样，而非 AI 回了什么。

借鉴被测项目 llm-api 模块的 OkHttp MockWebServer 做法（OllamaChannelClientTest 用
mockWebServer.takeRequest() 反查请求体断言字段），把"面单填对没"变成可执行断言。

为什么要有这个文件（都是真实踩过的坑，响应侧回归完全覆盖不到）：
    1) 追问 500 的最终根因是 httpx 在 files=None 时把 Content-Type 静默降级成
       application/x-www-form-urlencoded，后端 Spring 依赖 multipart 绑定参数故报 500。
       修复手段是往 files 里追加一个空文件部分强制 multipart——那段代码形似冗余，被当成
       无用代码清理掉的概率很高，一清理追问就回到 500。本文件第 2 条用例就是那把锁。
    2) 字段对齐改造曾多传 pdfFileIds / threadId（前端追问根本不发），把可自修的客户端问题
       误报成后端缺陷挂了好几天。本文件用"字段集合精确相等"锁死多余字段。
    3) mode 与 modeName、keywords 必须是 JSON 字符串、conversationId 必须以字符串提交、
       首次提问不传 conversationId——这些只靠 sse_client.py 的注释保护，注释不会失败。

维护约定：改动 sse_client.py 的请求字段、编码方式、鉴权头、重试/重登策略时，必须同步
增删本文件对应用例；新增豁免/字段请写清"没有这条断言会漏掉什么事故"。

运行（秒级、不连真服务、不消耗 Judge token）：
    python -m pytest test_cases/paper_interpret/test_sse_request_contract_offline.py -q
    python -m pytest -m offline -q          # 与判定函数离线回归一起跑
"""
import json
from typing import Any, Dict, List

import pytest

from core.clients import sse_client as sse_client_module
from core.clients.sse_client import (
    OSS_UPLOAD_PATH,
    PAPER_CHAT_STREAM_PATH,
    SseClient,
    SseError,
)
from core.testing.mock_gateway import MockGateway

pytestmark = [pytest.mark.paper, pytest.mark.offline]

# 追问场景的字段全集契约：多一个少一个都算违约（曾多传字段导致误判后端缺陷）
FOLLOW_UP_FIELD_CONTRACT = ["conversationId", "taskType", "userInput"]


@pytest.fixture(scope="module")
def gateway():
    """模块级假网关：起一次本地端口，全文件复用。"""
    with MockGateway() as gw:
        yield gw


@pytest.fixture(autouse=True)
def _clear_gateway(gateway: MockGateway):
    """每条用例前清空捕获记录，避免相互串请求。"""
    gateway.reset()


@pytest.fixture
def client(gateway: MockGateway) -> SseClient:
    """指向假网关的客户端（base_url 显式传入，不依赖 config 的真实地址）。"""
    return SseClient(base_url=gateway.base_url, timeout=10)


def _make_pdf(tmp_path) -> str:
    """造一个最小 PDF 文件：客户端只做上传，不解析内容，无需真 PDF。"""
    pdf = tmp_path / "contract_probe.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% contract probe placeholder\n")
    return str(pdf)


def _file_part_by_name(req, name: str) -> Dict[str, Any]:
    """按表单字段名取文件段，取不到即失败并打印实际收到的段。"""
    for part in req.files:
        if part["name"] == name:
            return part
    raise AssertionError(f"请求缺少文件段 {name}，实际文件段：{req.files}")


class TestFirstAskRequestContract:
    """首次提问（带 PDF）：字段集 + 文件段 + OSS 前置上传 + 鉴权头。"""

    def test_首次提问上传PDF并携带OSS文件信息(self, client: SseClient, gateway: MockGateway, tmp_path):
        pdf_path = _make_pdf(tmp_path)
        client.paper_chat_stream(user_input="解读当前文献", task_type="interpret", pdf_path=pdf_path)

        # 解读链路是"先传 OSS 拿文件信息，再发 chatStream"，顺序与次数都是契约的一部分
        oss_requests = gateway.requests_for(OSS_UPLOAD_PATH)
        assert len(oss_requests) == 1, f"预期恰好 1 次 OSS 上传，实际 {len(oss_requests)} 次"
        assert _file_part_by_name(oss_requests[0], "pdfFile")["filename"] == "contract_probe.pdf"

        req = gateway.last_request(PAPER_CHAT_STREAM_PATH)
        assert req.method == "POST"
        assert req.is_multipart, f"chatStream 必须是 multipart，实际 Content-Type={req.content_type}"

        fields = req.fields
        assert fields["taskType"] == "interpret"
        assert fields["userInput"] == "解读当前文献"
        # fileInfos 走 Spring 索引式表单绑定：fileInfos[0].ossUrl，字段名格式写错后端绑不上
        assert fields["fileInfos[0].ossUrl"] == "https://mock-oss.local/paper/mock.pdf"
        assert fields["fileInfos[0].fileName"] == "mock_oss_file.pdf"
        assert fields["fileInfos[0].fileSize"].isdigit(), "fileSize 必须以数字字符串提交"

        # 首次提问不传 conversationId：由后端在首个事件里返回，客户端传了反而破坏会话创建
        assert "conversationId" not in fields, f"首次提问不应带 conversationId，实际字段：{req.field_names()}"

        pdf_part = _file_part_by_name(req, "pdfFile")
        assert pdf_part["content_type"] == "application/pdf"
        assert pdf_part["size"] > 0

    def test_鉴权头对齐前端requestFetch拦截器(self, client: SseClient, gateway: MockGateway):
        client.paper_chat_stream(user_input="追问内容", conversation_id=900000000000000001)
        headers = gateway.last_request().headers
        # 三个头缺任一个都会被网关拦掉，且必须是前端那套自定义头（Uniplore-Auth 而非通用 Bearer）
        for required in ("uniplore-auth", "authorization", "accept-language"):
            assert required in headers, f"缺少鉴权头 {required}，实际：{sorted(headers)}"
        assert headers["accept-language"] == "zh-CN"
        assert "content-type" not in headers or headers["content-type"].startswith("multipart/form-data"), (
            "不应手动写死 Content-Type：boundary 需由 httpx 生成，写死会导致后端解析失败"
        )


class TestFollowUpRequestContract:
    """追问（不带文件）：编码不降级 + 字段集合精确相等。本文件最高价值用例。"""

    def test_追问无文件时禁止降级为urlencoded(self, client: SseClient, gateway: MockGateway):
        """httpx 在 files=None 时会静默降级为 urlencoded，后端绑定失败报 500。

        删掉 _post_sse_multipart 里"追加空文件部分"那两行，本用例立即失败——这就是它的锁。
        """
        client.paper_chat_stream(user_input="第二段讲了什么", conversation_id=900000000000000001)
        req = gateway.last_request()
        assert not req.encoding_degraded, (
            "追问请求被降级为 application/x-www-form-urlencoded，真服务必然返回 HTTP 500 "
            "（后端 Spring 依赖 multipart 绑定参数）。修复位置：sse_client._post_sse_multipart "
            "中 files 为空时追加空文件部分。"
        )
        assert req.is_multipart
        assert req.anonymous_parts, (
            "追问请求应包含那个用于强制 multipart 的匿名空段；它看似垃圾代码，实为 500 修复本体"
            "（httpx 仅当 files 非空时才生成 multipart 编码）"
        )
        assert not any(p["name"] == "pdfFile" for p in req.files), "追问不应重复上传 PDF"
        assert not gateway.requests_for(OSS_UPLOAD_PATH), "追问不应触发 OSS 上传"

    def test_追问字段集合精确相等禁止多余字段(self, client: SseClient, gateway: MockGateway):
        client.paper_chat_stream(user_input="第二段讲了什么", conversation_id=900000000000000001)
        req = gateway.last_request()
        assert req.field_names() == FOLLOW_UP_FIELD_CONTRACT, (
            f"追问字段集与前端不一致：期望 {FOLLOW_UP_FIELD_CONTRACT}，实际 {req.field_names()}。"
            "多余字段（如 pdfFileIds/threadId）本身就是 500 的触发条件之一，不能凭 DTO 有该字段就发送"
        )
        # conversationId 以 String 提交（对齐前端 String(conversationId)）
        assert req.fields["conversationId"] == "900000000000000001"

    def test_threadId与pdfFileIds仅显式传参才出现(self, client: SseClient, gateway: MockGateway):
        """这两个字段默认必须不发送；参数存在≠前端也发送（历史误判的根源）。"""
        client.paper_chat_stream(
            user_input="第二段讲了什么",
            conversation_id=900000000000000001,
            thread_id="mock-thread-1",
            pdf_file_ids=["2103006702847791104"],
        )
        fields = gateway.last_request().fields
        assert fields["threadId"] == "mock-thread-1"
        assert fields["pdfFileIds"] == json.dumps(["2103006702847791104"])


class TestFieldEncodingContract:
    """字段命名与序列化：注释里写过的规矩，逐条变成断言。"""

    def test_问答模式字段名是modeName(self, client: SseClient, gateway: MockGateway):
        client.paper_chat_stream(user_input="解读", mode="thinking")
        fields = gateway.last_request().fields
        assert fields["modeName"] == "thinking"
        assert "mode" not in fields, "前端字段名是 modeName，写成 mode 会被后端取 modeName 的兼容分支漏掉"

    def test_keywords以JSON字符串提交且中文不转义(self, client: SseClient, gateway: MockGateway):
        """ChatStreamRequestDTO.keywords 是 String 类型，传成数组会让后端绑定失败。"""
        client.paper_chat_stream(
            user_input="找相关文献",
            task_type="research",
            subject="计算机科学",
            keywords=["医学影像", "Transformer"],
        )
        fields = gateway.last_request().fields
        raw = fields["keywords"]
        assert raw == json.dumps(["医学影像", "Transformer"], ensure_ascii=False)
        assert "医学影像" in raw, "keywords 被转成 \\uXXXX 转义后中文关键词检索不到"
        assert fields["subject"] == "计算机科学"

    def test_模型名以modelName提交(self, client: SseClient, gateway: MockGateway):
        client.paper_chat_stream(user_input="解读", model_name="qwen3.7-plus")
        fields = gateway.last_request().fields
        assert fields["modelName"] == "qwen3.7-plus"
        assert "/" not in fields["modelName"], "模型名须为裸名，带渠道前缀后端会报没有可用渠道"


class TestRetryContract:
    """容错策略契约：500 重试次数与退避节奏、非 500 不重试、401 只重登一次。"""

    @pytest.fixture
    def sleeps(self, monkeypatch) -> List[float]:
        """拦掉真实等待，同时记录退避序列（否则重试用例要空等 6 秒）。"""
        recorded: List[float] = []
        monkeypatch.setattr(sse_client_module.time, "sleep", lambda sec: recorded.append(sec))
        return recorded

    def test_持续500时重试两次后报错(self, client: SseClient, gateway: MockGateway, sleeps):
        gateway.enqueue_chat_statuses([500, 500, 500])
        with pytest.raises(SseError) as exc_info:
            client.paper_chat_stream(user_input="追问", conversation_id=1)
        assert exc_info.value.status_code == 500
        assert len(gateway.requests_for(PAPER_CHAT_STREAM_PATH)) == 3, "契约：首次 + 最多 2 次重试"
        assert sleeps == [2, 4], f"指数退避节奏应为 2s、4s，实际 {sleeps}"

    def test_非500状态码不重试(self, client: SseClient, gateway: MockGateway, sleeps):
        """404/403 类请求本身错误，重试只会掩盖问题并拖慢用例。"""
        gateway.enqueue_chat_statuses([404])
        with pytest.raises(SseError) as exc_info:
            client.paper_chat_stream(user_input="追问", conversation_id=1)
        assert exc_info.value.status_code == 404
        assert len(gateway.requests_for(PAPER_CHAT_STREAM_PATH)) == 1
        assert sleeps == []

    def test_401触发重新登录回调并重发一次(self, gateway: MockGateway):
        calls: List[int] = []
        client = SseClient(base_url=gateway.base_url, timeout=10, on_401=lambda: calls.append(1))
        gateway.enqueue_chat_statuses([401, 200])
        answer, _, _ = client.paper_chat_stream(user_input="追问", conversation_id=1)
        assert len(calls) == 1, "401 应触发一次重新登录回调"
        assert len(gateway.requests_for(PAPER_CHAT_STREAM_PATH)) == 2, "重登后应重发一次"
        assert answer, "重发成功后应正常拿到回答"


class TestGatewayFidelity:
    """假网关自身的可信度：流格式必须能被真解析逻辑消费，否则契约测试等于自娱自乐。"""

    def test_假SSE流被客户端正确解析(self, client: SseClient, gateway: MockGateway):
        answer, chunks, timing = client.paper_chat_stream(user_input="解读", task_type="interpret")
        assert answer == "这是假网关返回的第一段解读内容。第二段内容。"
        # 只校验前 4 个事件顺序：客户端收到 end 后 break，残留状态会在流末尾被再解析一次，
        # 多出一个重复的 end 块——这是既有行为，不断言 chunks 总数以免把巧合当契约
        assert [c["event"] for c in chunks][:4] == ["start", "messages-tuple", "messages-tuple", "end"]
        assert set(timing) == {"first_chunk_ms", "total_ms"}
        # 首包耗时应跳过 start 控制事件，从首个内容事件起算
        assert chunks[1]["ts_ms"] == timing["first_chunk_ms"]
