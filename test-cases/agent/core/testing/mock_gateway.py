"""离线假网关：在本地随机端口起 HTTP 服务，捕获 SSE 客户端真实发出的请求，用于请求侧契约测试。

借鉴被测项目 uniresearch-server 的 OkHttp MockWebServer 用法（见
uniplore-spring-boot3-starter-llm-api 的 OllamaChannelClientTest）：不访问外网、不烧 token，
把"发出的请求长什么样"变成可断言对象，专治字段写错、编码降级、鉴权头缺失、重试没生效这类
只能从请求侧发现问题、响应侧回归永远覆盖不到的坑。

为什么必须锁住请求侧（真实踩坑，勿删）：
    文献解读追问持续 HTTP 500 的最终根因，不是后端缺陷，而是 httpx 在 files=None/[] 时
    把 Content-Type 从 multipart/form-data 静默降级为 application/x-www-form-urlencoded，
    后端 Spring Controller 依赖 multipart 绑定参数故绑定失败。客户端用"追加一个空文件部分"
    强制 multipart 修复（见 sse_client._post_sse_multipart）。那段写法形似冗余垃圾代码，
    极易被后人当无用代码清理掉——一旦清理，追问用例立刻回到 500，且排障成本是数天。
    本模块与 test_sse_request_contract_offline.py 就是给这个坑上的锁。

维护约定：新增/修改 sse_client 的请求字段、编码方式、鉴权头、重试策略时，必须同步
在 test_sse_request_contract_offline.py 增删对应契约断言。
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs

from core.clients.sse_client import (  # 复用真实路径常量，避免契约测试与客户端各写一份路径
    OSS_UPLOAD_PATH,
    PAPER_CHAT_STREAM_PATH,
)

# 假 SSE 事件流：格式对齐真服务（event 行 + data 行 + 空行分隔，末事件为 end/[DONE]）
# 取 messages-tuple 结构，对齐 paper 透传 LangGraph 的真实形态（见 sse_client._extract_delta_text）
DEFAULT_SSE_EVENTS: List[Tuple[str, Any]] = [
    ("start", {"conversationId": "900000000000000001", "threadId": "mock-thread-1"}),
    ("messages-tuple", [{"content": "这是假网关返回的第一段解读内容。", "type": "AIMessageChunk"}, {"langgraph_node": "agent"}]),
    ("messages-tuple", [{"content": "第二段内容。", "type": "AIMessageChunk"}, {"langgraph_node": "agent"}]),
    ("end", "[DONE]"),
]

# 500 响应体：复刻真服务形态，便于确认客户端读到的状态码/响应体一致
ERROR_SERVICE_BODY = {"code": 1000, "msg": "Error service"}


def build_sse_body(events: List[Tuple[str, Any]]) -> bytes:
    """把 (事件名, data) 列表序列化为 SSE 文本流字节；data 非字符串时按 JSON 编码。"""
    lines: List[str] = []
    for name, data in events:
        payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        lines.append(f"event: {name}\ndata: {payload}\n\n")
    return "".join(lines).encode("utf-8")


def _split_multipart(content_type: str, body: bytes) -> List[Dict[str, Any]]:
    """按 boundary 手工切分 multipart 请求体，返回原始段列表（不做语义归类）。

    手工切分而非用 stdlib email/cgi：一是 cgi 已废弃、版本兼容性差；
    二是文件段含 PDF 二进制，逐段二分 headers/正文已足够满足契约断言。

    每段结构：{name, filename, content_type, size, text}。filename 为 None 表示该段
    header 里没有 filename 参数——注意 httpx 生成的"强制 multipart"空段属于这种形态，
    它既不是文本字段也不是文件段，故此处只忠实记录，由 CapturedRequest 分类。
    """
    match = re.search(r'boundary="?([^";]+)"?', content_type)
    if not match:
        return []
    delim = b"--" + match.group(1).encode()
    segments: List[Dict[str, Any]] = []
    for piece in body.split(delim):
        if not piece or piece.startswith(b"--"):  # 跳过前置空段与结束段 --
            continue
        segment = piece[2:] if piece.startswith(b"\r\n") else piece  # 去掉分隔符后的 CRLF
        head, sep, content = segment.partition(b"\r\n\r\n")
        if not sep:
            continue
        if content.endswith(b"\r\n"):  # 去掉本段结尾 CRLF（下一个分隔符前的换行）
            content = content[:-2]
        header_text = head.decode("utf-8", errors="replace")
        name_match = re.search(r'name="([^"]*)"', header_text)
        filename_match = re.search(r'filename="([^"]*)"', header_text)
        ctype_match = re.search(r"Content-Type:\s*([^\r\n;]+)", header_text, re.I)
        segments.append({
            "name": name_match.group(1) if name_match else "",
            "filename": filename_match.group(1) if filename_match else None,
            "content_type": ctype_match.group(1).strip() if ctype_match else "",
            "size": len(content),
            "text": content.decode("utf-8", errors="replace"),
        })
    return segments


class CapturedRequest:
    """一次被捕获的请求：保留原始字节，字段/文件按需解析。"""

    def __init__(self, method: str, path: str, headers: Dict[str, str], body: bytes) -> None:
        self.method = method
        self.path = path
        self.headers = headers  # 键统一小写，查找大小写不敏感
        self.body = body
        self._segments: Optional[List[Dict[str, Any]]] = None  # 解析结果缓存（PDF 二进制不应反复切）

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")

    @property
    def is_multipart(self) -> bool:
        """请求体是否为 multipart/form-data（追问 500 的关键契约位）。"""
        return self.content_type.startswith("multipart/form-data")

    @property
    def encoding_degraded(self) -> bool:
        """是否被 httpx 静默降级为 urlencoded——降级即后端 500，契约测试的核心失败信号。"""
        return self.content_type.startswith("application/x-www-form-urlencoded")

    @property
    def segments(self) -> List[Dict[str, Any]]:
        """请求体的全部 multipart 段（原始事实），按 name/filename 分类前的完整列表。"""
        if self._segments is None:
            if self.is_multipart:
                self._segments = _split_multipart(self.content_type, self.body)
            elif self.encoding_degraded:
                # urlencoded 降级时也能解出字段，让失败信息可读而非"无字段"
                parsed = parse_qs(self.body.decode("utf-8", errors="replace"))
                self._segments = [
                    {"name": k, "filename": None, "content_type": "", "size": len(v[-1]), "text": v[-1]}
                    for k, v in parsed.items()
                ]
            else:
                self._segments = []
        return self._segments

    @property
    def fields(self) -> Dict[str, str]:
        """具名文本字段（已排除强制 multipart 的匿名空段，不污染字段集合断言）。"""
        return {s["name"]: s["text"] for s in self.segments if s["filename"] is None and s["name"]}

    @property
    def files(self) -> List[Dict[str, Any]]:
        """带 filename 的真文件段。"""
        return [s for s in self.segments if s["filename"] is not None]

    @property
    def anonymous_parts(self) -> List[Dict[str, Any]]:
        """既非具名字段也非文件的匿名段——即客户端为强制 multipart 追加的空文件部分。

        它的存在就是 500 修复本体，不是垃圾代码。
        """
        return [s for s in self.segments if s["filename"] is None and not s["name"]]

    @property
    def json_body(self) -> Any:
        return json.loads(self.body.decode("utf-8")) if self.body else None

    def field_names(self) -> List[str]:
        return sorted(self.fields)

    def __repr__(self) -> str:  # 失败信息里只露关键字段，避免刷屏
        return (
            f"<CapturedRequest {self.method} {self.path} "
            f"ct={self.content_type.split(';')[0]} fields={self.field_names()} "
            f"files={[f['filename'] for f in self.files]} anonymous={len(self.anonymous_parts)}>"
        )


class _Handler(BaseHTTPRequestHandler):
    """请求处理：捕获请求后按路径路由到 chatStream / OSS 上传，响应编排取自 gateway 状态。"""

    protocol_version = "HTTP/1.1"  # 连接语义与真网关一致，避免每请求重建连接

    def _gw(self) -> "MockGateway":
        return self.server.gateway  # type: ignore[attr-defined]  # 由 start() 绑定

    def do_POST(self) -> None:  # noqa: N802 - stdlib 固定命名
        gw = self._gw()
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else b""
        req = CapturedRequest("POST", self.path, {k.lower(): v for k, v in self.headers.items()}, body)
        gw.record(req)
        if self.path == OSS_UPLOAD_PATH:
            self._send_json(200, {
                "code": 200,
                "msg": "success",
                "data": {
                    "url": "https://mock-oss.local/paper/mock.pdf",
                    "fileName": "mock_oss_file.pdf",
                    "size": length,
                },
            })
            return
        if self.path == PAPER_CHAT_STREAM_PATH:
            status = gw.next_chat_status()
            if status == 200:
                self._send(200, "text/event-stream", build_sse_body(gw.sse_events))
            else:
                self._send_json(status, ERROR_SERVICE_BODY)
            return
        self._send_json(404, {"code": 404, "msg": f"mock 网关未定义该路径：{self.path}"})

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        self._send(status, "application/json", json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def log_message(self, *args: Any) -> None:  # 屏蔽 stdlib 默认访问日志，避免污染测试输出
        pass


class MockGateway:
    """本地假网关：起线程监听随机端口，记录请求，可编程指定 chatStream 的响应序列。

    用法::

        with MockGateway() as gw:
            client = SseClient(base_url=gw.base_url)
            client.paper_chat_stream(user_input="解读", task_type="interpret")
            assert gw.last_request().is_multipart
    """

    def __init__(self, sse_events: Optional[List[Tuple[str, Any]]] = None) -> None:
        self.requests: List[CapturedRequest] = []
        self.sse_events = sse_events if sse_events is not None else DEFAULT_SSE_EVENTS
        self.chat_statuses: List[int] = []  # chatStream 状态码队列，按序消耗；耗尽后返回 200
        self._lock = threading.Lock()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def __enter__(self) -> "MockGateway":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    def start(self) -> "MockGateway":
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.gateway = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    @property
    def base_url(self) -> str:
        """客户端的网关地址；路径常量本身已含 /uniplore-server-uniresearch 前缀，此处不带前缀。"""
        if self._server is None:
            raise RuntimeError("MockGateway 未启动，请先 start() 或使用 with 语句")
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    # ------------------------------------------------------------------
    # 编排与查询
    # ------------------------------------------------------------------
    def record(self, req: CapturedRequest) -> None:
        with self._lock:
            self.requests.append(req)

    def next_chat_status(self) -> int:
        with self._lock:
            if self.chat_statuses:
                return self.chat_statuses.pop(0)
        return 200

    def enqueue_chat_statuses(self, statuses: List[int]) -> None:
        """预设 chatStream 连续返回的状态码（测 500 重试、401 重登用），按序消耗。"""
        with self._lock:
            self.chat_statuses = list(statuses)

    def reset(self) -> None:
        """清空捕获记录与状态码队列，供同一 fixture 内多次调用隔离。"""
        with self._lock:
            self.requests.clear()
            self.chat_statuses = []

    def requests_for(self, path: str) -> List[CapturedRequest]:
        return [r for r in self.requests if r.path == path]

    def last_request(self, path: str = PAPER_CHAT_STREAM_PATH) -> CapturedRequest:
        matched = self.requests_for(path)
        if not matched:
            raise AssertionError(
                f"未捕获到 {path} 的请求，实际收到：{[(r.method, r.path) for r in self.requests]}"
            )
        return matched[-1]
