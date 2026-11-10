"""Token 自动续期模块：通过 refresh_token 获取新 access_token，避免手动拖滑块登录。"""
import json  # 解析响应
from typing import Any, Dict, Optional

import httpx  # HTTP 客户端

from core.utils.config import config  # 全局配置


# OAuth2 token 端点路径（通过网关路由到 auth 服务）
OAUTH2_TOKEN_PATH = "/uniplore-server-auth/oauth2/token"


class TokenRefreshError(RuntimeError):
    """Token 刷新失败时抛出的异常。"""


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """调用 OAuth2 token 端点，使用 refresh_token 获取新 access_token。

    Args:
        refresh_token: 刷新令牌。

    Returns:
        {"access_token": "...", "refresh_token": "...", "expires_in": 3600}

    Raises:
        TokenRefreshError: 刷新失败时（refresh_token 过期、网络错误等）。
    """
    url = f"{config.base_url}{OAUTH2_TOKEN_PATH}"  # 拼接完整 URL

    try:
        resp = httpx.post(
            url,
            json={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={
                "Authorization": config.authorization,  # Basic Auth（客户端凭据）
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise TokenRefreshError(f"Token 刷新请求失败（网络错误）：{exc}") from exc

    if resp.status_code != 200:
        raise TokenRefreshError(
            f"Token 刷新失败（HTTP {resp.status_code}）：{resp.text[:500]}"
        )

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        raise TokenRefreshError(f"Token 刷新响应解析失败：{resp.text[:200]}") from exc

    # 后端响应格式：{"code": 200, "data": {"accessToken": "...", "refreshToken": "...", "expiresIn": 3600}}
    # 或直接 OAuth2 标准格式：{"access_token": "...", "refresh_token": "...", "expires_in": 3600}
    access_token = _extract_field(data, "accessToken", "access_token")
    new_refresh_token = _extract_field(data, "refreshToken", "refresh_token") or refresh_token
    expires_in = _extract_field(data, "expiresIn", "expires_in")

    if not access_token:
        raise TokenRefreshError(
            f"Token 刷新响应中未找到 access_token：{json.dumps(data, ensure_ascii=False)[:500]}"
        )

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "expires_in": expires_in,
    }


def _extract_field(data: Any, *keys: str) -> Optional[Any]:
    """从响应数据中按多个候选键名提取值（兼容嵌套 data 层）。"""
    # 先尝试从 data.data 中提取（后端统一包装格式）
    inner = data.get("data") if isinstance(data, dict) else None
    if isinstance(inner, dict):
        for key in keys:
            if inner.get(key) is not None:
                return inner[key]
    # 再尝试顶层
    if isinstance(data, dict):
        for key in keys:
            if data.get(key) is not None:
                return data[key]
    return None


def update_env_token(access_token: str, refresh_token: Optional[str] = None) -> None:
    """将新 token 回写到 .env 文件，确保下次运行自动使用。

    Args:
        access_token: 新的 access_token。
        refresh_token: 新的 refresh_token（如有则一并更新）。
    """
    from core.utils.config import ENV_FILE  # 延迟导入避免循环依赖

    content = ENV_FILE.read_text(encoding="utf-8")  # 读取当前 .env 内容
    lines = content.splitlines(keepends=True)  # 保留行尾换行

    new_lines = []
    token_updated = False
    refresh_updated = False

    for line in lines:
        stripped = line.strip()
        # 更新 TOKEN= 行
        if stripped.startswith("TOKEN=") and not stripped.startswith("#"):
            new_lines.append(f"TOKEN={access_token}\n")
            token_updated = True
        # 更新 REFRESH_TOKEN= 行
        elif refresh_token and stripped.startswith("REFRESH_TOKEN=") and not stripped.startswith("#"):
            new_lines.append(f"REFRESH_TOKEN={refresh_token}\n")
            refresh_updated = True
        else:
            new_lines.append(line)

    # 如果 TOKEN 行不存在，追加到文件末尾
    if not token_updated:
        new_lines.append(f"\nTOKEN={access_token}\n")
    if refresh_token and not refresh_updated:
        new_lines.append(f"REFRESH_TOKEN={refresh_token}\n")

    ENV_FILE.write_text("".join(new_lines), encoding="utf-8")  # 回写文件

    # 同步更新当前进程的环境变量，使后续 config.token 读到新值
    import os
    os.environ["TOKEN"] = access_token
    if refresh_token:
        os.environ["REFRESH_TOKEN"] = refresh_token
