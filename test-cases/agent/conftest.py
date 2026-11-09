"""pytest 全局夹具（A′-3 最小子集移植自 agent-test/conftest.py）。

本文件当前只承载离线契约用例所需的公共部分。源仓根 conftest 的完整能力中，
以下部分**尚未移植**，待真实环境用例批量接入时逐项回补（实现以源仓版本为准）：
- token / peer_token / sse_client / model_name 等 session 级夹具
  （自动登录 → refresh 续期 → 静态 TOKEN 三级回退，及 401 重登回调）；
- Langfuse Trace 上报的 pytest 生命周期钩子（sessionstart / runtest_protocol /
  makereport / sessionfinish）；
- Windows GBK 控制台输出流保护（本文件已带）。

回补前提：框架侧 config/.env（或根 .env）提供 BASE_URL/TOKEN 等凭证，
凭证一律不入库、不从源仓迁移。
"""
import sys  # 输出流编码容错（Windows GBK 控制台）

import pytest  # pytest 框架

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
