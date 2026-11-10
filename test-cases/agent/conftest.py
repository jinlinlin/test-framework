"""pytest 全局夹具（移植自 agent-test/conftest.py，A′-3 最小子集 + 真实环境回补）。

与源仓的差异只有一处刻意不回补：方案 2 浏览器滑块登录（core/utils/
browser_login.py）未随迁——真实环境验证按 TOKEN 复用 → REFRESH_TOKEN 续期
两级回退已够（lazy import 分支报错后自然走 pytest.skip，不崩溃）；
连带 peer_token 跨账号用例（依赖 auto_login）在当前环境恒为 skip。
Langfuse Trace 钩子已回补：LANGFUSE_* 未配置时 reporter.enabled=False 静默跳过，
offline 用例不建 Trace（源仓 2026-10-28 实测防污染约定，随迁保留）。

本文件另提供 score_sink 夹具：评分收口层（源仓无对应机制，为框架侧新契约）——
把 Judge 结果写入 junit <properties> 的 score/threshold/dimensions，供
AgentBehaviorEngine 收口为评分制 TestResult。量纲契约：score 为 0~1 归一比
（Judge 5 分制 ÷ scale），与引擎 defaults 的 default_threshold=0.75 同标度。
"""
import json  # dimensions 序列化进 junit properties
import os  # 环境变量读取（TEST_MODEL_OUTPUT_DIR 覆盖）
import sys  # 输出流编码容错（Windows GBK 控制台）
from pathlib import Path  # 产物输出目录路径

import pytest  # pytest 框架

from core.clients.langfuse_integration import (  # Langfuse Trace 上报 + 维度标签
    build_trace_tags,
    get_langfuse_reporter,
)
from core.clients.sse_client import SseClient  # SSE 流式客户端
from core.scoring import (  # 平均分重算与维度归一化（源仓单一实现，不自写第二份）
    compute_average,
    normalize_dimension_scores,
)
from core.utils.config import PROJECT_ROOT, ConfigError, config  # 全局配置与项目根

# Windows PowerShell 控制台默认 GBK：报告打印的 ✓/✗ 等不可编码字符会抛
# UnicodeEncodeError，使用例因非产品原因崩溃。仅设 errors="replace"
# （保持原编码，中文显示不受影响），不可编码字符降级为 ?；落盘产物仍用
# UTF-8 写入，不受此处影响。（与源仓 conftest 逐字一致）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass  # 非标准流（如被 pytest/插件包装）不支持时静默跳过


@pytest.fixture(autouse=True)
def _offline_placeholder_token(request, monkeypatch):
    """为 offline 标记用例注入占位 TOKEN，不依赖 config/.env。

    离线契约用例请求的是本地假网关：鉴权头契约只断言 Uniplore-Auth 等头的
    **存在性**、不校验取值，但 SseClient 构头会走 config.token 的必填校验
    （require("TOKEN")），无 .env 环境下会直接 ConfigError——这不是用例
    语义要求的失败。真实环境用例不受本夹具影响，仍按凭证缺失路径报错/跳过。
    """
    if request.node.get_closest_marker("offline"):
        monkeypatch.setenv("TOKEN", "offline-placeholder-token")


@pytest.fixture
def score_sink(request):
    """评分收口夹具：把 Judge 结果以 junit properties 形式交给引擎。

    写 user_properties（pytest 官方机制，junitxml 落为 <properties>）：
    - score：指定维度算术平均分 ÷ scale 归一到 0~1；不信任裁判 LLM 自报
      average，经 core.scoring.compute_average 代码重算（与 judge_client
      内部重算同一实现）。
    - threshold：用例显式声明才写；缺省由引擎按 default_threshold 回退。
    - dimensions：各维度数值 JSON（维度英文名→数值），供跨引擎趋势分析。

    返回 emit(judge_result, threshold=None, dimensions=None, scale=5.0)。
    """

    def emit(judge_result, threshold=None, dimensions=None, scale=5.0):
        avg = compute_average(judge_result, dimensions)  # 代码重算，非 LLM 自报
        normed = normalize_dimension_scores(judge_result)
        normed.pop("average", None)  # 裁判顶层自均值不是评估维度，不得混入趋势词表
        if dimensions is not None:  # 仅保留参与计分的维度，避免无关字段混入趋势
            normed = {k: v for k, v in normed.items() if k in dimensions}
        request.node.user_properties.append(("score", str(round(avg / scale, 4))))
        if threshold is not None:
            request.node.user_properties.append(("threshold", str(threshold)))
        request.node.user_properties.append(
            ("dimensions", json.dumps(normed, ensure_ascii=False))
        )
        return round(avg / scale, 4)  # 回传归一分数，供用例内断言直接用

    return emit


# ── 以下 session 夹具与 Langfuse 钩子逐字对齐源仓根 conftest（回补）──


@pytest.fixture(scope="session")
def output_dir() -> Path:
    """产物输出目录：自动创建 test_output/ 并返回其路径（session 级复用）。

    支持 TEST_MODEL_OUTPUT_DIR 环境变量覆盖（多模型对比时，每个模型写入独立目录）。
    """
    override = os.environ.get("TEST_MODEL_OUTPUT_DIR")
    if override:
        out = Path(override)
    else:
        out = PROJECT_ROOT / "test_output"  # 产物输出根目录（已加入 .gitignore）
    out.mkdir(parents=True, exist_ok=True)  # 递归创建目录；已存在时不报错
    return out  # 返回目录路径供用例写入 LLM 原始响应与评测产物


def _verify_token(token_value: str) -> bool:
    """轻量校验 token 是否仍有效：调用一个低成本接口，200 即有效。"""
    import httpx
    try:
        resp = httpx.get(
            f"{config.base_url}/uniplore-server-aischeduler/dashboard/user/models",
            headers={"Uniplore-Auth": token_value, "Authorization": config.authorization},
            timeout=10.0,
            verify=False,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _do_login() -> str:
    """获取有效 token：先复用已有 → 再 refresh_token 续期 → 最后重新登录。

    方案 2（浏览器滑块登录）实现未随迁：lazy import 失败后落入全部失败
    分支 pytest.skip，行为友好且可观测（见文件头差异声明）。

    Returns:
        str: 有效的 access_token

    Raises:
        pytest.skip: 所有方式均失败时跳过测试。
    """
    from core.utils.token_refresher import update_env_token

    # ── 方案 0：复用已有 token（上次登录/续期后已写入 .env 和环境变量）──
    try:
        existing = config.token
        if existing and _verify_token(existing):
            print(f"\n[Token] 复用已有 token（校验通过，无需重新登录）")
            return existing
        elif existing:
            print(f"\n[Token] 已有 token 已失效，尝试重新获取...")
    except ConfigError:
        pass  # 无 TOKEN 配置，跳过

    # ── 方案 1：refresh_token 续期（轻量，无需浏览器）──
    refresh = config.get("REFRESH_TOKEN")
    if refresh:
        try:
            from core.utils.token_refresher import TokenRefreshError, refresh_access_token
            result = refresh_access_token(refresh)
            new_token = result["access_token"]
            new_refresh = result.get("refresh_token")
            config.set_runtime_token(new_token)
            update_env_token(new_token, new_refresh)
            print(f"\n[Token 续期] 自动刷新成功（新 refresh_token 已保存）")
            return new_token
        except TokenRefreshError as exc:
            print(f"\n[Token 续期] 自动刷新失败：{exc}")

    # ── 方案 2：自动登录（API 密码 → 浏览器滑块）；browser_login 未随迁 ──
    login_user = config.get("LOGIN_USERNAME")
    login_pass = config.get("LOGIN_PASSWORD")
    if login_user and login_pass:
        try:
            from core.utils.browser_login import BrowserLoginError, auto_login
            result = auto_login()
            new_token = result["access_token"]
            new_refresh = result.get("refresh_token")
            config.set_runtime_token(new_token)
            update_env_token(new_token, new_refresh or None)
            print(f"\n[Token 获取] 自动登录成功：{login_user}")
            return new_token
        except Exception as exc:
            print(f"\n[Token 获取] 自动登录失败：{exc}")

    # ── 全部失败 ──
    pytest.skip(
        "未配置登录信息或所有方式均失败。请在 config/.env 中填写以下任一方式：\n"
        "  方式 1（推荐）：LOGIN_USERNAME=xxx + LOGIN_PASSWORD=xxx（密码自动登录）\n"
        "  方式 2：TOKEN=xxx（手动从浏览器复制）"
    )


def _relogin_on_401() -> str:
    """Token 失效时重新登录并返回新 token（供 SseClient 回调，跳过复用校验）。"""
    print(f"\n[Token 续期] 检测到 401，重新登录...")
    # 清空运行时 token，强制走续期/登录流程
    config._runtime_token = None
    os.environ.pop("TOKEN", None)
    return _do_login()


@pytest.fixture(scope="session")
def token() -> str:
    """登录态 token 自动获取：自动登录 → refresh_token 续期 → 静态 TOKEN。"""
    try:
        config.base_url  # 校验 BASE_URL（SSE 调用必需）
    except ConfigError as exc:
        pytest.skip(str(exc))

    return _do_login()


@pytest.fixture(scope="session")
def peer_token() -> str:
    """第二个账号（对端账号）的登录态 token：跨账号越权用例需要两个独立账号。

    未配置 LOGIN_USERNAME_B/LOGIN_PASSWORD_B 或登录失败时跳过用例（而非默认通过）；
    不写入 .env（与主账号登录态隔离，会话属主为对端账号）。
    当前 browser_login 未随迁，本夹具恒走 skip 分支。
    """
    peer_user = config.get("LOGIN_USERNAME_B")
    peer_pass = config.get("LOGIN_PASSWORD_B")
    if not peer_user or not peer_pass:
        pytest.skip(
            "未配置对端账号：跨账号越权用例需要第二个账号，"
            "请在 config/.env 中填写 LOGIN_USERNAME_B / LOGIN_PASSWORD_B"
        )
    try:
        config.base_url
    except ConfigError as exc:
        pytest.skip(str(exc))
    try:
        from core.utils.browser_login import auto_login
        result = auto_login(peer_user, peer_pass)
    except Exception as exc:
        pytest.skip(f"对端账号 {peer_user} 登录失败，无法验证跨账号越权：{exc}")
    print(f"\n[对端账号] 登录成功：{peer_user}（token 长度={len(result['access_token'])}）")
    return result["access_token"]


@pytest.fixture(scope="session")
def sse_client(token: str, request: pytest.FixtureRequest) -> SseClient:
    """SSE 客户端实例（session 级复用；依赖 token 校验，未配置时自动跳过）。

    verbose 模式自动跟随 pytest -s 参数：使用 -s 运行时实时打印 SSE 事件流。
    内置 401 自动重新登录：token 失效时自动调用 auto_login 获取新 token 并重试请求。
    """
    # 检测 pytest 是否以 -s（--capture=no）运行，是则开启 SSE 事件实时打印
    capture_disabled = request.config.option.capture == "no"
    return SseClient(verbose=capture_disabled, on_401=_relogin_on_401)


@pytest.fixture(scope="session")
def model_name(sse_client: SseClient) -> str:
    """运行模型名称（session 级）：优先读取 .env 的 MODEL_NAME，未配置则自动获取第一个可用模型。"""
    # 优先读取 .env 配置的模型名称
    configured = config.get("MODEL_NAME")
    if configured:
        print(f"\n[模型配置] 使用 config/.env 指定的模型：{configured}")
        return configured
    # 未配置时自动获取可用模型列表
    try:
        models = sse_client.get_user_available_models()
        if models:
            selected = models[0]  # 默认使用第一个可用模型
            print(f"\n[模型配置] 未配置 MODEL_NAME，自动选择第一个可用模型：{selected}")
            print(f"[模型配置] 全部可用模型：{models}")
            print(f"[模型配置] 如需指定模型，请在 config/.env 中配置 MODEL_NAME={selected}")
            return selected
    except Exception as e:
        print(f"\n[模型配置] 获取可用模型列表失败：{e}")
    # 无法获取时返回 None（由用例决定是否跳过）
    print(f"\n[模型配置] 未配置且无法自动获取模型，将使用后端默认模型")
    return None  # type: ignore


# ── Langfuse Trace 集成（pytest 钩子，逐字对齐源仓）──

def pytest_sessionstart(session):
    """pytest session 开始时初始化 Langfuse 报告器（未配置时静默跳过）。"""
    reporter = get_langfuse_reporter()
    session._langfuse_reporter = reporter  # 挂载到 session 供后续钩子使用


def pytest_runtest_protocol(item, nextitem):
    """每个测试用例开始前创建 Langfuse Trace（offline 纯函数用例除外）。"""
    reporter = getattr(item.session, "_langfuse_reporter", None)
    if reporter and reporter.enabled:
        # offline 标记的纯函数用例不打真实服务，Trace 的 observations/耗时全空，
        # 只会污染 Traces 列表（2026-10-28 实测：一次离线回归产生 65 条空 Trace，
        # 淹没真实 E2E 记录）。跳过建 Trace，也不参与 makereport 的结果写入。
        if any(m.name == "offline" for m in item.iter_markers()):
            return None
        # 尝试计数归零：本 hook 每个 item 只触发一次，而 pytest_runtest_setup 会在
        # 每次重试时再触发（rerunfailures 是循环调用完整 protocol）
        item._langfuse_attempt = 0
        reporter.set_attempt(1)
        trace = reporter.start_trace(
            name=item.name,
            metadata={
                "file": str(item.fspath),
                "module": item.module.__name__ if item.module else "",
                "markers": [m.name for m in item.iter_markers()],
            },
            # 标签含 环境/被测模型/裁判模型/黄金集版本，Langfuse 侧才能按维度横向对比趋势
            tags=build_trace_tags(markers=[m.name for m in item.iter_markers()]),
        )
        item._langfuse_trace = trace
        # 设置全局当前 Trace，供 _save_full_artifacts() 使用
        from core.clients.langfuse_integration import set_current_trace
        set_current_trace(trace)
    return None  # 返回 None 让 pytest 继续默认协议


def pytest_runtest_setup(item):
    """每次尝试（含 rerunfailures 重试）进入测试体前递增尝试序号并同步给上报器。

    为什么在 setup 而不是 makereport：产物上报（report_trace）发生在测试体的 finally
    里，早于 makereport；序号必须在测试体执行前就位，重试轮的所有 Span/Event 才能带上
    正确的 ·#N 后缀。setup 阶段失败同样计数，序号与实际尝试次数保持一致。
    """
    reporter = getattr(item.session, "_langfuse_reporter", None)
    # 只对已建 Trace 的用例计数（offline 用例在 protocol 钩子里就被跳过，无 _langfuse_trace；
    # 若此处照样递增，会把上一条用例的 attempt 值推高，虽不影响其上报，但语义不干净）
    if not (reporter and reporter.enabled) or getattr(item, "_langfuse_trace", None) is None:
        return
    item._langfuse_attempt = getattr(item, "_langfuse_attempt", 0) + 1
    reporter.set_attempt(item._langfuse_attempt)


def pytest_runtest_makereport(item, call):
    """每个测试用例结束后，记录通过/失败结果到 Langfuse Trace（含失败原因）。"""
    if call.when != "call":
        return
    reporter = getattr(item.session, "_langfuse_reporter", None)
    trace = getattr(item, "_langfuse_trace", None)
    if reporter and reporter.enabled and trace:
        passed = call.excinfo is None
        # 提取失败原因（AssertionError 的消息）
        failure_message = None
        if not passed and call.excinfo:
            exc = call.excinfo.value
            # 优先取 AssertionError 的消息（如“首次提问未生成输出文档”）
            failure_message = str(exc) if exc else f"{call.excinfo.typename}"
        reporter.add_test_result(
            trace,
            passed=passed,
            failure_message=failure_message,
            attempt=getattr(item, "_langfuse_attempt", 1) or 1,
        )


def pytest_sessionfinish(session, exitstatus):
    """pytest session 结束时，刷新 Langfuse 数据到服务端。"""
    reporter = getattr(session, "_langfuse_reporter", None)
    if reporter and reporter.enabled:
        reporter.flush()
