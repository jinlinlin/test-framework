"""离线假裁判：本地随机端口起 OpenAI 兼容 /chat/completions 服务，返回预设评分 JSON。

与 mock_gateway 同族定位（请求侧/响应侧都可控、不连真服务、不烧 token），专供
Judge 评分链路的离线契约测试：JudgeClient 按 base_url 显式指向假裁判即可运行，
不依赖 config/.env 的 JUDGE_* 配置。

响应形态对齐真 DashScope compatible-mode：
    choices[0].message.content = 裁判评分 JSON 文本（六维新格式 dict{score,...}）
    usage = prompt/completion/total tokens

维护约定：judge_client._call_llm 的请求协议或 evaluate 的输出校验变化时，
同步增删本模块的返回形态与 test_score_pipeline_offline.py 的断言。
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

# 主观六维默认分值（新格式：dict 含 score/name/reason），用例可经 set_scores 覆盖
DEFAULT_SCORES: Dict[str, Any] = {
    d: {"score": 4.5, "name": d, "reason": "mock 裁判固定评价"}
    for d in ("relevance", "completeness", "depth",
              "instruction_follow", "format", "key_concepts")
}


class FakeJudge:
    """上下文管理器形态的假裁判服务：with 起停，requests 记录收到的请求体。"""

    def __init__(self) -> None:
        self.scores: Dict[str, Any] = dict(DEFAULT_SCORES)  # 下一次响应的六维内容
        self.extra_fields: Dict[str, Any] = {}  # 追加到裁判输出顶层（如错误的 average）
        self.requests: List[Dict[str, Any]] = []  # 收到的请求体（供 prompt 契约断言）
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def __enter__(self) -> "FakeJudge":
        """启动服务（随机空闲端口），返回自身供取 base_url。"""
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802（BaseHTTPRequestHandler 命名约定）
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                outer.requests.append(body)
                judge_output = dict(outer.scores)
                judge_output.update(outer.extra_fields)
                content = json.dumps(judge_output, ensure_ascii=False)
                resp = {
                    "choices": [{"message": {"role": "assistant", "content": content}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                }
                payload = json.dumps(resp, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args) -> None:  # 静默默认 stderr 访问日志
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        """停止服务并等待线程退出。"""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        """假服务基地址（OpenAI 兼容语义：JudgeClient 会拼 /chat/completions）。"""
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    # ------------------------------------------------------------------
    # 行为控制
    # ------------------------------------------------------------------
    def set_scores(self, scores: Dict[str, Any]) -> None:
        """覆盖下一次响应的六维内容（数字旧格式与 dict 新格式均支持）。"""
        self.scores = dict(scores)

    def set_average(self, value: float) -> None:
        """在裁判输出顶层写入 LLM 自报 average（用于验证客户端代码重算覆盖它）。"""
        self.extra_fields = {"average": value}
