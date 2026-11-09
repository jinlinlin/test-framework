"""SSE 流式客户端：封装知识库对话与论文 AI 两个真实接口的流式调用、文本拼接与耗时统计。"""
import json  # 解析/序列化 SSE data 行的 JSON 内容
import time  # 统计首包耗时与总耗时
from pathlib import Path  # 处理待上传 PDF 文件路径
from typing import Any, Dict, List, Optional, Tuple  # 类型标注

import httpx  # HTTP 客户端，支持 multipart 上传与流式响应读取

try:
    import httpcore  # 底层 HTTP 库（httpx 基于 httpcore，部分异常会从 httpcore 直接抛出）
except ImportError:
    httpcore = None  # httpcore 未安装时设为 None，异常捕获时跳过

from core.utils.config import config  # 全局配置（BASE_URL / TOKEN / DATASET_ID 等）

KNOWLEDGE_COMPLETIONS_PATH = "/uniplore-server-uniresearch/knowledge/chat/completions"  # 知识库 AI 问答（KnowledgeChatController.postChatCompletions）
PAPER_CHAT_STREAM_PATH = "/uniplore-server-uniresearch/paper/chatStream"  # 论文 SSE 流式多轮对话（PaperController.chatStream）
OSS_UPLOAD_PATH = "/uniplore-server-uniresearch/paper/upload/oss"  # 论文 PDF 上传到 OSS（PaperUploadController.uploadToOss）
PAPER_CONVERSATIONS_CREATE_PATH = "/uniplore-server-uniresearch/paper/conversations/create"  # 论文会话创建（PaperController.createConversation）
PAPER_CONVERSATIONS_PATH = "/uniplore-server-uniresearch/paper/conversations"  # 论文会话查询/删除（DELETE {id}）
PAPER_CHECK_RESUME_PATH = "/uniplore-server-uniresearch/paper/checkStreamResume"  # SSE 断流恢复检查
PAPER_RESUME_PATH = "/uniplore-server-uniresearch/paper/chatStreamResume"  # SSE 断流恢复续传

# 注：接口路径常量是本模块对外契约的单一事实源；paper_interpret / robust 等用例包一律
# 从这里 import（不得再各自定义同名字面量，避免三份并存）。

SseResult = Tuple[str, List[Dict[str, Any]], Dict[str, float]]  # 返回值类型：(完整文本, 原始块列表, 耗时信息)


def build_auth_headers(token: Optional[str] = None) -> Dict[str, str]:
    """构造与前端 requestFetch.ts 请求拦截器一致的真实鉴权头。

    token 为 None 时回退 config.token；供 SseClient 与 robust 等直发 httpx 的用例共用
    （原先 robust/test_agent_robust.py 自带一份 _headers 平行实现，已收敛至此）。
    """
    return {
        "Uniplore-Auth": token or config.token,  # 自定义登录态头：真正生效的用户鉴权（前端 accessToken）
        "Authorization": config.authorization,  # 客户端 Basic 认证：Base64(clientID:clientSecret)
        "Accept-Language": "zh-CN",  # 语言头，对齐前端 preferences.app.locale
    }


def extract_biz_code(resp: httpx.Response) -> Optional[int]:
    """解析网关响应体业务码（非 JSON 响应如 SSE 流时返回 None）。

    该网关对业务错误统一返回 HTTP 200，判定拒绝与否必须看 body 里的 code。
    （原先 robust/test_agent_robust.py 的 _biz_code 平行实现，已收敛至此。）
    """
    try:
        return resp.json().get("code")
    except Exception:
        return None


class SseError(RuntimeError):
    """SSE 请求/解析失败时抛出的异常（HTTP 非 200、文件缺失等传输层错误）。"""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        """初始化异常：message 为中文错误信息，status_code 记录 HTTP 状态码供用例精确断言。"""
        super().__init__(message)  # 调用父类构造
        self.status_code = status_code  # HTTP 状态码（非 200 时记录；非 HTTP 错误为 None）


class SseClient:
    """SSE 流式调用客户端：按前端真实鉴权头发起请求，逐块解析并拼接完整文本。"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 180.0,
        verbose: bool = False,
        on_401: Optional[Any] = None,
    ) -> None:
        """初始化客户端：base_url 默认取 config.base_url，timeout 为默认读流超时（秒）。

        Args:
            base_url: 网关基础地址，默认从 config 读取。
            timeout: 默认读流超时（秒），单次调用可用 timeout 参数覆盖。
            verbose: 是否实时打印 SSE 事件流（Agent 调试模式），默认关闭。
            on_401: 401 回调函数，返回新 token 的 callable（用于自动重新登录）。
        """
        self.base_url = (base_url or config.base_url).rstrip("/")  # 网关基础地址，去尾部斜杠
        self.timeout = timeout  # 默认读流超时（秒），单次调用可用 timeout 参数覆盖
        self.verbose = verbose  # 实时打印 SSE 事件流
        self.on_401 = on_401  # 401 自动重新登录回调

    # ------------------------------------------------------------------
    # 鉴权头
    # ------------------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        """构造与前端 requestFetch.ts 请求拦截器一致的真实鉴权头（委托模块级 build_auth_headers）。"""
        return build_auth_headers()

    # ------------------------------------------------------------------
    # 模型列表：获取当前用户可用的 LLM 模型
    # ------------------------------------------------------------------
    def get_user_available_models(self) -> List[str]:
        """GET /uniplore-server-aischeduler/dashboard/user/models：获取当前用户可用模型列表。

        返回模型名称列表，为**裸模型名（不含渠道前缀）**，如 ['qwen3.7-plus', 'deepseek-v4-flash']。
        渠道由后端根据模型名自行解析；传入带 “/” 的自建格式会报“没有可用的渠道支持模型”。
        支持 401 自动重新登录重试。
        """
        path = "/uniplore-server-aischeduler/dashboard/user/models"  # 用户可用模型 API 路径
        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:  # 独立客户端
                resp = client.get(self.base_url + path, headers=self._headers())  # 携带鉴权头
            if resp.status_code != 200:  # 请求失败
                raise SseError(
                    f"获取可用模型列表失败：HTTP {resp.status_code}，响应体：{resp.text[:500]}",
                    status_code=resp.status_code,
                )
            result = resp.json()  # 解析 JSON（Result 包装）
            data = result.get("data")  # 取 data 字段
            if isinstance(data, list):  # data 为字符串列表
                return [str(m) for m in data]  # 返回模型名称列表
            return []  # 无数据时返回空列表
        except SseError as exc:
            if exc.status_code == 401 and self.on_401:
                self.on_401()
                with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                    resp = client.get(self.base_url + path, headers=self._headers())
                if resp.status_code != 200:
                    raise SseError(
                        f"获取可用模型列表失败（重试后）：HTTP {resp.status_code}，响应体：{resp.text[:500]}",
                        status_code=resp.status_code,
                    )
                result = resp.json()
                data = result.get("data")
                if isinstance(data, list):
                    return [str(m) for m in data]
                return []
            raise

    # ------------------------------------------------------------------
    # 接口 1：知识库 AI 问答（application/json + SSE）
    # ------------------------------------------------------------------
    def knowledge_chat(
        self,
        content: str,
        conversation_id: int,
        source: str = "knowledge.dataset",
        source_id: Optional[int] = None,
        mode: str = "mix",
        enable_thinking: bool = False,
        model_name: Optional[str] = None,
        refresh_message_id: Optional[str] = None,
        selected_content: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> SseResult:
        """POST /knowledge/chat/completions：JSON body 字段严格对齐 ChatMessageDTO。"""
        if source_id is None:  # 调用方未显式传 sourceId 时
            source_id = (
                int(config.dataset_id) if source == "knowledge.dataset" else 0
            )  # 知识库问答默认取 .env 的 DATASET_ID；其余来源对齐后端默认值 0
        body: Dict[str, Any] = {
            "conversationId": conversation_id,  # 对话ID（必填）：需先由 POST /knowledge/chat/conversations 创建获得
            "content": content,  # 提问内容（必填）
            "stream": True,  # 固定流式：本客户端只处理 SSE 响应
            "source": source,  # 业务来源：paper.summary / knowledge.dataset / knowledge.literature
            "sourceId": source_id,  # 业务来源ID：知识库问答时为知识库ID
            "enableThinking": enable_thinking,  # 是否返回思考过程，默认 False
            "mode": mode,  # 对话模式：local / global / hybrid / mix，默认 mix
        }
        if model_name is not None:  # 指定模型（格式：裸模型名，需在本接口可用清单内），不传则用后端默认模型
            body["modelName"] = model_name
        if refresh_message_id is not None:  # 刷新指定 AI 回答记录的 message_id
            body["refreshMessageId"] = refresh_message_id
        if selected_content is not None:  # 用户选中的文本内容（作为首要上下文提供给 LLM）
            body["selectedContent"] = selected_content
        return self._post_sse_json(KNOWLEDGE_COMPLETIONS_PATH, body, timeout)  # 发起请求并消费事件流

    # ------------------------------------------------------------------
    # OSS 文件上传：上传 PDF 到 OSS，获取 ossUrl/fileName/fileSize
    # ------------------------------------------------------------------
    def upload_to_oss(self, pdf_path: str) -> Dict[str, Any]:
        """POST /paper/upload/oss：上传 PDF 到 OSS，返回文件信息（ossUrl/fileName/fileSize）。

        后端文献解读场景依赖 fileInfos（OSS 文件信息）触发 FC 从 OSS 拉取文件，
        仅传原始 pdfFile 不足以触发文件上传流程。
        使用论文专用上传接口（返回签名 OSS URL），而非通用 ossUploadFile 接口（不返回 URL）。
        支持 401 自动重新登录重试。
        """
        pdf = Path(pdf_path)  # 归一化路径
        if not pdf.is_file():  # 文件不存在时给出中文报错
            raise SseError(f"PDF 文件不存在：{pdf}（请检查 config/.env 的 PDF_PATH 或调用传参）")
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:  # 独立客户端（上传可能较慢）
                with open(pdf, "rb") as f:  # 二进制只读打开
                    resp = client.post(
                        self.base_url + OSS_UPLOAD_PATH,
                        files={"pdfFile": (pdf.name, f, "application/pdf")},  # 字段名 pdfFile 对齐 @RequestPart("pdfFile")
                        headers=self._headers(),
                    )
            if resp.status_code != 200:  # HTTP 层失败
                raise SseError(f"OSS 上传失败：HTTP {resp.status_code}，响应体：{resp.text[:500]}", status_code=resp.status_code)
            result = resp.json()  # 解析 JSON（Result 包装）
            if result.get("code") != 200:  # 业务层失败
                raise SseError(f"OSS 上传业务失败：{result.get('msg', '未知错误')}")
            data = result.get("data") or {}  # PaperUploadOssVO
        except SseError as exc:
            if exc.status_code == 401 and self.on_401:
                self.on_401()  # 重新登录
                with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                    with open(pdf, "rb") as f:
                        resp = client.post(
                            self.base_url + OSS_UPLOAD_PATH,
                            files={"pdfFile": (pdf.name, f, "application/pdf")},
                            headers=self._headers(),
                        )
                if resp.status_code != 200:
                    raise SseError(f"OSS 上传失败（重试后）：HTTP {resp.status_code}，响应体：{resp.text[:500]}", status_code=resp.status_code)
                result = resp.json()
                if result.get("code") != 200:
                    raise SseError(f"OSS 上传业务失败（重试后）：{result.get('msg', '未知错误')}")
                data = result.get("data") or {}
            else:
                raise
        return {
            "ossUrl": data.get("url", ""),  # OSS 文件 URL（签名 URL）
            "fileName": data.get("fileName", pdf.name),  # 存储文件名
            "fileSize": int(data.get("size", pdf.stat().st_size)),  # 文件大小（字节）
        }

    # ------------------------------------------------------------------
    # 接口 2：论文 SSE 流式多轮对话（multipart/form-data + SSE）
    # ------------------------------------------------------------------
    def paper_chat_stream(
        self,
        user_input: str,
        task_type: str = "interpret",
        pdf_path: Optional[str] = None,
        conversation_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        subject: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        model_name: Optional[str] = None,
        mode: Optional[str] = None,
        pdf_file_ids: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> SseResult:
        """POST /paper/chatStream：multipart 表单字段严格对齐 ChatStreamRequestDTO。"""
        data: Dict[str, str] = {
            "taskType": task_type,  # 任务类型（必填）：research/interpret/matrix/figure/retrieval/experiment-task-execute/experiment-task-chat
            "userInput": user_input,  # 用户输入/追问内容（1~2000 字符；interpret/matrix 场景留空时后端默认"解读当前文献"）
        }
        if conversation_id is not None:  # 追问时传已有对话 ID；首次提问不传（后端首个事件返回 conversation_id）
            data["conversationId"] = str(conversation_id)
        if thread_id is not None:  # 线程 ID（追问时传入，对齐前端 threadId 字段）
            data["threadId"] = thread_id
        if subject is not None:  # 学科分类（research 研究探索场景使用）
            data["subject"] = subject
        if keywords:  # 关键词列表：前端以 JSON 字符串提交（ChatStreamRequestDTO.keywords 为 String 类型）
            data["keywords"] = json.dumps(keywords, ensure_ascii=False)
        if model_name is not None:  # 模型名称（格式：裸模型名，需可用清单内；渠道由后端解析）
            data["modelName"] = model_name
        if mode is not None:  # 问答模式：flash / thinking / pro（对齐前端 modeName 字段）
            data["modeName"] = mode
        if pdf_file_ids is not None:  # 追问时复用已上传的 PDF 文件 ID 列表（对齐前端 pdfFileIds 字段）
            data["pdfFileIds"] = json.dumps(pdf_file_ids, ensure_ascii=False)

        files: Optional[list] = None  # multipart 文件段，默认不上传文件
        file_handle = None  # 文件句柄，用于 finally 中关闭
        file_infos: Optional[List[Dict[str, Any]]] = None  # OSS 文件信息列表（fileInfos 字段）
        if pdf_path is not None:  # 文献解读/矩阵解读场景需上传 PDF
            pdf = Path(pdf_path)  # 归一化路径
            if not pdf.is_file():  # 文件不存在时给出中文报错
                raise SseError(f"PDF 文件不存在：{pdf}（请检查 config/.env 的 PDF_PATH 或调用传参）")
            file_handle = pdf.open("rb")  # 二进制只读打开
            files = [("pdfFile", (pdf.name, file_handle, "application/pdf"))]  # 字段名 pdfFile 对齐 ChatStreamRequestDTO.pdfFile（MultipartFile[]）
            # 先上传到 OSS 获取文件信息（后端 SummaryFileUploadStrategy 依赖 fileInfos 触发 FC from-url 拉取）
            oss_info = self.upload_to_oss(pdf_path)
            file_infos = [oss_info]  # fileInfos 与 pdfFile 按下标一一对应
        if file_infos is not None:  # 传入 OSS 文件信息（索引格式，对齐前端 FormData.append 行为）
            # 后端 List<PdfFileInfoDTO> 使用 Spring 表单绑定：fileInfos[0].ossUrl=xxx
            for idx, info in enumerate(file_infos):
                data[f"fileInfos[{idx}].ossUrl"] = info["ossUrl"]
                data[f"fileInfos[{idx}].fileName"] = info["fileName"]
                data[f"fileInfos[{idx}].fileSize"] = str(info["fileSize"])

        try:
            return self._post_sse_multipart(PAPER_CHAT_STREAM_PATH, data, files, timeout)  # 发起请求并消费事件流
        finally:
            if file_handle is not None:
                file_handle.close()  # 无论成功与否都关闭文件句柄

    # ------------------------------------------------------------------
    # 底层：发起 SSE POST 并消费事件流
    # ------------------------------------------------------------------
    def _post_sse_json(self, path: str, body: Dict[str, Any], timeout: Optional[float], max_retries: int = 2) -> SseResult:
        """以 application/json 发起 POST，并流式消费 SSE 响应。支持 401 自动重新登录重试、500 自动重试。"""
        read_timeout = timeout or self.timeout  # 读流超时：单次调用可覆盖默认值
        httpx_timeout = httpx.Timeout(read_timeout, connect=10.0)  # 连接超时固定 10 秒；读超时作用于流式分块间隔
        last_exc: Optional[SseError] = None
        for attempt in range(max_retries + 1):  # 首次 + 重试
            try:
                with httpx.Client(timeout=httpx_timeout) as client:  # 每次调用独立客户端，避免长流占用共享连接
                    with client.stream(
                        "POST", self.base_url + path, json=body, headers=self._headers()
                    ) as response:  # json= 自动携带 Content-Type: application/json
                        self._ensure_ok(response)  # 非 200 抛出 SseError
                        return self._consume_sse(response)  # 逐块解析并拼接文本
            except SseError as exc:
                last_exc = exc
                if exc.status_code == 401 and self.on_401:
                    self.on_401()  # 重新登录，更新 config.token
                    with httpx.Client(timeout=httpx_timeout) as client:
                        with client.stream(
                            "POST", self.base_url + path, json=body, headers=self._headers()
                        ) as response:
                            self._ensure_ok(response)
                            return self._consume_sse(response)
                elif exc.status_code == 500 and attempt < max_retries:
                    wait_sec = 2 ** (attempt + 1)  # 2s, 4s
                    print(f"[SSE 重试] 第 {attempt + 1} 次遇到 HTTP 500，{wait_sec}s 后重试...")
                    time.sleep(wait_sec)
                    continue
                raise
        raise last_exc

    def _post_sse_multipart(
        self,
        path: str,
        data: Dict[str, str],
        files: Optional[list],
        timeout: Optional[float],
        max_retries: int = 2,  # 500 错误最大重试次数
    ) -> SseResult:
        """以 multipart/form-data 发起 POST，并流式消费 SSE 响应。支持 401 自动重新登录重试、500 自动重试。"""
        # httpx 在 files=None/[] 时降级为 application/x-www-form-urlencoded，
        # 而前端 FormData 始终发送 multipart/form-data；后端 Spring Controller 依赖 multipart 编码，
        # urlencoded 会导致参数绑定失败返回 HTTP 500。追加空文件部分强制 multipart（与前端行为一致）。
        if not files:
            files = [('', ('', b'', 'application/octet-stream'))]
        read_timeout = timeout or self.timeout  # 读流超时：单次调用可覆盖默认值
        httpx_timeout = httpx.Timeout(read_timeout, connect=10.0)  # 连接超时固定 10 秒
        last_exc: Optional[SseError] = None
        for attempt in range(max_retries + 1):  # 首次 + 重试
            try:
                with httpx.Client(timeout=httpx_timeout) as client:
                    with client.stream(
                        "POST", self.base_url + path, data=data, files=files, headers=self._headers()
                    ) as response:  # 不手动设置 Content-Type：由 httpx 自动生成 boundary（与前端拦截器删除 Content-Type 的行为一致）
                        self._ensure_ok(response)  # 非 200 抛出 SseError
                        return self._consume_sse(response)  # 逐块解析并拼接文本
            except SseError as exc:
                last_exc = exc
                if exc.status_code == 401 and self.on_401:
                    self.on_401()  # 重新登录，更新 config.token
                    with httpx.Client(timeout=httpx_timeout) as client:
                        with client.stream(
                            "POST", self.base_url + path, data=data, files=files, headers=self._headers()
                        ) as response:
                            self._ensure_ok(response)
                            return self._consume_sse(response)
                elif exc.status_code == 500 and attempt < max_retries:
                    # 500 服务端错误：等待后重试（指数退避）
                    wait_sec = 2 ** (attempt + 1)  # 2s, 4s
                    print(f"[SSE 重试] 第 {attempt + 1} 次遇到 HTTP 500，{wait_sec}s 后重试...")
                    time.sleep(wait_sec)
                    continue  # 进入下一次重试
                raise  # 非 500 或重试耗尽：抛出异常
        raise last_exc  # 重试耗尽仍未成功

    # ------------------------------------------------------------------
    # 通用非流式 JSON 请求（创建/删除对话等管理接口）
    # ------------------------------------------------------------------
    def request_json(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """发起非流式 JSON 请求（如创建/删除对话），返回解析后的 JSON 字典（Result 包装）。

        支持 401 自动重新登录重试。
        """
        request_timeout = timeout or 30.0  # 非流式请求默认 30 秒超时
        try:
            with httpx.Client(timeout=httpx.Timeout(request_timeout, connect=10.0)) as client:  # 独立客户端
                resp = client.request(method, self.base_url + path, json=body, headers=self._headers())  # 携带真实鉴权头
            if resp.status_code != 200:  # HTTP 层失败：抛出带状态码的 SseError
                raise SseError(
                    f"请求失败：HTTP {resp.status_code}，响应体：{resp.text[:500]}",
                    status_code=resp.status_code,
                )
            content_type = resp.headers.get("content-type", "")  # 响应内容类型
            if "application/json" not in content_type:  # 非 JSON 响应（如误返回 SSE 流）：无法按 Result 解析
                raise SseError(f"响应非 JSON：Content-Type={content_type}", status_code=resp.status_code)
            return resp.json()  # 返回解析后的 JSON 字典（含 code/msg/data 等字段）
        except SseError as exc:
            if exc.status_code == 401 and self.on_401:
                self.on_401()  # 重新登录
                with httpx.Client(timeout=httpx.Timeout(request_timeout, connect=10.0)) as client:
                    resp = client.request(method, self.base_url + path, json=body, headers=self._headers())
                if resp.status_code != 200:
                    raise SseError(
                        f"请求失败（重试后）：HTTP {resp.status_code}，响应体：{resp.text[:500]}",
                        status_code=resp.status_code,
                    )
                return resp.json()
            raise

    @staticmethod
    def _ensure_ok(response: httpx.Response) -> None:
        """校验 HTTP 状态码：非 200 时读取响应体并抛出带中文信息的 SseError。"""
        if response.status_code != 200:  # 网关/后端校验失败会直接返回非 200 JSON
            response.read()  # 流式模式下需先读取 body 才能取 text
            raise SseError(
                f"SSE 请求失败：HTTP {response.status_code}，响应体：{response.text[:500]}",
                status_code=response.status_code,  # 记录状态码供用例断言
            )

    # ------------------------------------------------------------------
    # 底层：SSE 事件流解析（协议对齐前端 stream.ts 的 parseSSEStream）
    # ------------------------------------------------------------------
    def _consume_sse(self, response: httpx.Response) -> SseResult:
        """逐行读取 SSE 流，按空行切分事件，拼接增量文本并统计首包/总耗时。

        容错：服务端提前关闭连接时（RemoteProtocolError），若已收到 end 事件则正常返回，
        否则抛出带上下文的 SseError（含已接收事件数）。
        """
        start = time.perf_counter()  # 流计时起点（响应头到达后起算）
        first_chunk_ms: Optional[float] = None  # 首包耗时（首个完整事件分发时记录）
        chunks: List[Dict[str, Any]] = []  # 原始事件块列表：{event, data, id, ts_ms}
        text_parts: List[str] = []  # 增量文本片段（仅消息类事件参与拼接）
        event_name: Optional[str] = None  # 当前事件的 event 字段
        event_id: Optional[str] = None  # 当前事件的 id 字段
        data_lines: List[str] = []  # 当前事件的 data 行（多行 data 按 SSE 规范以换行拼接）
        stream_ended = False  # 是否已收到 end 事件（用于判断连接中断是否可忽略）

        try:
            for raw_line in response.iter_lines():  # 逐行读取（服务端按行推送事件）
                line = raw_line.strip()  # 去掉首尾空白与回车
                if not line:  # 空行：一个事件结束，进行分发
                    if event_name is not None or data_lines:  # 有事件名或数据才构成一个完整事件
                        ts_ms = round((time.perf_counter() - start) * 1000, 2)  # 本事件到达时间（相对流起点，毫秒）
                        chunk = self._build_chunk(event_name, event_id, data_lines, ts_ms)  # 组装原始块（含到达时间戳）
                        if first_chunk_ms is None and event_name not in ("start", "heartbeat", "end", "error"):  # 跳过控制事件，首个内容事件即首包耗时
                            first_chunk_ms = ts_ms
                        chunks.append(chunk)  # 记录原始块
                        # if self.verbose:  # 实时打印 SSE 事件（Agent 调试模式）
                        #     self._print_sse_event(chunk)
                        delta = self._extract_delta_text(chunk["event"], chunk["data"])  # 提取增量文本
                        if delta:  # 有增量文本则拼接
                            text_parts.append(delta)
                        if chunk["event"] == "end":  # 服务端结束标记（SseEventPublisher.sendDone：event=end, data=[DONE]）
                            stream_ended = True  # 标记已正常结束
                            break  # 收到结束标记后主动停止读取，避免长连接空等
                    event_name, event_id, data_lines = None, None, []  # 重置状态，准备解析下一个事件
                    continue  # 处理下一行
                if line.startswith("event:"):  # 事件名行
                    event_name = line[len("event:"):].strip()
                elif line.startswith("data:"):  # 数据行（JSON 字符串或 [DONE]）
                    data_lines.append(line[len("data:"):].strip())
                elif line.startswith("id:"):  # 事件 id 行
                    event_id = line[len("id:"):].strip()
        except httpx.RemoteProtocolError as exc:
            # 服务端提前关闭连接的处理策略：
            # 1. 若已收到 end 事件 → 正常返回（数据已完整）
            # 2. 若已收到大量数据（chunks > 10 或有文本内容）→ 视为数据已完整，正常返回
            #    （服务端可能发完数据后未正确关闭 chunked 编码，浏览器更宽容但 httpx 严格）
            # 3. 若数据量很少 → 抛出错误（真正的连接中断）
            # 注：httpcore.RemoteProtocolError 在 httpcore 可用时也会被 httpx 包装抛出
            has_end_event = any(c.get("event") == "end" for c in chunks)
            has_substantial_data = len(chunks) > 10 or len(text_parts) > 0
            if has_end_event:
                pass  # 已收到 end 事件，正常结束
            elif has_substantial_data:
                # 数据已基本完整，服务端关闭连接时未正确发送 chunked 终止块
                # 这种情况浏览器能正常接收但 httpx 会报错，视为正常完成
                # if self.verbose:
                #     print(f"\n[注意] 连接被服务端非正常关闭，但已接收 {len(chunks)} 个事件，"
                #           f"{sum(len(t) for t in text_parts):,} 字，视为正常完成。")
                pass  # 静默处理，不打印到控制台
            else:
                # 数据量很少，真正的连接中断
                raise SseError(
                    f"SSE 连接被服务端中断（已接收 {len(chunks)} 个事件，"
                    f"已拼接 {sum(len(t) for t in text_parts):,} 字）。"
                    f"可能原因：网关超时、服务端异常、负载均衡器切断长连接。"
                    f"原始错误：{exc}",
                ) from exc

        if event_name is not None or data_lines:  # 流末尾可能残留未以空行结束的事件
            ts_ms = round((time.perf_counter() - start) * 1000, 2)  # 残留事件到达时间
            chunk = self._build_chunk(event_name, event_id, data_lines, ts_ms)  # 组装残留事件
            if first_chunk_ms is None and event_name not in ("start", "heartbeat", "end", "error"):  # 极端情况：首个内容事件即残留事件
                first_chunk_ms = ts_ms
            chunks.append(chunk)  # 记录原始块
            # if self.verbose:  # 实时打印
            #     self._print_sse_event(chunk)
            delta = self._extract_delta_text(chunk["event"], chunk["data"])  # 提取增量文本
            if delta:  # 有增量文本则拼接
                text_parts.append(delta)

        total_ms = round((time.perf_counter() - start) * 1000, 2)  # 总耗时（毫秒）
        timing = {
            "first_chunk_ms": first_chunk_ms if first_chunk_ms is not None else total_ms,  # 无任何内容时退化为总耗时
            "total_ms": total_ms,  # 总耗时
        }
        return "".join(text_parts), chunks, timing  # 返回 (完整文本, 原始块列表, 耗时信息)

    @staticmethod
    def _build_chunk(event_name: Optional[str], event_id: Optional[str], data_lines: List[str], ts_ms: float) -> Dict[str, Any]:
        """组装一个原始事件块：data 尝试 JSON 解析（对齐前端 JSON.parse 逻辑），并记录到达时间戳。"""
        raw = "\n".join(data_lines)  # 多行 data 按 SSE 规范拼接
        try:
            data: Any = json.loads(raw)  # 优先按 JSON 解析（服务端 data 均为 JSON 字符串）
        except (json.JSONDecodeError, ValueError):  # 非 JSON 内容
            data = None if raw == "null" else raw  # 'null' 归一为 None，其余保留原字符串（如 [DONE]）
        return {"event": event_name, "data": data, "id": event_id, "ts_ms": ts_ms}  # 原始块结构（ts_ms：相对流起点的到达毫秒数，供首包耗时统计）

    # ------------------------------------------------------------------
    # SSE 事件实时打印（verbose 模式）
    # ------------------------------------------------------------------
    def _print_sse_event(self, chunk: Dict[str, Any]) -> None:
        """实时打印一个 SSE 事件到控制台（verbose 模式下调用）。

        打印策略：
        - start/end/metadata/intent_recognition：完整打印（关键节点）
        - progress：打印 data 摘要（文件上传进度等）
        - messages：打印工具调用或 AI 内容片段
        - values/updates：打印事件类型 + 数据长度（状态快照太大）
        - heartbeat：不打印（避免刷屏）
        """
        event = chunk.get("event", "?")
        ts_ms = chunk.get("ts_ms", 0)
        data = chunk.get("data")

        # heartbeat 不打印（避免刷屏）
        if event == "heartbeat":
            return

        # 格式化 data 摘要
        data_summary = self._summarize_event_data(event, data)

        # 按事件类型选择打印详细度
        if event in ("start", "end", "metadata", "intent_recognition", "thread_id", "conversation_id"):
            # 关键节点：完整打印
            print(f"[{ts_ms:>10.0f}ms]  {event:<22s} {data_summary}")
        elif event == "progress":
            # 进度事件：打印进度内容
            print(f"[{ts_ms:>10.0f}ms]  {event:<22s} {data_summary}")
        elif event == "messages":
            # messages 事件：打印工具调用或 AI 内容
            print(f"[{ts_ms:>10.0f}ms]  {event:<22s} {data_summary}")
        elif event in ("artifact",):
            # artifact 事件：打印类型和长度
            print(f"[{ts_ms:>10.0f}ms]  {event:<22s} {data_summary}")
        else:
            # values/updates 等：仅打印事件名 + 数据规模
            print(f"[{ts_ms:>10.0f}ms]  {event:<22s} (data: {self._data_size_desc(data)})")

    @staticmethod
    def _summarize_event_data(event: str, data: Any) -> str:
        """将事件 data 压缩为一行可读摘要，针对不同类型事件提取关键信息。"""
        if data is None:
            return ""
        if isinstance(data, str):
            # 字符串 data：截断到 120 字符
            return data[:120] + ("..." if len(data) > 120 else "")
        if isinstance(data, dict):
            # 字典 data：提取关键字段
            parts = []
            for key in ("thread_id", "conversation_id", "status", "type", "title", "intent", "confidence"):
                if key in data:
                    val = data[key]
                    parts.append(f"{key}={val}")
            if parts:
                return ", ".join(parts)
            # 没有关键字段时，打印所有键名
            keys = list(data.keys())[:5]
            return "{" + ", ".join(keys) + ("..." if len(data) > 5 else "") + "}"
        if isinstance(data, list) and data:
            # messages 事件：提取工具调用或 AI 内容片段
            return SseClient._summarize_messages_data(data)
        if isinstance(data, list):
            return f"list[{len(data)}]"
        return str(data)[:80]

    @staticmethod
    def _summarize_messages_data(data: list) -> str:
        """从 messages 事件中提取工具调用或 AI 内容摘要。"""
        if not data or not isinstance(data[0], dict):
            return f"list[{len(data)}]"
        
        msg = data[0]  # LangGraph messages-tuple: [message, metadata]
        content = msg.get("content", "")
        role = msg.get("role", msg.get("type", ""))
        tool_calls = msg.get("tool_calls") or msg.get("additional_kwargs", {}).get("tool_calls")
        name = msg.get("name", "")  # 工具名称（tool message 有）
        
        # 工具调用：显示工具名称
        if tool_calls:
            tool_names = [tc.get("name", tc.get("function", {}).get("name", "?")) for tc in tool_calls[:3]]
            return f"[TOOL] tool_calls: {', '.join(tool_names)}"
        
        # 工具执行结果（ToolMessage）
        if role == "tool" and name:
            return f"[RESULT] tool_result: {name}"
        
        # AI 内容：显示前 80 字符
        if isinstance(content, str) and content:
            preview = content[:80].replace("\n", " ")
            return f"[AI] {role}: {preview}{'...' if len(content) > 80 else ''}"
        if isinstance(content, list):
            # ContentPart 格式：[{"type": "text", "text": "..."}]
            text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text" and p.get("text")]
            if text_parts:
                combined = " ".join(text_parts)[:80]
                return f"[AI] {role}: {combined}{'...' if len(' '.join(text_parts)) > 80 else ''}"
        
        # 空内容消息：显示消息类型
        if role:
            return f"[{role}] (empty)"
        
        # 未知结构：显示键名
        keys = list(msg.keys())[:4]
        return f"msg{{{', '.join(keys)}}}"

    @staticmethod
    def _data_size_desc(data: Any) -> str:
        """描述 data 的规模（用于非关键事件的简洁打印）。"""
        if data is None:
            return "empty"
        if isinstance(data, str):
            return f"{len(data)} chars"
        if isinstance(data, dict):
            return f"dict[{len(data)} keys]"
        if isinstance(data, list):
            return f"list[{len(data)} items]"
        return type(data).__name__

    # ------------------------------------------------------------------
    # 可中断的 SSE 事件流解析（供断流测试等需要精确控制读取时长的场景使用）
    # ------------------------------------------------------------------
    def interruptible_consume_sse(
        self,
        response: httpx.Response,
        max_seconds: Optional[float] = None,
        disconnect_after_text_seconds: Optional[float] = None,
    ) -> Tuple[str, List[Dict[str, Any]], bool]:
        """可中断的 SSE 流消费：支持按时长或收到文本后等待时长主动断开。

        与 _consume_sse() 共享同一套解析逻辑（_build_chunk + _extract_delta_text），
        但额外支持两种主动断开模式，供断流测试等场景使用。

        Args:
            response: 已打开的 httpx 流式响应。
            max_seconds: 从开始读取起计时，到时间就断（None 表示不限制）。
            disconnect_after_text_seconds: 收到第一个文本事件后再等 N 秒断开（None 表示不限制）。

        Returns:
            (text, chunks, stream_ended)：拼接文本、事件列表、是否正常收到 end 事件。
        """
        import time as _time
        start = _time.perf_counter()
        first_chunk_ms: Optional[float] = None
        chunks: List[Dict[str, Any]] = []
        text_parts: List[str] = []
        event_name: Optional[str] = None
        event_id: Optional[str] = None
        data_lines: List[str] = []
        stream_ended = False
        first_text_at: Optional[float] = None

        for raw_line in response.iter_lines():
            line = raw_line.strip()
            if not line:
                if event_name is not None or data_lines:
                    ts_ms = round((_time.perf_counter() - start) * 1000, 2)
                    chunk = self._build_chunk(event_name, event_id, data_lines, ts_ms)
                    if first_chunk_ms is None and event_name not in ("start", "heartbeat", "end", "error"):
                        first_chunk_ms = ts_ms
                    chunks.append(chunk)
                    delta = self._extract_delta_text(chunk["event"], chunk["data"])
                    if delta:
                        text_parts.append(delta)
                        if first_text_at is None:
                            first_text_at = _time.perf_counter()
                    if chunk["event"] == "end":
                        stream_ended = True
                        break
                event_name, event_id, data_lines = None, None, []
                continue
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
            elif line.startswith("id:"):
                event_id = line[len("id:"):].strip()

            # 时间中断检查
            if max_seconds is not None and (_time.perf_counter() - start) >= max_seconds:
                break
            if disconnect_after_text_seconds is not None and first_text_at is not None:
                if (_time.perf_counter() - first_text_at) >= disconnect_after_text_seconds:
                    break

        # 流末尾可能残留未以空行结束的事件
        if event_name is not None or data_lines:
            ts_ms = round((_time.perf_counter() - start) * 1000, 2)
            chunk = self._build_chunk(event_name, event_id, data_lines, ts_ms)
            chunks.append(chunk)
            delta = self._extract_delta_text(chunk["event"], chunk["data"])
            if delta:
                text_parts.append(delta)

        return "".join(text_parts), chunks, stream_ended

    # ------------------------------------------------------------------
    # 文本提取：仅对消息类事件做增量拼接，避免 values 全量快照重复计数
    # ------------------------------------------------------------------
    def _extract_delta_text(self, event_name: Optional[str], data: Any) -> str:
        """从消息类事件中提取 AI 增量文本；非消息事件返回空串。"""
        if event_name not in ("message", "messages", "messages-tuple"):  # 知识库增量事件为 message；paper 透传 LangGraph 的 messages/messages-tuple
            return ""
        if isinstance(data, dict) and isinstance(data.get("message"), dict):  # 知识库格式：{"message": {"id","role":"assistant","content","reasoning"?}}
            return self._content_to_text(data["message"].get("content"))
        if isinstance(data, list) and data and isinstance(data[0], dict):  # LangGraph messages-tuple：[message, metadata]
            return self._content_to_text(data[0].get("content"))
        if isinstance(data, dict) and "content" in data:  # 单消息直传：{"content": ...}
            return self._content_to_text(data.get("content"))
        return ""  # 其余结构不提取

    @staticmethod
    def _content_to_text(content: Any) -> str:
        """把消息 content 归一为文本：字符串直取；ContentPart 列表只取 type=text 的 text。"""
        if isinstance(content, str):  # 纯文本内容
            return content
        if isinstance(content, list):  # LangChain ContentPart[]：[{"type":"text","text":...},{"type":"thinking",...}]
            return "".join(
                part["text"]  # 文本片段
                for part in content  # 遍历内容分片
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text")  # 只取非空 text 分片（thinking 等不计入正文）
            )
        return ""  # 其他类型不提取
